from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Callable
import concurrent.futures
import os
import re
import time
import requests


# Providers that need no API key at all (LibreTranslate + Argos).
NO_KEY_PROVIDERS = ("libretranslate", "argos")


@dataclass
class TranslatorConfig:
    endpoint: str
    source_lang: str
    target_lang: str
    timeout_s: int = 30
    provider: str = "libretranslate"  # libretranslate | argos | google | deepl
    api_key: str = ""


class TranslationError(RuntimeError):
    pass


class Translator:

    BATCH_SIZE = 100

    RE_TOKEN = re.compile(
        r"(\\\\n|\\\\\"|\{[^}]*\}|\[[^\]]*\]|%\([^)]+\)[#0\- +]?\d*(?:\.\d+)?[a-zA-Z]|%[sdrof]|%%)"
    )

    # DeepL uses a few non-plain-ISO codes for some targets.
    _DEEPL_TARGET_OVERRIDES = {"en": "EN-US", "pt": "PT-PT"}

    def __init__(self, cfg: TranslatorConfig, on_setup_log: Callable[[str], None] | None = None):
        self.cfg = cfg
        self.cache: dict[str, str] = {}
        self.cancel_requested = False
        self._on_setup_log = on_setup_log
        self._argos_ready = False
        self._argos_workers = 1

        if cfg.provider not in NO_KEY_PROVIDERS and not (cfg.api_key or "").strip():
            raise TranslationError(
                f"Missing API key for provider '{cfg.provider}'."
            )

    def _setup_log(self, msg: str) -> None:
        if self._on_setup_log:
            self._on_setup_log(msg)

    # ==========================================================
    # PUBLIC
    # ==========================================================

    def translate_many(
        self,
        texts: Iterable[str],
        progress_cb: Callable[[int, int], None] | None = None,
        batch_start_cb: Callable[[int, int], None] | None = None,
        batch_end_cb: Callable[[int, int], None] | None = None,
        log_cb: Callable[[str, str], None] | None = None,
    ) -> dict[str, str]:

        unique = list(dict.fromkeys(texts))
        total = len(unique)

        batches = [
            unique[i: i + self.BATCH_SIZE]
            for i in range(0, total, self.BATCH_SIZE)
        ]

        done = 0
        batch_count = len(batches)

        for batch_index, batch in enumerate(batches):

            if self.cancel_requested:
                raise TranslationError("Translation cancelled by user.")

            if batch_start_cb:
                batch_start_cb(batch_index + 1, batch_count)

            translations = self._translate_batch(batch)

            if batch_end_cb:
                batch_end_cb(batch_index + 1, batch_count)

            for original, translated in zip(batch, translations):
                self.cache[original] = translated
                done += 1

                if progress_cb:
                    progress_cb(done, total)

                if log_cb:
                    log_cb(original, translated)

        return dict(self.cache)

    def cancel(self):
        self.cancel_requested = True

    # ==========================================================
    # INTERNAL
    # ==========================================================

    def _normalize_endpoint(self, url: str) -> str:
        u = (url or "").strip()
        if u.endswith("/"):
            u = u[:-1]
        if not u.endswith("/translate"):
            u += "/translate"
        return u

    def _translate_batch(self, texts: list[str]) -> list[str]:

        protected_texts = []
        token_maps = []

        for text in texts:
            protected, mapping = self._protect_tokens(text)
            protected_texts.append(protected)
            token_maps.append(mapping)

        translated_segments = self._translate_raw_batch(protected_texts)

        results = []

        for translated, mapping in zip(translated_segments, token_maps):
            restored = self._restore_tokens(translated, mapping)
            restored = restored.replace("%", "%%")
            results.append(restored)

        return results

    def _translate_raw_batch(self, texts: list[str]) -> list[str]:
        provider = self.cfg.provider

        if provider == "argos":
            return self._raw_argos(texts)
        if provider == "google":
            return self._raw_google(texts)
        if provider == "deepl":
            return self._raw_deepl(texts)
        return self._raw_libretranslate(texts)

    def _raw_libretranslate(self, texts: list[str]) -> list[str]:
        ep = self._normalize_endpoint(self.cfg.endpoint)

        payload = {
            "q": texts,
            "source": self.cfg.source_lang,
            "target": self.cfg.target_lang,
            "format": "text",
        }

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        r = requests.post(
            ep,
            json=payload,
            headers=headers,
            timeout=self.cfg.timeout_s,
        )

        if r.status_code != 200:
            raise TranslationError(f"Server error {r.status_code}")

        data = r.json()

        if isinstance(data, list):
            return [item.get("translatedText", "") for item in data]

        if isinstance(data, dict):
            if isinstance(data.get("translatedText"), list):
                return data["translatedText"]
            if isinstance(data.get("translatedText"), str):
                return [data["translatedText"]]

        raise TranslationError("Unexpected API response structure.")

    def _raw_google(self, texts: list[str]) -> list[str]:
        url = "https://translation.googleapis.com/language/translate/v2"
        params = {"key": self.cfg.api_key}
        payload = {
            "q": texts,
            "source": self.cfg.source_lang,
            "target": self.cfg.target_lang,
            "format": "text",
        }

        r = requests.post(url, params=params, json=payload, timeout=self.cfg.timeout_s)

        if r.status_code != 200:
            raise TranslationError(f"Google Translate error {r.status_code}: {r.text[:300]}")

        try:
            translations = r.json()["data"]["translations"]
        except (KeyError, ValueError) as e:
            raise TranslationError(f"Unexpected Google Translate response: {e}")

        return [t.get("translatedText", "") for t in translations]

    def _raw_deepl(self, texts: list[str]) -> list[str]:
        api_key = self.cfg.api_key.strip()
        host = "api-free.deepl.com" if api_key.endswith(":fx") else "api.deepl.com"
        url = f"https://{host}/v2/translate"

        source = self.cfg.source_lang.upper()
        target = self._DEEPL_TARGET_OVERRIDES.get(self.cfg.target_lang, self.cfg.target_lang.upper())

        headers = {"Authorization": f"DeepL-Auth-Key {api_key}"}
        data = {"text": texts, "source_lang": source, "target_lang": target}

        r = requests.post(url, headers=headers, data=data, timeout=self.cfg.timeout_s)

        if r.status_code != 200:
            raise TranslationError(f"DeepL error {r.status_code}: {r.text[:300]}")

        try:
            translations = r.json()["translations"]
        except (KeyError, ValueError) as e:
            raise TranslationError(f"Unexpected DeepL response: {e}")

        return [t.get("text", "") for t in translations]

    def _ensure_argos_package(self) -> None:
        """Install the offline Argos Translate language pack for this language
        pair on first use (cached afterwards for the life of this Translator).

        Argos's own docstrings claim missing languages/translations raise an
        exception, but the actual implementation returns None instead in most
        cases (only a missing *source* language raises, via AttributeError on
        None) - so both paths are checked here rather than trusting either
        docstring.
        """
        if self._argos_ready:
            return

        import argostranslate.package
        import argostranslate.settings
        import argostranslate.translate

        self._tune_argos_concurrency(argostranslate.settings)

        from_code, to_code = self.cfg.source_lang, self.cfg.target_lang

        try:
            translation = argostranslate.translate.get_translation_from_codes(from_code, to_code)
        except Exception:
            translation = None

        if translation is None:
            self._setup_log(f"⬇️ Argos Translate: downloading language pack {from_code} → {to_code}…")
            argostranslate.package.update_package_index()
            installed_ok = argostranslate.package.install_package_for_language_pair(from_code, to_code)
            if not installed_ok:
                raise TranslationError(
                    f"Argos Translate has no offline package for {from_code} → {to_code}."
                )
            self._setup_log(f"✅ Argos Translate: package {from_code} → {to_code} installed.")

        # The FIRST real translation for a language pair lazily builds things
        # like the sentence-boundary ("stanza") model - including extracting
        # files to disk - with no internal locking. Doing that single warm-up
        # call here, on this thread, before the worker pool exists, means
        # every concurrent worker later reuses the already-initialized
        # pipeline instead of racing to extract the same files at once
        # (which surfaces as a Windows "[WinError 5] Access denied" rename).
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                argostranslate.translate.translate(".", from_code, to_code)
                last_error = None
                break
            except Exception as e:
                last_error = e
                time.sleep(0.6)

        if last_error is not None:
            raise TranslationError(
                f"Argos Translate failed to initialize for {from_code} → {to_code}: {last_error}"
            )

        self._argos_ready = True

    def _tune_argos_concurrency(self, argos_settings) -> None:
        """Argos Translate (CTranslate2) processes one `.translate()` call at a
        time by default (inter_threads=1), so translating a batch one string
        after another leaves most CPU cores idle. CTranslate2 translators are
        thread-safe and designed to serve concurrent requests, so instead we
        run several single-threaded workers in parallel - one per CPU core -
        which keeps the whole batch loop from being serialized on one core.

        Skipped entirely if the user already set ARGOS_INTER_THREADS/
        ARGOS_INTRA_THREADS themselves (env var), to respect their choice.
        """
        cpu_count = os.cpu_count() or 4

        if "ARGOS_INTER_THREADS" not in os.environ:
            argos_settings.inter_threads = max(1, cpu_count)
        if "ARGOS_INTRA_THREADS" not in os.environ:
            argos_settings.intra_threads = 1

        self._argos_workers = max(1, int(getattr(argos_settings, "inter_threads", 1)))

    def _raw_argos(self, texts: list[str]) -> list[str]:
        try:
            self._ensure_argos_package()
            import argostranslate.translate
        except TranslationError:
            raise
        except Exception as e:
            raise TranslationError(f"Argos Translate is unavailable: {e}")

        def do_translate(text: str) -> str:
            return argostranslate.translate.translate(text, self.cfg.source_lang, self.cfg.target_lang)

        workers = min(len(texts), self._argos_workers)
        if workers <= 1:
            return [do_translate(t) for t in texts]

        results: list[str] = [""] * len(texts)
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(do_translate, t): i for i, t in enumerate(texts)}
            for future in concurrent.futures.as_completed(futures):
                results[futures[future]] = future.result()

        return results

    # ==========================================================
    # TOKEN PROTECTION
    # ==========================================================

    def _protect_tokens(self, text: str):
        """
        Remplace les tokens Ren'Py par des placeholders très stables.
        Exemple: ⟪RNT0⟫, ⟪RNT1⟫ ...
        """
        mapping = {}
        counter = 0

        def replacer(match):
            nonlocal counter
            key = f"⟪RNT{counter}⟫"
            mapping[key] = match.group(0)
            counter += 1
            return key

        protected = self.RE_TOKEN.sub(replacer, text)
        return protected, mapping

    def _restore_tokens(self, text: str, mapping: dict[str, str]) -> str:
        """
        Restore:
        - exact tokens (⟪RNT0⟫)
        - tolerance: si l'API a "cassé" le token (espaces, ponctuation enlevée)
          on tente une restauration en mode "normalisé".
        """

        # 1) Restore exact (rapide)
        for key, value in mapping.items():
            text = text.replace(key, value)

        # 2) Restore tolérant (si l'API a modifié le token)
        # Normalisation: on garde que A-Z0-9
        def norm(s: str) -> str:
            return re.sub(r"[^A-Za-z0-9]", "", s).upper()

        norm_map = {norm(k): v for k, v in mapping.items()}
        if not norm_map:
            return text

        # On remplace toute séquence qui ressemble à un token (même cassé)
        # ex: "RNT 0", "⟪ RNT0 ⟫", "R N T 0"
        def repl(m):
            candidate = norm(m.group(0))
            return norm_map.get(candidate, m.group(0))

        # Cherche des formes type RNT + chiffre(s) avec du bruit entre
        text = re.sub(r"(?:⟪\s*)?R\s*N\s*T\s*\d+(?:\s*⟫)?", repl, text, flags=re.IGNORECASE)

        return text