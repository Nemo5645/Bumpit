"""Launch power, reworked. Safe to run repeatedly. Run with the editor closed, then rerun apply_launch_guide.py
(it also fills PowerToExit, below):
UnrealEditor-Cmd.exe Bumpit.uproject -run=pythonscript -script=<this file> -unattended -nullrhi -culture=en

The launch is split in two, like two balls, with the middle of the lane hidden under LaneCover (a board on the
rails of BP_PinballTable from x -120 to 240; no collision).
   exit speed = PowerToExit at Power (blended between its entries) x WeightSpeedScale
PowerToExit is worked out by apply_launch_guide.py so that power 0..1 moves the arrow's tip evenly along a band
across the top of the playfield, from the right end to the left end. Heavy and light balls keep their 0.85 / 1.15
factor on top (they fall shorter / run further than the arrow's band would suggest for the same press).
1. Lane: the plunger fires at the speed that, losing LaneDecel (515 cm/s per second, measured in the narrow lane)
   on the way, arrives at the cover's top end with the corner entry speed. So a harder press looks faster.
2. Under the cover (x >= HideX) ApplyLaunchPower parks the ball, still and weightless, at (SpawnX, SpawnY) =
   (226, 355), just inside the cover's top end, for as long as the roll from HideX to there would take.
3. Corner: it comes out of the cover and rides up the lane end and round the top-right corner on a fixed path
   (straight to x RideCX, then a quarter circle of RideRadius 60 about (RideCX, RideCY) = (278, 295), clear of the
   walls), slowing as it climbs like a real roll would (RideDecel, the 303 cm/s per second of the tilt):
       speed at x = max(RideMinSpeed, sqrt(exit^2 + 2 x RideDecel x (exit point x - x)))
   Left to physics, the ball bounced along the corner's wall differently for every speed, so the same press could
   land anywhere; on the ride it always comes out the same way.
4. At the top, (RideCX + RideRadius, RideCY) heading left along the top rail, it is handed back to physics at the
   exit speed, with no spin. A soft press drops just below the corner on the right; a hard one runs far left.
It is the same ball all along, so scoring, hits and the launch gate work as before.
5. Holding Space no longer stops at full: the gauge runs 0 -> 1 -> 0 -> ... (ChargeSeconds per half, BP_BumpitHUD)
   until Space is released.

Before this, the launch was 760 + 360 x Power cm/s (x WeightSpeedScale), set by apply_table_tuning.py in
GetLaunchSpeed. Launch no longer reads GetLaunchSpeed, so rerunning that script doesn't undo this.
LaunchExitMin / LaunchExitMax / LaunchCurve are only used while PowerToExit is empty.
"""
import math
import sys
from pathlib import Path

import unreal as u

sys.path.insert(0, str(Path(__file__).parent))
helpers = {}
source = (Path(__file__).parent / 'apply_gimmicks.py').read_text(encoding='utf-8-sig')
exec(compile(source.split('with toolset_registry.tool_raising_exceptions():')[0], '<gimmick helpers>', 'exec'), helpers)
function, add_variables, insert_call, is_entry = helpers['function'], helpers['add_variables'], helpers['insert_call'], helpers['is_entry']
BT, infos_of, pin, make_node = helpers['BT'], helpers['infos_of'], helpers['pin'], helpers['make_node']

ROOT = '/Game/Bumpit/Blueprints/'
TABLE, HUD, RULES = (u.load_asset(ROOT + n) for n in ('BP_PinballTable', 'BP_BumpitHUD', 'BP_RoundRules'))
helpers['BPS'].update(table=TABLE, hud=HUD, rules=RULES)

LAUNCH_EXIT_MIN, LAUNCH_EXIT_MAX, LAUNCH_CURVE = 30.0, 650.0, 0.0  # fallback while PowerToExit is empty
LANE_DECEL = 515.0         # cm/s per second the ball loses in the narrow lane (PIE recordings, 2026-11-23)
LANE_START_X = -269.0      # where the ball waits (ResetBall)
RIDE_CX, RIDE_CY, RIDE_RADIUS = 278.0, 295.0, 60.0  # corner wall: radius 72 about (278, 295); ball radius 9.7
RIDE_DECEL = 303.0         # 980 x sin 18: what the tilt takes off a climbing ball, per second
RIDE_MIN_SPEED = 90.0      # cm/s: a soft shot slows towards the top but doesn't creep (at 10 cm/s it took 1.9 s)
CHARGE_SECONDS = 1.4       # 0 -> full, as before; then back down

