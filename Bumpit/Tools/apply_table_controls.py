"""Adds the side arrow on the table and in the shop, and the word-style HUD text, to BP_BumpitHUD.

Run once after apply_ui_style.py, with the editor closed:
UnrealEditor-Cmd.exe Bumpit.uproject -run=pythonscript -script=<this file> -unattended -nullrhi
"""
import unreal

ASSET = "/Game/Bumpit/Blueprints/BP_BumpitHUD"
ARROW_LINKS = 6
RETURN_LINKS = 6
MINIMUM_LINES = 10

hud = unreal.load_asset(ASSET)
links = unreal.BumpitRoundSetup.apply_shop_arrow(hud)
if links != ARROW_LINKS:
    raise RuntimeError(f"Made {links} links, expected {ARROW_LINKS}; nothing saved")
back = unreal.BumpitRoundSetup.apply_shop_return(hud)
if back != RETURN_LINKS:
    raise RuntimeError(f"Made {back} return links, expected {RETURN_LINKS}; nothing saved")
lines = unreal.BumpitRoundSetup.apply_word_text(hud)
if lines < MINIMUM_LINES:
    raise RuntimeError(f"Changed {lines} strings, expected at least {MINIMUM_LINES}; nothing saved")
unreal.BlueprintEditorLibrary.compile_blueprint(hud)
if hud.get_editor_property("status") == unreal.BlueprintStatus.BS_ERROR:
    raise RuntimeError("Blueprint failed to compile; nothing saved")
unreal.EditorAssetLibrary.save_loaded_asset(hud)
unreal.log(f"BUMPIT_TABLE_CONTROLS_APPLIED links={links} lines={lines}")
