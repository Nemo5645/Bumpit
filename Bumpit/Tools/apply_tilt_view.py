"""Builds the black circle that closes in on the whole screen, HUD included, as tilts are used.
Safe to run repeatedly.

Run with the editor closed:
UnrealEditor-Cmd.exe Bumpit.uproject -run=pythonscript -script=<this file> -unattended -nullrhi
"""
import unreal

MOOD = "/Game/Bumpit/Mood"
NAME = "M_UI_BumpitTunnel"
# Width of the circle's soft edge, in screen heights.
SOFTNESS = 0.2
# The pinball board's centre from the screen's, in screen heights; the table camera sits off to its right.
BOARD_OFFSET_X = -0.11
# Matches PIXEL_GRID in apply_mood.py, so the circle has the same chunky pixels as the view.
PIXEL_GRID = (420.0, 259.0)
MEL = unreal.MaterialEditingLibrary
EAL = unreal.EditorAssetLibrary

path = f"{MOOD}/{NAME}"
if EAL.does_asset_exist(path):
    mat = unreal.load_asset(path)
    MEL.delete_all_material_expressions(mat)
else:
    mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(NAME, MOOD, unreal.Material, unreal.MaterialFactoryNew())
mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_UI)
mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)

uv = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -700, -120)
aspect = MEL.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -700, 0)
aspect.set_editor_property("parameter_name", "Aspect")
aspect.set_editor_property("default_value", 1.6)
radius = MEL.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -700, 120)
radius.set_editor_property("parameter_name", "Radius")
radius.set_editor_property("default_value", 2.0)
black = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -300, -200)

circle = MEL.create_material_expression(mat, unreal.MaterialExpressionCustom, -300, 0)
circle.set_editor_property("code", f"""
float2 cells = float2({PIXEL_GRID[0]}, {PIXEL_GRID[1]});
float2 pixel = (floor(UV * cells) + 0.5) / cells;
float2 offset = (pixel - 0.5) * float2(Aspect, 1.0) - float2({BOARD_OFFSET_X}, 0.0);
return smoothstep(Radius, Radius + {SOFTNESS}, length(offset));
""")
circle.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT1)
pins = []
for name in ("UV", "Aspect", "Radius"):
    pin = unreal.CustomInput()
    pin.set_editor_property("input_name", name)
    pins.append(pin)
circle.set_editor_property("inputs", pins)

MEL.connect_material_expressions(uv, "", circle, "UV")
MEL.connect_material_expressions(aspect, "", circle, "Aspect")
MEL.connect_material_expressions(radius, "", circle, "Radius")
MEL.connect_material_property(black, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
MEL.connect_material_property(circle, "", unreal.MaterialProperty.MP_OPACITY)
MEL.recompile_material(mat)
EAL.save_loaded_asset(mat)
unreal.log("BUMPIT_TILT_VIEW_APPLIED")
