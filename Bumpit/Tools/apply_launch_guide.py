"""Launch guide: a dashed arrow on the table view that shows where the ball will go at the current power.
Safe to run repeatedly. Needs apply_launch_power.py first. Run with the editor closed:
UnrealEditor-Cmd.exe Bumpit.uproject -run=pythonscript -script=<this file> -unattended -nullrhi -culture=en

While Space is held to charge a launch (Phase 0, Station 1, a bought ball left, the camera settled), BP_BumpitHUD
draws the path where the ball can be seen: from the waiting ball up to the lane cover, then from the cover's top
end round the corner (the fixed ride of apply_launch_power.py) and on across the playfield, up to an invisible
line across the top of the playfield (BAND_LINE_X, the bottom of the band the arrow's tip moves in). It follows
Power as the gauge swings, and stops early at a placed obstacle or the left rail.

The playfield part is recorded, not modelled: from the top of the corner the ball always starts the same way for a
given exit speed, so record_launch_guide.py launches it at exit speeds 20-900 cm/s (every 20) and stores where it
went (launch_guide_paths.json, every 0.04 s). The HUD blends the two recordings either side of the current exit
speed, so the arrow lies on the real path.

This script also fills BP_PinballTable.PowerToExit: from the recordings, the exit speed for each power step
(0, 0.05, ... 1) that puts the tip at an even step along the line, from BAND_RIGHT_Y (power 0) to BAND_LEFT_Y
(power 1). Heavy and light balls then go 0.85 / 1.15 times as fast, so their tips land shorter / further.

Look (BP_BumpitHUD, category "Launch Guide"): GuideColor, GuideAlpha, GuideThickness, GuideDash, GuideGap,
GuideFlow (how fast the dashes run, px/s), GuideFieldSteps. Screen sizes are multiplied by ScaleHUD.
"""
import json
import math
import sys
from pathlib import Path

import unreal as u

sys.path.insert(0, str(Path(__file__).parent))
helpers = {}
source = (Path(__file__).parent / 'apply_gimmicks.py').read_text(encoding='utf-8-sig')
exec(compile(source.split('with toolset_registry.tool_raising_exceptions():')[0], '<gimmick helpers>', 'exec'), helpers)
function, add_variables, insert_call, is_entry = helpers['function'], helpers['add_variables'], helpers['insert_call'], helpers['is_entry']
BT, ContainerType = helpers['BT'], helpers['ContainerType']

ROOT = '/Game/Bumpit/Blueprints/'
TABLE, HUD, RULES = (u.load_asset(ROOT + n) for n in ('BP_PinballTable', 'BP_BumpitHUD', 'BP_RoundRules'))
helpers['BPS'].update(table=TABLE, hud=HUD, rules=RULES)

PATHS = json.loads((Path(__file__).parent / 'launch_guide_paths.json').read_text(encoding='utf8'))
SPEEDS, STEPS = PATHS['speeds'], PATHS['steps']
PER_SPEED = STEPS + 1
SPEED0, SPEED_STEP = SPEEDS[0], SPEEDS[1] - SPEEDS[0]
SPAWN_X, SPAWN_Y = PATHS['spawn']

# --- Table space (cm) -----------------------------------------------------------------------------------------
LANE_Y, Z = 356.0, 10.0
COVER_X0, COVER_X1 = -120.0, 240.0         # LaneCover (apply_launch_power.py)
RIDE_CX, RIDE_CY, RIDE_RADIUS = 278.0, 295.0, 60.0  # the corner ride (apply_launch_power.py)
BAND_LINE_X = 210.0                        # the invisible line the tip stops on: bottom of the band, 140 cm below the top rail
BAND_RIGHT_Y, BAND_LEFT_Y = 281.0, -262.0  # tip at power 0 / power 1 (the band runs y -268 .. 318); 281 is the
                                           # slowest recording (20 cm/s), just below where the ball comes out
LEFT_LIMIT, BOTTOM_LIMIT = -277.0, -330.0  # left rail face + ball radius; just above the goals
HIT_RADIUS = 27.0                          # bumper radius 16.2 + ball radius 9.7, rounded up
START_AHEAD = 12.0                         # the arrow starts just in front of the waiting ball (radius 9.7)

