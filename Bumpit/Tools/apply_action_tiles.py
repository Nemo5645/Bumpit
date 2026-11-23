"""Add action tiles and three distinct free offers per round. UE 5.8, run once.
48 copy slots = maximum number of one-shot copy tiles on the 48-cell board.
No runtime Python; all logic is compiled into Blueprints.
"""
import sys,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from blueprint_graph import *
# Reuse graph/component helpers, without executing the earlier migration.
helper={}
exec(compile((Path(__file__).parent/'apply_gimmicks.py').read_text(encoding='utf-8-sig').split('with toolset_registry.tool_raising_exceptions():')[0],'<gimmick_helpers>','exec'),helper)
TABLE=u.load_asset(ROOT+'BP_PinballTable');TP=TABLE.generated_class().get_path_name()
helper['BPS'].update(table=TABLE,hud=HUD,rules=RULES)
error_scope=helper['toolset_registry'].tool_raising_exceptions();error_scope.__enter__()
fn=helper['function'];addvars=helper['add_variables'];addcomp=helper['add_component'];infos=helper['infos_of'];pin=helper['pin'];insert=helper['insert_call'];entry=helper['is_entry'];CT=helper['ContainerType']
assert 'ActionTilesVersion' not in B.list_variables(TABLE),'Action tiles already applied'
native={
 'Native|IsValid':'/Script/Engine.KismetSystemLibrary:IsValid',
 'Native|DistanceSegment':'/Script/Engine.KismetMathLibrary:GetPointDistanceToSegment',
 'Native|SetVisibility':'/Script/Engine.SceneComponent:SetVisibility',
 'Native|SetCollision':'/Script/Engine.PrimitiveComponent:SetCollisionEnabled',
 'Native|SetSimulate':'/Script/Engine.PrimitiveComponent:SetSimulatePhysics',
 'Native|GetMaterial':'/Script/Engine.PrimitiveComponent:GetMaterial',
 'Native|SetMaterial':'/Script/Engine.PrimitiveComponent:SetMaterial',
 'Native|GetMass':'/Script/Engine.PrimitiveComponent:GetMass',
 'Native|SetMass':'/Script/Engine.PrimitiveComponent:SetMassOverrideInKg',
 'Native|WorldLocation':'/Script/Engine.SceneComponent:K2_GetComponentLocation',
 'Native|WorldDelta':'/Script/Engine.GameplayStatics:GetWorldDeltaSeconds',
 'Native|Rotate':'/Script/Engine.KismetMathLibrary:RotateAngleAxis',
 'Native|Reflect':'/Script/Engine.KismetMathLibrary:GetReflectionVector',
 'Native|BreakHit':'/Script/Engine.GameplayStatics:BreakHitResult',
}
old_factory=helper['make_node']
def factory(graph,type_id,pos,declaring_class=None):
 if type_id in native:
  n=u.BlueprintGraphEditor.get_graph_editor(graph).add_call_function_node(native[type_id]);n.set_node_pos(pos);return n
 return old_factory(graph,type_id,pos,declaring_class)
helper['make_node']=factory

def declare(bp,name,params,output=None):
 g=Graph(bp,name)
 for n,t in params:
  g.e.add_graph_input_parameter(n,B._make_variable_type(t) if isinstance(t,str) else u.BlueprintEditorLibrary.get_object_reference_type(t.static_class()))
 if output:g.e.add_graph_output_parameter(output[0],B._make_variable_type(output[1]))
 return g
def code(bp,name,params,body):
 if any(t=='HitResult' for _,t in params):
  g=declare(bp,name,[(n,t) for n,t in params if t!='HitResult'])
  for n,t in params:
   if t=='HitResult':B.add_struct_function_param(g.g,n,u.load_object(None,'/Script/Engine.HitResult'),True)
 fn(bp,name,params,'(fn '+name+' ('+' '.join(n for n,_ in params)+')\n'+body+'\n)')
 B.compile_blueprint(bp,warnings_as_errors=True)
def retcode(bp,name,params,typ,body):
 g=declare(bp,name,params,('ReturnValue',typ));g.ret(0 if typ!='bool' else False)
 helper['rebuild_returning'](bp,name,'(fn '+name+' ('+' '.join(n for n,_ in params)+')\n'+body+'\n)')
