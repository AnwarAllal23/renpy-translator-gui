# Ren'Py Translator – Free RenPy Translation Tool (GUI)

A powerful and easy-to-use **Ren'Py Translator tool** to translate Ren'Py games automatically.

This desktop application (built with Python & PySide6) scans `.rpy` script files, translates dialogue using LibreTranslate, generates the correct `game/tl/<language>/` structure, and can apply translations back to packaged `.rpa` releases.

Perfect for developers who want to **translate a Ren'Py game**, localize visual novels, or create multilingual versions quickly.

---

## Features

- ✅ Translate Ren'Py `.rpy` script files automatically  
- ✅ Supports classic Ren'Py projects  
- ✅ Supports packaged `.rpa` releases  
- ✅ Automatic dialogue detection  
- ✅ Generates proper `game/tl/<lang>/` folders  
- ✅ Re-apply translation to original game  
- ✅ Clean and simple GUI (PySide6)  
- ✅ Fast project scanning  

---

## 🛠 How It Works

1. Select your Ren'Py project folder
2. The tool scans `.rpy` files
3. Dialogue lines are detected automatically
4. Text is translated using LibreTranslate
5. A new `tl/<language>/` folder is generated
6. (Optional) Apply the translation back to the packaged game

This follows the official Ren'Py localization workflow.

---

## 📦 Installation

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
python main.py
