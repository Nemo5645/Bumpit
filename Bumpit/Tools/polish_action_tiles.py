"""Improve contrast of the arrow and charge markers on the dash pad."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from blueprint_graph import *
h={}
exec(compile((Path(__file__).parent/'apply_gimmicks.py').read_text(encoding='utf-8-sig').split('with toolset_registry.tool_raising_exceptions():')[0],'<helpers>','exec'),h)
table=u.load_asset(ROOT+'BP_PinballTable')
_,_,parts=h['subobjects'](table)
base=h['colour_material']('MI_Tile_DashBase',(.005,.025,.055),.02)
pip=h['colour_material']('MI_Tile_DashCharge',(.95,.95,1.0),.15)
parts['DashBase'][1].set_editor_property('override_materials',[base])
for i in range(3):parts['DashPip'+str(i)][1].set_editor_property('override_materials',[pip])
B.compile_blueprint(table,warnings_as_errors=True)
assert u.EditorAssetLibrary.save_loaded_asset(table)
u.log('ACTION_TILES_POLISHED')
