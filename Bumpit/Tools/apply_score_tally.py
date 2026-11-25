"""Scoreboard tally: after each ball the board in the workshop (BP_BumpitShow) plays the points out step by step.
Safe to run repeatedly. Run after apply_score_combo.py, with the editor closed:
UnrealEditor-Cmd.exe Bumpit.uproject -run=pythonscript -script=<this file> -unattended -nullrhi -culture=en

Scoring (BP_BumpitHUD.Settle): the goal multiplier comes last. The ball's points are
    (base + combo) x goal        base = 100 + bumper hits x 25 (x2 for the bumper-boost ball), combo = ComboPoints
so a ball in the x0 goal, or a lost ball, scores 0 however long its combo was (BP_RoundRules.ScoreCombo).
The split ball and copies keep their own goals and are added after that.

Idle, the board shows only the target and the total ("목표", "총점").
When a ball is settled (BP_BumpitHUD.Settle -> StartScoreTally -> BP_BumpitShow.StartTally) it clears and plays:
  0  "획득": the ball's base points slam in                                                         TimeBase
  1  "콤보 +N": the combo counts onto them (only if there is one)                                   TimeAdd
  2  the goal multiplier slams in, "x5", over the sum (pocket sound x1/x2/x5/x10, drain for x0;
     x2 / x5 / x10 shake the camera, harder the bigger)                                              TimeMult
  3  the number rushes up to (base + combo) x goal (down to 0 for x0), ticking                     TimeCountMin-Max
  4  "최종": it lands with a slam; the camera shakes by how big it is                                TimeLand
  5  "추가 공 +N": the split ball and copies' points count on (only if there are any)              TimeAdd
  6  "총점": the total counts from the old total to the new one                                    TimeTotal
then it holds a moment (TimeHold) and goes back to target / total.
Milestones double from TallyMilestoneBase: 200, 400, 800, ... 25600. Each one the count passes pops the number, plays
the milestone sound and, from 400 up, shakes the camera (the combo camera shakes: 400 the light one, 800 T1,
1600 T2, 3200 T3, 6400 and up T4 and harder still). The number grows a step at each milestone and shakes in place
from 400 on, more with every milestone (TallyTextShake); from 3200 the board glows and pulses.
The stage's pass / fail banner (BP_RoundRules.FinalScoreSeconds) waits for the tally.
"""
import sys
from pathlib import Path

import unreal as u

sys.path.insert(0, str(Path(__file__).parent))
helpers = {}
source = (Path(__file__).parent / 'apply_gimmicks.py').read_text(encoding='utf-8-sig')
exec(compile(source.split('with toolset_registry.tool_raising_exceptions():')[0], '<gimmick helpers>', 'exec'), helpers)
function, add_variables, insert_call, is_entry = helpers['function'], helpers['add_variables'], helpers['insert_call'], helpers['is_entry']
BT = helpers['BT']
from blueprint_graph import Graph, put

ROOT = '/Game/Bumpit/Blueprints/'
TABLE, HUD, RULES, SHOW = (u.load_asset(ROOT + n) for n in ('BP_PinballTable', 'BP_BumpitHUD', 'BP_RoundRules', 'BP_BumpitShow'))
helpers['BPS'].update(table=TABLE, hud=HUD, rules=RULES, show=SHOW)

TIMES = {'TimeBase': 0.7, 'TimeMult': 0.8, 'TimeCountMin': 0.5, 'TimeCountMax': 2.0, 'TimeLand': 0.7, 'TimeAdd': 0.65,
         'TimeTotal': 0.9, 'TimeHold': 0.4}
LOOKS = {'TallyMilestoneBase': 200.0, 'TallyTextShake': 1.6}   # plus TallyMilestoneCount 8 (int)
A = '/Game/Bumpit/Audio/Workshop/'
SND = {k: f'{A}{v}.{v}' for k, v in (('slam', 'S_36_Banner'), ('x10', 'S_04_PocketX10'), ('x5', 'S_04_PocketX5'),
                                       ('x2', 'S_04_PocketX2'), ('x1', 'S_04_PocketX1'), ('x0', 'S_05_Drain'),
                                       ('tick', 'S_32_ScoreTick'), ('add', 'S_13_Milestone'), ('total', 'S_11_Overdrive'))}
