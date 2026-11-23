"""Combo points, and a live score that swells and shakes as it climbs. Run after apply_combo_hud.py and
apply_launch_power.py. Safe to run repeatedly. Run with the editor closed:
UnrealEditor-Cmd.exe Bumpit.uproject -run=pythonscript -script=<this file> -unattended -nullrhi -culture=en

Combo points (BP_PinballTable): every counted bumper hit (the ball, the split ball, copies) adds
    ComboPointStep x (combo - 1) x bumper multiplier          (10 per step; the bumper-boost ball doubles it)
so the 2nd hit of a chain is worth +10, the 10th +90, the 20th +190, the 50th +490, with no cap. ComboPoints is
cleared at each launch and Settle adds it to the round's points on top of the balls' own scores (it is not
multiplied by the goal, so it counts even when a ball ends in the x0 goal or is lost).

Live score (BP_BumpitHUD.DrawLiveScore): the box stays as it is (470, 40, 180 x 72); the number in it now shows
the balls' points plus ComboPoints, and it jumps at milestones that double: ScoreMilestoneBase x 2^k =
200, 400, 800, 1600, 3200, 6400, 12800, 25600 (ScoreMilestoneCount 8; past the last one the number stays as it is).
    every milestone passed      the number jumps a size step (ScoreStepSize 0.75 on top of 2.4) and pops for
                                0.35 s; between milestones it creeps up only a quarter step, so the jumps stand out
    from the 2nd one (400)      it shakes: ScoreShakeBase px (HUD units) x (milestones past 400 + 1)^1.3, a fresh
                                random offset every frame plus a wobble
    around 800 - 1600           the number outgrows the box and spills out of it
The colour heats from gold to orange to red-white with the milestones.
"""
import sys
from pathlib import Path

import unreal as u

sys.path.insert(0, str(Path(__file__).parent))
helpers = {}
source = (Path(__file__).parent / 'apply_gimmicks.py').read_text(encoding='utf-8-sig')
exec(compile(source.split('with toolset_registry.tool_raising_exceptions():')[0], '<gimmick helpers>', 'exec'), helpers)
function, add_variables, insert_call, is_entry = helpers['function'], helpers['add_variables'], helpers['insert_call'], helpers['is_entry']
BT, infos_of, pin = helpers['BT'], helpers['infos_of'], helpers['pin']
from blueprint_graph import Graph, put

ROOT = '/Game/Bumpit/Blueprints/'
TABLE, HUD, RULES = (u.load_asset(ROOT + n) for n in ('BP_PinballTable', 'BP_BumpitHUD', 'BP_RoundRules'))
helpers['BPS'].update(table=TABLE, hud=HUD, rules=RULES)

COMBO_POINT_STEP = 10
SCORE_MILESTONE_BASE = 200.0   # milestones: 200, 400, 800, 1600, ...
SCORE_MILESTONE_COUNT = 8      # ... up to 25600
SCORE_STEP_SIZE = 0.75         # text size added at each milestone
SCORE_SHAKE_FROM_STEP = 2      # shaking starts at the 2nd milestone (400)
SCORE_SHAKE_BASE = 2.5         # px of shake at 400

ADD_COMBO = """
(fn AddComboPoints ()
  (bind step (* (|GetComboPointStep) (- (|GetBumperComboCount) 1)))
  (bind rules (|GetActiveRules))
  (Utilities|IsValid rules
    (:"Is Valid"
      (|SetComboPoints (+ (|GetComboPoints) (* step (|BallScoreMultiplier :self rules)))))
    (:"Is Not Valid"
      (|SetComboPoints (+ (|GetComboPoints) step)))))
"""

RESET_COMBO = """
(fn ResetComboPoints ()
  (|SetComboPoints 0))
"""

