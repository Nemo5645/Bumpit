"""PIE regression for paid rerolls and rotating only remaining balls."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parents[1]/'Tools'))
from blueprint_graph import Graph,B,HUD,RULES
# In-memory fixture setters; never save these test-only graphs to project assets.
for bp,fields in [(HUD,{'Credits':'int','Station':'int','Blending':'bool','Looking':'bool','Charging':'bool'}),(RULES,{'ShopOffer0':'int'})]:
 for name,kind in fields.items():
  g=Graph(bp,'TestSet_'+name,True)
  g.e.add_graph_input_parameter('Value',B._make_variable_type(kind))
  g.set(name,g.arg('Value'))
 B.compile_blueprint(bp)
def setp(obj,name,value):obj.call_method('TestSet_'+name,(value,))
source=(Path(__file__).parent/'ball_progression_playtest.py').read_text(encoding='utf-8-sig').split('u.EditorLoadingAndSavingUtils.load_map')[0]
source=source.replace('ball_progression.json','shop_controls.json').replace('All progression and physical split-ball assertions passed','Paid rerolls and ball switching passed')
exec(compile(source,__file__,'exec'))

def exercise(h):
 r=p(h,'Rules'); t=p(h,'Table')
 setp(h,'Credits',100)
 setp(h,'Station',2)
 setp(h,'Blending',False)
 setp(h,'Looking',False)
 check(p(r,'RerollCost')==5,'Initial reroll costs 5')
 setp(r,'ShopOffer0',3)
 call(h,'PurchaseOffer',0)
 check(p(r,'ShopOffer0')==-1,'Purchased slot becomes empty')
 for cost in (5,10,15):
  before=p(h,'Credits');queue=list(p(r,'BallQueue'))
  call(h,'RerollShop')
  check(p(h,'Credits')==before-cost and p(r,'RerollCost')==cost+5,f'Reroll deducts {cost} and raises next price')
  check(p(r,'ShopOffer0')==-1 and list(p(r,'BallQueue'))==queue,'Sold slots and purchased queue preserved')
 setp(h,'Credits',19)
 offers=[p(r,'ShopOffer'+str(i)) for i in range(5)]
 call(h,'RerollShop')
 check(p(h,'Credits')==19 and p(r,'RerollCost')==20 and offers==[p(r,'ShopOffer'+str(i)) for i in range(5)],'Insufficient credits changes nothing')
 setp(h,'Credits',100)
 call(h,'Purchase',4);call(h,'Purchase',6)
 check(list(p(r,'BallQueue'))==[3,4,6],'Mixed ball queue ready')
 call(h,'CycleBall')
 check(list(p(r,'BallQueue'))==[4,6,3] and p(r,'ActiveBallType')==4,'Q action rotates remaining balls')
 check(p(t,'WeightSpeedScale')>1 and p(t,'Ball').get_material(0).get_name()=='MI_Ball_Light','Preview mass speed and material refresh')
 # Render both panels for a visual check when run without -nullrhi.
 call(h,'Visit',2)
 for _ in range(90):yield
 world=editor.get_game_world();pc=u.GameplayStatics.get_player_controller(world,0)
 u.SystemLibrary.execute_console_command(world,'Shot showui',pc)
 for _ in range(5):yield
 call(h,'Visit',1)
 for _ in range(90):yield
 u.SystemLibrary.execute_console_command(world,'Shot showui',pc)
 for _ in range(5):yield
 call(h,'CycleBall');call(h,'CycleBall')
 check(list(p(r,'BallQueue'))==[3,4,6] and p(r,'MaxBalls')==3 and p(r,'BallsUsed')==0,'Cycling wraps without changing round count')
 setp(h,'Charging',True);call(h,'CycleBall')
 check(list(p(r,'BallQueue'))==[3,4,6],'Switch blocked during charging')
 setp(h,'Charging',False)
 choose(h,0);call(h,'StartRound')
 queue=list(p(r,'BallQueue'));credits=p(h,'Credits');cost=p(r,'RerollCost')
 call(h,'CycleBall');call(h,'RerollShop')
 check(list(p(r,'BallQueue'))==queue and p(h,'Credits')==credits and p(r,'RerollCost')==cost,'Flight blocks switching and paid rerolls')
 lane=list(p(r,'Multipliers')).index(10)
 call(h,'Settle',lane);call(h,'NextStage')
 setp(h,'Station',1);setp(h,'Blending',False)
 call(h,'CycleBall')
 check(list(p(r,'BallQueue'))==[3,6,4] and p(r,'ActiveBallType')==6,'Used prefix preserved when switching next round')
 choose(h,0);call(h,'StartRound');call(h,'Settle',lane);call(h,'NextStage')
 queue=list(p(r,'BallQueue'));call(h,'CycleBall')
 check(list(p(r,'BallQueue'))==queue,'One remaining ball cannot be rotated')
 choose(h,0);call(h,'StartRound');call(h,'Settle',lane)
 call(r,'TickClearShow',10.0);call(r,'TickCoins',10.0)
 check(p(r,'RerollCost')==5,'New stage resets price to 5')
 check(all(p(r,'ShopOffer'+str(i))>=0 for i in range(5)),'New stage restocks offers')
 yield

u.EditorLoadingAndSavingUtils.load_map('/Game/Bumpit/Maps/BumpitCell')
handle=u.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
