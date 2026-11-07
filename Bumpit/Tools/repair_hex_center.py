"""Restores BP_PinballTable's HexCenter. Row was a float and its links to three nodes were lost,
so every cell after the first row got a position off the table.

Run once with the editor closed:
UnrealEditor-Cmd.exe Bumpit.uproject -run=pythonscript -script=<this file> -unattended -nullrhi
"""
import unreal

ASSET = "/Game/Bumpit/Blueprints/BP_PinballTable"
EXPECTED = 7

table = unreal.load_asset(ASSET)
links = unreal.BumpitKeyRepair.repair_hex_center(table)
if links != EXPECTED:
    raise RuntimeError(f"Made {links} links, expected {EXPECTED}; nothing saved")
unreal.BlueprintEditorLibrary.compile_blueprint(table)
unreal.EditorAssetLibrary.save_loaded_asset(table)
unreal.log(f"BUMPIT_HEX_REPAIRED {links}")