LIVE = """
(fn DrawLiveScore ()
  (if (== (|GetPhase) 1)
    (bind (balls pulse) (|LiveBallScore :self (|GetRules)))
    (bind score (+ balls (|GetComboPoints :self (|GetTable))))
    (bind v (Math|Conversions|ToFloat(Integer) score))
    (bind s (|GetScaleHUD))
    (bind t (Utilities|Time|GetGameTimeinSeconds))
    ; milestones ScoreMilestoneBase x 2^k: how many are passed, and the last one passed
    (|SetScoreStepNow 0)
    (|SetScoreStepLow (|GetScoreMilestoneBase))
    (for i (range (|GetScoreMilestoneCount))
      (bind m (* (|GetScoreMilestoneBase) (Math|Float|Power 2.0 (Math|Conversions|ToFloat(Integer) i))))
      (if (>= v m)
        (|SetScoreStepNow (+ i 1))
        (|SetScoreStepLow m)))
    (if (> (|GetScoreStepNow) (|GetScoreStepShown))
      (|SetScorePopTime t))
    (|SetScoreStepShown (|GetScoreStepNow))
    (bind steps (Math|Conversions|ToFloat(Integer) (|GetScoreStepNow)))
    ; 0..1 on the way to the next milestone (none past the last one)
    (bind frac (select (>= (|GetScoreStepNow) (|GetScoreMilestoneCount)) 0.0 (select (> (|GetScoreStepNow) 0) (Math|Float|Max(Float) 0.0 (Math|Float|Min(Float) 1.0 (- (/ v (|GetScoreStepLow)) 1.0))) (Math|Float|Max(Float) 0.0 (Math|Float|Min(Float) 1.0 (/ v (|GetScoreMilestoneBase)))))))
    (bind pop (Math|Float|Max(Float) 0.0 (- 1.0 (/ (- t (|GetScorePopTime)) 0.35))))
    (bind size (+ (+ (+ 2.4 (* (|GetScoreStepSize) (+ steps (* 0.25 frac)))) (* pulse 0.7)) (* pop 1.6)))
    (bind shakeSteps (select (>= (|GetScoreStepNow) (|GetScoreShakeFromStep)) (+ (- steps (Math|Conversions|ToFloat(Integer) (|GetScoreShakeFromStep))) (+ 1.0 (* 0.25 frac))) 0.0))
    (bind amp (+ (+ (* (|GetScoreShakeBase) (Math|Float|Power (Math|Float|Max(Float) 0.0001 shakeSteps) 1.3)) (* pulse 2.0)) (* pop 12.0)))
    (bind jx (+ (Math|Random|RandomFloatInRange (- 0.0 amp) amp) (* (* amp 0.5) (Math|Trig|Sin(Radians) (* t 47.0)))))
    (bind jy (+ (Math|Random|RandomFloatInRange (- 0.0 amp) amp) (* (* amp 0.5) (Math|Trig|Sin(Radians) (* t 39.0)))))
    (bind heat (Math|Float|Min(Float) 1.0 (/ (+ steps (* 0.25 frac)) 7.0)))
    (bind hot (Math|Color|Lerp(LinearColor) "(R=1.0,G=0.42,B=0.16,A=1)" "(R=1.0,G=0.93,B=0.82,A=1)" (Math|Float|Max(Float) 0.0 (- (* heat 2.0) 1.0))))
    (bind col (Math|Color|Lerp(LinearColor) (Math|Color|Lerp(LinearColor) "(R=0.92,G=0.62,B=0.22,A=1)" "(R=1.0,G=0.42,B=0.16,A=1)" (Math|Float|Min(Float) 1.0 (* heat 2.0))) hot (Math|Float|Max(Float) 0.0 (- (* heat 2.0) 1.0))))
    (bind text (Utilities|String|BuildString(Integer) "" "" score))
    (bind (tw th) (HUD|GetTextSize :Text text :Font "/Game/Bumpit/UI/F_Galmuri.F_Galmuri" :Scale (* size s)))
    (bind x (+ (- 560.0 (/ tw (* 2.0 s))) jx))
    (bind y (+ (- 76.0 (/ th (* 2.0 s))) jy))
    ; HUD functions take named pins: headless-built calls carry a self pin first, so positions would be one off
    (|Panel :X 470.0 :Y 40.0 :W 180.0 :H 72.0 :Tint "(R=0.016,G=0.010,B=0.008,A=0.86)")
    (|Frame :X 470.0 :Y 40.0 :W 180.0 :H 72.0 :Line 2.0 :Tint "(R=0.30,G=0.15,B=0.07,A=1)")
    (|Label :Caption text :X (+ x (* 0.3 size)) :Y (+ y (* 0.3 size)) :Size size :Tint "(R=0.06,G=0.018,B=0.008,A=0.8)")
    (|Label :Caption text :X x :Y y :Size size :Tint (Math|Color|Lerp(LinearColor) col "(R=1.0,G=1.0,B=1.0,A=1)" (* pulse 0.6)))))
"""