FONT = '/Game/Bumpit/UI/F_Galmuri.F_Galmuri'
RED, GREEN = '(R=0.42,G=0.03,B=0.02,A=1)', '(R=0.03,G=0.30,B=0.07,A=1)'
CREAM, GOLD = '(R=1,G=0.86,B=0.62,A=1)', '(R=1,G=0.72,B=0.12,A=1)'
ORANGE, WHITE_HOT, GLOW = '(R=1.0,G=0.42,B=0.16,A=1)', '(R=1.0,G=0.97,B=0.9,A=1)', '(R=0.85,G=0.28,B=0.05,A=1)'
GREY = '(R=0.45,G=0.40,B=0.38,A=1)'
SHAKES = ['/Game/Bumpit/Blueprints/' + n + '.' + n + '_C' for n in
          ('BP_BumperCameraShake', 'BP_BumperCameraShake_T1', 'BP_BumperCameraShake_T2', 'BP_BumperCameraShake_T3',
           'BP_BumperCameraShake_T4')]

WRITE_AT = f"""
(fn WriteAt (Canvas Caption X Y Size Tint)
  (Canvas|DrawText :self Canvas :RenderFont "{FONT}" :RenderText Caption :ScreenPosition (Math|Vector2D|MakeVector2D X Y) :Scale (Math|Vector2D|MakeVector2D Size Size) :RenderColor Tint :Kerning 0.0 :ShadowColor "(R=0.05,G=0.005,B=0.002,A=0.85)" :ShadowOffset (Math|Vector2D|MakeVector2D (* Size 1.2) (* Size 1.2)) :bCentreX true :bCentreY true))
"""

# how many milestones (TallyMilestoneBase x 2^k) Value has passed -> TallyStepCalc, 0..1 on the way to the next -> TallyStepFrac
COUNT_STEPS = """
(fn CountSteps (Value)
  (|SetTallyStepCalc 0)
  (|SetTallyStepLow (|GetTallyMilestoneBase))
  (for i (range (|GetTallyMilestoneCount))
    (bind m (* (|GetTallyMilestoneBase) (Math|Float|Power 2.0 (Math|Conversions|ToFloat(Integer) i))))
    (if (>= Value m)
      (|SetTallyStepCalc (+ i 1))
      (|SetTallyStepLow m)))
  (|SetTallyStepFrac (select (>= (|GetTallyStepCalc) (|GetTallyMilestoneCount)) 0.0 (select (> (|GetTallyStepCalc) 0) (Math|Float|Max(Float) 0.0 (Math|Float|Min(Float) 1.0 (- (/ Value (|GetTallyStepLow)) 1.0))) (Math|Float|Max(Float) 0.0 (Math|Float|Min(Float) 1.0 (/ Value (|GetTallyMilestoneBase))))))))
"""

# camera shake for a milestone count: 2 (400) the light combo shake, 3 T1, 4 T2, 5 T3, 6+ T4 and harder per step
CASES = '\n'.join(f'      (:{i} (CameraShakes|StartCameraShake :self cam :ShakeClass "{c}" :Scale scale))' for i, c in enumerate(SHAKES))
TALLY_SHAKE = f"""
(fn TallyShake (Steps Boost)
  (bind tier (select (>= Steps 6) 4 (select (>= Steps 5) 3 (select (>= Steps 4) 2 (select (>= Steps 3) 1 (select (>= Steps 2) 0 -1))))))
  (bind scale (* Boost (+ 1.0 (* 0.5 (Math|Conversions|ToFloat(Integer) (select (> Steps 6) (- Steps 6) 0))))))
  (if (>= tier 0)
    (bind cam (Game|GetPlayerCameraManager :PlayerIndex 0))
    (switch int tier
{CASES})))
"""

