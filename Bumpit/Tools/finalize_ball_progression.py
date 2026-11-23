"""Finish live score, preview and secondary-ball recovery after split-ball migration."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from blueprint_graph import *
TABLE=u.load_asset(ROOT+'BP_PinballTable');TP=ROOT+'BP_PinballTable.BP_PinballTable_C'
def tableget(g,name):
    n=g.e.add_get_member_variable_node(name,TP);put(n.find_input_pin('self'),g.get('Table'));return n.find_output_pin(name)

g=Graph(RULES,'LiveBallScore')
hits=g.math('Add_IntInt',tableget(g,'Hits'),tableget(g,'SplitHits'))
put(g.pin('K2Node_PromotableOperator_0','A'),hits)
put(g.pin('K2Node_VariableSet_1','LastHits'),hits)
put(g.pin('K2Node_PromotableOperator_2','B'),g.math('Multiply_IntInt',hits,g.call('BallScoreMultiplier').find_output_pin('ReturnValue')))
splitint=g.call('/Script/Engine.KismetMathLibrary:Conv_BoolToInt',InBool=tableget(g,'SplitSpawned')).find_output_pin('ReturnValue')
put(g.pin('K2Node_PromotableOperator_3','A'),g.math('Multiply_IntInt',g.get('BaseBallScore'),g.math('Add_IntInt',splitint,1)))

g=Graph(TABLE,'ResetBall')
g.tail=g.old('K2Node_CallFunction_9').find_then_pin()
g.action('/Script/Engine.SceneComponent:SetVisibility',self=g.get('Ball'),bNewVisibility=True,bPropagateToChildren=False)

# The extra ball receives the same minimum impulse requirement as the original.
g=Graph(TABLE,'EventGraph')
ev=next(n for n in B.find_nodes(g.g) if 'OnComponentHit(SplitBall)' in B._get_node_info(n).type_id)
start=ev.find_then_pin()
target=B._resolve_pin(next(p for p in B._get_node_info(ev).output_pins if p.name=='then').connected_pins[0])
start.break_pin_links();g.tail=start
impulse=g.call('/Script/Engine.KismetMathLibrary:VSize',A=ev.find_output_pin('NormalImpulse')).find_output_pin('ReturnValue')
mass=g.call('/Script/Engine.PrimitiveComponent:GetMass',self=g.get('SplitBall')).find_output_pin('ReturnValue')
yes,no=g.branch(g.math('Greater_DoubleDouble',impulse,g.math('Multiply_DoubleDouble',mass,35)))
put(target,yes)

g=Graph(TABLE,'RescueSplitBall',True)
g.reject(g.math('Not_PreBool',g.get('SplitSpawned')));g.reject(g.get('SplitDone'))
velocity=g.action('/Script/Engine.PrimitiveComponent:GetPhysicsLinearVelocity',self=g.get('SplitBall')).find_output_pin('ReturnValue')
speed=g.call('/Script/Engine.KismetMathLibrary:VSize',A=velocity).find_output_pin('ReturnValue')
moving,still=g.branch(g.math('Greater_DoubleDouble',speed,6))
g.tail=moving;g.set('SplitStillSeconds',0)
g.tail=still
delta=g.call('/Script/Engine.GameplayStatics:GetWorldDeltaSeconds').find_output_pin('ReturnValue')
g.set('SplitStillSeconds',g.math('Add_DoubleDouble',g.get('SplitStillSeconds'),delta))
g.reject(g.math('Less_DoubleDouble',g.get('SplitStillSeconds'),5))
g.set('SplitStillSeconds',0)
impulse=g.call('/Script/Engine.KismetMathLibrary:TransformDirection',T=g.call('/Script/Engine.Actor:GetTransform').find_output_pin('ReturnValue'),Direction='-750,220,120').find_output_pin('ReturnValue')
g.action('/Script/Engine.PrimitiveComponent:AddImpulse',self=g.get('SplitBall'),Impulse=impulse,bVelChange=True)
B.compile_blueprint(TABLE)
g=Graph(TABLE,'CheckBall')
target=B._resolve_pin(next(p for p in B._get_node_info(g.entry.get_owning_node()).output_pins if p.name=='then').connected_pins[0])
g.entry.break_pin_links();g.action('RescueSplitBall');put(target,g.tail)

for bp in (TABLE,RULES,HUD):B.compile_blueprint(bp)
for bp in (TABLE,RULES,HUD):assert u.EditorAssetLibrary.save_loaded_asset(bp)
u.log('BALL_PROGRESSION_FINALIZED')