def getarr(name,index):return f'(Utilities|Array|Get(acopy) (|Get{name}) {index})'
def setarr(name,index,value):return f'(Utilities|Array|SetArrayElem (|Get{name}) {index} {value} false)'

addvars(TABLE,[(n,t,CT.ARRAY) for n,t in [('ActionTypes','int'),('DashCharges','int'),('PadInside','bool'),('PadPrevious','Vector'),('PadValid','bool'),('CopyBalls',u.PrimitiveComponent),('CopyStates','int'),('CopyHits','int'),('CopyVelocities','Vector'),('CopyStill','float')]]+[(n,t,None) for n,t in [('CopyActiveCount','int'),('CopyPoints','int'),('CopyLivePoints','int'),('SpinnerAngle','float'),('ActionTilesVersion','int')]],'Action Tiles')
addvars(HUD,[(n,t,CT.ARRAY) for n,t in [('ObstacleOffers','int'),('OfferPool','int'),('ObstacleDescriptions','string')]]+[(n,'int',None) for n in ['OfferStage','OfferRound','OfferDrawIndex']],'Obstacle Offers')
for bp in (TABLE,HUD):B.compile_blueprint(bp)

# Visible geometry. Nonblocking floor arrows and a gate; spinners are physical bars.
_,_,parts=helper['subobjects'](TABLE)
template=parts['RoundBumpers'][1];ball=parts['Ball'][1]
materials={k:helper['colour_material']('MI_Tile_'+k,c,.6) for k,c in [('Dash',(.05,.65,1)),('Copy',(.8,.1,1)),('Spinner',(1,.45,.04))]}
materials['DashBase']=helper['colour_material']('MI_Tile_DashBase',(.005,.025,.055),.02)
materials['DashCharge']=helper['colour_material']('MI_Tile_DashCharge',(.95,.95,1.0),.15)
for name,kind,blocking in [('DashBase','Dash',False),('DashShaft','Dash',False),('DashWingL','Dash',False),('DashWingR','Dash',False),('DashPip0','Dash',False),('DashPip1','Dash',False),('DashPip2','Dash',False),('CopyBase','Copy',False),('CopyPostL','Copy',False),('CopyPostR','Copy',False),('CopyTop','Copy',False),('SpinnerBars','Spinner',True)]:
 c=addcomp(TABLE,name,u.InstancedStaticMeshComponent)
 c.set_editor_property('static_mesh',u.load_asset('/Engine/BasicShapes/Cube.Cube'))
 c.set_editor_property('override_materials',[materials['DashBase' if name=='DashBase' else 'DashCharge' if name.startswith('DashPip') else kind]])
 c.set_editor_property('mobility',u.ComponentMobility.MOVABLE)
 c.set_editor_property('body_instance',template.get_editor_property('body_instance'))
 c.set_collision_enabled(u.CollisionEnabled.QUERY_AND_PHYSICS if blocking else u.CollisionEnabled.NO_COLLISION)
 c.set_editor_property('component_tags',[u.Name('Bumper'),u.Name('Spinner')] if blocking else [])
 c.clear_instances()
 for _ in range(48):c.add_instance(u.Transform(location=u.Vector(0,0,-3000)),False)

copy_parts=[]
for i in range(48):
 c=addcomp(TABLE,f'CopyBall{i:02}',u.StaticMeshComponent)
 for prop in ('static_mesh','relative_scale3d','body_instance','override_materials','mobility'):c.set_editor_property(prop,ball.get_editor_property(prop))
 c.set_editor_property('relative_location',u.Vector(0,0,-3000))
 c.set_simulate_physics(False);c.set_collision_enabled(u.CollisionEnabled.NO_COLLISION);c.set_visibility(False)
 copy_parts.append(c)
B.compile_blueprint(TABLE)
from functools import lru_cache
helper['members']=lru_cache(maxsize=None)(helper['members'])

def show(name,condition,x,y,z,sx,sy,sz,yaw='0.0'):
 loc=f'(Math|Vector|MakeVector (+ (.x c) {x}) (+ (.y c) {y}) (select {condition} {z} -3000.0))'
 return f'(Components|InstancedStaticMesh|UpdateInstanceTransform (|Get{name}) Index (Math|Transform|MakeTransform {loc} (Math|Rotator|MakeRotator 0.0 0.0 {yaw}) (Math|Vector|MakeVector {sx} {sy} {sz})) false true true)'
body='(bind c (|HexCenter :Index Index))\n(bind typ '+getarr('ActionTypes','Index')+')\n'
for name,x,y,z,sx,sy,sz,yaw in [('DashBase',0,0,1,.48,.48,.015,0),('DashShaft',-3,0,2,.25,.045,.025,0),('DashWingL',8,5,2,.17,.045,.025,-45),('DashWingR',8,-5,2,.17,.045,.025,45)]:body+=show(name,'(== typ 8)',x,y,z,sx,sy,sz,str(yaw))+ '\n'
for i in range(3):body+=show('DashPip'+str(i),f'(and (== typ 8) (> {getarr("DashCharges","Index")} {i}))',-17,-12+i*12,3,.055,.055,.035)+'\n'
for name,x,y,z,sx,sy,sz in [('CopyBase',0,0,1,.12,.5,.02),('CopyPostL',0,-23,16,.045,.045,.32),('CopyPostR',0,23,16,.045,.045,.32),('CopyTop',0,0,32,.045,.50,.045)]:body+=show(name,'(== typ 9)',x,y,z,sx,sy,sz)+'\n'
body+=show('SpinnerBars','(== typ 10)',0,0,14,.56,.085,.28,'(|GetSpinnerAngle)')
code(TABLE,'DrawActionCell',[('Index','int')],body)
code(TABLE,'SetActionTile',[('Index','int'),('Type','int')],f'''
 (if (and (>= Index 0) (< Index 48))
  {setarr('ActionTypes','Index','Type')}
  {setarr('DashCharges','Index','3')}
  (|DrawActionCell :Index Index))''')
code(TABLE,'StopCopyBall',[('Target',u.PrimitiveComponent)],'''
 (Native|SetSimulate Target false)
 (Native|SetCollision Target "NoCollision")
 (Native|SetVisibility Target false false)''')
B.compile_blueprint(TABLE)

# Reset per-launch charges, crossings and copy bookkeeping; leave board placement intact.
body='(Utilities|Array|Clear (|GetCopyBalls))\n'
body+='\n'.join(f'(Utilities|Array|Add (|GetCopyBalls) (|GetCopyBall{i:02}))' for i in range(48))
body+='''
 (|SetCopyActiveCount 0) (|SetCopyPoints 0) (|SetCopyLivePoints 0)
 (for i (range 48)
  (|StopCopyBall :Target (Utilities|Array|Get(acopy) (|GetCopyBalls) i))
  (Utilities|Array|SetArrayElem (|GetCopyStates) i -3 false)
  (Utilities|Array|SetArrayElem (|GetCopyHits) i 0 false)
  (Utilities|Array|SetArrayElem (|GetCopyStill) i 0.0 false)
  (Utilities|Array|SetArrayElem (|GetDashCharges) i 3 false)
  (|DrawActionCell :Index i))
 (for i (range 2400) (Utilities|Array|SetArrayElem (|GetPadInside) i false false))
 (for i (range 50) (Utilities|Array|SetArrayElem (|GetPadValid) i false false))
'''
code(TABLE,'ResetActionRound',[],body)
code(TABLE,'StopAllCopies',[],'''(for i (range (Utilities|Array|Length (|GetCopyBalls))) (|StopCopyBall :Target (Utilities|Array|Get(acopy) (|GetCopyBalls) i)))''')

# Clone inherits material, mass, speed, and scoring type. Each consumed board cell owns one slot.
code(TABLE,'SpawnTileCopy',[('Index','int'),('Source',u.PrimitiveComponent)],f'''
 (if (and (>= Index 0) (< Index 48))
  (if (== {getarr('CopyStates','Index')} -3)
   (bind dst {getarr('CopyBalls','Index')})
   (bind up (Transformation|GetActorUpVector))
   (bind vel (Physics|GetPhysicsLinearVelocity Source))
   (bind side (Math|Vector|Normalize (Math|Vector|CrossProduct up vel)))
   (Transformation|SetWorldLocation dst (+ (Native|WorldLocation Source) (+ (* side 24.0) (* up 3.0))) false true)
   (Native|SetMaterial dst 0 (Native|GetMaterial Source 0))
   (Native|SetMass dst "None" (Native|GetMass Source) true)
   (Native|SetVisibility dst true false)
   (Native|SetCollision dst "QueryAndPhysics")
   (Native|SetSimulate dst true)
   (bind v (Native|Rotate vel 18.0 up))
   (Physics|SetPhysicsLinearVelocity dst v false)
   {setarr('CopyVelocities','Index','v')}
   {setarr('CopyStates','Index','-1')}
   {setarr('CopyHits','Index','0')}
   {setarr('CopyStill','Index','0.0')}
   (|SetCopyActiveCount (+ (|GetCopyActiveCount) 1))
   (|SetObstacle :Index Index :Type 0)
   (Utilities|Array|SetArrayElem (|GetCellTypes :self (|GetHud :self (|GetActiveRules))) Index 0 false)))''')

# Sweep the ball centre between frames so fast launches cannot tunnel through pads.
# PadInside is per ball/per cell: lingering on a dash pad cannot spend all three uses.
code(TABLE,'ProcessActionBall',[('Target',u.PrimitiveComponent),('Slot','int')],f'''
 (if (Physics|IsSimulatingPhysics Target)
  (bind world (Native|WorldLocation Target))
  (bind local (Math|Transform|InverseTransformLocation (Transformation|GetActorTransform) world))
  (bind cur (Math|Vector|MakeVector (.x local) (.y local) 0.0))
  (bind prev (select {getarr('PadValid','Slot')} {getarr('PadPrevious','Slot')} cur))
  (for cell (range 48)
   (bind typ {getarr('ActionTypes','cell')})
   (if (or (== typ 8) (== typ 9))
    (bind c (|HexCenter :Index cell))
    (bind flat (Math|Vector|MakeVector (.x c) (.y c) 0.0))
    (bind idx (+ (* Slot 48) cell))
    (bind near (< (Math|Vector|VectorLength (- cur flat)) 25.0))
    (if (and (not {getarr('PadInside','idx')}) (and (< (Native|DistanceSegment flat prev cur) 23.0) (and (> (.z local) -5.0) (< (.z local) 38.0))))
     (if (and (== typ 8) (> {getarr('DashCharges','cell')} 0))
      {setarr('DashCharges','cell',f'(- {getarr("DashCharges","cell")} 1)')}
      (Physics|SetPhysicsLinearVelocity Target (Math|Transform|TransformDirection (Transformation|GetActorTransform) (Math|Vector|MakeVector 1350.0 0.0 0.0)) false)
      (|DrawActionCell :Index cell))
     (if (== typ 9) (|SpawnTileCopy :Index cell :Source Target)))
    {setarr('PadInside','idx','near')}))
  {setarr('PadPrevious','Slot','cur')}
  {setarr('PadValid','Slot','true')})''')

code(TABLE,'SpinnerHit',[('Target',u.PrimitiveComponent),('Other',u.PrimitiveComponent),('Normal','Vector'),('Velocity','Vector')],'''
 (if (Components|ComponentHasTag Other "Spinner")
  (Physics|SetPhysicsLinearVelocity Target (+ (Native|Reflect Velocity Normal) (* Normal 100.0)) false))''')
B.compile_blueprint(TABLE)

code(TABLE,'CopyHit',[('Index','int'),('Other',u.PrimitiveComponent),('Impulse','Vector'),('Hit','HitResult')],f'''
 (if (== {getarr('CopyStates','Index')} -1)
  (bind target {getarr('CopyBalls','Index')})
  (bind oldv {getarr('CopyVelocities','Index')})
  (bind normal (Math|Vector|Normalize Impulse))
  (if (Components|ComponentHasTag Other "Bumper")
   {setarr('CopyHits','Index',f'(+ {getarr("CopyHits","Index")} 1)')}
   (|SpawnBumperHitFX :OtherComp Other :Impulse Impulse :Hit Hit)
   (if (Components|ComponentHasTag Other "RoundBumper")
    (Physics|SetPhysicsLinearVelocity target (Native|Reflect oldv normal) false))
   (if (Components|ComponentHasTag Other "Gold")
    {setarr('CopyHits','Index',f'(+ {getarr("CopyHits","Index")} (|GetGoldHits))')}
    (else (|ApplyGimmick :Comp Other :TargetBall target :Split false))))
  (|SpinnerHit :Target target :Other Other :Normal normal :Velocity oldv)
  (if (and (== (|GetActiveBallType :self (|GetActiveRules)) 5) (not (Components|ComponentHasTag Other "Bumper")))
   (if (< (Math|Float|Absolute(Float) (Math|Vector|DotProduct normal (Transformation|GetActorUpVector))) 0.7)
    (Physics|SetPhysicsLinearVelocity target (* (Native|Reflect oldv normal) 0.95) false))))''')

code(TABLE,'TickCopies',[],f'''
 (|SetCopyLivePoints 0)
 (for i (range (Utilities|Array|Length (|GetCopyBalls)))
  (if (== {getarr('CopyStates','i')} -1)
   (bind ball {getarr('CopyBalls','i')})
   (bind pos (Math|Transform|InverseTransformLocation (Transformation|GetActorTransform) (Native|WorldLocation ball)))
   (bind status (|BallStatus :Position pos))
   (if (!= status -1)
    {setarr('CopyStates','i','status')}
    (|SetCopyPoints (+ (|GetCopyPoints) (|ScoreBall :self (|GetActiveRules) :Hits {getarr('CopyHits','i')} :Lane status)))
    (|SetCopyActiveCount (- (|GetCopyActiveCount) 1))
    (|StopCopyBall :Target ball)
    (else
     (|PullBall :TargetBall ball)
     (|ProcessActionBall :Target ball :Slot (+ i 2))
     (bind v (Physics|GetPhysicsLinearVelocity ball))
     {setarr('CopyVelocities','i','v')}
     (if (< (Math|Vector|VectorLength v) 6.0)
      {setarr('CopyStill','i',f'(+ {getarr("CopyStill","i")} (Native|WorldDelta))')}
      (else {setarr('CopyStill','i','0.0')}))
     (if (> {getarr('CopyStill','i')} 5.0)
      {setarr('CopyStill','i','0.0')}
      (Physics|AddImpulse ball (Math|Transform|TransformDirection (Transformation|GetActorTransform) (Math|Vector|MakeVector -750.0 220.0 120.0)) "None" true))
     (|SetCopyLivePoints (+ (|GetCopyLivePoints) (+ 100 (* {getarr('CopyHits','i')} (* 25 (|BallScoreMultiplier :self (|GetActiveRules)))))))))))''')
B.compile_blueprint(TABLE)
code(TABLE,'TickActionTiles',[],'''
 (|SetSpinnerAngle (+ (|GetSpinnerAngle) (* (Native|WorldDelta) 90.0)))
 (for i (range 48)
  (if (== (Utilities|Array|Get(acopy) (|GetActionTypes) i) 10) (|DrawActionCell :Index i)))
 (if (Native|IsValid (|GetActiveRules))
  (if (== (|GetPhase :self (|GetHud :self (|GetActiveRules))) 1)
   (|ProcessActionBall :Target (|GetBall) :Slot 0)
   (|ProcessActionBall :Target (|GetSplitBall) :Slot 1)
   (|TickCopies)))''')
B.compile_blueprint(TABLE)

# Extend existing life-cycle and collision paths, keeping the two built-in balls intact.
insert(TABLE,'SetObstacle',entry,'SetActionTile',[('Index','Index'),('Type','Type')])
insert(TABLE,'Launch',entry,'ResetActionRound')
insert(TABLE,'StopBall',entry,'StopAllCopies')
insert(TABLE,'EventGraph',lambda i:isinstance(i.node,u.K2Node_Event) and 'Tick' in i.node.get_node_title(),'TickActionTiles')
g=Graph(TABLE,'EventGraph')
for i,c in enumerate(copy_parts):
 ev=B.add_component_bound_event(c,'OnComponentHit',g.g);g.tail=ev.find_then_pin()
 g.action('CopyHit',Index=i,Other=ev.find_output_pin('OtherComp'),Impulse=ev.find_output_pin('NormalImpulse'),Hit=ev.find_output_pin('Hit'))
for comp,velocity in [('Ball','IncomingVelocity'),('SplitBall','SplitVelocity')]:
 ev=helper['bound_event'](g.g,comp)
 targets=[B._resolve_pin(p) for p in pin(ev,'then').connected_pins]
 tail=ev.node.find_then_pin();tail.break_pin_links();g.tail=tail
 hit=g.call('/Script/Engine.GameplayStatics:BreakHitResult',Hit=ev.node.find_output_pin('Hit'))
 g.action('SpinnerHit',Target=g.get(comp),Other=ev.node.find_output_pin('OtherComp'),Normal=hit.find_output_pin('ImpactNormal'),Velocity=g.get(velocity))
 for t in targets:assert g.tail.try_create_connection(t)

# Final settlement waits for every cloned ball. A cloned drain scores once, not another round.
g=Graph(TABLE,'CheckBall')
for n in list(B.find_nodes(g.g)):
 if isinstance(n,u.K2Node_FunctionResult):
  p=n.find_input_pin('Lane');info=next(p for p in B._get_node_info(n).input_pins if p.name=='Lane')
  old=B._resolve_pin(info.connected_pins[0]) if info.connected_pins else int(info.value)
  sel=g.call('/Script/Engine.KismetMathLibrary:SelectInt',A=-1,B=old,bPickA=g.math('Greater_IntInt',g.get('CopyActiveCount'),0)).find_output_pin('ReturnValue');put(p,sel)
B.compile_blueprint(TABLE)
def tableget(g,name):
 n=g.e.add_get_member_variable_node(name,TP);put(n.find_input_pin('self'),g.get('Table'));return n.find_output_pin(name)
g=Graph(HUD,'Settle')
targets=[B._resolve_pin(p) for p in next(p for p in B._get_node_info(g.entry.get_owning_node()).output_pins if p.name=='then').connected_pins]
g.entry.break_pin_links();g.reject(g.math('Greater_IntInt',tableget(g,'CopyActiveCount'),0))
for t in targets:assert g.tail.try_create_connection(t)
total=g.math('Add_IntInt',g.old('K2Node_PromotableOperator_5').find_output_pin('ReturnValue'),tableget(g,'CopyPoints'))
for nodename,pname in [('K2Node_VariableSet_0','LastPoints'),('K2Node_PromotableOperator_1','B'),('K2Node_CallFunction_5','Points'),('K2Node_CallFunction_9','Points')]:
 put(g.old(nodename).find_input_pin(pname),total)
g=Graph(RULES,'LiveBallScore')
for n in list(B.find_nodes(g.g)):
 if isinstance(n,u.K2Node_FunctionResult):
  p=next(p for p in B._get_node_info(n).input_pins if p.name=='Score')
  old=B._resolve_pin(p.connected_pins[0])
  put(n.find_input_pin('Score'),g.math('Add_IntInt',old,g.math('Add_IntInt',tableget(g,'CopyLivePoints'),tableget(g,'CopyPoints'))))

# Asset defaults: all cells empty until normal SetObstacle calls populate them.
B.compile_blueprint(TABLE)
cdo=B.get_default_object(TABLE)
for name,value in [('ActionTypes',[0]*48),('DashCharges',[3]*48),('PadInside',[False]*2400),('PadPrevious',[u.Vector()]*50),('PadValid',[False]*50),('CopyStates',[-3]*48),('CopyHits',[0]*48),('CopyVelocities',[u.Vector()]*48),('CopyStill',[0.0]*48),('ActionTilesVersion',1)]:cdo.set_editor_property(name,value)

# Random offer/UI changes are in the second module, sharing the helpers above.
exec(compile((Path(__file__).parent/'action_tile_offers.py').read_text(encoding='utf-8'),'<action_tile_offers>','exec'))
for bp in (TABLE,RULES,HUD):B.compile_blueprint(bp,warnings_as_errors=True)
for bp in (TABLE,RULES,HUD):assert u.EditorAssetLibrary.save_loaded_asset(bp)
u.log('ACTION_TILES_APPLIED')
