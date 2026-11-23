"""Bumper camera shake (and contact flash) that keep growing with the combo. Run after apply_bumper_impact.py and
apply_combo_hud.py. Safe to run repeatedly. Run with the editor closed:
UnrealEditor-Cmd.exe Bumpit.uproject -run=pythonscript -script=<this file> -unattended -nullrhi -culture=en

The combo is BumperComboCount, the same uncapped count the COMBO number on screen shows (the hit sounds stop
climbing at 16, the shake doesn't). Five shakes, one per combo tier, each longer and wider than the last:

    tier   combo    lasts    sideways   tilt (pitch/yaw/roll)   zoom kick
    0      1-4      0.12 s   2.5 cm     -                       -
    1      5-9      0.18 s   4 cm       0.25 deg                -
    2      10-19    0.26 s   7 cm       0.7 deg                 0.6 deg     <- seen from across the room
    3      20-49    0.38 s   12 cm      1.4 deg                 1.5 deg     <- wild
    4      50+      0.60 s   36 cm      4 deg                   4 deg       <- wilder, and no top
Within a tier the shake is scaled up by ShakeComboGrowth (0.06) for every hit past the tier's first combo, with
no cap, so each tier opens a little above where the one before it ended and tier 4 just keeps growing. Each new
hit restarts the shake, so a fast chain shakes without a break.

The contact flash grows too: FlashBase x (1 + FlashGrowth x combo), up to FlashMaxCombo (850 x up to 4.2).

It is only the camera: the table, the ball and the physics are untouched (the tilt is a separate system).
Earlier version: ShowBumperImpact scaled one shake by BumperNoteIndex^2, capped at 3.5x and at combo 16.
"""
import sys
from pathlib import Path

import unreal as u

sys.path.insert(0, str(Path(__file__).parent))
helpers = {}
source = (Path(__file__).parent / 'apply_gimmicks.py').read_text(encoding='utf-8-sig')
exec(compile(source.split('with toolset_registry.tool_raising_exceptions():')[0], '<gimmick helpers>', 'exec'), helpers)
function, add_variables, insert_call, is_entry = helpers['function'], helpers['add_variables'], helpers['insert_call'], helpers['is_entry']
BT, ContainerType, infos_of, pin = helpers['BT'], helpers['ContainerType'], helpers['infos_of'], helpers['pin']

ROOT = '/Game/Bumpit/Blueprints/'
TABLE, HUD, RULES = (u.load_asset(ROOT + n) for n in ('BP_PinballTable', 'BP_BumpitHUD', 'BP_RoundRules'))
helpers['BPS'].update(table=TABLE, hud=HUD, rules=RULES)
CATEGORY = 'Bumper Shake'

# name, first combo, duration, blend out, loc (x, y, z) cm @ Hz, rot (pitch, yaw, roll) deg @ Hz, fov deg @ Hz
TIERS = [
    ('BP_BumperCameraShake',    1,  0.12, 0.09, ((0.0, 2.5, 1.35), (0, 76, 58)), ((0.0, 0.0, 0.0), (0, 0, 0)), (0.0, 0)),
    ('BP_BumperCameraShake_T1', 5,  0.18, 0.12, ((1.0, 4.0, 2.5), (50, 70, 55)), ((0.25, 0.25, 0.0), (40, 36, 0)), (0.0, 0)),
    ('BP_BumperCameraShake_T2', 10, 0.26, 0.16, ((2.0, 7.0, 4.5), (45, 60, 50)), ((0.7, 0.7, 0.3), (34, 30, 28)), (0.6, 20)),
    ('BP_BumperCameraShake_T3', 20, 0.38, 0.22, ((4.0, 12.0, 8.0), (42, 55, 48)), ((1.4, 1.4, 0.8), (32, 29, 26)), (1.5, 18)),
    ('BP_BumperCameraShake_T4', 50, 0.60, 0.30, ((12.0, 36.0, 24.0), (40, 50, 44)), ((4.0, 4.0, 3.0), (30, 27, 24)), (4.0, 16)),
]
SHAKE_COMBO_GROWTH = 0.06
FLASH_BASE, FLASH_GROWTH, FLASH_MAX_COMBO = 850.0, 0.08, 40.0


def make_shake(name, duration, blend_out, loc, rot, fov):
    path = ROOT + name
    shake = u.load_asset(path)
    if not shake:
        factory = u.BlueprintFactory()
        factory.set_editor_property('parent_class', u.LegacyCameraShake)
        shake = u.AssetToolsHelpers.get_asset_tools().create_asset(name, ROOT.rstrip('/'), u.Blueprint, factory)
    BT.compile_blueprint(shake)
    c = BT.get_default_object(shake)
    for key, value in (('single_instance', True), ('oscillation_duration', duration),
                       ('oscillation_blend_in_time', 0.0), ('oscillation_blend_out_time', blend_out)):
        c.set_editor_property(key, value)
    for prop, axes, (amps, freqs) in (('loc_oscillation', ('x', 'y', 'z'), loc), ('rot_oscillation', ('pitch', 'yaw', 'roll'), rot)):
        group = c.get_editor_property(prop)
        for axis, amp, freq in zip(axes, amps, freqs):
            osc = group.get_editor_property(axis)
            osc.set_editor_property('amplitude', amp)
            osc.set_editor_property('frequency', float(freq))
            osc.set_editor_property('initial_offset', u.InitialOscillatorOffset.EOO_OFFSET_ZERO if prop == 'loc_oscillation'
                                    else u.InitialOscillatorOffset.EOO_OFFSET_RANDOM)
            group.set_editor_property(axis, osc)
        c.set_editor_property(prop, group)
    osc = c.get_editor_property('fov_oscillation')
    osc.set_editor_property('amplitude', fov[0])
    osc.set_editor_property('frequency', float(fov[1]))
    c.set_editor_property('fov_oscillation', osc)
    assert u.EditorAssetLibrary.save_loaded_asset(shake, False)
    return shake.generated_class().get_path_name()


