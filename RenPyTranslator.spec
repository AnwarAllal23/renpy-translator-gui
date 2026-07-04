# -*- mode: python ; coding: utf-8 -*-

import sys


a = Analysis(
    ['entrypoint.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

if sys.platform == 'darwin':
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='RenPyTranslator',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
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
        upx=True,
        upx_exclude=[],
        name='RenPyTranslator',
    )

    app = BUNDLE(
        coll,
        name='RenPyTranslator.app',
        icon=None,
        bundle_identifier='com.anwarallal.renpytranslator',
        info_plist={
            'CFBundleName': "Ren'Py Translator",
            'CFBundleDisplayName': "Ren'Py Translator",
            'CFBundleShortVersionString': '0.3.0',
            'CFBundleVersion': '0.3.0',
            'NSHighResolutionCapable': 'True',
        },
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name='RenPyTranslator',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
    )
