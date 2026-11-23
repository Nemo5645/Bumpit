"""Replace provisional special effects with the requested split and bumper-score balls.
Run once after apply_special_balls.py; all gameplay remains native Blueprints.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from blueprint_graph import *
from editor_toolset.toolsets.actor import ActorTools as A
TABLE=u.load_asset(ROOT+'BP_PinballTable');TP=ROOT+'BP_PinballTable.BP_PinballTable_C'
assert 'SplitSpawned' not in B.list_variables(TABLE),'Split balls already applied'
for name,kind,default in [('SplitSpawned','bool',False),('PrimaryDone','bool',False),('SplitDone','bool',False),('PrimaryLane','int',-1),('SplitLane','int',-1),('SplitHits','int',0),('SplitVelocity','Vector',u.Vector()),('SplitStillSeconds','float',0.0)]:
    B.add_variable(TABLE,name,kind)
    B.compile_blueprint(TABLE);B.get_default_object(TABLE).set_editor_property(name,default)
components=A.get_components(B.get_default_object(TABLE))
ball=next(c for c in components if c.get_name().startswith('Ball') and isinstance(c,u.StaticMeshComponent))
extra=A.add_component(TABLE,u.StaticMeshComponent.static_class(),'SplitBall')
for prop in ('static_mesh','relative_scale3d','body_instance','override_materials','mobility'):
    extra.set_editor_property(prop,ball.get_editor_property(prop))
extra.set_editor_property('relative_location',u.Vector(0,0,-3000))
extra.set_simulate_physics(False);extra.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
extra.set_visibility(False)
B.compile_blueprint(TABLE)

def foreign(g,name,owner,path):
    n=g.e.add_get_member_variable_node(name,path);put(n.find_input_pin('self'),owner);return n.find_output_pin(name)
def vector(g,name,**args): return g.call('/Script/Engine.KismetMathLibrary:'+name,**args).find_output_pin('ReturnValue')
def tablevar(g,name): return foreign(g,name,g.get('Table'),TP)
def pcall(g,name,**args): return g.action('/Script/Engine.PrimitiveComponent:'+name,**args)
def stop(g,ball):
    pcall(g,'SetSimulatePhysics',self=ball,bSimulate=False)
    pcall(g,'SetCollisionEnabled',self=ball,NewType='NoCollision')
    g.action('/Script/Engine.SceneComponent:SetVisibility',self=ball,bNewVisibility=False,bPropagateToChildren=False)

# Type 1 doubles bumper-derived points only. Type 2 splits once on a side bounce.
g=Graph(RULES,'BallName',True)
for typ,name in [(1,'범퍼 강화공'),(2,'분열공')]:
    yes,no=g.branch(g.math('EqualEqual_IntInt',g.arg('Type'),typ));g.tail=yes;g.ret(name);g.tail=no
g.ret('일반공')
g=Graph(RULES,'SpecialBallHit',True) # Retire provisional demolition; no manual removal bypass.
g=Graph(RULES,'BallScoreMultiplier',True)
yes,no=g.branch(g.math('EqualEqual_IntInt',g.get('ActiveBallType'),1));g.tail=yes;g.ret(2);g.tail=no;g.ret(1)
g=Graph(RULES,'ScoreBall',True)
for name in ('Hits','Lane'):g.e.add_graph_input_parameter(name,B._make_variable_type('int'))
g.e.add_graph_output_parameter('ReturnValue',B._make_variable_type('int'));g.e.set_is_pure_function(True)
yes,no=g.branch(g.math('Less_IntInt',g.arg('Lane'),0));g.tail=yes;g.ret(0);g.tail=no
hits=g.math('Multiply_IntInt',g.arg('Hits'),g.call('BallScoreMultiplier').find_output_pin('ReturnValue'))
base=g.math('Add_IntInt',100,g.math('Multiply_IntInt',hits,25))
g.ret(g.math('Multiply_IntInt',base,g.call('LaneMultiplier',Lane=g.arg('Lane')).find_output_pin('ReturnValue')))
B.compile_blueprint(RULES)

# Retarget existing reflection to either ball, preserving the established round-bumper geometry.
g=Graph(TABLE,'ReflectBumper')
g.e.add_graph_input_parameter('TargetBall',u.BlueprintEditorLibrary.get_object_reference_type(u.PrimitiveComponent.static_class()))
g.e.add_graph_input_parameter('VelocityIn',B._make_variable_type('Vector'))
for n in list(B.find_nodes(g.g)):
    info=B._get_node_info(n)
    if info.type_id=='|GetBall':
        for target in info.output_pins[0].connected_pins:put(B._resolve_pin(target),g.arg('TargetBall'))
    if info.type_id=='|GetIncomingVelocity' and n.get_name()=='K2Node_VariableGet_0':
        for target in info.output_pins[0].connected_pins:put(B._resolve_pin(target),g.arg('VelocityIn'))
g=Graph(TABLE,'EventGraph')
old=g.old('K2Node_CallFunction_25');info=B._get_node_info(old)
B.delete_node(old)
B.compile_blueprint(TABLE)
reflect=g.call('ReflectBumper')
for p in info.input_pins:
    for source in p.connected_pins:put(reflect.find_input_pin(p.name),B._resolve_pin(source))
for p in info.output_pins:
    for target in p.connected_pins:put(B._resolve_pin(target),reflect.find_output_pin(p.name))
put(reflect.find_input_pin('TargetBall'),g.get('Ball'));put(reflect.find_input_pin('VelocityIn'),g.get('IncomingVelocity'))
B.compile_blueprint(TABLE)

g=Graph(TABLE,'MaybeSplit',True)
g.e.add_graph_input_parameter('Normal',B._make_variable_type('Vector'))
rules=g.get('ActiveRules')
g.reject(g.math('Not_PreBool',g.call('/Script/Engine.KismetSystemLibrary:IsValid',Object=rules).find_output_pin('ReturnValue')))
g.reject(g.math('NotEqual_IntInt',foreign(g,'ActiveBallType',rules,CP[RULES]),2))
g.reject(g.get('SplitSpawned'));g.reject(g.get('PrimaryDone'))
sim=g.call('/Script/Engine.SceneComponent:IsSimulatingPhysics',self=g.get('Ball')).find_output_pin('ReturnValue')
g.reject(g.math('Not_PreBool',sim))
up=g.call('/Script/Engine.Actor:GetActorUpVector').find_output_pin('ReturnValue')
dot=vector(g,'Dot_VectorVector',A=g.arg('Normal'),B=up)
g.reject(g.math('Greater_DoubleDouble',vector(g,'Abs',A=dot),.75)) # Floor contact is not a bounce.
pos=g.call('/Script/Engine.SceneComponent:K2_GetComponentLocation',self=g.get('Ball')).find_output_pin('ReturnValue')
local=vector(g,'InverseTransformLocation',T=g.call('/Script/Engine.Actor:GetTransform').find_output_pin('ReturnValue'),Location=pos)
y=g.call('/Script/Engine.KismetMathLibrary:BreakVector',InVec=local).find_output_pin('Y')
g.reject(g.math('Greater_DoubleDouble',y,280)) # Wait until the ball leaves the launch rail.
g.set('SplitSpawned',True);g.set('SplitDone',False);g.set('SplitHits',0)
reflected=vector(g,'GetReflectionVector',Direction=g.get('IncomingVelocity'),SurfaceNormal=g.arg('Normal'))
velocity=vector(g,'RotateAngleAxis',InVect=reflected,AngleDeg=-22,Axis=up)
normalOffset=vector(g,'Multiply_VectorFloat',A=g.arg('Normal'),B=20)
lift=vector(g,'Multiply_VectorFloat',A=up,B=8)
spawn=vector(g,'Add_VectorVector',A=pos,B=vector(g,'Add_VectorVector',A=normalOffset,B=lift))
g.action('/Script/Engine.SceneComponent:K2_SetWorldLocation',self=g.get('SplitBall'),NewLocation=spawn,bSweep=False,bTeleport=True)
pcall(g,'SetMaterial',self=g.get('SplitBall'),ElementIndex=0,Material='/Game/Bumpit/Materials/MI_Ball_Demolition.MI_Ball_Demolition')
g.action('/Script/Engine.SceneComponent:SetVisibility',self=g.get('SplitBall'),bNewVisibility=True,bPropagateToChildren=False)
pcall(g,'SetCollisionEnabled',self=g.get('SplitBall'),NewType='QueryAndPhysics')
pcall(g,'SetSimulatePhysics',self=g.get('SplitBall'),bSimulate=True)
pcall(g,'SetPhysicsLinearVelocity',self=g.get('SplitBall'),NewVel=velocity,bAddToCurrent=False)
g.set('SplitVelocity',velocity)
B.compile_blueprint(TABLE)

# Route the original ball's contact into split detection, then continue its original FX/score path.
g=Graph(TABLE,'EventGraph')
event=g.old('K2Node_ComponentBoundEvent_0')
g.tail=event.find_then_pin();g.tail.break_pin_links()
g.action('MaybeSplit',Normal=g.old('K2Node_CallFunction_24').find_output_pin('ImpactNormal'))
put(g.old('K2Node_IfThenElse_4').find_execute_pin(),g.tail)
# Additional ball has its own collision counting and reflected velocity, and cannot recursively split.
ev=B.add_component_bound_event(extra,'OnComponentHit',g.g)
g.tail=ev.find_then_pin()
has=g.call('/Script/Engine.ActorComponent:ComponentHasTag',self=ev.find_output_pin('OtherComp'),Tag='Bumper').find_output_pin('ReturnValue')
yes,no=g.branch(has);g.tail=yes
g.set('SplitHits',g.math('Add_IntInt',g.get('SplitHits'),1))
g.action('SpawnBumperHitFX',OtherComp=ev.find_output_pin('OtherComp'),Impulse=ev.find_output_pin('NormalImpulse'),Hit=ev.find_output_pin('Hit'))
roundhit=g.call('/Script/Engine.ActorComponent:ComponentHasTag',self=ev.find_output_pin('OtherComp'),Tag='RoundBumper').find_output_pin('ReturnValue')
yes,no=g.branch(roundhit);g.tail=yes
hit=g.call('/Script/Engine.GameplayStatics:BreakHitResult',Hit=ev.find_output_pin('Hit'))
g.action('ReflectBumper',Point=hit.find_output_pin('ImpactPoint'),Normal=hit.find_output_pin('ImpactNormal'),Index=hit.find_output_pin('HitItem'),TargetBall=g.get('SplitBall'),VelocityIn=g.get('SplitVelocity'))
# Track pre-physics velocity independently, even after the original ball has finished.
g.tail=g.old('K2Node_Event_2').find_then_pin();g.tail.break_pin_links()
vel=g.action('/Script/Engine.PrimitiveComponent:GetPhysicsLinearVelocity',self=g.get('SplitBall'))
g.set('SplitVelocity',vel.find_output_pin('ReturnValue'))
put(g.old('K2Node_IfThenElse_2').find_execute_pin(),g.tail)

# Reset extras for every launch, and restore primary visibility/collision after its previous drain.
g=Graph(TABLE,'Launch')
first=next(p for p in B._get_node_info(g.entry.get_owning_node()).output_pins if p.name=='then').connected_pins[0]
target=B._resolve_pin(first);g.entry.break_pin_links()
for name,value in [('SplitSpawned',False),('PrimaryDone',False),('SplitDone',False),('PrimaryLane',-1),('SplitLane',-1),('SplitHits',0),('SplitStillSeconds',0)]:g.set(name,value)
stop(g,g.get('SplitBall'))
g.action('/Script/Engine.SceneComponent:SetVisibility',self=g.get('Ball'),bNewVisibility=True,bPropagateToChildren=False)
pcall(g,'SetCollisionEnabled',self=g.get('Ball'),NewType='QueryAndPhysics')
put(target,g.tail)
g=Graph(TABLE,'StopBall')
g.tail=g.old('K2Node_CallFunction_3').find_then_pin();stop(g,g.get('SplitBall'))

# Poll both physical balls. Returning -1 means the same round is still in flight.
g=Graph(TABLE,'CheckBall',True)
def poll(which,done,lane):
    yes,no=g.branch(g.get(done));g.tail=no
    pos=g.call('/Script/Engine.SceneComponent:K2_GetComponentLocation',self=g.get(which)).find_output_pin('ReturnValue')
    local=vector(g,'InverseTransformLocation',T=g.call('/Script/Engine.Actor:GetTransform').find_output_pin('ReturnValue'),Location=pos)
    status=g.action('BallStatus',Position=local)
    g.set(lane,status.find_output_pin('Lane'))
    terminal,active=g.branch(g.math('NotEqual_IntInt',g.get(lane),-1));g.tail=terminal
    g.set(done,True);stop(g,g.get(which))
    # A harmless setter joins the already-finished, newly-finished, and active branches.
    join=g.e.add_set_member_variable_node('SplitStillSeconds');put(join.find_input_pin('SplitStillSeconds'),g.get('SplitStillSeconds'))
    for tail in (yes,active,g.tail): assert tail.try_create_connection(join.find_execute_pin())
    g.tail=join.find_then_pin()
poll('Ball','PrimaryDone','PrimaryLane')
yes,no=g.branch(g.get('SplitSpawned'))
g.tail=no
notdone,done=g.branch(g.math('Not_PreBool',g.get('PrimaryDone')));g.tail=notdone;g.ret(-1,'Lane');g.tail=done;g.ret(g.get('PrimaryLane'),'Lane')
g.tail=yes;poll('SplitBall','SplitDone','SplitLane')
notdone,done=g.branch(g.math('Not_PreBool',g.math('BooleanAND',g.get('PrimaryDone'),g.get('SplitDone'))))
g.tail=notdone;g.ret(-1,'Lane');g.tail=done;g.ret(g.get('PrimaryLane'),'Lane')
B.compile_blueprint(TABLE)

# Compute both ball scores once; the completed pair consumes a single purchased round.
g=Graph(HUD,'Settle')
primary=g.rulecall('ScoreBall',Hits=tablevar(g,'Hits'),Lane=g.arg('Lane')).find_output_pin('ReturnValue')
secondary=g.rulecall('ScoreBall',Hits=tablevar(g,'SplitHits'),Lane=tablevar(g,'SplitLane')).find_output_pin('ReturnValue')
total=g.math('Add_IntInt',primary,secondary)
for node,pin in [('K2Node_VariableSet_0','LastPoints'),('K2Node_PromotableOperator_1','B'),('K2Node_CallFunction_5','Points'),('K2Node_CallFunction_9','Points')]:put(g.pin(node,pin),total)
# Prevent any alternate settlement call from ending an unfinished split round.
first=next(p for p in B._get_node_info(g.entry.get_owning_node()).output_pins if p.name=='then').connected_pins[0]
target=B._resolve_pin(first);g.entry.break_pin_links()
pending=g.math('BooleanAND',tablevar(g,'SplitSpawned'),g.math('Not_PreBool',g.math('BooleanAND',tablevar(g,'PrimaryDone'),tablevar(g,'SplitDone'))))
g.reject(pending);put(target,g.tail)

# Live score and the older score utility use the bumper-only multiplier as well.
g=Graph(HUD,'RoundScore')
put(g.pin('K2Node_PromotableOperator_0','A'),g.math('Multiply_IntInt',g.arg('Hits'),g.rulecall('BallScoreMultiplier').find_output_pin('ReturnValue')))
g=Graph(HUD,'DrawShop')
for n in B.find_nodes(g.g):
    for p in B._get_node_info(n).input_pins:
        replacements={'점수공':'범퍼 강화공','획득 점수 2배':'범퍼 충돌 점수만 2배','철거공':'분열공','첫 충돌 장애물 1개 제거':'첫 반사 때 공이 2개로 분열'}
        if p.value in replacements:put(B._resolve_pin(p.pin_id),replacements[p.value])
for bp in (RULES,TABLE,HUD):B.compile_blueprint(bp)
for bp in (RULES,TABLE,HUD):assert u.EditorAssetLibrary.save_loaded_asset(bp)
u.log('SPLIT_AND_BUMPER_BALLS_APPLIED')