SHAKE = """
(fn BumperShake ()
  (bind combo (|GetBumperComboCount))
  (|SetShakeTierNow 0)
  (for i (range (Utilities|Array|Length (|GetShakeTierStarts)))
    (if (>= combo (Utilities|Array|Get(acopy) (|GetShakeTierStarts) i))
      (|SetShakeTierNow i)))
  (bind first (Utilities|Array|Get(acopy) (|GetShakeTierStarts) (|GetShakeTierNow)))
  ; no cap: every hit past the tier's first combo adds ShakeComboGrowth
  (|SetShakeScaleNow (+ 1.0 (* (|GetShakeComboGrowth) (Math|Conversions|ToFloat(Integer) (- combo first)))))
  (|SetShakeLightNow (* (|GetFlashBase) (+ 1.0 (* (|GetFlashGrowth) (Math|Float|Min(Float) (|GetFlashMaxCombo) (Math|Conversions|ToFloat(Integer) combo))))))
  (bind cam (Game|GetPlayerCameraManager :PlayerIndex 0))
  (switch int (|GetShakeTierNow)
{cases}))
"""


def replace_old_shake(table):
    """ShowBumperImpact: the fixed StartCameraShake (and its scale and camera-manager nodes) gives way to a call to
    BumperShake right after the entry; the flash reads ShakeLightNow. Nodes nothing uses any more are removed."""
    graph = BT.get_graph(table, 'ShowBumperImpact')
    shakes = [i for i in infos_of(graph) if 'ShakeClass' in [p.name for p in i.input_pins]]
    if shakes:
        shake = shakes[0]
        for s in list(pin(shake, 'execute').connected_pins):
            for t in list(pin(shake, 'then').connected_pins):
                BT.connect_pins(s, t)
        BT.delete_node(shake.node)
    insert_call(table, 'ShowBumperImpact', is_entry, 'BumperShake')
    graph = BT.get_graph(table, 'ShowBumperImpact')
    light = next(i for i in infos_of(graph) if 'NewIntensity' in [p.name for p in i.input_pins])
    src = [BT._get_node_info(c.node).type_id for c in pin(light, 'NewIntensity').connected_pins]
    if src != ['|GetShakeLightNow']:
        existing = {i.node.get_name() for i in infos_of(graph)}
        helpers['make_node'](graph, '|GetShakeLightNow', u.IntPoint(light.position.x - 250, light.position.y + 120))
        get = next(i for i in infos_of(graph) if i.node.get_name() not in existing)
        for c in list(pin(BT._get_node_info(light.node), 'NewIntensity').connected_pins):
            BT.break_pins(c, pin(BT._get_node_info(light.node), 'NewIntensity').pin_id)
        BT.connect_pins(next(p for p in get.output_pins).pin_id, pin(BT._get_node_info(light.node), 'NewIntensity').pin_id)
    while True:  # prune pure nodes whose outputs go nowhere
        dead = [i for i in infos_of(graph) if not is_entry(i)
                and not any(p.type_id == 'Exec' for p in list(i.input_pins) + list(i.output_pins))
                and i.output_pins and not any(p.connected_pins for p in i.output_pins)]
        if not dead:
            break
        for i in dead:
            BT.delete_node(i.node)


with helpers['toolset_registry'].tool_raising_exceptions():
    classes = [make_shake(name, d, b, loc, rot, fov) for name, _, d, b, loc, rot, fov in TIERS]
    add_variables(TABLE, [('ShakeTierStarts', 'int', ContainerType.ARRAY), ('ShakeTierNow', 'int', None),
                          ('ShakeScaleNow', 'float', None), ('ShakeLightNow', 'float', None), ('ShakeComboGrowth', 'float', None),
                          ('FlashBase', 'float', None), ('FlashGrowth', 'float', None), ('FlashMaxCombo', 'float', None)], CATEGORY)
    BT.compile_blueprint(TABLE)
    cases = '\n'.join(f'    (:{i} (CameraShakes|StartCameraShake :self cam :ShakeClass "{cls}" :Scale (|GetShakeScaleNow)))'
                      for i, cls in enumerate(classes))
    function(TABLE, 'BumperShake', [], SHAKE.replace('{cases}', cases))
    BT.compile_blueprint(TABLE)
    replace_old_shake(TABLE)
    BT.compile_blueprint(TABLE, warnings_as_errors=True)
    cdo = BT.get_default_object(TABLE)
    for name, value in (('ShakeTierStarts', [t[1] for t in TIERS]), ('ShakeComboGrowth', SHAKE_COMBO_GROWTH),
                        ('FlashBase', FLASH_BASE), ('FlashGrowth', FLASH_GROWTH), ('FlashMaxCombo', FLASH_MAX_COMBO)):
        cdo.set_editor_property(name, value)
    assert u.EditorAssetLibrary.save_loaded_asset(TABLE, False)
u.log('BUMPIT_COMBO_SHAKE_APPLIED tiers=' + ', '.join(f'{t[0]}@{t[1]}' for t in TIERS))
