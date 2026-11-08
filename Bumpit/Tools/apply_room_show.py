"""Fits the HUD's camera views to the narrowed room and builds the score screen's material.

Run once with the editor closed:
UnrealEditor-Cmd.exe Bumpit.uproject -run=pythonscript -script=<this file> -unattended -nullrhi
"""
import unreal

MOOD = "/Game/Bumpit/Mood"
NAME = "M_BumpitScreen"
GLOW = 1.8
EXPECTED_CHANGES = 26
MEL = unreal.MaterialEditingLibrary
EAL = unreal.EditorAssetLibrary

path = f"{MOOD}/{NAME}"
if EAL.does_asset_exist(path):
    mat = unreal.load_asset(path)
    MEL.delete_all_material_expressions(mat)
else:
    mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(NAME, MOOD, unreal.Material, unreal.MaterialFactoryNew())
mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
image = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureSampleParameter2D, -500, 0)
image.set_editor_property("parameter_name", "Image")
image.set_editor_property("texture", unreal.load_asset("/Engine/EngineResources/DefaultTexture"))
glow = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -500, 240)
glow.set_editor_property("r", GLOW)
lit = MEL.create_material_expression(mat, unreal.MaterialExpressionMultiply, -200, 0)
MEL.connect_material_expressions(image, "RGB", lit, "A")
MEL.connect_material_expressions(glow, "", lit, "B")
MEL.connect_material_property(lit, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
MEL.recompile_material(mat)
EAL.save_loaded_asset(mat)

hud = unreal.load_asset("/Game/Bumpit/Blueprints/BP_BumpitHUD")
changes = unreal.BumpitRoundSetup.apply_room_views(hud)
if changes != EXPECTED_CHANGES:
    raise RuntimeError(f"Made {changes} changes, expected {EXPECTED_CHANGES}; nothing saved")
unreal.BlueprintEditorLibrary.compile_blueprint(hud)
if hud.get_editor_property("status") == unreal.BlueprintStatus.BS_ERROR:
    raise RuntimeError("Blueprint failed to compile; nothing saved")
EAL.save_loaded_asset(hud)
unreal.log(f"BUMPIT_ROOM_SHOW_APPLIED {changes}")