def add_combo_to_settle(hud):
    """Settle: the round total (balls + split + copies, an int64 sum) gets + ComboPoints; everything that read the
    old total (last points, total points, credits, RecordBall) reads the new one."""
    g = Graph(hud, 'Settle')
    infos = [BT._get_node_info(n) for n in g.nodes.values()]
    adds = [i for i in infos if i.type_id == 'Math|Integer64|integer64+integer64']
    for i in adds:  # already done?
        for p in i.input_pins:
            for c in p.connected_pins:
                src = BT._get_node_info(c.node)
                if any(BT._get_node_info(cc.node).type_id == '|GetComboPoints' for q in src.input_pins for cc in q.connected_pins):
                    return
    total = next(i for i in adds if any(BT._get_node_info(c.node).type_id == '|GetCopyPoints'
                                        for p in i.input_pins for c in p.connected_pins))
    out = next(p for p in total.output_pins if p.type_id != 'Exec')
    consumers = [BT._resolve_pin(c) for c in out.connected_pins]
    combo = g.e.add_get_member_variable_node('ComboPoints', TABLE.generated_class().get_path_name())
    put(combo.find_input_pin('self'), g.get('Table'))
    combo64 = g.call('/Script/Engine.KismetMathLibrary:Conv_IntToInt64', InInt=combo.find_output_pin('ComboPoints')).find_output_pin('ReturnValue')
    new_total = g.call('/Script/Engine.KismetMathLibrary:Add_Int64Int64', A=BT._resolve_pin(out.pin_id), B=combo64).find_output_pin('ReturnValue')
    for c in consumers:
        put(c, new_total)


with helpers['toolset_registry'].tool_raising_exceptions():
    add_variables(TABLE, [('ComboPoints', 'int', None), ('ComboPointStep', 'int', None)], 'Combo Score')
    BT.compile_blueprint(TABLE)
    function(TABLE, 'AddComboPoints', [], ADD_COMBO)
    function(TABLE, 'ResetComboPoints', [], RESET_COMBO)
    BT.compile_blueprint(TABLE)
    insert_call(TABLE, 'PlayBumperNote', lambda i: i.type_id == '|SetBumperComboCount', 'AddComboPoints')
    insert_call(TABLE, 'Launch', is_entry, 'ResetComboPoints')
    BT.compile_blueprint(TABLE, warnings_as_errors=True)
    BT.get_default_object(TABLE).set_editor_property('ComboPointStep', COMBO_POINT_STEP)
    assert u.EditorAssetLibrary.save_loaded_asset(TABLE, False)

    add_variables(HUD, [('ScoreMilestoneBase', 'float', None), ('ScoreMilestoneCount', 'int', None), ('ScoreStepSize', 'float', None),
                        ('ScoreShakeFromStep', 'int', None), ('ScoreShakeBase', 'float', None),
                        ('ScoreStepNow', 'int', None), ('ScoreStepLow', 'float', None),
                        ('ScoreStepShown', 'int', None), ('ScorePopTime', 'float', None)],
                  'Live Score')
    BT.compile_blueprint(HUD)
    function(HUD, 'DrawLiveScore', [], LIVE)
    add_combo_to_settle(HUD)
    BT.compile_blueprint(HUD, warnings_as_errors=True)
    cdo = BT.get_default_object(HUD)
    for name, value in (('ScoreMilestoneBase', SCORE_MILESTONE_BASE), ('ScoreMilestoneCount', SCORE_MILESTONE_COUNT),
                        ('ScoreStepSize', SCORE_STEP_SIZE),
                        ('ScoreShakeFromStep', SCORE_SHAKE_FROM_STEP), ('ScoreShakeBase', SCORE_SHAKE_BASE),
                        ('ScorePopTime', -10.0)):
        cdo.set_editor_property(name, value)
    assert u.EditorAssetLibrary.save_loaded_asset(HUD, False)
u.log('BUMPIT_SCORE_COMBO_APPLIED')
