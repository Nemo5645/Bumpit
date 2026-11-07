"""Imports the Galmuri HUD font and applies the workshop UI palette to BP_BumpitHUD.

Run after apply_bumper_slots.py, with the editor closed:
UnrealEditor-Cmd.exe Bumpit.uproject -run=pythonscript -script=<this file> -unattended -nullrhi
"""
import os
import unreal

HUD = "/Game/Bumpit/Blueprints/BP_BumpitHUD"
FOLDER = "/Game/Bumpit/UI"
FACE_NAME = "FF_Galmuri"
FONT_NAME = "F_Galmuri"
FONT_SIZE = 13
MINIMUM_COLORS = 50
SOURCE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ThirdParty", "Galmuri", "Galmuri11-Bold.ttf")

assets = unreal.EditorAssetLibrary
assets.make_directory(FOLDER)

task = unreal.AssetImportTask()
task.set_editor_property("filename", os.path.normpath(SOURCE))
task.set_editor_property("destination_path", FOLDER)
task.set_editor_property("destination_name", FACE_NAME)
task.set_editor_property("automated", True)
task.set_editor_property("replace_existing", True)
task.set_editor_property("save", True)
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
unreal.log(f"BUMPIT_UI imported={list(task.get_editor_property('imported_object_paths'))}")
unreal.log(f"BUMPIT_UI folder={list(assets.list_assets(FOLDER, recursive=False))}")

face = None
for path in assets.list_assets(FOLDER, recursive=False):
    candidate = unreal.load_asset(path)
    if isinstance(candidate, unreal.FontFace):
        face = candidate
if face is None:
    raise RuntimeError("Font face was not imported; nothing saved")

font_path = f"{FOLDER}/{FONT_NAME}"
if assets.does_asset_exist(font_path):
    font = unreal.load_asset(font_path)
else:
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    font = tools.create_asset(FONT_NAME, FOLDER, unreal.Font, unreal.FontFactory())
unreal.BumpitRoundSetup.configure_ui_font(font, face, FONT_SIZE)
assets.save_loaded_asset(font)

hud = unreal.load_asset(HUD)
changed = unreal.BumpitRoundSetup.apply_ui_style(hud, font)
if changed < MINIMUM_COLORS:
    raise RuntimeError(f"Recolored {changed} pins, expected at least {MINIMUM_COLORS}; nothing saved")
unreal.BlueprintEditorLibrary.compile_blueprint(hud)
if hud.get_editor_property("status") == unreal.BlueprintStatus.BS_ERROR:
    raise RuntimeError("Blueprint failed to compile; nothing saved")
assets.save_loaded_asset(hud)
unreal.log(f"BUMPIT_UI_APPLIED colors={changed}")