REDRAW = f"""
(fn Redraw ()
  (bind banner (|GetBanner))
  (bind hasBanner (not (Utilities|String|IsEmpty banner)))
  (Rendering|ClearRenderTarget2D :TextureRenderTarget (|GetScreenImage) :ClearColor (|PickColor :UseFirst (and hasBanner (|GetBannerGreen)) :First "{GREEN}" :Second "{RED}"))
  (bind (canvas size ctx) (Rendering|BeginDrawCanvasToRenderTarget :TextureRenderTarget (|GetScreenImage)))
  (if hasBanner
    (|Write :Canvas canvas :Caption banner :OffsetY 0.0 :Size 6.0 :Tint "{CREAM}")
    (else
      (|Write :Canvas canvas :Caption (Utilities|String|BuildString(Integer) "" "목표  " (|GetShownTarget)) :OffsetY -32.0 :Size 3.4 :Tint "{CREAM}")
      (|Write :Canvas canvas :Caption (Utilities|String|BuildString(Integer) "" "총점  " (|GetShownRound)) :OffsetY 34.0 :Size 3.4 :Tint (|PickColor :UseFirst (>= (|GetShownRound) (|GetShownTarget)) :First "{GOLD}" :Second "{CREAM}"))))
  (Rendering|EndDrawCanvasToRenderTarget :Context ctx))
"""

SHOW_SCORE = """
(fn ShowScore (BallPoints Target RoundPoints)
  (|SetShownBall BallPoints)
  (|SetPendingTarget Target)
  (|SetPendingRound RoundPoints)
  (|SetBanner "")
  ; while a tally runs it brings the new total in itself
  (if (== (|GetTallyStage) 0)
    (|SetShownTarget Target)
    (|SetShownRound RoundPoints)
    (|Redraw)))
"""

SHOW_BANNER = """
(fn ShowBanner (Caption Green)
  (|SetBanner Caption)
  (|SetBannerGreen Green)
  (if (== (|GetTallyStage) 0)
    (|Redraw)))
"""

START = """
(fn StartTally (Base Mult Extra Combo From To Target)
  (|SetTallyBase Base)
  (|SetTallyMult Mult)
  (|SetTallyFinal (* (+ Base Combo) Mult))
  (|SetTallyExtra Extra)
  (|SetTallyCombo Combo)
  (|SetTallyFrom From)
  (|SetTallyTo To)
  (|SetPendingTarget Target)
  (|SetPendingRound To)
  (|SetBanner "")
  (bind sub (+ Base Combo))
  (bind diff (Math|Float|Absolute(Float) (Math|Conversions|ToFloat(Integer) (- (* sub Mult) sub))))
  (|SetTallyT1 (|GetTimeBase))
  (|SetTallyT2 (+ (|GetTallyT1) (select (> Combo 0) (|GetTimeAdd) 0.0)))
  (|SetTallyT3 (+ (|GetTallyT2) (|GetTimeMult)))
  (|SetTallyT4 (+ (|GetTallyT3) (Math|Float|Min(Float) (|GetTimeCountMax) (+ (|GetTimeCountMin) (* 0.0005 diff)))))
  (|SetTallyT5 (+ (|GetTallyT4) (|GetTimeLand)))
  (|SetTallyT6 (+ (|GetTallyT5) (select (> Extra 0) (|GetTimeAdd) 0.0)))
  (|SetTallyEnd (+ (|GetTallyT6) (|GetTimeTotal)))
  (|SetTallyLength (+ (|GetTallyEnd) (|GetTimeHold)))
  (|SetTallyStepShown 0)
  (|SetTallyPopTime -10.0)
  (|SetTallyStart (Utilities|Time|GetGameTimeinSeconds))
  (|SetTallyPhase -1)
  (|SetTallyStage 1))
"""


def snd(key, vol=0.85):
    return f'(Audio|PlaySound2D :Sound "{SND[key]}" :VolumeMultiplier {vol})'


