from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Callable
import re
import requests


@dataclass
class TranslatorConfig:
    endpoint: str
    source_lang: str
    target_lang: str
    timeout_s: int = 30


class TranslationError(RuntimeError):
    pass


class Translator:

    BATCH_SIZE = 100

    RE_TOKEN = re.compile(
        r"(\\\\n|\\\\\"|\{[^}]*\}|\[[^\]]*\]|%\([^)]+\)[#0\- +]?\d*(?:\.\d+)?[a-zA-Z]|%[sdrof]|%%)"
    )

    def __init__(self, cfg: TranslatorConfig):
        self.cfg = cfg
        self.cache: dict[str, str] = {}
        self.cancel_requested = False

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