# --- Look -----------------------------------------------------------------------------------------------------
GUIDE_COLOR = (1.0, 0.72, 0.40, 1.0)  # warm lamp amber, like the power bar
GUIDE_ALPHA = 0.55
GUIDE_THICKNESS = 2.5
GUIDE_DASH, GUIDE_GAP = 9.0, 8.0
GUIDE_FLOW = 26.0
GUIDE_FIELD_STEPS = STEPS  # the whole recording: the band line, an obstacle or the left rail ends the arrow first

f = lambda v: f'{v:.4f}'
ride_points = f"""
  (Utilities|Array|Add (|GetGuidePoints) (Math|Vector|MakeVector {f(COVER_X1)} {f(RIDE_CY + RIDE_RADIUS)} {f(Z)}))""" + ''.join(
    f"""
  (Utilities|Array|Add (|GetGuidePoints) (Math|Vector|MakeVector {f(RIDE_CX + RIDE_RADIUS * math.cos(t))} {f(RIDE_CY + RIDE_RADIUS * math.sin(t))} {f(Z)}))"""
    for t in (math.pi / 2 * (1 - i / 10) for i in range(10)))

table_points = [u.Vector(x, y, Z) for path in PATHS['paths'] for x, y in path + [path[-1]] * (PER_SPEED - len(path))]
table_ends = [len(path) - 1 for path in PATHS['paths']]


def band_crossing(path):
    """Where a recorded path crosses the band line (its y), or None."""
    for (x0, y0), (x1, y1) in zip(path, path[1:]):
        if x0 >= BAND_LINE_X > x1:
            return y0 + (y1 - y0) * (x0 - BAND_LINE_X) / (x0 - x1)
    return None


# Exit speed -> tip position, from the recordings (a dead drop at 0). It runs right to left as the speed grows.
crossings = [(0.0, SPAWN_Y)] + [(v, y) for v, y in ((v, band_crossing(p)) for v, p in zip(SPEEDS, PATHS['paths'])) if y is not None]
for (v0, y0), (v1, y1) in zip(crossings, crossings[1:]):
    assert y1 < y0, f'tip positions must run one way: {v0} -> {y0:.0f}, {v1} -> {y1:.0f}'
assert crossings[-1][1] <= BAND_LEFT_Y, f'no recording reaches the left end of the band ({crossings[-1]})'


def speed_for(y):
    for (v0, y0), (v1, y1) in zip(crossings, crossings[1:]):
        if y1 <= y <= y0:
            return v0 + (v1 - v0) * (y0 - y) / (y0 - y1)
    raise ValueError(y)


power_to_exit = [round(speed_for(BAND_RIGHT_Y + (BAND_LEFT_Y - BAND_RIGHT_Y) * i / 20), 2) for i in range(21)]

GUIDE_LANE = f"""
(fn GuideLane (ToX)
  (bind table (|GetTable))
  (bind ball (Math|Transform|InverseTransformLocation (Transformation|GetActorTransform :self table) (Transformation|GetWorldLocation :self (|GetBall :self table))))
  (bind xs (Math|Float|Min(Float) (- ToX 1.0) (+ (.x ball) {f(START_AHEAD)})))
  (for i (range 13)
    (Utilities|Array|Add (|GetGuidePoints) (Math|Vector|MakeVector (+ xs (* (- ToX xs) (/ (Math|Conversions|ToFloat(Integer) i) 12.0))) {f(LANE_Y)} {f(Z)}))))
"""

