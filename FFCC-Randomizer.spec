# -*- mode: python ; coding: utf-8 -*-
# Builds the GUI as one file: FFCC-Randomizer.exe on Windows, FFCC-Randomizer
# on Linux. PyInstaller only builds for the system it runs on.
import sys


a = Analysis(
    ['ffcc_gui.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets')],
    # imported inside functions (boss shuffle); listed so they're always bundled
    hiddenimports=['bossshuffle', 'cftpatch', 'worldzones', 'progression', 'chestflags', 'treasure', 'spawn_map', 'lootcft', 'titlelogo', 'chestcolors', 'shortcuts', 'itemicons', 'hidechests', 'apmodel', 'shopchecks', 'shops', 'tribestats', 'customitem', 'othergender', 'cycleselect', 'lynarinorth', 'qolpatch', 'miasmaskip', 'monstertint', 'gbaradar', 'gbanames', 'gbaloot', 'gbaloot_code'],
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
    name='FFCC-Randomizer',
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
    # Windows shows the .ico on the exe. On Linux the window icon comes from
    # assets/icon.png at run time.
    icon=['assets/icon.ico'] if sys.platform == 'win32' else None,
)
