"""Add a camera kick and a brief amber contact light to scored bumper hits."""
import sys
from pathlib import Path

import unreal as u

sys.path.insert(0, str(Path(__file__).parent))
from blueprint_graph import B, Graph, ROOT, put

table = u.load_asset(ROOT + 'BP_PinballTable')
shake_path = ROOT + 'BP_BumperCameraShake'
shake = u.load_asset(shake_path)
if not shake:
    factory = u.BlueprintFactory()
    factory.set_editor_property('parent_class', u.LegacyCameraShake)
    shake = u.AssetToolsHelpers.get_asset_tools().create_asset(
        'BP_BumperCameraShake', ROOT.rstrip('/'), u.Blueprint, factory)
B.compile_blueprint(shake)
settings = B.get_default_object(shake)
for key, value in [('single_instance', True), ('oscillation_duration', .115),
                   ('oscillation_blend_in_time', 0), ('oscillation_blend_out_time', .09)]:
    settings.set_editor_property(key, value)
loc = settings.get_editor_property('loc_oscillation')
for axis, amplitude, frequency in [('y', 2.5, 76), ('z', 1.35, 58)]:
    osc = loc.get_editor_property(axis)
    osc.set_editor_property('amplitude', amplitude)
    osc.set_editor_property('frequency', frequency)
    osc.set_editor_property('initial_offset', u.InitialOscillatorOffset.EOO_OFFSET_ZERO)
    loc.set_editor_property(axis, osc)
settings.set_editor_property('loc_oscillation', loc)
assert u.EditorAssetLibrary.save_loaded_asset(shake, False)

helpers = {}
source = (Path(__file__).parent / 'apply_gimmicks.py').read_text(encoding='utf-8-sig')
exec(compile(source.split('with toolset_registry.tool_raising_exceptions():')[0], '<table components>', 'exec'), helpers)
light = helpers['add_component'](table, 'BumperContactLight', u.PointLightComponent)
light.set_mobility(u.ComponentMobility.MOVABLE)
light.set_editor_property('intensity', 0)
light.set_editor_property('attenuation_radius', 85)
light.set_editor_property('cast_shadows', False)
light.set_light_color(u.LinearColor(1, .45, .12, 1))
B.compile_blueprint(table)

g = Graph(table, 'EndBumperFlash', True)
g.action('/Script/Engine.LightComponent:SetIntensity', self=g.get('BumperContactLight'), NewIntensity=0)
g = Graph(table, 'ShowBumperImpact', True)
if 'Contact' not in [p.name for p in B._get_node_info(g.entry.get_owning_node()).output_pins]:
    g.e.add_graph_input_parameter('Contact', B._make_variable_type('Vector'))
# BumperNoteIndex has already been updated by the scoring event.
note_index = g.call('/Script/Engine.KismetMathLibrary:Conv_IntToDouble', InInt=g.get('BumperNoteIndex')).find_output_pin('ReturnValue')
gain = g.math('Add_DoubleDouble', 1.0, g.math('Multiply_DoubleDouble', note_index, .045))
manager = g.call('/Script/Engine.GameplayStatics:GetPlayerCameraManager', PlayerIndex=0).find_output_pin('ReturnValue')
g.action('/Script/Engine.PlayerCameraManager:StartCameraShake', self=manager,
         ShakeClass=shake.generated_class().get_path_name(), Scale=gain)
point = g.math('Add_VectorVector', g.arg('Contact'), '(X=0,Y=0,Z=12)')
g.action('/Script/Engine.SceneComponent:K2_SetWorldLocation', self=g.get('BumperContactLight'), NewLocation=point)
g.action('/Script/Engine.LightComponent:SetIntensity', self=g.get('BumperContactLight'),
         NewIntensity=g.math('Multiply_DoubleDouble', gain, 850))
g.action('/Script/Engine.KismetSystemLibrary:K2_SetTimer', FunctionName='EndBumperFlash', Time=.067)
B.compile_blueprint(table, warnings_as_errors=True)

for name in ('EventGraph', 'CopyHit'):
    g = Graph(table, name)
    nodes = [B._get_node_info(n) for n in B.find_nodes(g.g)]
    hooks = [info for info in nodes if info.type_id == '|PlayBumperNote']
    assert len(hooks) == (2 if name == 'EventGraph' else 1)
    for hook in hooks:
        dest = next(p for p in hook.output_pins if p.name == 'then').connected_pins
        if any(B._get_node_info(p.node).type_id == '|ShowBumperImpact' for p in dest):
            continue
        if name == 'CopyHit':
            hit = g.arg('Hit')
        else:
            prev = next(p for p in hook.input_pins if p.name == 'execute').connected_pins[0]
            ball = 'SplitBall' if B._get_node_info(prev.node).type_id == '|SetSplitHits' else 'Ball'
            hit = next(n.node for n in nodes if n.type_id.endswith('OnComponentHit(' + ball + ')')).find_output_pin('Hit')
        contact = g.call('/Script/Engine.GameplayStatics:BreakHitResult', Hit=hit).find_output_pin('ImpactPoint')
        g.tail = hook.node.find_then_pin()
        g.tail.break_pin_links()
        g.action('ShowBumperImpact', Contact=contact)
        for pin in dest:
            put(B._resolve_pin(pin), g.tail)
B.compile_blueprint(table, warnings_as_errors=True)
assert u.EditorAssetLibrary.save_loaded_asset(table, False)
u.log('BUMPER_IMPACT_INSTALLED')


