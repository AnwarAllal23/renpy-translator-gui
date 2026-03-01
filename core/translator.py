"""Ren'Py Translator - Translation backend abstraction.

The Translator class isolates translation logic from the UI:
- It supports local or remote endpoints
- It batches requests where possible
- It returns structured results and raises TranslationError on failures
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Callable
import re
import requests


@dataclass
class TranslatorConfig:
    """Configuration for the translation backend."""
    endpoint: str
    source_lang: str
    target_lang: str
    timeout_s: int = 30


class TranslationError(RuntimeError):
    """Raised when the translation backend fails or returns invalid data."""
    pass


class Translator:
    """
    LibreTranslate REST API — multi-langues

    Notes:
    - protège les éléments Ren'Py (interpolations [var], tags {i}, \" et \\n)
    - robuste aux endpoints publics qui renvoient du HTML (Cloudflare/anti-bot/rate-limit)
    - fallback automatique vers quelques endpoints publics (désactivable en modifiant FALLBACK_ENDPOINTS)
    """

    # Ren'Py special elements
    RE_INTERPOLATION = re.compile(r"\[([^\]]+)\]")
    RE_TEXT_TAG = re.compile(r"\{(/?)([a-zA-Z]+)(?:=[^}]*)?\}")
    RE_ESCAPED_NEWLINE = re.compile(r"\\\\n")
    RE_ESCAPED_QUOTE = re.compile(r'\\"')

    # Tokenize segments we must NEVER translate or reorder.
    # - Ren'Py text tags: {...}
    # - Interpolations: [...]
    # - Escaped newline/quote: \\n, \"
    # - Python-style formatting placeholders: %(name)s, %s, %d, %% (literal percent already escaped)
    RE_TOKEN = re.compile(
        r"(\\\\n|\\\\\"|\{[^}]*\}|\[[^\]]*\]|%\([^)]+\)[#0\- +]?\d*(?:\.\d+)?[a-zA-Z]|%[sdrof]|%%)"
    )

    FALLBACK_ENDPOINTS = [
        "https://libretranslate.de/translate",
        "https://translate.cutie.dating/translate",
    ]

    def __init__(self, cfg: TranslatorConfig):
        self.cfg = cfg
        self.cache: dict[str, str] = {}
        self.cancel_requested = False
        self._placeholders: dict[str, str] = {}
        self._ph_counter = 0

    # -------------------- public API --------------------
    def translate_many(
        self,
        texts: Iterable[str],
        progress_cb: Callable[[int, int], None] | None = None,
        log_cb: Callable[[str, str], None] | None = None,
    ) -> dict[str, str]:
        unique: list[str] = []
        for t in texts:
            if t not in unique:
                unique.append(t)

        total = len(unique)
        done = 0

        for text in unique:
            if self.cancel_requested:
                raise TranslationError("Traduction annulée par l'utilisateur.")

            translated = self._translate_one(text)
            self.cache[text] = translated

            done += 1
            if progress_cb:
                progress_cb(done, total)
            if log_cb:
                log_cb(text, translated)

        return dict(self.cache)

    def cancel(self):
        self.cancel_requested = True

    # -------------------- internals --------------------
    def _make_placeholder(self, original: str) -> str:
        ph = f"__RENPY_PH_{self._ph_counter}__"
        self._ph_counter += 1
        self._placeholders[ph] = original
        return ph

    def _protect(self, text: str) -> str:
        # order matters: handle escaped sequences first
        text = self.RE_ESCAPED_NEWLINE.sub(lambda m: self._make_placeholder(m.group(0)), text)
        text = self.RE_ESCAPED_QUOTE.sub(lambda m: self._make_placeholder(m.group(0)), text)
        text = self.RE_TEXT_TAG.sub(lambda m: self._make_placeholder(m.group(0)), text)
        text = self.RE_INTERPOLATION.sub(lambda m: self._make_placeholder(m.group(0)), text)
        return text

    def _restore(self, text: str) -> str:
        for ph, original in sorted(self._placeholders.items(), key=lambda x: -len(x[0])):
            text = text.replace(ph, original)
        self._placeholders.clear()
        self._ph_counter = 0
        return text

    def _normalize_endpoint(self, url: str) -> str:
        u = (url or "").strip()
        if not u:
            return ""
        if u.endswith("/"):
            u = u[:-1]
        # Accept base host like http://localhost:5000 and auto-add /translate
        if not u.endswith("/translate"):
            u = u + "/translate"
        return u

    def _translate_one(self, text: str) -> str:
        # Split the string into "protected tokens" + "plain text" segments.
        # We translate ONLY the plain text segments, keeping tokens untouched and in place.
        parts: list[str] = []
        last = 0
        for m in self.RE_TOKEN.finditer(text):
            if m.start() > last:
                plain = text[last:m.start()]
                parts.append(self._translate_plain_segment(plain))
            parts.append(m.group(0))  # keep token exactly as-is
            last = m.end()

        if last < len(text):
            parts.append(self._translate_plain_segment(text[last:]))

        return "".join(parts)

    def _translate_plain_segment(self, segment: str) -> str:
        # Skip empty/whitespace-only segments (avoid useless API calls).
        if not segment or segment.strip() == "":
            return segment

        translated = self._translate_raw_with_fallbacks(segment)

        # IMPORTANT:
        # Ren'Py uses Python-style % formatting internally when displaying dialogue.
        # Any literal '%' must be escaped as '%%' or it can crash with "incomplete format".
        # We already protect real placeholders like %s / %(name)s via RE_TOKEN, so remaining
        # percent signs are treated as literal.
        translated = translated.replace("%", "%%")
        return translated

    def _translate_raw_with_fallbacks(self, text: str) -> str:
        endpoints = [self.cfg.endpoint] + [e for e in self.FALLBACK_ENDPOINTS if e != self.cfg.endpoint]
        last_err: Exception | None = None

        for ep in endpoints:
            ep = self._normalize_endpoint(ep)
            if not ep:
                continue
            try:
                return self._post_translate(ep, text)
            except Exception as e:
                last_err = e
                continue

        if last_err:
            raise TranslationError(str(last_err))
        raise TranslationError("Impossible de traduire : aucun endpoint disponible.")

    def _post_translate(self, endpoint: str, text: str) -> str:
        payload = {
            "q": text,
            "source": self.cfg.source_lang,
            "target": self.cfg.target_lang,
            "format": "text",
        }

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "RenpyTranslator/1.0 (requests)",
        }

        try:
            r = requests.post(endpoint, json=payload, headers=headers, timeout=self.cfg.timeout_s)
        except requests.RequestException as e:
            raise TranslationError("Impossible de contacter le serveur de traduction.") from e

        if r.status_code != 200:
            snippet = (r.text or "").strip().replace("\n", " ")[:180]
            raise TranslationError(f"Erreur serveur ({r.status_code}). Réponse: {snippet}")

        # Some public endpoints return HTML pages (anti-bot) -> not JSON
        content_type = (r.headers.get("Content-Type") or "").lower()
        try:
            data = r.json()
        except ValueError:
            snippet = (r.text or "").strip().replace("\n", " ")[:180]
            raise TranslationError(
                "Réponse invalide du serveur de traduction (HTML/anti-bot probable). "
                f"Endpoint: {endpoint} | Aperçu: {snippet}"
            )

        translated = data.get("translatedText")
        if not translated:
            err = data.get("error")
            if err:
                raise TranslationError(f"Erreur API: {err}")
            raise TranslationError("Traduction vide.")

        return translated
