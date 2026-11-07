"""Restores BP_BumpitHUD's input keys. Every Key pin had been saved as "(", so no key matched.

Run with the editor closed:
UnrealEditor-Cmd.exe Bumpit.uproject -run=pythonscript -script=<this file> -unattended -nullrhi
"""
import unreal

ASSET = "/Game/Bumpit/Blueprints/BP_BumpitHUD"
EXPECTED = 15

hud = unreal.load_asset(ASSET)
repaired = unreal.BumpitKeyRepair.repair_hud_keys(hud)
if repaired != EXPECTED:
    raise RuntimeError(f"Repaired {repaired} key pins, expected {EXPECTED}; nothing saved")
unreal.BlueprintEditorLibrary.compile_blueprint(hud)
unreal.EditorAssetLibrary.save_loaded_asset(hud)
unreal.log(f"BUMPIT_KEYS_REPAIRED {repaired}")