F = 'Math|Conversions|ToFloat(Integer)'
TICK = f"""
(fn TickTally ()
  (if (== (|GetTallyStage) 1)
    (bind t (- (Utilities|Time|GetGameTimeinSeconds) (|GetTallyStart)))
    ; 0 base, 1 combo, 2 multiplier, 3 count, 4 land, 5 extra balls, 6 total, 7 hold, 8 done
    (|SetTallyNow 8)
    (if (< t (|GetTallyLength)) (|SetTallyNow 7))
    (if (< t (|GetTallyEnd)) (|SetTallyNow 6))
    (if (< t (|GetTallyT6)) (|SetTallyNow 5))
    (if (< t (|GetTallyT5)) (|SetTallyNow 4))
    (if (< t (|GetTallyT4)) (|SetTallyNow 3))
    (if (< t (|GetTallyT3)) (|SetTallyNow 2))
    (if (< t (|GetTallyT2)) (|SetTallyNow 1))
    (if (< t (|GetTallyT1)) (|SetTallyNow 0))
    (bind now (|GetTallyNow))
    (bind mult (|GetTallyMult))
    (if (!= now (|GetTallyPhase))
      (|SetTallyPhase now)
      (|SetTallyNextTick t)
      (|SetTallyPopTime t)
      (if (== now 0) {snd('slam')})
      (if (or (== now 1) (== now 5)) {snd('add')})
      (if (== now 2)
        (if (>= mult 10) {snd('x10', 1.0)}
          (elif (>= mult 5) {snd('x5', 1.0)}
            (elif (>= mult 2) {snd('x2', 1.0)}
              (elif (>= mult 1) {snd('x1', 1.0)}
                (else {snd('x0', 1.0)})))))
        (|TallyShake :Steps (select (>= mult 10) 4 (select (>= mult 5) 3 (select (>= mult 2) 2 0))) :Boost 1.0))
      (if (== now 4)
        (|CountSteps :Value ({F} (|GetTallyFinal)))
        (if (> (|GetTallyFinal) 0) {snd('slam', 1.0)})
        (|TallyShake :Steps (|GetTallyStepCalc) :Boost 1.4))
      (if (== now 6) {snd('total')}))
    (if (== now 8)
      (|SetTallyStage 0)
      (|SetShownTarget (|GetPendingTarget))
      (|SetShownRound (|GetPendingRound))
      (|Redraw)
      (else
        ; counting phases tick like a slot machine
        (if (and (or (or (== now 1) (== now 3)) (or (== now 5) (== now 6))) (>= t (|GetTallyNextTick)))
          {snd('tick', 0.55)}
          (|SetTallyNextTick (+ t 0.05)))
        (bind start (select (== now 0) 0.0 (select (== now 1) (|GetTallyT1) (select (== now 2) (|GetTallyT2) (select (== now 3) (|GetTallyT3) (select (== now 4) (|GetTallyT4) (select (== now 5) (|GetTallyT5) (select (== now 6) (|GetTallyT6) (|GetTallyEnd)))))))))
        (bind stop (select (== now 1) (|GetTallyT2) (select (== now 3) (|GetTallyT4) (select (== now 5) (|GetTallyT6) (|GetTallyEnd)))))
        ; the count steps every 0.05 s, in time with the ticks: a slot-machine roll, and each number holds long enough to read
        (bind tq (+ start (* 0.05 ({F} (Math|Float|Round (- (/ (- t start) 0.05) 0.5))))))
        (bind p (Math|Float|Max(Float) 0.0 (Math|Float|Min(Float) 1.0 (/ (- tq start) (Math|Float|Max(Float) 0.01 (- stop start))))))
        (bind e (- 1.0 (* (- 1.0 p) (- 1.0 p))))
        (bind rush (* p p))
        (bind base ({F} (|GetTallyBase)))
        (bind sub (+ base ({F} (|GetTallyCombo))))
        (bind final ({F} (|GetTallyFinal)))
        (bind gross (+ final ({F} (|GetTallyExtra))))
        (bind from ({F} (|GetTallyFrom)))
        (bind to ({F} (|GetTallyTo)))
        (bind v (select (== now 0) base (select (== now 1) (+ base (* (- sub base) e)) (select (== now 2) sub (select (== now 3) (+ sub (* (- final sub) rush))
                  (select (== now 4) final (select (== now 5) (+ final (* (- gross final) e)) (select (== now 6) (+ from (* (- to from) e)) to))))))))
        (bind shown (Math|Float|Round v))
        ; the ball's own points set the heat (in the totals too); every milestone the count passes pops and shakes
        (|CountSteps :Value (select (>= now 6) gross v))
        (if (and (> (|GetTallyStepCalc) (|GetTallyStepShown)) (or (or (== now 1) (== now 3)) (== now 5)))
          (|SetTallyPopTime t)
          {snd('add', 0.9)}
          (|TallyShake :Steps (|GetTallyStepCalc) :Boost 1.0))
        (|SetTallyStepShown (|GetTallyStepCalc))
        (bind steps (+ ({F} (|GetTallyStepCalc)) (* 0.25 (|GetTallyStepFrac))))
        (bind pop (Math|Float|Max(Float) 0.0 (- 1.0 (/ (- t (|GetTallyPopTime)) 0.3))))
        (bind tt (Utilities|Time|GetGameTimeinSeconds))
        ; x0: no fanfare, the number just greys out
        (bind zero (and (>= now 3) (== mult 0)))
        ; the ball's points shake hardest; the total counting after them a third as much, so it stays readable
        (bind amp (select zero (* pop 3.0) (* (select (>= now 6) 0.35 1.0) (+ (* (|GetTallyTextShake) (Math|Float|Power (Math|Float|Max(Float) 0.0001 (- steps 1.0)) 1.3)) (* pop 8.0)))))
        ; smooth fast wobbles, not a fresh random spot each frame: on the in-world board the anti-aliasing smears those
        (bind jx (* amp (+ (* 0.65 (Math|Trig|Sin(Radians) (* tt 61.0))) (* 0.35 (Math|Trig|Sin(Radians) (+ (* tt 97.0) 1.3))))))
        (bind jy (* amp (+ (* 0.65 (Math|Trig|Sin(Radians) (+ (* tt 53.0) 2.1))) (* 0.35 (Math|Trig|Sin(Radians) (+ (* tt 89.0) 0.4))))))
        (bind cap (select (>= v 100000.0) 9.0 (select (>= v 10000.0) 10.5 12.0)))
        (bind big (Math|Float|Min(Float) cap (* (+ 4.2 (* 0.7 steps)) (+ 1.0 (* 0.45 pop)))))
        (bind heat (Math|Float|Min(Float) 1.0 (/ steps 7.0)))
        (bind hot (Math|Color|Lerp(LinearColor) "{ORANGE}" "{WHITE_HOT}" (Math|Float|Max(Float) 0.0 (- (* heat 2.0) 1.0))))
        (bind warm (Math|Color|Lerp(LinearColor) (Math|Color|Lerp(LinearColor) "{CREAM}" "{ORANGE}" (Math|Float|Min(Float) 1.0 (* heat 2.0))) hot (Math|Float|Max(Float) 0.0 (- (* heat 2.0) 1.0))))
        (bind col (Math|Color|Lerp(LinearColor) warm "{GREY}" (select zero 1.0 0.0)))
        (bind glow (* (Math|Float|Max(Float) 0.0 (Math|Float|Min(Float) 1.0 (/ (- steps 4.0) 3.0))) (* 0.5 (+ 1.0 (Math|Trig|Sin(Radians) (* tt 18.0))))))
        (Rendering|ClearRenderTarget2D :TextureRenderTarget (|GetScreenImage) :ClearColor (Math|Color|Lerp(LinearColor) "{RED}" "{GLOW}" (select zero 0.0 (Math|Float|Min(Float) 1.0 (+ (* pop 0.6) (* glow 0.45))))))
        (bind (canvas size ctx) (Rendering|BeginDrawCanvasToRenderTarget :TextureRenderTarget (|GetScreenImage)))
        (if (== now 2)
          (bind mj (* pop 12.0))
          (bind mx (* mj (Math|Trig|Sin(Radians) (* tt 61.0))))
          (bind my (* mj (Math|Trig|Sin(Radians) (+ (* tt 53.0) 2.1))))
          (|WriteAt :Canvas canvas :Caption (Utilities|String|BuildString(Integer) "" "" (+ (|GetTallyBase) (|GetTallyCombo))) :X 288.0 :Y 28.0 :Size 2.4 :Tint "{CREAM}")
          (|WriteAt :Canvas canvas :Caption (Utilities|String|BuildString(Integer) "" "×" mult) :X (+ 288.0 mx) :Y (+ 102.0 my) :Size (* (select (>= mult 10) 7.8 (select (>= mult 5) 7.2 6.4)) (+ 1.0 (* 0.8 pop))) :Tint (Math|Color|Lerp(LinearColor) "{GOLD}" "{GREY}" (select (== mult 0) 1.0 0.0)))
          (else
            (bind caption (select (== now 0) "획득" (select (== now 1) (Utilities|String|BuildString(Integer) "" "콤보  +" (|GetTallyCombo)) (select (== now 3) (Utilities|String|BuildString(Integer) "" "×" mult) (select (== now 4) "최종" (select (== now 5) (Utilities|String|BuildString(Integer) "" "추가 공  +" (|GetTallyExtra)) "총점"))))))
            (|WriteAt :Canvas canvas :Caption caption :X 288.0 :Y 22.0 :Size 2.0 :Tint "{GOLD}")
            (|WriteAt :Canvas canvas :Caption (Utilities|String|BuildString(Integer) "" "" shown) :X (+ 288.0 jx) :Y (+ 106.0 jy) :Size big :Tint col)))
        (Rendering|EndDrawCanvasToRenderTarget :Context ctx)))))
"""

