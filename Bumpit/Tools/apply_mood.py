"""Applies the dark workshop mood. Safe to run repeatedly; tune the tables below.

Run with the editor closed:
UnrealEditor-Cmd.exe Bumpit.uproject -run=pythonscript -script=<this file> -unattended -nullrhi
"""
import unreal

MOOD = "/Game/Bumpit/Mood"
MATERIALS = "/Game/Bumpit/Materials/"
BLUEPRINTS = "/Game/Bumpit/Blueprints/"
MAP = "/Game/Bumpit/Maps/BumpitCell"
MEL = unreal.MaterialEditingLibrary
EAL = unreal.EditorAssetLibrary

# Material instance -> (role, base colour, glow)
PALETTE = {
    "MI_Cell_35_90_140": ("table felt", (0.040, 0.110, 0.075), 0.0),
    "MI_Cell_100_230_300": ("tarnished brass rails", (0.340, 0.205, 0.068), 0.0),
    "MI_Cell_280_115_56": ("rusted walls", (0.300, 0.100, 0.045), 0.0),
    "MI_Cell_75_85_82": ("iron", (0.110, 0.100, 0.090), 0.0),
    "MI_Cell_20_27_31": ("dark housing", (0.040, 0.036, 0.034), 0.0),
    "MI_Cell_15_20_25": ("goal pockets", (0.006, 0.005, 0.005), 0.0),
    "MI_Cell_210_135_73": ("old wood", (0.210, 0.120, 0.055), 0.0),
    "MI_Cell_90_650_460": ("lit panels", (0.170, 0.020, 0.010), 2.4),
    "MI_Cell_50_850_650": ("round bumpers", (0.640, 0.520, 0.110), 0.30),
    "MI_Cell_1000_540_80": ("left ramps", (0.850, 0.290, 0.030), 0.30),
    "MI_Cell_960_190_110": ("right ramps", (0.620, 0.025, 0.022), 0.35),
    "MI_Cell_950_960_990": ("ball", (0.780, 0.720, 0.590), 0.12),
}

# Component -> settings
LIGHTS = {
    "KeyLight": {"intensity": 0.22, "color": (130, 150, 160)},
    "TableLamp": {"intensity": 95000.0, "radius": 1700.0, "color": (255, 176, 104), "location": (60.0, 20.0, 350.0)},
    "CounterLamp": {"intensity": 16000.0, "radius": 1100.0, "color": (255, 62, 38), "location": (-783.0, 20.0, 275.0)},
}

POST_PROCESS = {
    "vignette_intensity": 0.72,
    "film_grain_intensity": 0.32,
    "scene_fringe_intensity": 0.55,
    "bloom_intensity": 0.9,
    "motion_blur_amount": 0.0,
}
GRADE = {
    "color_saturation": (0.86, 0.82, 0.78, 1.0),
    "color_contrast": (1.16, 1.14, 1.12, 1.0),
    "color_gain": (1.08, 0.98, 0.90, 1.0),
}

PIXEL_GRID = (420.0, 259.0)
COLOUR_STEPS = 28.0
FOG_DENSITY = 0.005


def material(name, domain=None):
    path = f"{MOOD}/{name}"
    if EAL.does_asset_exist(path):
        mat = unreal.load_asset(path)
        MEL.delete_all_material_expressions(mat)
    else:
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        mat = tools.create_asset(name, MOOD, unreal.Material, unreal.MaterialFactoryNew())
    if domain is not None:
        mat.set_editor_property("material_domain", domain)
    return mat


def custom(mat, code, output, inputs, x, y):
    node = MEL.create_material_expression(mat, unreal.MaterialExpressionCustom, x, y)
    node.set_editor_property("code", code)
    node.set_editor_property("output_type", output)
    pins = []
    for name in inputs:
        pin = unreal.CustomInput()
        pin.set_editor_property("input_name", name)
        pins.append(pin)
    node.set_editor_property("inputs", pins)
    return node