# Covers, table space (cm). Rails stand 54 cm tall from z -12, so their tops are at z 42; the covers lie on them.
COVER_X0 = -120.0          # where the lane disappears; the plunger end below stays visible
COVER_Z, COVER_THICK = 44.0, 4.0
LANE_COVER_X1 = 240.0      # the lane board ends here, where the lane divider does; the corner stays in view
LANE_COVER = ((COVER_X0 + LANE_COVER_X1) / 2, 356.0), (LANE_COVER_X1 - COVER_X0, 48.0)  # over divider, lane, outer rail
HIDE_X = -80.0             # ball centre fully under LaneCover
SPAWN_X, SPAWN_Y = 226.0, RIDE_CY + RIDE_RADIUS  # just inside the cover's top end, on the ride's line (y 355)

ARM = """
(fn ArmLaunchPower (Power)
  (|SetPendingPower Power)
  (|SetPowerPending true)
  (|SetLaunchStage 1)
  (Physics|SetEnableGravity :self (|GetBall) :bGravityEnabled true)
  (bind raw (Math|Float|Max(Float) 0.0 (Math|Float|Min(Float) 1.0 Power)))
  (bind n (Utilities|Array|Length (|GetPowerToExit)))
  (if (> n 1)
    (bind f (* raw (Math|Conversions|ToFloat(Integer) (- n 1))))
    (|SetExitIdx 0)
    (for j (range (- n 1))
      (if (>= f (Math|Conversions|ToFloat(Integer) j))
        (|SetExitIdx j)))
    (bind e0 (Utilities|Array|Get(acopy) (|GetPowerToExit) (|GetExitIdx)))
    (bind e1 (Utilities|Array|Get(acopy) (|GetPowerToExit) (+ (|GetExitIdx) 1)))
    (bind a (Math|Float|Min(Float) 1.0 (- f (Math|Conversions|ToFloat(Integer) (|GetExitIdx)))))
    (|SetExitSpeedNow (* (+ e0 (* (- e1 e0) a)) (|GetWeightSpeedScale)))
    (else
      (bind s (+ raw (* (|GetLaunchCurve) (- (* raw raw) raw))))
      (|SetExitSpeedNow (* (+ (|GetLaunchExitMin) (* (- (|GetLaunchExitMax) (|GetLaunchExitMin)) s)) (|GetWeightSpeedScale)))))
  ; The corner entry speed (at the cover's top end) that climbs to the exit speed, and the plunger speed that
  ; rolls up the lane to it.
  (|SetEntrySpeedNow (Math|Float|Sqrt (+ (* (|GetExitSpeedNow) (|GetExitSpeedNow)) (* (* 2.0 (|GetRideDecel)) (- (+ (|GetRideCX) (|GetRideRadius)) (|GetSpawnX))))))
  (|SetLaneSpeedNow (Math|Float|Sqrt (+ (* (|GetEntrySpeedNow) (|GetEntrySpeedNow)) (* (* 2.0 (|GetLaneDecel)) (- (|GetSpawnX) (|GetLaneStartX)))))))
"""