HUD_START = """
(fn StartScoreTally ()
  (bind rules (|GetRules))
  (bind table (|GetTable))
  (bind show (|GetShow :self rules))
  (Utilities|IsValid show
    (:"Is Valid"
      (bind lane (|GetPrimaryLane :self table))
      (bind kind (|GetActiveBallType :self rules))
      (bind bm (select (== kind 1) 2 1))
      (bind base (+ 100 (* (* (|GetHits :self table) bm) 25)))
      (bind laneMult (Utilities|Array|Get(acopy) (|GetMultipliers :self rules) (select (< lane 0) 0 lane)))
      (bind mult (select (< lane 0) 0 (* laneMult (select (== kind 6) 2 1))))
      (bind total (|GetLastPoints))
      (bind combo (|GetComboPoints :self table))
      ; (base + combo) x goal is the ball's own; the rest is the split ball and copies
      (bind extra (- total (* (+ base combo) mult)))
      (bind from (|GetRoundPoints :self rules))
      (|StartTally :self show :Base base :Mult mult :Extra (select (< extra 0) 0 extra) :Combo combo :From from :To (+ from total) :Target (|TargetFor :self rules :Level (|GetCurrentRound :self rules)))
      ; the stage's pass / fail banner waits for the tally
      (|SetFinalScoreSeconds :self rules :FinalScoreSeconds (+ (|GetTallyLength :self show) 0.3)))))
"""