def build_surface():
    mat = material("M_BumpitMood")
    mat.set_editor_property("used_with_instanced_static_meshes", True)
    color = MEL.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -700, 0)
    color.set_editor_property("parameter_name", "Color")
    glow = MEL.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -700, 260)
    glow.set_editor_property("parameter_name", "Glow")
    rough = MEL.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -700, 380)
    rough.set_editor_property("parameter_name", "Roughness")
    rough.set_editor_property("default_value", 0.82)
    position = MEL.create_material_expression(mat, unreal.MaterialExpressionWorldPosition, -700, -180)
    grime = custom(mat, """
float3 fine = floor(Pos / 7.0);
float3 broad = floor(Pos / 56.0);
float a = frac(sin(dot(fine, float3(12.9898, 78.233, 37.719))) * 43758.5453);
float b = frac(sin(dot(broad, float3(3.137, 17.71, 9.31))) * 9871.13);
return Base * lerp(0.60, 1.0, a) * lerp(0.68, 1.0, b);
""", unreal.CustomMaterialOutputType.CMOT_FLOAT3, ["Pos", "Base"], -350, -80)
    MEL.connect_material_expressions(position, "", grime, "Pos")
    MEL.connect_material_expressions(color, "", grime, "Base")
    emissive = MEL.create_material_expression(mat, unreal.MaterialExpressionMultiply, -350, 200)
    MEL.connect_material_expressions(color, "", emissive, "A")
    MEL.connect_material_expressions(glow, "", emissive, "B")
    MEL.connect_material_property(grime, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(emissive, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.recompile_material(mat)
    EAL.save_loaded_asset(mat)
    return mat


def build_retro_filter():
    mat = material("M_PP_BumpitRetro", unreal.MaterialDomain.MD_POST_PROCESS)
    mat.set_editor_property("blendable_location", unreal.BlendableLocation.BL_SCENE_COLOR_AFTER_TONEMAPPING)
    screen = MEL.create_material_expression(mat, unreal.MaterialExpressionScreenPosition, -900, 0)
    grid = custom(mat, f"""
float2 cells = float2({PIXEL_GRID[0]}, {PIXEL_GRID[1]});
return (floor(UV * cells) + 0.5) / cells;
""", unreal.CustomMaterialOutputType.CMOT_FLOAT2, ["UV"], -600, 0)
    MEL.connect_material_expressions(screen, "", grid, "UV")
    scene = MEL.create_material_expression(mat, unreal.MaterialExpressionSceneTexture, -300, 0)
    scene.set_editor_property("scene_texture_id", unreal.SceneTextureId.PPI_POST_PROCESS_INPUT0)
    MEL.connect_material_expressions(grid, "", scene, "UVs")
    steps = custom(mat, f"""
float2 cell = floor(UV * float2({PIXEL_GRID[0]}, {PIXEL_GRID[1]}));
float dither = frac(52.9829189 * frac(dot(cell, float2(0.06711056, 0.00583715)))) - 0.5;
return floor(Color.rgb * {COLOUR_STEPS} + dither + 0.5) / {COLOUR_STEPS};
""", unreal.CustomMaterialOutputType.CMOT_FLOAT3, ["Color", "UV"], 0, 0)
    MEL.connect_material_expressions(scene, "Color", steps, "Color")
    MEL.connect_material_expressions(screen, "", steps, "UV")
    MEL.connect_material_property(steps, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(mat)
    EAL.save_loaded_asset(mat)
    return mat


def apply_palette(surface):
    for name, (_, rgb, glow) in PALETTE.items():
        mi = unreal.load_asset(MATERIALS + name)
        MEL.set_material_instance_parent(mi, surface)
        MEL.set_material_instance_vector_parameter_value(mi, "Color", unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))
        MEL.set_material_instance_scalar_parameter_value(mi, "Glow", glow)
        MEL.update_material_instance(mi)
        EAL.save_loaded_asset(mi)


def components(bp):
    sub = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    lib = unreal.SubobjectDataBlueprintFunctionLibrary
    found = {}
    for handle in sub.k2_gather_subobject_data_for_blueprint(bp):
        obj = lib.get_object(sub.k2_find_subobject_data_from_handle(handle))
        if obj:
            found[obj.get_name()] = obj
    return found


def apply_lights():
    bp = unreal.load_asset(BLUEPRINTS + "BP_WorkshopLighting")
    parts = components(bp)
    for name, settings in LIGHTS.items():
        light = parts[name + "_GEN_VARIABLE"]
        light.modify()
        light.set_editor_property("intensity", settings["intensity"])
        r, g, b = settings["color"]
        light.set_editor_property("light_color", unreal.Color(r=r, g=g, b=b, a=255))
        if "radius" in settings:
            light.set_editor_property("attenuation_radius", settings["radius"])
        if "location" in settings:
            x, y, z = settings["location"]
            light.set_editor_property("relative_location", unreal.Vector(x, y, z))
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    EAL.save_loaded_asset(bp)


def apply_camera(filter_material):
    bp = unreal.load_asset(BLUEPRINTS + "BP_WorkshopCamera")
    lens = components(bp)["CameraComponent"]
    lens.modify()
    settings = lens.get_editor_property("post_process_settings")
    for name, value in POST_PROCESS.items():
        settings.set_editor_property("override_" + name, True)
        settings.set_editor_property(name, value)
    for name, value in GRADE.items():
        settings.set_editor_property("override_" + name, True)
        settings.set_editor_property(name, unreal.Vector4(*value))
    blendable = unreal.WeightedBlendable()
    blendable.set_editor_property("weight", 1.0)
    blendable.set_editor_property("object", filter_material)
    blendables = unreal.WeightedBlendables()
    blendables.set_editor_property("array", [blendable])
    settings.set_editor_property("weighted_blendables", blendables)
    lens.set_editor_property("post_process_settings", settings)
    lens.set_editor_property("post_process_blend_weight", 1.0)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    EAL.save_loaded_asset(bp)


def apply_level():
    unreal.EditorLoadingAndSavingUtils.load_map(MAP)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    labels = {}
    for actor in actors.get_all_level_actors():
        labels.setdefault(actor.get_actor_label(), []).append(actor)
    # Editor previews of the runtime lights; the game spawns BP_WorkshopLighting itself.
    for actor in labels.get("Workshop preview light", []):
        actor.get_component_by_class(unreal.PointLightComponent).set_editor_property("hidden_in_game", True)

    fog = labels.get("Mood fog", [None])[0]
    if fog is None:
        fog = actors.spawn_actor_from_class(unreal.ExponentialHeightFog, unreal.Vector(-310, 0, -230))
        fog.set_actor_label("Mood fog")
    part = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    part.set_editor_property("fog_density", FOG_DENSITY)
    part.set_editor_property("fog_height_falloff", 0.12)
    part.set_editor_property("fog_inscattering_luminance", unreal.LinearColor(0.012, 0.007, 0.005, 1.0))
    part.set_volumetric_fog(True)
    part.set_volumetric_fog_extinction_scale(1.0)

    if "Lamp flicker" not in labels:
        flicker_class = unreal.load_class(None, "/Script/Bumpit.BumpitLampFlicker")
        flicker = actors.spawn_actor_from_class(flicker_class, unreal.Vector(60, 20, 340))
        flicker.set_actor_label("Lamp flicker")
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()


EAL.make_directory(MOOD)
surface = build_surface()
retro = build_retro_filter()
apply_palette(surface)
apply_lights()
apply_camera(retro)
apply_level()
unreal.log("BUMPIT_MOOD_APPLIED")
