# -*- mode: python ; coding: utf-8 -*-

import os
import sys

# Tìm tools nếu có ở thư mục hiện tại
my_binaries = []
for tool in ['ffmpeg.exe', 'ffprobe.exe', 'yt-dlp.exe']:
    if os.path.exists(tool):
        my_binaries.append((tool, '.'))

python_base = sys.base_prefix
python_dlls = os.path.join(python_base, 'DLLs')
for tk_binary in ['_tkinter.pyd', 'tcl86t.dll', 'tk86t.dll']:
    tk_binary_path = os.path.join(python_dlls, tk_binary)
    if os.path.exists(tk_binary_path):
        my_binaries.append((tk_binary_path, '.'))

my_datas = []
if os.path.exists('tools'):
    my_datas.append(('tools', 'tools'))
if os.path.exists('THIRD_PARTY_LICENSES'):
    my_datas.append(('THIRD_PARTY_LICENSES', 'THIRD_PARTY_LICENSES'))
if os.path.exists('assets'):
    my_datas.append(('assets', 'assets'))
if os.path.exists('update_manifest_url.txt'):
    my_datas.append(('update_manifest_url.txt', '.'))

tcl_root = os.path.join(python_base, 'tcl')
for tcl_dir in ['tcl8.6', 'tk8.6']:
    tcl_dir_path = os.path.join(tcl_root, tcl_dir)
    if os.path.exists(tcl_dir_path):
        my_datas.append((tcl_dir_path, os.path.join('tcl', tcl_dir)))

tcl_data_path = os.path.join(tcl_root, 'tcl8.6')
tk_data_path = os.path.join(tcl_root, 'tk8.6')
if os.path.exists(tcl_data_path):
    my_datas.append((tcl_data_path, '_tcl_data'))
if os.path.exists(tk_data_path):
    my_datas.append((tk_data_path, '_tk_data'))


a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=my_binaries,
    datas=my_datas,
    hiddenimports=['playwright', 'customtkinter'], # Giữ playwright và ctk nếu project phụ thuộc
    hookspath=['pyinstaller_hooks'],
    hooksconfig={},
    runtime_hooks=['pyi_tkinter_runtime_hook.py'],
    excludes=['keygen', 'keygen_gui'], # Block keygen tools
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='HupTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\logo_hup_tool.ico'] if os.path.exists('assets/logo_hup_tool.ico') else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='HupTool',
)
