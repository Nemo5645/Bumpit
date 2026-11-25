"""Round bumpers come with the stage, not from the cards. Safe to run repeatedly. Run with the editor closed:
UnrealEditor-Cmd.exe Bumpit.uproject -run=pythonscript -script=<this file> -unattended -nullrhi -culture=en

- The free obstacle cards (3 a round, BP_BumpitHUD.EnsureObstacleOffers) no longer include card 0, the round
  bumper: they are drawn from the other nine.
- SeedRoundBumpers (BP_BumpitHUD) puts the stage's round bumpers on the board: it takes away every round bumper
  (CellTypes 1) and places RoundBumperStart - RoundBumperDrop x (stage - 1) new ones (never fewer than
  RoundBumperMin) on random empty cells, so the obstacles and tiles the player placed keep their cells. With the
  defaults that is 10 on stage 1, 9 on stage 2, ... 0 from stage 11.
  It runs at the start (InitializeBoard) and after every NextStage, and only acts when the stage number has
  changed (RoundBumperStage), so moving to the next round of the same stage leaves them alone.
- BumperAudioTestLayout (the 11 fixed round bumpers of the bumper-sound test) is switched off.
"""
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

ROUND_BUMPER_START, ROUND_BUMPER_DROP, ROUND_BUMPER_MIN = 10, 1, 0

OFFERS = """
(fn EnsureObstacleOffers ()
  (bind rules (|GetRules))
  (Utilities|IsValid rules
    (:"Is Valid"
      (if (|GetChoicePending :self rules)
        (if (or (!= (|GetOfferStage) (|GetCurrentRound :self rules)) (or (!= (|GetOfferRound) (|GetBallsUsed :self rules)) (!= (Utilities|Array|Length (|GetObstacleOffers)) 3)))
          (Utilities|Array|Clear (|GetOfferPool))
          (Utilities|Array|Clear (|GetObstacleOffers))
          ; cards 1-9: card 0, the round bumper, comes with the stage instead (SeedRoundBumpers)
          (for i (range 1 10)
            (Utilities|Array|Add (|GetOfferPool) i))
          (for n (range 3)
            (|SetOfferDrawIndex (Math|Random|RandomIntegerInRange 0 (- (Utilities|Array|Length (|GetOfferPool)) 1)))
            (Utilities|Array|Add (|GetObstacleOffers) (Utilities|Array|Get(acopy) (|GetOfferPool) (|GetOfferDrawIndex)))
            (Utilities|Array|RemoveIndex (|GetOfferPool) (|GetOfferDrawIndex)))
          (|SetOfferStage (|GetCurrentRound :self rules))
          (|SetOfferRound (|GetBallsUsed :self rules)))))))
"""

SEED = """
(fn SeedRoundBumpers ()
  (bind rules (|GetRules))
  (Utilities|IsValid rules
    (:"Is Valid"
      (bind stage (|GetCurrentRound :self rules))
      (if (!= stage (|GetRoundBumperStage))
        (|SetRoundBumperStage stage)
        (bind table (|GetTable))
        ; last stage's round bumpers go
        (for i (range (Utilities|Array|Length (|GetCellTypes)))
          (if (== (Utilities|Array|Get(acopy) (|GetCellTypes) i) 1)
            (Utilities|Array|SetArrayElem (|GetCellTypes) i 0)
            (|SetObstacle :self table :Index i :Type 0)))
        ; the new ones go on random cells nothing else uses
        (Utilities|Array|Clear (|GetRoundBumperFree))
        (for i (range (Utilities|Array|Length (|GetCellTypes)))
          (if (== (Utilities|Array|Get(acopy) (|GetCellTypes) i) 0)
            (Utilities|Array|Add (|GetRoundBumperFree) i)))
        (Utilities|Array|Shuffle (|GetRoundBumperFree))
        (bind wanted (- (|GetRoundBumperStart) (* (|GetRoundBumperDrop) (- stage 1))))
        (bind floored (select (< wanted (|GetRoundBumperMin)) (|GetRoundBumperMin) wanted))
        (bind free (Utilities|Array|Length (|GetRoundBumperFree)))
        (for j (range (select (< floored free) floored free))
          (bind c (Utilities|Array|Get(acopy) (|GetRoundBumperFree) j))
          (Utilities|Array|SetArrayElem (|GetCellTypes) c 1)
          (|SetObstacle :self table :Index c :Type 1))))))
"""

with helpers['toolset_registry'].tool_raising_exceptions():
    add_variables(HUD, [('RoundBumperStart', 'int', None), ('RoundBumperDrop', 'int', None), ('RoundBumperMin', 'int', None),
                        ('RoundBumperStage', 'int', None), ('RoundBumperFree', 'int', ContainerType.ARRAY)], 'Round Bumpers')
    BT.compile_blueprint(HUD)
    function(HUD, 'EnsureObstacleOffers', [], OFFERS)
    function(HUD, 'SeedRoundBumpers', [], SEED)
    BT.compile_blueprint(HUD)
    insert_call(HUD, 'InitializeBoard', lambda i: i.type_id == '|SeedBumperAudioTest', 'SeedRoundBumpers')
    insert_call(HUD, 'NextStage', lambda i: i.type_id == '|SetStage', 'SeedRoundBumpers')
    BT.compile_blueprint(HUD, warnings_as_errors=True)
    cdo = BT.get_default_object(HUD)
    for name, value in (('RoundBumperStart', ROUND_BUMPER_START), ('RoundBumperDrop', ROUND_BUMPER_DROP),
                        ('RoundBumperMin', ROUND_BUMPER_MIN), ('RoundBumperStage', -1), ('BumperAudioTestLayout', False)):
        cdo.set_editor_property(name, value)
    assert u.EditorAssetLibrary.save_loaded_asset(HUD, False)
u.log('BUMPIT_ROUND_BUMPERS_APPLIED')
