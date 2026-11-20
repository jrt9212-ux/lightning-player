# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[
        (r'C:\Windows\System32\vcruntime140.dll', '.'),
        (r'C:\Windows\System32\vcruntime140_1.dll', '.'),
        (r'C:\Windows\System32\msvcp140.dll', '.'),
        (r'C:\Windows\System32\msvcp140_1.dll', '.'),
        (r'C:\Windows\System32\msvcp140_2.dll', '.'),
    ],
    datas=[('client', 'client'), ('icon.ico', '.'), ('icon.png', '.'), ('categories_catalog.json', '.')],
    hiddenimports=['webview', 'clr_loader', 'pythonnet', 'cffi'],
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
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