# Speed is the exit speed onto the playfield (cm/s), as ApplyLaunchPower will set it.
BUILD = f"""
(fn BuildLaunchGuide (Speed)
  (Utilities|Array|Clear (|GetGuidePoints))
  (Utilities|Array|Clear (|GetGuideObs))
  (bind table (|GetTable))
  (for c (range (Utilities|Array|Length (|GetCellTypes)))
    (if (!= (Utilities|Array|Get(acopy) (|GetCellTypes) c) 0)
      (Utilities|Array|Add (|GetGuideObs) (|HexCenter :self table :Index c))))
  (|GuideLane :ToX {f(COVER_X0 - 4.0)})
  ; A point with z -999 breaks the line: the ball is out of sight under the cover in between.
  (Utilities|Array|Add (|GetGuidePoints) (Math|Vector|MakeVector 0.0 0.0 -999.0))
  ; The corner ride: out of the cover's top end, up to the corner and round it.{ride_points}
  (|SetGuideIdx 0)
  (for j (range {len(SPEEDS) - 1})
    (if (>= Speed (+ {f(SPEED0)} (* {f(SPEED_STEP)} (Math|Conversions|ToFloat(Integer) j))))
      (|SetGuideIdx j)))
  (bind a (Math|Float|Max(Float) 0.0 (Math|Float|Min(Float) 1.0 (/ (- Speed (+ {f(SPEED0)} (* {f(SPEED_STEP)} (Math|Conversions|ToFloat(Integer) (|GetGuideIdx))))) {f(SPEED_STEP)}))))
  (bind e0 (Utilities|Array|Get(acopy) (|GetGuideEnds) (|GetGuideIdx)))
  (bind e1 (Utilities|Array|Get(acopy) (|GetGuideEnds) (+ (|GetGuideIdx) 1)))
  (bind ends (select (< e0 e1) e0 e1))
  (bind last (select (< (|GetGuideFieldSteps) ends) (|GetGuideFieldSteps) ends))
  (|SetGuideStop false)
  (for k (range (+ last 1))
    (if (not (|GetGuideStop))
      (bind p0 (Utilities|Array|Get(acopy) (|GetGuideTable) (+ (* (|GetGuideIdx) {PER_SPEED}) k)))
      (bind p1 (Utilities|Array|Get(acopy) (|GetGuideTable) (+ (* (+ (|GetGuideIdx) 1) {PER_SPEED}) k)))
      (bind p (+ p0 (* (- p1 p0) a)))
      (if (< (.x p) {f(BAND_LINE_X)})
        ; Over the band line: the tip goes exactly on it, between the last point and this one.
        (bind t (/ (- (|GetGuideLX) {f(BAND_LINE_X)}) (Math|Float|Max(Float) 0.001 (- (|GetGuideLX) (.x p)))))
        (Utilities|Array|Add (|GetGuidePoints) (Math|Vector|MakeVector {f(BAND_LINE_X)} (+ (|GetGuideLY) (* (- (.y p) (|GetGuideLY)) t)) {f(Z)}))
        (|SetGuideStop true)
        (else
          (Utilities|Array|Add (|GetGuidePoints) p)
          (|SetGuideLX (.x p))
          (|SetGuideLY (.y p))))
      (if (or (< (.y p) {f(LEFT_LIMIT)}) (< (.x p) {f(BOTTOM_LIMIT)}))
        (|SetGuideStop true))
      (for o (|GetGuideObs)
        (bind dx (- (.x p) (.x o)))
        (bind dy (- (.y p) (.y o)))
        (if (< (+ (* dx dx) (* dy dy)) {f(HIT_RADIUS * HIT_RADIUS)})
          (|SetGuideStop true))))))
"""

GUIDE_LINE = """
(fn GuideLine (X1 Y1 X2 Y2 Along)
  (bind s (|GetScaleHUD))
  (bind fade (Math|Float|Min(Float) 1.0 (/ Along (* 36.0 s))))
  (bind a (* (* (|GetGuideAlpha) fade) (select (|GetCharging) 1.0 0.7)))
  (bind (cr cg cb ca) (Utilities|Struct|BreakLinearColor (|GetGuideColor)))
  (bind w (* (|GetGuideThickness) s))
  (bind o (* 1.5 s))
  (HUD|DrawLine :StartScreenX (+ X1 o) :StartScreenY (+ Y1 o) :EndScreenX (+ X2 o) :EndScreenY (+ Y2 o) :LineColor (Math|Color|MakeColor 0.03 0.012 0.006 (* a 0.7)) :LineThickness w)
  (HUD|DrawLine :StartScreenX X1 :StartScreenY Y1 :EndScreenX X2 :EndScreenY Y2 :LineColor (Math|Color|MakeColor cr cg cb a) :LineThickness w))
"""

