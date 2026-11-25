"""Live PIE checks; no editor shutdown, no saved fixture functions."""
import sys,json,time,traceback
from pathlib import Path
import unreal as u
project_dir=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir()))
sys.path.insert(0,str(project_dir/'Tools'))
report_dir=project_dir/'Saved'/'Tests' if Path(__file__).parent.name=='Tests' else Path(__file__).parent
report_dir.mkdir(parents=True,exist_ok=True)
from blueprint_graph import *
u.EditorPythonScripting.set_keep_python_script_alive(True)
editor=u.get_editor_subsystem(u.UnrealEditorSubsystem)
level=u.get_editor_subsystem(u.LevelEditorSubsystem)
checks=[];done=False;scenario=None;deadline=time.monotonic()+120
fixtures=[]
for name,kind in [('Station','int'),('Blending','bool'),('Looking','bool'),('Phase','int')]:
 g=Graph(HUD,'UITestSet'+name,True)
 g.e.add_graph_input_parameter('Value',B._make_variable_type(kind));g.set(name,g.arg('Value'))
 fixtures.append('UITestSet'+name)
g=Graph(HUD,'UITestStock',True)
g.e.add_graph_input_parameter('Type',B._make_variable_type('int'));g.e.add_graph_input_parameter('Count',B._make_variable_type('int'))
g.action('/Script/Engine.KismetArrayLibrary:Array_Set',TargetArray=g.get('Stock'),Index=g.arg('Type'),Item=g.arg('Count'),bSizeToFit=False)
fixtures.append('UITestStock');B.compile_blueprint(HUD)
def p(o,n):return o.get_editor_property(n)
def call(o,n,*args):return o.call_method(n,args)
def check(c,m):
 assert c,m
 checks.append(m)