APPLY = """
(fn ApplyLaunchPower ()
  (bind ball (|GetBall))
  (bind xf (Transformation|GetActorTransform))
  (bind now (Utilities|Time|GetGameTimeinSeconds))
  (if (and (== (|GetLaunchStage) 1) (Physics|IsSimulatingPhysics :self ball))
    (bind p (Math|Transform|InverseTransformLocation xf (Transformation|GetWorldLocation :self ball)))
    ; Under the lane cover: park the ball at the cover's top end, still and weightless, for as long as the roll
    ; there would take: from the speed it has now down to the corner entry speed, at LaneDecel.
    ; Only a ball still in the lane channel (y 345-367): one put elsewhere (a test, a future gimmick) is left alone.
    (if (and (>= (.x p) (|GetHideX)) (>= (.y p) 345.0))
      (|SetLaunchStage 2)
      (|SetRideZ (.z p))
      (bind vnow (Math|Float|Sqrt (Math|Float|Max(Float) 0.0 (- (* (|GetLaneSpeedNow) (|GetLaneSpeedNow)) (* (* 2.0 (|GetLaneDecel)) (- (.x p) (|GetLaneStartX)))))))
      (|SetHiddenUntil (+ now (Math|Float|Max(Float) 0.02 (/ (- vnow (|GetEntrySpeedNow)) (|GetLaneDecel)))))
      (Physics|SetEnableGravity :self ball :bGravityEnabled false)
      (Transformation|SetWorldLocation :self ball :NewLocation (Math|Transform|TransformLocation xf (Math|Vector|MakeVector (|GetSpawnX) (|GetSpawnY) (.z p))) :bSweep false :bTeleport true)
      (Physics|SetPhysicsAngularVelocityinDegrees :self ball :NewAngVel (Math|Vector|MakeVector 0.0 0.0 0.0) :bAddToCurrent false)
      (Physics|SetPhysicsLinearVelocity :self ball :NewVel (Math|Vector|MakeVector 0.0 0.0 0.0) :bAddToCurrent false)))
  (if (and (== (|GetLaunchStage) 2) (>= now (|GetHiddenUntil)))
    (|SetLaunchStage 3)
    (|SetRideDist 0.0)
    (|SetRideLast now)
    (|SetRideSpeed (|GetEntrySpeedNow)))
  ; The ride: up the lane end and round the corner on a fixed path, slowing as it climbs.
  (if (== (|GetLaunchStage) 3)
    (bind straight (- (|GetRideCX) (|GetSpawnX)))
    (bind R (|GetRideRadius))
    (|SetRideDist (+ (|GetRideDist) (* (|GetRideSpeed) (- now (|GetRideLast)))))
    (|SetRideLast now)
    (if (>= (|GetRideDist) (+ straight (* R 1.5707963)))
      ; Top of the corner: back to physics, heading left along the top rail at the exit speed.
      (|SetLaunchStage 0)
      (|SetPowerPending false)
      (Transformation|SetWorldLocation :self ball :NewLocation (Math|Transform|TransformLocation xf (Math|Vector|MakeVector (+ (|GetRideCX) R) (|GetRideCY) (|GetRideZ))) :bSweep false :bTeleport true)
      (Physics|SetEnableGravity :self ball :bGravityEnabled true)
      (Physics|SetPhysicsAngularVelocityinDegrees :self ball :NewAngVel (Math|Vector|MakeVector 0.0 0.0 0.0) :bAddToCurrent false)
      (|SetIncomingVelocity (Math|Transform|TransformDirection xf (Math|Vector|MakeVector 0.0 (- 0.0 (|GetExitSpeedNow)) 0.0)))
      (Physics|SetPhysicsLinearVelocity :self ball :NewVel (|GetIncomingVelocity) :bAddToCurrent false)
      (else
        (bind d (|GetRideDist))
        (bind onArc (> d straight))
        (bind th (- 90.0 (* (/ (- d straight) R) 57.29578)))
        (bind x (select onArc (+ (|GetRideCX) (* R (Math|Trig|Cos(Degrees) th))) (+ (|GetSpawnX) d)))
        (bind y (select onArc (+ (|GetRideCY) (* R (Math|Trig|Sin(Degrees) th))) (|GetSpawnY)))
        (bind tx (select onArc (Math|Trig|Sin(Degrees) th) 1.0))
        (bind ty (select onArc (- 0.0 (Math|Trig|Cos(Degrees) th)) 0.0))
        ; never slower than RideMinSpeed, or a soft shot would creep over the top for seconds
        (|SetRideSpeed (Math|Float|Max(Float) (|GetRideMinSpeed) (Math|Float|Sqrt (+ (* (|GetExitSpeedNow) (|GetExitSpeedNow)) (* (* 2.0 (|GetRideDecel)) (Math|Float|Max(Float) 0.0 (- (+ (|GetRideCX) R) x)))))))
        (Transformation|SetWorldLocation :self ball :NewLocation (Math|Transform|TransformLocation xf (Math|Vector|MakeVector x y (|GetRideZ))) :bSweep false :bTeleport true)
        (Physics|SetPhysicsLinearVelocity :self ball :NewVel (Math|Transform|TransformDirection xf (Math|Vector|MakeVector (* tx (|GetRideSpeed)) (* ty (|GetRideSpeed)) 0.0)) :bAddToCurrent false)))))
"""

ADVANCE = """
(fn AdvanceCharge (Delta)
  (|SetChargeTime (+ (|GetChargeTime) Delta))
  (bind t (Math|Float|%(Float) (/ (|GetChargeTime) (Math|Float|Max(Float) 0.1 (|GetChargeSeconds))) 2.0))
  (|SetPower (- 1.0 (Math|Float|Absolute(Float) (- t 1.0)))))
"""

RESET = """
(fn ResetCharge ()
  (|SetChargeTime 0.0))
"""