DASH_SEGMENT = """
(fn DashSegment (AX AY BX BY Period Dash Flow)
  (bind dx (- BX AX))
  (bind dy (- BY AY))
  (bind len (Math|Float|Sqrt (+ (* dx dx) (* dy dy))))
  ; A point behind the camera projects far off screen: skip such a segment rather than dash thousands of px.
  (if (and (> len 0.5) (< len 2500.0))
    (|SetGuideDirX (/ dx len))
    (|SetGuideDirY (/ dy len))
    (|SetGuideCursor 0.0)
    (|SetGuideIter 0)
    (while (and (< (|GetGuideCursor) len) (< (|GetGuideIter) 400))
      (|SetGuideIter (+ (|GetGuideIter) 1))
      (bind d (+ (|GetGuideDist) (|GetGuideCursor)))
      (bind phase (Math|Float|%(Float) (- (+ d Period) Flow) Period))
      (if (< phase (- Dash 0.01))
        (bind e (Math|Float|Min(Float) len (+ (|GetGuideCursor) (- Dash phase))))
        (|GuideLine :X1 (+ AX (* (|GetGuideDirX) (|GetGuideCursor))) :Y1 (+ AY (* (|GetGuideDirY) (|GetGuideCursor))) :X2 (+ AX (* (|GetGuideDirX) e)) :Y2 (+ AY (* (|GetGuideDirY) e)) :Along d)
        (|SetGuideCursor e)
        (else
          (|SetGuideCursor (Math|Float|Min(Float) len (+ (|GetGuideCursor) (Math|Float|Max(Float) 0.01 (- Period phase))))))))
    (|SetGuideDist (+ (|GetGuideDist) len))))
"""

PAINT = """
(fn PaintLaunchGuide ()
  (bind n (Utilities|Array|Length (|GetGuidePoints)))
  (if (> n 1)
    (bind xf (Transformation|GetActorTransform :self (|GetTable)))
    (bind s (|GetScaleHUD))
    (bind period (* (+ (|GetGuideDash) (|GetGuideGap)) s))
    (bind dash (* (|GetGuideDash) s))
    (bind flow (Math|Float|%(Float) (* (Utilities|Time|GetGameTimeinSeconds) (* (|GetGuideFlow) s)) period))
    (|SetGuideDist 0.0)
    (|SetGuideHasPrev false)
    (for i (range n)
      (bind pt (Utilities|Array|Get(acopy) (|GetGuidePoints) i))
      (if (< (.z pt) -100.0)
        (|SetGuideHasPrev false)
        (else
          ; HUD|Project gives canvas coordinates. The player controller's world-to-screen gives viewport ones, which
          ; are off by the black bars when the view keeps its aspect ratio (28 px in editor play).
          (bind scr (HUD|Project :Location (Math|Transform|TransformLocation xf pt) :bClampToZeroPlane false))
          (bind sx (.x scr))
          (bind sy (.y scr))
          (if (|GetGuideHasPrev)
            (|DashSegment :AX (|GetGuidePX) :AY (|GetGuidePY) :BX sx :BY sy :Period period :Dash dash :Flow flow))
          (|SetGuidePX sx)
          (|SetGuidePY sy)
          (|SetGuideHasPrev true))))
    (bind tx (|GetGuidePX))
    (bind ty (|GetGuidePY))
    (bind bx (- 0.0 (|GetGuideDirX)))
    (bind by (- 0.0 (|GetGuideDirY)))
    (bind L (* 13.0 s))
    (|GuideLine :X1 tx :Y1 ty :X2 (+ tx (* L (- (* bx 0.866) (* by 0.5)))) :Y2 (+ ty (* L (+ (* bx 0.5) (* by 0.866)))) :Along 999.0)
    (|GuideLine :X1 tx :Y1 ty :X2 (+ tx (* L (+ (* bx 0.866) (* by 0.5)))) :Y2 (+ ty (* L (- (* by 0.866) (* bx 0.5)))) :Along 999.0)))
"""

