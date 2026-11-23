"""One-time upgrade after apply_ball_progression.py. UE 5.8 editor commandlet.
Normal / score x2 / first-hit demolition balls, FIFO queue, shared five-ball cap.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from blueprint_graph import *
from editor_toolset.toolsets.blueprint import ContainerType

TABLE=u.load_asset(ROOT+'BP_PinballTable')
TP=ROOT+'BP_PinballTable.BP_PinballTable_C'
assert 'BallQueue' not in B.list_variables(RULES), 'Special balls already applied'
B.add_variable(RULES,'BallQueue','int',container_type=ContainerType.ARRAY)
for name,kind,value in [('ActiveBallType','int',0),('SpecialUsed','bool',False)]: rulesvar(name,kind,value)
B.add_object_variable(TABLE,'ActiveRules',RULES.generated_class())
B.compile_blueprint(TABLE)

g=Graph(RULES,'BallName',True)
g.e.add_graph_input_parameter('Type',B._make_variable_type('int'))
g.e.add_graph_output_parameter('ReturnValue',B._make_variable_type('string'))
g.e.set_is_pure_function(True)
for typ,name in [(1,'점수공'),(2,'철거공')]:
    yes,no=g.branch(g.math('EqualEqual_IntInt',g.arg('Type'),typ))
    g.tail=yes;g.ret(name);g.tail=no
g.ret('일반공')
g=Graph(RULES,'BallCost',True)
g.e.add_graph_input_parameter('Type',B._make_variable_type('int'))
g.e.add_graph_output_parameter('ReturnValue',B._make_variable_type('int'))
g.e.set_is_pure_function(True)
yes,no=g.branch(g.math('EqualEqual_IntInt',g.arg('Type'),0))
g.tail=yes;g.ret(g.get('BallPrice'));g.tail=no;g.ret(5)
B.compile_blueprint(RULES)

# Distinct ball colours use the existing material parent and preserve the mesh.
normal='/Game/Bumpit/Materials/MI_Cell_950_960_990'
materials=[normal]
for name,color in [('MI_Ball_Score',(1.0,.65,.04)),('MI_Ball_Demolition',(1.0,.05,.025))]:
    dest='/Game/Bumpit/Materials/'+name
    mat=u.EditorAssetLibrary.duplicate_asset(normal,dest)
    assert mat,dest
    u.MaterialEditingLibrary.set_material_instance_vector_parameter_value(mat,'Color',u.LinearColor(*color,1))
    u.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(mat,'Glow',.8)
    u.EditorAssetLibrary.save_loaded_asset(mat)
    materials.append(dest)

g=Graph(HUD,'RefreshBall',True)
g.set('ActiveBallType',0,RULES)
yes,no=g.branch(g.math('Greater_IntInt',g.get('MaxBalls',RULES),g.get('BallsUsed',RULES)))
g.tail=yes
item=g.call('/Script/Engine.KismetArrayLibrary:Array_Get',TargetArray=g.get('BallQueue',RULES),Index=g.get('BallsUsed',RULES)).find_output_pin('Item')
g.set('ActiveBallType',item,RULES)
join=g.e.add_set_member_variable_node('SpecialUsed',CP[RULES]);put(join.find_input_pin('self'),g.get('Rules'));put(join.find_input_pin('SpecialUsed'),False)
put(join.find_execute_pin(),g.tail);assert no.try_create_connection(join.find_execute_pin());g.tail=join.find_then_pin()
ballnode=g.e.add_get_member_variable_node('Ball',TP);put(ballnode.find_input_pin('self'),g.get('Table'))
for typ,mat in enumerate(materials):
    yes,no=g.branch(g.math('EqualEqual_IntInt',g.get('ActiveBallType',RULES),typ))
    g.tail=yes
    g.action('/Script/Engine.PrimitiveComponent:SetMaterial',self=ballnode.find_output_pin('Ball'),ElementIndex=0,Material=mat+'.'+mat.split('/')[-1])
    g.tail=no
B.compile_blueprint(HUD)

g=Graph(HUD,'Purchase',True)
g.reject(g.math('NotEqual_IntInt',g.get('Phase'),0))
g.reject(g.get('StageStarted',RULES),'구슬 구매는 스테이지 시작 전에만 가능합니다')
g.reject(g.math('NotEqual_IntInt',g.get('State',RULES),0))
g.reject(g.math('Less_IntInt',g.arg('Type'),0))
g.reject(g.math('Greater_IntInt',g.arg('Type'),2))
g.reject(g.math('GreaterEqual_IntInt',g.get('MaxBalls',RULES),5),'구슬은 종류 합산 최대 5개까지 구매 가능합니다')
cost=g.rulecall('BallCost',Type=g.arg('Type')).find_output_pin('ReturnValue')
g.reject(g.math('Less_IntInt',g.get('Credits'),cost),'크레딧 부족')
g.set('Credits',g.math('Subtract_IntInt',g.get('Credits'),cost))
g.action('/Script/Engine.KismetArrayLibrary:Array_Add',TargetArray=g.get('BallQueue',RULES),NewItem=g.arg('Type'))
g.set('MaxBalls',g.math('Add_IntInt',g.get('MaxBalls',RULES),1),RULES)
g.action('RefreshBall')
g.msg(g.textnum('구매 ',g.get('MaxBalls',RULES),' / 5개 · 구매 순서대로 발사'))

# Insert preview setup immediately before the existing physics launch.
g=Graph(HUD,'StartRound')
launch=next(n for n in B.find_nodes(g.g) if B._get_node_info(n).type_id=='|Launch')
inp=next(p for p in B._get_node_info(launch).input_pins if p.name=='execute')
g.tail=B._resolve_pin(inp.connected_pins[0]);g.tail.break_pin_links()
g.action('RefreshBall');put(launch.find_execute_pin(),g.tail)
# NextStage is used for both next-round and next-stage preparation.
g=Graph(HUD,'NextStage')
message=next(n for n in B.find_nodes(g.g) if B._get_node_info(n).type_id=='|SetMessage')
g.tail=message.find_then_pin();g.action('RefreshBall')
g=Graph(RULES,'AdvanceRound')
reset=next(n for n in B.find_nodes(g.g) if B._get_node_info(n).type_id=='|SetMaxBalls')
inp=next(p for p in B._get_node_info(reset).input_pins if p.name=='execute')
g.tail=B._resolve_pin(inp.connected_pins[0]);g.tail.break_pin_links()
g.action('/Script/Engine.KismetArrayLibrary:Array_Clear',TargetArray=g.get('BallQueue'))
put(reset.find_execute_pin(),g.tail)

# A pure multiplier keeps the result, stage points, and credit calculations consistent.
g=Graph(RULES,'BallScoreMultiplier',True)
g.e.add_graph_output_parameter('ReturnValue',B._make_variable_type('int'))
g.e.set_is_pure_function(True)
yes,no=g.branch(g.math('EqualEqual_IntInt',g.get('ActiveBallType'),1))
g.tail=yes;g.ret(2);g.tail=no;g.ret(1)
B.compile_blueprint(RULES)
g=Graph(HUD,'Settle')
score=g.old('K2Node_CallFunction_4')
out=next(p for p in B._get_node_info(score).output_pins if p.name=='Points')
targets=[B._resolve_pin(p) for p in out.connected_pins]
mult=g.math('Multiply_IntInt',score.find_output_pin('Points'),g.rulecall('BallScoreMultiplier').find_output_pin('ReturnValue'))
for target in targets: put(target,mult)

# Demolition is an in-flight special effect, separate from manual ticket use.
g=Graph(RULES,'SpecialBallHit',True)
g.e.add_graph_input_parameter('Index',B._make_variable_type('int'))
g.reject(g.math('NotEqual_IntInt',g.get('Phase',HUD),1))
g.reject(g.math('NotEqual_IntInt',g.get('ActiveBallType'),2))
g.reject(g.get('SpecialUsed'))
g.reject(g.math('Less_IntInt',g.arg('Index'),0))
g.reject(g.math('GreaterEqual_IntInt',g.arg('Index'),48))
arr=g.get('CellTypes',HUD)
item=g.call('/Script/Engine.KismetArrayLibrary:Array_Get',TargetArray=arr,Index=g.arg('Index')).find_output_pin('Item')
g.reject(g.math('LessEqual_IntInt',item,0))
g.set('SpecialUsed',True)
g.action('/Script/Engine.KismetArrayLibrary:Array_Set',TargetArray=arr,Index=g.arg('Index'),Item=0,bSizeToFit=False)
g.action(TP+':SetObstacle',self=g.get('Table'),Index=g.arg('Index'),Type=0)
g.set('Message','철거공 발동 · 장애물 1개 제거',HUD)
B.compile_blueprint(RULES)
g=Graph(HUD,'CreateRoundRules')
g.tail=g.old('K2Node_CallFunction_2').find_then_pin()
n=g.e.add_set_member_variable_node('ActiveRules',TP)
put(n.find_input_pin('self'),g.get('Table'));put(n.find_input_pin('ActiveRules'),g.get('Rules'));g.exec(n)
g=Graph(TABLE,'EventGraph')
rules=g.get('ActiveRules')
hit=g.call(CP[RULES]+':SpecialBallHit',self=rules,Index=g.old('K2Node_CallFunction_24').find_output_pin('HitItem'))
# Both paths run only after a bumper hit; round reflection finishes first.
put(hit.find_execute_pin(),g.old('K2Node_CallFunction_25').find_then_pin())
assert g.old('K2Node_IfThenElse_6').find_output_pin('else').try_create_connection(hit.find_execute_pin())

# Three shop rows, all sharing the same limit and FIFO inventory.
g=Graph(HUD,'PointerInput')
put(g.pin('K2Node_MacroInstance_0','LastIndex'),2)
g=Graph(HUD,'DrawShop',True)
ink='(R=0.86,G=0.79,B=0.66,A=1)';accent='(R=0.95,G=0.36,B=0.16,A=1)'
def label(text,x,y,size=1,tint=ink): g.action('Label',Caption=text,X=x,Y=y,Size=size,Tint=tint)
g.action('Panel',X=732,Y=103,W=421,H=560,Tint='(R=0.016,G=0.01,B=0.008,A=0.94)')
label('MARBLE SHOP',750,131,1.4,accent)
label(g.textnum('크레딧 ',g.get('Credits'),append=''),750,181)
label(g.textnum('구매 ',g.get('MaxBalls',RULES),' / 5'),990,181)
for typ,(title,description) in enumerate([('일반공','기본 구슬'),('점수공','획득 점수 2배'),('철거공','첫 충돌 장애물 1개 제거')]):
    y=233+82*typ
    g.action('Panel',X=750,Y=y,W=380,H=70,Tint='(R=0.18,G=0.065,B=0.025,A=1)')
    label(title,768,y+7,1.05)
    label(description,768,y+39,.82)
    label(g.textnum('구매 ',g.rulecall('BallCost',Type=typ).find_output_pin('ReturnValue')),1020,y+19,.95,accent)
label('구매 순서대로 발사 · 첫 발사 후 구매 불가',750,481,.83)
label(g.textnum('철거권 ',g.get('RemovalTickets',RULES),'개 · 첫 발사 전에 우클릭 사용'),750,513,.82)
# Show the purchased order as short names, without indexing beyond the queue.
for index in range(5):
    yes,no=g.branch(g.math('Greater_IntInt',g.get('MaxBalls',RULES),index));g.tail=yes
    typ=g.call('/Script/Engine.KismetArrayLibrary:Array_Get',TargetArray=g.get('BallQueue',RULES),Index=index).find_output_pin('Item')
    label(g.rulecall('BallName',Type=typ).find_output_pin('ReturnValue'),750+76*index,548,.85)
    # Continue subsequent rows regardless of this slot being populated.
    join=g.call('Label',Caption='',X=0,Y=0,Size=0,Tint=ink)
    put(join.find_execute_pin(),g.tail);assert no.try_create_connection(join.find_execute_pin());g.tail=join.find_then_pin()
label(g.get('Message'),750,585,.68)
g.action('DrawSideArrow',Caption='테이블')
g=Graph(HUD,'DrawTable')
put(g.pin('K2Node_CallFunction_1','Caption'),g.rulecall('BallName',Type=g.get('ActiveBallType',RULES)).find_output_pin('ReturnValue'))

for bp in (RULES,TABLE,HUD): B.compile_blueprint(bp)
for bp in (RULES,TABLE,HUD): assert u.EditorAssetLibrary.save_loaded_asset(bp)
u.log('SPECIAL_BALLS_APPLIED')