def fixed_lane_speed(table):
    """Launch: the velocity along the lane was GetLaunchSpeed(Power) x WeightSpeedScale; it becomes LaneSpeedNow
    (set by ArmLaunchPower, which runs first). An earlier version of this script used a fixed LaneLaunchSpeed."""
    graph = BT.get_graph(table, 'Launch')
    vec = next(i for i in infos_of(graph) if i.type_id == 'Math|Vector|MakeVector' and pin(i, 'X').connected_pins)
    src = BT._get_node_info(pin(vec, 'X').connected_pins[0].node)
    if src.type_id == '|GetLaneSpeedNow':
        return
    old = [src.node] + [BT._get_node_info(c.node).node for p in src.input_pins for c in p.connected_pins]
    get = BT._get_node_info(make_node(graph, '|GetLaneSpeedNow', u.IntPoint(vec.position.x - 250, vec.position.y)))
    BT.connect_pins(next(p for p in get.output_pins).pin_id, pin(BT._get_node_info(vec.node), 'X').pin_id)
    for node in old:  # the multiply, GetLaunchSpeed and the WeightSpeedScale read, now unused
        info = BT._get_node_info(node)
        ins = [p for p in info.input_pins if p.type_id == 'Exec']
        outs = [p for p in info.output_pins if p.type_id == 'Exec']
        if ins and outs:  # GetLaunchSpeed is an impure call inside Launch's exec chain: bridge it
            for s in list(ins[0].connected_pins):
                for t in list(outs[0].connected_pins):
                    BT.connect_pins(s, t)
        BT.delete_node(node)