def build_score_combo():
    """BP_RoundRules.ScoreCombo(Combo, Lane): the combo times the ball's goal, 0 for a lost ball."""
    if 'ScoreCombo' in [g.get_name() for g in BT.list_graphs(RULES)]:
        return
    g = Graph(RULES, 'ScoreCombo')
    for name in ('Combo', 'Lane'):
        g.e.add_graph_input_parameter(name, BT._make_variable_type('int'))
    g.e.add_graph_output_parameter('ReturnValue', BT._make_variable_type('int'))
    g.e.set_is_pure_function(True)
    yes, no = g.branch(g.math('Less_IntInt', g.arg('Lane'), 0))
    g.tail = yes
    g.ret(0)
    g.tail = no
    g.ret(g.math('Multiply_IntInt', g.arg('Combo'), g.call('LaneMultiplier', Lane=g.arg('Lane')).find_output_pin('ReturnValue')))


def multiply_combo_in_settle():
    """Settle: the ComboPoints that apply_score_combo.py adds to the total goes through ScoreCombo(ComboPoints, Lane)."""
    g = Graph(HUD, 'Settle')
    infos = [BT._get_node_info(n) for n in g.nodes.values()]
    if any(i.type_id == '|ScoreCombo' for i in infos):
        return
    combo = next(i for i in infos if i.type_id == '|GetComboPoints')
    out = next(p for p in combo.output_pins if p.type_id != 'Exec')
    consumers = [BT._resolve_pin(c) for c in out.connected_pins]
    assert consumers, 'ComboPoints is not used in Settle: run apply_score_combo.py first'
    scored = g.rulecall('ScoreCombo', Combo=BT._resolve_pin(out.pin_id), Lane=g.arg('Lane')).find_output_pin('ReturnValue')
    for c in consumers:
        put(c, scored)


