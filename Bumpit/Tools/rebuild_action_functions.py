"""Rebuild selected action functions after the initial migration (no component recreation)."""
import ast
from pathlib import Path
source=(Path(__file__).parent/'apply_action_tiles.py').read_text(encoding='utf-8')
setup=source.split('addvars(TABLE,')[0]
setup=setup.replace("assert 'ActionTilesVersion' not in B.list_variables(TABLE),'Action tiles already applied'",'')
exec(compile(setup,__file__,'exec'))
from functools import lru_cache
helper['members']=lru_cache(maxsize=None)(helper['members'])
WANTED={'EnsureObstacleOffers','TickActionTiles'}
for filename in ('apply_action_tiles.py','action_tile_offers.py'):
 text=(Path(__file__).parent/filename).read_text(encoding='utf-8')
 for node in ast.parse(text).body:
  if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=='code':
   if ast.literal_eval(node.value.args[1]) in WANTED:
    exec(compile(ast.Module(body=[node],type_ignores=[]),filename,'exec'))
for bp in (TABLE,HUD,RULES):
 B.compile_blueprint(bp,warnings_as_errors=True)
 assert u.EditorAssetLibrary.save_loaded_asset(bp)
u.log('ACTION_FUNCTIONS_REBUILT')