def setp(o,n,v):call(o,'UITestSet'+n,v)
def exercise(h):
 r=p(h,'Rules')
 for n,v in [('Station',1),('Blending',False),('Looking',False)]:setp(h,n,v)
 check(not call(h,'ObstacleModalOpen'),'No blocking modal before buying a ball')
 for _ in range(3):call(h,'Purchase',0)
 call(h,'Visit',1)
 for _ in range(100):yield
 setp(h,'Blending',False)
 check(call(h,'ObstacleModalOpen'),'Free three-choice modal opens for purchased round')
 call(h,'EnsureObstacleOffers');offers=list(p(h,'ObstacleOffers'))
 check(len(set(offers))==3,'Three distinct random offers')
 before=sum(p(h,'Stock'));credits=p(h,'Credits');cells=list(p(h,'CellTypes'))
 check(call(h,'HandleObstacleUI',50.,100.,True),'Outside modal click consumed')
 check(sum(p(h,'Stock'))==before,'Outside modal click grants nothing')
 check(call(h,'HandleObstacleUI',250.,300.,False),'Right click consumed by modal')
 check(p(r,'ChoicePending'),'Right click cannot choose')
 world=editor.get_game_world();pc=u.GameplayStatics.get_player_controller(world,0)
 u.SystemLibrary.execute_console_command(world,'Shot showui',pc)
 for _ in range(8):yield
 def click_card(row):
  ox,oy=call(h,'PointerOrigin')
  scale=p(h,'ScaleHUD')
  pc.set_mouse_location(round(ox+(250+342*row)*scale),round(oy+300*scale))
  u.log('OBSTACLE_UI_POINTER '+repr((row,call(h,'ClickedHudPoint'),p(h,'Station'),p(h,'Looking'),p(h,'Blending'))))
  call(h,'PointerInput',True,False)
 click_card(0)
 check(not p(r,'ChoicePending') and sum(p(h,'Stock'))==before+1,'First card through PointerInput grants exactly one free piece')
 check(p(h,'Credits')==credits and list(p(h,'CellTypes'))==cells,'Choosing does not charge or place')
 call(h,'RebuildObstacleInventory')
 check(list(p(h,'InventoryPieces'))==[offers[0]],'One owned piece becomes one hex slot')
 call(h,'HandleObstacleUI',932.,365.,True)
 check(p(h,'Selected')==offers[0],'Hex click selects owned type')
 call(h,'EditCell',0,False);call(h,'RebuildObstacleInventory')
 check(len(p(h,'InventoryPieces'))==0 and p(h,'CellTypes')[0]==offers[0]+1,'Successful placement consumes one slot')
 for kind in range(10):call(h,'UITestStock',kind,2)
 call(h,'RebuildObstacleInventory')
 check(len(p(h,'InventoryPieces'))==20 and list(p(h,'InventoryPieces'))[:4]==[0,0,1,1],'Duplicate pieces each get their own slot')
 call(h,'HandleObstacleUI',1140.,615.,True)
 check(p(h,'InventoryPage')==1,'Next page reaches overflow stock')
 call(h,'HandleObstacleUI',932.,365.,True)
 check(p(h,'Selected')==6,'Second page selects correct flattened type')
 call(h,'HandleObstacleUI',1140.,615.,True)
 check(p(h,'InventoryPage')==1,'Cannot page past last item')
 call(h,'HandleObstacleUI',930.,615.,True)
 check(p(h,'InventoryPage')==0,'Previous page works')
 u.SystemLibrary.execute_console_command(world,'Shot showui',pc)
 for _ in range(8):yield
 call(h,'EditCell',0,False);call(h,'RebuildObstacleInventory')
 check(len(p(h,'InventoryPieces'))==20,'Occupied cell does not consume inventory')
 check(call(h,'HandleObstacleUI',1160.,590.,True),'Empty panel space consumes clicks')
 setp(h,'Phase',1);old=p(h,'Selected')
 call(h,'HandleObstacleUI',1016.,365.,True)
 check(p(h,'Selected')==old,'Inventory cannot change selection during flight')
 setp(h,'Phase',0);setp(h,'Station',2)
 check(not call(h,'HandleObstacleUI',250.,300.,True),'Obstacle UI does not intercept shop')
 setp(h,'Station',1)
 for kind in range(10):call(h,'UITestStock',kind,0)
 call(h,'RebuildObstacleInventory')
 check(p(h,'InventorySelected')==-1 and p(h,'InventoryPage')==0,'Empty inventory clears selection and page')
 # Start and settle actual round; next round must offer exactly one free selection again.
 call(h,'StartRound');call(h,'Settle',list(p(r,'Multipliers')).index(10));call(h,'NextStage')
 call(h,'EnsureObstacleOffers')
 check(p(r,'BallsUsed')==1 and call(h,'ObstacleModalOpen'),'Next round reopens free choice')
 check(len(set(p(h,'ObstacleOffers')))==3,'Next round retains distinct three offers')
 for row in (1,2):
  expected=p(h,'ObstacleOffers')[row]
  previous=sum(p(h,'Stock'))
  click_card(row)
  check(not p(r,'ChoicePending') and p(h,'Selected')==expected and sum(p(h,'Stock'))==previous+1,f'Card {row+1} through PointerInput grants the displayed piece')
  if row==1:
   call(h,'StartRound');call(h,'Settle',list(p(r,'Multipliers')).index(10));call(h,'NextStage');call(h,'EnsureObstacleOffers')
 yield
def finish(ok,msg):
 global done
 done=True
 (report_dir/'obstacle_ui_test.json').write_text(json.dumps({'passed':ok,'message':msg,'checks':checks},ensure_ascii=False,indent=2),encoding='utf8')
 u.unregister_slate_post_tick_callback(handle)
 level.editor_request_end_play()
 global cleanup_handle
 cleanup_handle=u.register_slate_post_tick_callback(cleanup)
def cleanup(dt):
 if editor.get_game_world():return
 u.unregister_slate_post_tick_callback(cleanup_handle)
 for name in fixtures:B.remove_function_graph(HUD,name)
 B.compile_blueprint(HUD,warnings_as_errors=True)
 u.EditorAssetLibrary.save_loaded_asset(HUD)
def tick(dt):
 global scenario
 if done:return
 try:
  world=editor.get_game_world()
  if world:
   pc=u.GameplayStatics.get_player_controller(world,0);hud=pc.get_hud() if pc else None
   if hud and p(hud,'Rules'):
    if scenario is None:scenario=exercise(hud)
    try:next(scenario)
    except StopIteration:finish(True,'All obstacle UI checks passed')
    return
  if time.monotonic()>deadline:raise TimeoutError('PIE startup timed out')
 except Exception:finish(False,traceback.format_exc())
handle=u.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
