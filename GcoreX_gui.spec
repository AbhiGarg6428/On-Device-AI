# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['gui\\GcoreX_gui.py'],
    pathex=[],
    binaries=[],
    datas=[('core', 'core'), ('tools', 'tools'), ('helper', 'helper'), ('data', 'data'), ('assets', 'assets')],
    hiddenimports=['GcoreX'],
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
    name='GcoreX_gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