def build_covers(table):
    """LaneCover: a rail-coloured board lying on the rails, with no collision. Corner covers from earlier versions
    of this script (CornerCover, CornerBand00-09) are removed."""
    sub, root, found = helpers['subobjects'](table)
    for name, (handle, _) in list(found.items()):
        if name.startswith('CornerCover') or name.startswith('CornerBand'):
            sub.delete_subobject(root, handle, table)
    _, _, found = helpers['subobjects'](table)
    rail = found['UpperRail'][1]
    pieces = {'LaneCover': (LANE_COVER[0], LANE_COVER[1], 0.0, COVER_Z)}
    for name, ((cx, cy), (lx, ly), yaw, z) in pieces.items():
        part = helpers['add_component'](table, name, u.StaticMeshComponent)
        part.set_editor_property('static_mesh', rail.static_mesh)
        part.set_editor_property('override_materials', rail.get_editor_property('override_materials'))
        part.set_editor_property('relative_location', u.Vector(cx, cy, z))
        part.set_editor_property('relative_rotation', u.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
        part.set_editor_property('relative_scale3d', u.Vector(lx / 100.0, ly / 100.0, COVER_THICK / 100.0))
        body = part.get_editor_property('body_instance')
        body.set_editor_property('collision_enabled', u.CollisionEnabled.NO_COLLISION)
        body.set_editor_property('collision_profile_name', 'NoCollision')
        part.set_editor_property('body_instance', body)
        part.set_editor_property('generate_overlap_events', False)


def ping_pong_charge(hud):
    """UpdateBoard: Power = Min(1, Power + Delta / 1.4) becomes AdvanceCharge(Delta); ResetCharge runs where a
    new charge starts (Power = 0)."""
    graph = BT.get_graph(hud, 'UpdateBoard')
    infos = infos_of(graph)
    setters = [i for i in infos if i.type_id == '|SetPower']
    start = next(i for i in setters if not pin(i, 'Power').connected_pins)
    insert_call(hud, 'UpdateBoard', lambda i: i.node.get_name() == start.node.get_name(), 'ResetCharge')
    grow = [i for i in setters if pin(i, 'Power').connected_pins]
    if not grow:
        return  # already replaced
    grow = grow[0]
    entry = next(i for i in infos_of(graph) if is_entry(i))
    chain, todo = [], [BT._get_node_info(c.node) for c in pin(grow, 'Power').connected_pins]
    while todo:  # the Min / + / / / literal nodes feeding the old setter (not the entry or the Power read's owner)
        i = todo.pop()
        if is_entry(i) or i.node in chain:
            continue
        chain.append(i.node)
        todo += [BT._get_node_info(c.node) for p in i.input_pins for c in p.connected_pins]
    sources, targets = list(pin(grow, 'execute').connected_pins), list(pin(grow, 'then').connected_pins)
    existing = {i.node.get_name() for i in infos_of(graph)}
    make_node(graph, '|AdvanceCharge', u.IntPoint(grow.position.x, grow.position.y))
    call = next(i for i in infos_of(graph) if i.node.get_name() not in existing)
    BT.delete_node(grow.node)
    for node in chain:
        BT.delete_node(node)
    call = BT._get_node_info(call.node)
    for s in sources:
        BT.connect_pins(s, pin(call, 'execute').pin_id)
    for t in targets:
        BT.connect_pins(pin(call, 'then').pin_id, t)
    BT.connect_pins(pin(BT._get_node_info(entry.node), 'Delta').pin_id, pin(BT._get_node_info(call.node), 'Delta').pin_id)


with helpers['toolset_registry'].tool_raising_exceptions():
    add_variables(TABLE, [('PowerPending', 'bool', None), ('PendingPower', 'float', None),
                          ('LaneSpeedMin', 'float', None), ('LaneSpeedMax', 'float', None), ('LaneSpeedNow', 'float', None),
                          ('SpawnX', 'float', None), ('SpawnY', 'float', None), ('LaunchStage', 'int', None),
                          ('HideX', 'float', None), ('HiddenDistance', 'float', None), ('HiddenUntil', 'float', None),
                          ('LaunchExitAngle', 'float', None), ('LaunchExitFloor', 'float', None),
                          ('ExitSpeedNow', 'float', None), ('LaneDecel', 'float', None), ('LaneStartX', 'float', None),
                          ('EntrySpeedNow', 'float', None), ('ExitIdx', 'int', None), ('PowerToExit', 'float', helpers['ContainerType'].ARRAY),
                          ('RideCX', 'float', None), ('RideCY', 'float', None), ('RideRadius', 'float', None),
                          ('RideDecel', 'float', None), ('RideDist', 'float', None), ('RideSpeed', 'float', None), ('RideZ', 'float', None), ('RideLast', 'float', None), ('RideMinSpeed', 'float', None),
                          ('LaunchExitMin', 'float', None), ('LaunchExitMax', 'float', None), ('LaunchCurve', 'float', None)],
                  'Launch Power')
    build_covers(TABLE)
    BT.compile_blueprint(TABLE)
    function(TABLE, 'ArmLaunchPower', [('Power', 'float')], ARM)
    function(TABLE, 'ApplyLaunchPower', [], APPLY)
    BT.compile_blueprint(TABLE)
    fixed_lane_speed(TABLE)
    insert_call(TABLE, 'Launch', is_entry, 'ArmLaunchPower', [('Power', 'Power')])
    tick = lambda i: isinstance(i.node, u.K2Node_Event) and 'Tick' in i.node.get_node_title()
    insert_call(TABLE, 'EventGraph', tick, 'ApplyLaunchPower')
    BT.compile_blueprint(TABLE, warnings_as_errors=True)
    cdo = BT.get_default_object(TABLE)
    for name, value in (('LaneSpeedNow', 0.0), ('ExitSpeedNow', 0.0), ('RideCX', RIDE_CX), ('RideCY', RIDE_CY),
                        ('RideRadius', RIDE_RADIUS), ('RideDecel', RIDE_DECEL), ('RideMinSpeed', RIDE_MIN_SPEED),
                        ('LaneDecel', LANE_DECEL), ('LaneStartX', LANE_START_X),
                        ('SpawnX', SPAWN_X), ('SpawnY', SPAWN_Y), ('LaunchExitMin', LAUNCH_EXIT_MIN),
                        ('LaunchExitMax', LAUNCH_EXIT_MAX), ('LaunchCurve', LAUNCH_CURVE), ('PowerPending', False),
                        ('LaunchStage', 0), ('HideX', HIDE_X)):
        cdo.set_editor_property(name, value)

    add_variables(HUD, [('ChargeTime', 'float', None), ('ChargeSeconds', 'float', None)], 'Launch Power')
    BT.compile_blueprint(HUD)
    function(HUD, 'AdvanceCharge', [('Delta', 'float')], ADVANCE)
    function(HUD, 'ResetCharge', [], RESET)
    BT.compile_blueprint(HUD)
    ping_pong_charge(HUD)
    BT.compile_blueprint(HUD, warnings_as_errors=True)
    BT.get_default_object(HUD).set_editor_property('ChargeSeconds', CHARGE_SECONDS)
    for bp in (TABLE, HUD):
        assert u.EditorAssetLibrary.save_loaded_asset(bp, False)
u.log('BUMPIT_LAUNCH_POWER_APPLIED')