# Exit speed exactly as ApplyLaunchPower (apply_launch_power.py) will set it.
DRAW = """
(fn DrawLaunchGuide ()
  ; Only while Space is held, and not while the camera glides in or looks around (parts of the path can sit behind it).
  (if (and (and (and (== (|GetPhase) 0) (== (|GetStation) 1)) (|GetCharging)) (not (or (|GetBlending) (|GetLooking))))
    (bind table (|GetTable))
    (bind rules (|GetRules))
    (if (> (|GetMaxBalls :self rules) (|GetBallsUsed :self rules))
      ; Exit speed exactly as ArmLaunchPower works it out: PowerToExit at Power, x WeightSpeedScale.
      (bind raw (Math|Float|Max(Float) 0.0 (Math|Float|Min(Float) 1.0 (|GetPower))))
      (bind n (Utilities|Array|Length (|GetPowerToExit :self table)))
      (bind f (* raw (Math|Conversions|ToFloat(Integer) (- n 1))))
      (|SetGuideExitIdx 0)
      (for j (range (- n 1))
        (if (>= f (Math|Conversions|ToFloat(Integer) j))
          (|SetGuideExitIdx j)))
      (bind e0 (Utilities|Array|Get(acopy) (|GetPowerToExit :self table) (|GetGuideExitIdx)))
      (bind e1 (Utilities|Array|Get(acopy) (|GetPowerToExit :self table) (+ (|GetGuideExitIdx) 1)))
      (bind a (Math|Float|Min(Float) 1.0 (- f (Math|Conversions|ToFloat(Integer) (|GetGuideExitIdx)))))
      (|BuildLaunchGuide :Speed (* (+ e0 (* (- e1 e0) a)) (|GetWeightSpeedScale :self table)))
      (|PaintLaunchGuide))))
"""

with helpers['toolset_registry'].tool_raising_exceptions():
    add_variables(HUD, [
        ('GuidePoints', 'Vector', ContainerType.ARRAY), ('GuideObs', 'Vector', ContainerType.ARRAY),
        ('GuideTable', 'Vector', ContainerType.ARRAY), ('GuideEnds', 'int', ContainerType.ARRAY), ('GuideIdx', 'int', None),
        ('GuideStop', 'bool', None), ('GuideHasPrev', 'bool', None), ('GuideLX', 'float', None), ('GuideLY', 'float', None),
        ('GuideExitIdx', 'int', None),
        ('GuideDist', 'float', None), ('GuideCursor', 'float', None), ('GuidePX', 'float', None), ('GuidePY', 'float', None),
        ('GuideDirX', 'float', None), ('GuideDirY', 'float', None), ('GuideIter', 'int', None),
        ('GuideColor', 'LinearColor', None), ('GuideAlpha', 'float', None), ('GuideThickness', 'float', None),
        ('GuideDash', 'float', None), ('GuideGap', 'float', None), ('GuideFlow', 'float', None), ('GuideFieldSteps', 'int', None),
    ], 'Launch Guide')
    BT.compile_blueprint(HUD)
    function(HUD, 'GuideLane', [('ToX', 'float')], GUIDE_LANE)
    function(HUD, 'GuideLine', [(n, 'float') for n in ('X1', 'Y1', 'X2', 'Y2', 'Along')], GUIDE_LINE)
    BT.compile_blueprint(HUD)
    function(HUD, 'DashSegment', [(n, 'float') for n in ('AX', 'AY', 'BX', 'BY', 'Period', 'Dash', 'Flow')], DASH_SEGMENT)
    function(HUD, 'BuildLaunchGuide', [('Speed', 'float')], BUILD)
    BT.compile_blueprint(HUD)
    function(HUD, 'PaintLaunchGuide', [], PAINT)
    BT.compile_blueprint(HUD)
    function(HUD, 'DrawLaunchGuide', [], DRAW)
    BT.compile_blueprint(HUD)
    insert_call(HUD, 'DrawTable', is_entry, 'DrawLaunchGuide')  # first, so the panels draw over it
    BT.compile_blueprint(HUD, warnings_as_errors=True)
    cdo = BT.get_default_object(HUD)
    for name, value in (('GuideColor', u.LinearColor(*GUIDE_COLOR)), ('GuideAlpha', GUIDE_ALPHA),
                        ('GuideThickness', GUIDE_THICKNESS), ('GuideDash', GUIDE_DASH), ('GuideGap', GUIDE_GAP),
                        ('GuideFlow', GUIDE_FLOW), ('GuideFieldSteps', GUIDE_FIELD_STEPS),
                        ('GuideTable', table_points), ('GuideEnds', table_ends)):
        cdo.set_editor_property(name, value)
    assert u.EditorAssetLibrary.save_loaded_asset(HUD, False)
    BT.get_default_object(TABLE).set_editor_property('PowerToExit', power_to_exit)
    assert u.EditorAssetLibrary.save_loaded_asset(TABLE, False)
u.log(f'BUMPIT_LAUNCH_GUIDE_APPLIED speeds={len(SPEEDS)} points={len(table_points)} power_to_exit={power_to_exit}')
