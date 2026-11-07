"""Wires the round rules (Source/Bumpit/BumpitRound) into BP_BumpitHUD.

Run once on a HUD without the round wiring, with the editor closed:
UnrealEditor-Cmd.exe Bumpit.uproject -run=pythonscript -script=<this file> -unattended -nullrhi
"""
import unreal

ASSET = "/Game/Bumpit/Blueprints/BP_BumpitHUD"
EXPECTED = 42

hud = unreal.load_asset(ASSET)
links = unreal.BumpitRoundSetup.apply_round_system(hud)
if links != EXPECTED:
    raise RuntimeError(f"Made {links} links, expected {EXPECTED}; nothing saved")
unreal.BlueprintEditorLibrary.compile_blueprint(hud)
if hud.get_editor_property("status") == unreal.BlueprintStatus.BS_ERROR:
    raise RuntimeError("Blueprint failed to compile; nothing saved")
unreal.EditorAssetLibrary.save_loaded_asset(hud)
unreal.log(f"BUMPIT_ROUNDS_APPLIED {links}")