with helpers['toolset_registry'].tool_raising_exceptions():
    build_score_combo()
    BT.compile_blueprint(RULES, warnings_as_errors=True)
    assert u.EditorAssetLibrary.save_loaded_asset(RULES, False)

    ints = ['TallyStage', 'TallyBase', 'TallyMult', 'TallyFinal', 'TallyExtra', 'TallyCombo', 'TallyFrom', 'TallyTo',
            'PendingTarget', 'PendingRound', 'TallyPhase', 'TallyNow', 'TallyStepShown', 'TallyStepCalc', 'TallyMilestoneCount']
    floats = ['TallyStart', 'TallyT1', 'TallyT2', 'TallyT3', 'TallyT4', 'TallyT5', 'TallyT6', 'TallyEnd', 'TallyLength',
              'TallyNextTick', 'TallyPopTime', 'TallyStepLow', 'TallyStepFrac'] + list(TIMES) + list(LOOKS)
    add_variables(SHOW, [(n, 'int', None) for n in ints] + [(n, 'float', None) for n in floats], 'Score Tally')
    BT.compile_blueprint(SHOW)
    function(SHOW, 'WriteAt', [('Canvas', u.Canvas), ('Caption', 'string'), ('X', 'float'), ('Y', 'float'), ('Size', 'float'),
                               ('Tint', 'LinearColor')], WRITE_AT)
    function(SHOW, 'CountSteps', [('Value', 'float')], COUNT_STEPS)
    function(SHOW, 'TallyShake', [('Steps', 'int'), ('Boost', 'float')], TALLY_SHAKE)
    BT.compile_blueprint(SHOW)
    function(SHOW, 'Redraw', [], REDRAW)
    function(SHOW, 'ShowScore', [], SHOW_SCORE)
    function(SHOW, 'ShowBanner', [], SHOW_BANNER)
    function(SHOW, 'StartTally', [(n, 'int') for n in ('Base', 'Mult', 'Extra', 'Combo', 'From', 'To', 'Target')], START)
    BT.compile_blueprint(SHOW)
    function(SHOW, 'TickTally', [], TICK)
    BT.compile_blueprint(SHOW)
    insert_call(SHOW, 'EventGraph', lambda i: i.type_id == '|UpdateCoins', 'TickTally')
    BT.compile_blueprint(SHOW, warnings_as_errors=True)
    cdo = BT.get_default_object(SHOW)
    for name, value in list(TIMES.items()) + list(LOOKS.items()) + [('TallyMilestoneCount', 8)]:
        cdo.set_editor_property(name, value)
    assert u.EditorAssetLibrary.save_loaded_asset(SHOW, False)

    function(HUD, 'StartScoreTally', [], HUD_START)
    BT.compile_blueprint(HUD)
    insert_call(HUD, 'Settle', lambda i: i.type_id == '|SetStation', 'StartScoreTally')
    multiply_combo_in_settle()
    BT.compile_blueprint(HUD, warnings_as_errors=True)
    assert u.EditorAssetLibrary.save_loaded_asset(HUD, False)
u.log('BUMPIT_SCORE_TALLY_APPLIED')
