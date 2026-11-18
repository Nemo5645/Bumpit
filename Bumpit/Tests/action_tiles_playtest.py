"""Real PIE integration: random free offers, dash charges, copy lifecycle and spinners.
Fixture setters are only compiled in memory, never saved to project assets.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'Tools'))
from blueprint_graph import *
TABLE=u.load_asset(ROOT+'BP_PinballTable')
for bp,fields in [(HUD,{'Selected':'int','OfferStage':'int','Credits':'int'}),(TABLE,{'SpinnerAngle':'float'})]:
 for name,kind in fields.items():
  g=Graph(bp,'TestSet_'+name,True);g.e.add_graph_input_parameter('Value',B._make_variable_type(kind));g.set(name,g.arg('Value'))
 B.compile_blueprint(bp)
g=Graph(HUD,'TestActionOffers',True)
g.action('/Script/Engine.KismetArrayLibrary:Array_Clear',TargetArray=g.get('ObstacleOffers'))
for typ in (7,8,9):g.action('/Script/Engine.KismetArrayLibrary:Array_Add',TargetArray=g.get('ObstacleOffers'),NewItem=typ)
g.set('OfferStage',g.get('CurrentRound',RULES));g.set('OfferRound',g.get('BallsUsed',RULES))
g=Graph(HUD,'TestStock',True)
for typ in (7,8,9):g.action('/Script/Engine.KismetArrayLibrary:Array_Set',TargetArray=g.get('Stock'),Index=typ,Item=3,bSizeToFit=False)
B.compile_blueprint(HUD)
source=(Path(__file__).parent/'ball_progression_playtest.py').read_text(encoding='utf-8-sig').split('u.EditorLoadingAndSavingUtils.load_map')[0]
source=source.replace('ball_progression.json','action_tiles.json').replace('All progression and physical split-ball assertions passed','Random free offers and action tiles passed')
exec(compile(source,__file__,'exec'))
def setp(o,n,v):call(o,'TestSet_'+n,v)
def exercise(h):
 r=p(h,'Rules');t=p(h,'Table');ball=p(t,'Ball')
 check(len(p(h,'Stock'))==10 and len(p(h,'ObstacleNames'))==10,'Ten obstacle kinds in inventory')
 call(h,'EnsureObstacleOffers');offers=list(p(h,'ObstacleOffers'))
 check(len(offers)==len(set(offers))==3 and all(0<=v<10 for v in offers),f'Three distinct valid offers: {offers}; pool={list(p(h,"OfferPool"))}; pending={p(r,"ChoicePending")}; stage={p(h,"OfferStage")}; round={p(h,"OfferRound")}')
 for _ in range(5):call(h,'EnsureObstacleOffers')
 check(list(p(h,'ObstacleOffers'))==offers,'Offers stay fixed while browsing')
 seen=set()
 for _ in range(50):
  setp(h,'OfferStage',-1);call(h,'EnsureObstacleOffers');o=list(p(h,'ObstacleOffers'))
  check(len(set(o))==3,'Random roll has no duplicates');seen.update(o)
 check(seen==set(range(10)),'All ten obstacles can appear')
 for _ in range(3):call(h,'Purchase',0)
 call(h,'TestActionOffers')
 call(h,'Visit',1)
 for _ in range(75):yield
 world=editor.get_game_world();pc=u.GameplayStatics.get_player_controller(world,0)
 u.SystemLibrary.execute_console_command(world,'Shot showui',pc)
 for _ in range(3):yield
 before=p(h,'Credits');stock=list(p(h,'Stock'))
 call(h,'ChooseObstacle',0)
 check(p(r,'ChoicePending') and list(p(h,'Stock'))==stock,'Cannot choose a type absent from offers')
 call(h,'ChooseOffer',0)
 check(not p(r,'ChoicePending') and p(h,'Stock')[7]==1 and p(h,'Credits')==before,'Free choice grants only selected offer')
 stock=list(p(h,'Stock'));call(h,'ChooseObstacle',8)
 check(list(p(h,'Stock'))==stock,'Second grant in same round rejected')
 call(h,'TestStock')
 for typ,cell in [(7,20),(8,21),(9,22),(8,23)]:
  setp(h,'Selected',typ);call(h,'EditCell',cell,False)
 check(list(p(t,'ActionTypes'))[20:24]==[8,9,10,9],'New tiles place in regular cells')
 for _ in range(15):yield
 u.SystemLibrary.execute_console_command(world,'Shot showui',pc)
 for _ in range(3):yield
 call(h,'StartRound');ball.set_enable_gravity(False)
 transform=t.get_actor_transform()
 def move(comp,local):comp.set_world_location(u.MathLibrary.transform_location(transform,local),False,True)
 def center(cell):return call(t,'HexCenter',cell)+u.Vector(0,0,13)
 c=center(20)
 for left in (2,1,0):
  move(ball,c);call(t,'ProcessActionBall',ball,0)
  check(p(t,'DashCharges')[20]==left,'Entering dash consumes exactly one charge')
  localv=u.MathLibrary.inverse_transform_direction(transform,ball.get_physics_linear_velocity())
  check(localv.x>1340 and abs(localv.y)<1,'Dash fires along the visible arrow')
  call(t,'ProcessActionBall',ball,0)
  check(p(t,'DashCharges')[20]==left,'Staying on dash does not repeat trigger')
  move(ball,c+u.Vector(-60,0,0));call(t,'ProcessActionBall',ball,0)
 move(ball,c);ball.set_physics_linear_velocity(u.Vector())
 call(t,'ProcessActionBall',ball,0)
 check(p(t,'DashCharges')[20]==0 and ball.get_physics_linear_velocity().length()<1,'Fourth use is exhausted')
 # Crossing the copy gate creates a real additional simulated body, independent of SplitBall.
 move(ball,center(21));ball.set_physics_linear_velocity(u.MathLibrary.transform_direction(transform,u.Vector(500,0,0)))
 call(t,'ProcessActionBall',ball,0)
 check(p(t,'CopyActiveCount')==1 and p(t,'CopyStates')[21]==-1,'Copy gate spawns a tracked ball')
 extra=p(t,'CopyBalls')[21];extra.set_enable_gravity(False)
 check(extra.is_simulating_physics() and extra.get_material(0)==ball.get_material(0),'Copy inherits ball material and physics')
 check(abs(extra.get_mass()-ball.get_mass())<.01,'Copy inherits ball mass')
 check(p(h,'CellTypes')[21]==0 and p(t,'ActionTypes')[21]==0,'Used copy gate disappears from board data')
 check(p(t,'CopyTop').get_instance_transform(21,False).translation.z<-1000,'Copy gate visual disappears')
 call(t,'ProcessActionBall',ball,0)
 check(p(t,'CopyActiveCount')==1,'One-shot gate cannot duplicate again')
 move(extra,center(23));extra.set_physics_linear_velocity(u.MathLibrary.transform_direction(transform,u.Vector(500,0,0)))
 call(t,'ProcessActionBall',extra,23)
 check(p(t,'CopyActiveCount')==2 and p(t,'CopyStates')[23]==-1,'A copied ball can use a different copy gate')
 other=p(t,'CopyBalls')[23];other.set_enable_gravity(False)
 # Verify the clone's real OnComponentHit wiring, not only direct function calls.
 call(t,'SetObstacle',19,1)
 move(ball,u.Vector(300,-150,13));ball.set_physics_linear_velocity(u.Vector())
 move(other,u.Vector(300,150,13));other.set_physics_linear_velocity(u.Vector())
 move(extra,center(19)+u.Vector(-65,0,0))
 extra.set_physics_linear_velocity(u.MathLibrary.transform_direction(transform,u.Vector(280,0,0)))
 until=time.monotonic()+2
 while p(t,'CopyHits')[21]==0 and time.monotonic()<until:yield
 check(p(t,'CopyHits')[21]>0,'Real clone collision earns bumper hits')
 # Original pair's completion cannot settle while a clone remains.
 move(ball,u.Vector(-900,0,13));call(t,'CheckBall')
 used=p(r,'BallsUsed');call(h,'Settle',-2)
 check(p(r,'BallsUsed')==used and p(h,'Phase')==1,'Settlement waits for every copy')
 goal=list(p(r,'Multipliers')).index(10)
 goal_y=call(t,'GoalLabelLocal',goal).y
 goal_positions=[u.Vector(x,goal_y,13) for x in range(-300,-801,-10) if call(t,'BallStatus',u.Vector(x,goal_y,13))==goal]
 goalpos=goal_positions[len(goal_positions)//2]
 move(extra,goalpos);move(other,goalpos);call(t,'TickCopies')
 check(p(t,'CopyActiveCount')==0 and not extra.is_simulating_physics(),f'Finished copies stop and leave active count: count={p(t,"CopyActiveCount")}, states={list(p(t,"CopyStates"))}, goalpos={goalpos}')
 expected=sum(call(r,'ScoreBall',p(t,'CopyHits')[i],p(t,'CopyStates')[i]) for i in (21,23))
 check(p(t,'CopyPoints')==expected and expected>=2000,'Each clone contributes its own positive lane score')
 points=p(t,'CopyPoints');call(t,'TickCopies')
 check(p(t,'CopyPoints')==points,'Copy settlement is not counted twice')
 # Spinner changes its physical orientation while keeping cell placement fixed.
 a=p(t,'SpinnerBars').get_instance_transform(22,False)
 setp(t,'SpinnerAngle',45.0);call(t,'DrawActionCell',22)
 b=p(t,'SpinnerBars').get_instance_transform(22,False)
 check(abs(a.rotation.rotator().yaw-b.rotation.rotator().yaw)>20,'Spinner mesh rotates in its cell')
 ball.set_collision_enabled(u.CollisionEnabled.QUERY_AND_PHYSICS)
 move(ball,center(22)+u.Vector(-65,0,0))
 ball.set_simulate_physics(True)
 v=u.MathLibrary.transform_direction(transform,u.Vector(-300,0,0));n=u.MathLibrary.transform_direction(transform,u.Vector(1,0,0))
 call(t,'SpinnerHit',ball,p(t,'SpinnerBars'),n,v)
 check(u.MathLibrary.inverse_transform_direction(transform,ball.get_physics_linear_velocity()).x>300,f'Spinner redirects a contacting ball: velocity={ball.get_physics_linear_velocity()}, tags={p(t,"SpinnerBars").component_tags}, sim={ball.is_simulating_physics()}')
 ball.set_simulate_physics(False)
 before=p(h,'TotalPoints');lane=call(t,'CheckBall')
 call(h,'Settle',lane)
 check(p(h,'TotalPoints')-before==call(r,'ScoreBall',p(t,'Hits'),lane)+expected,'Final score includes original and both copies exactly once')
 call(h,'NextStage')
 call(h,'EnsureObstacleOffers')
 check(p(h,'OfferRound')==1 and len(set(p(h,'ObstacleOffers')))==3,'Next round gets its own three choices')
 call(h,'ChooseOffer',0);call(h,'StartRound')
 check(p(t,'DashCharges')[20]==3,'Next round replenishes dash charges')
 check(p(t,'CopyActiveCount')==0 and all(v==-3 for v in p(t,'CopyStates')),'New round clears old clone states')
 check(p(t,'ActionTypes')[21]==0 and p(h,'CellTypes')[21]==0,'Consumed copy tile stays removed next round')
 check(p(t,'ActionTypes')[20]==8 and p(t,'ActionTypes')[22]==10,'Reusable dash and spinner persist')
 yield

u.EditorLoadingAndSavingUtils.load_map('/Game/Bumpit/Maps/BumpitCell')
handle=u.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
