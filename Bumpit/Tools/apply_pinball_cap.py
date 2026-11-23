"""Replace the Niagara bumper burst with a per-instance illuminated spring cap."""
import sys
from pathlib import Path
import unreal as u

tools_dir = Path(__file__).parent
sys.path.insert(0, str(tools_dir))
from blueprint_graph import B, Graph, ROOT

table = u.load_asset(ROOT + 'BP_PinballTable')
mood = {}
exec(compile((tools_dir/'apply_mood.py').read_text(encoding='utf-8-sig').split('surface = build_surface()')[0], '<surface helpers>', 'exec'), mood)
parts = mood['components'](table)
mel = u.MaterialEditingLibrary
lib = u.EditorAssetLibrary
folder = '/Game/Bumpit/FX'
master_path = folder + '/M_PinballCap'
master = u.load_asset(master_path) if lib.does_asset_exist(master_path) else lib.duplicate_asset('/Game/Bumpit/Mood/M_BumpitMood', master_path)
# Use the original material's base shading and emissive as the unlit state.
emi = mel.get_material_property_input_node(master, u.MaterialProperty.MP_EMISSIVE_COLOR)
if emi.get_class().get_name() != 'MaterialExpressionCustom':
    def node(cls, x, y):
        return mel.create_material_expression(master, cls, x, y)
    def wire(src, dst, name):
        assert mel.connect_material_expressions(src, '', dst, name)
    def shader(code, typ, inputs, x, y):
        return mood['custom'](master, code, typ, list(inputs), x, y)
    stamp = node(u.MaterialExpressionPerInstanceCustomData, -900, 520)
    clock = node(u.MaterialExpressionTime, -900, 620)
    local = node(u.MaterialExpressionPreSkinnedPosition, -900, 720)
    age = shader('return Stamp > 0 ? max(0.0, Now - (Stamp - 1.0)) : 1000.0;',
                 u.CustomMaterialOutputType.CMOT_FLOAT1, ['Stamp','Now'], -620, 520)
    wire(stamp, age, 'Stamp')
    wire(clock, age, 'Now')
    # Vertex-only travel, in centimetres. The bottom of each collider stays planted.
    kick = shader("""
float top = saturate((P.z + 50.0) / 100.0);
float press = smoothstep(0.0, 0.022, Age) * (1.0 - smoothstep(0.026, 0.078, Age));
float rebound = smoothstep(0.048, 0.088, Age) * (1.0 - smoothstep(0.09, 0.165, Age));
return float3(0, 0, top * (-8.0 * press + 3.6 * rebound));
""", u.CustomMaterialOutputType.CMOT_FLOAT3, ['P','Age'], -250, 510)
    wire(local, kick, 'P')
    wire(age, kick, 'Age')
    assert mel.connect_material_property(kick, '', u.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    age_pixel = node(u.MaterialExpressionVertexInterpolator, -360, 800)
    coord = node(u.MaterialExpressionVertexInterpolator, -360, 940)
    wire(age, age_pixel, '')
    wire(local, coord, '')
    bar = node(u.MaterialExpressionScalarParameter, -360, 1090)
    bar.set_editor_property('parameter_name', 'RectangularCap')
    lamp = shader("""
float radius = lerp(length(P.xy), max(abs(P.x), abs(P.y)), Bar) / 50.0;
float rim = smoothstep(0.64, 0.71, radius) * (1.0 - smoothstep(0.87, 0.94, radius));
rim *= smoothstep(46.0, 49.5, P.z);
float pulse = 1.0 - smoothstep(0.045, 0.155, Age);
return Base + rim * (float3(0.12, 0.055, 0.012) + pulse * float3(6.0, 2.4, 0.42));
""", u.CustomMaterialOutputType.CMOT_FLOAT3, ['P','Age','Base','Bar'], 20, 780)
    for src, name in [(coord,'P'),(age_pixel,'Age'),(emi,'Base'),(bar,'Bar')]:
        wire(src, lamp, name)
    assert mel.connect_material_property(lamp, '', u.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.recompile_material(master)
    assert lib.save_loaded_asset(master, False)

bumpers = {}
for key, comp in parts.items():
    if not isinstance(comp, u.InstancedStaticMeshComponent) or 'Bumper' not in map(str,comp.component_tags):
        continue
    name = key.removesuffix('_GEN_VARIABLE')
    bumpers[name] = comp
    path = folder + '/MI_Cap_' + name
    mat = u.load_asset(path) if lib.does_asset_exist(path) else lib.duplicate_asset(comp.get_material(0).get_path_name().split('.')[0], path)
    mel.set_material_instance_parent(mat, master)
    mel.set_material_instance_scalar_parameter_value(mat, 'RectangularCap', float(comp.static_mesh.get_name() == 'Cube'))
    mel.update_material_instance(mat)
    assert lib.save_loaded_asset(mat, False)
    comp.modify()
    comp.set_editor_property('override_materials', [mat])
    comp.set_num_custom_data_floats(1)
assert len(bumpers) == 8

# All ball variants already forward their physical hit and OtherComp to this hook.
g = Graph(table, 'SpawnBumperHitFX', True)
hit = g.call('/Script/Engine.GameplayStatics:BreakHitResult', Hit=g.arg('Hit'))
index = hit.find_output_pin('HitItem')
now = g.call('/Script/Engine.GameplayStatics:GetTimeSeconds').find_output_pin('ReturnValue')
stamp = g.math('Add_DoubleDouble', now, 1.0)
for name in sorted(bumpers):
    part = g.get(name)
    match = g.math('EqualEqual_ObjectObject', g.arg('OtherComp'), part)
    yes, no = g.branch(match)
    g.tail = yes
    g.action('/Script/Engine.InstancedStaticMeshComponent:SetCustomDataValue',
             self=part, InstanceIndex=index, CustomDataIndex=0, CustomDataValue=stamp, bMarkRenderStateDirty=True)
    g.tail = no
B.compile_blueprint(table, warnings_as_errors=True)
assert lib.save_loaded_asset(table, False)
u.log('PINBALL_CAP_INSTALLED')


