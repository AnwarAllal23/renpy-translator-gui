# Ren'Py Translator (GUI)

Desktop app (PySide6) to **translate Ren'Py games** (classic projects or packaged `.rpa` releases).
It scans `.rpy` scripts, translates using LibreTranslate, generates `game/tl/<lang>/...`, and can **apply the translation back to the original game** (packaged workflow).

## Full documentation
For full details (workflow, internal logic, troubleshooting, Docker setup):

- English: **[DOC_EN.txt](DOC_EN.txt)**
- Français : **[DOC_FR.txt](DOC_FR.txt)**

---

## Install

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt