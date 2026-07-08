# -*- mode: python ; coding: utf-8 -*-
# macOS app bundle build:
#   pyinstaller RenPyTranslator-macos.spec
# Result: dist/RenPy Translator.app
#
# Unlike the Windows one-file spec, this uses a one-dir COLLECT wrapped in a
# BUNDLE: standard layout for .app bundles and much faster to launch (no
# self-extraction on every start).

a = Analysis(
    ['entrypoint.py'],
    pathex=[],
    binaries=[],
    datas=[('app/assets', 'app/assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RenPyTranslator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='RenPyTranslator',
)

app = BUNDLE(
    coll,
    name='RenPy Translator.app',
    icon='app/assets/icon.icns',
    bundle_identifier='com.anwarallal.renpytranslator',
    info_plist={
        'CFBundleName': 'RenPy Translator',
        'CFBundleDisplayName': "Ren'Py Translator",
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'NSHighResolutionCapable': True,
        'NSHumanReadableCopyright': '© 2026 AnwarAllal23 — MIT License',
    },
)
