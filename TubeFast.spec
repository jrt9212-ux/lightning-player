# -*- mode: python ; coding: utf-8 -*-


import sys, os
py_dir = os.path.dirname(sys.executable)

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[
        (os.path.join(py_dir, 'vcruntime140.dll'), '.'),
        (os.path.join(py_dir, 'vcruntime140_1.dll'), '.'),
    ],
    datas=[('client', 'client'), ('icon.ico', '.'), ('icon.png', '.'), ('categories_catalog.json', '.')],
    hiddenimports=['webview'],
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
    a.binaries,
    a.datas,
    [],
    name='Lightning Player',
    icon='icon.ico',
    version='version_info.txt',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
