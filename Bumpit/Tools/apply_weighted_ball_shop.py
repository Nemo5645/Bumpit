"""Five independent offers; sold slots stay empty through rerolls until next stage.
Run once against the migrated split-ball project, UE 5.8 editor commandlet.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from blueprint_graph import *
TABLE=u.load_asset(ROOT+'BP_PinballTable');TP=ROOT+'BP_PinballTable.BP_PinballTable_C'
assert 'ShopOffer0' not in B.list_variables(RULES),'Shop migration already applied'
for i in range(5):rulesvar('ShopOffer'+str(i),'int',-1)
B.add_variable(HUD,'PurchaseCountBefore','int')
B.add_variable(TABLE,'WeightSpeedScale','float')
B.compile_blueprint(TABLE);B.get_default_object(TABLE).set_editor_property('WeightSpeedScale',1.0)

names=['일반공','범퍼 강화공','분열공','무거운 공','가벼운 공']
descs=['기본 구슬','범퍼 충돌 점수만 2배','첫 반사 때 공이 2개로 분열','질량 2배 · 발사 속도 85%','질량 0.5배 · 발사 속도 115%']
for func,values,fallback in [('BallName',names,'구매 완료'),('BallDescription',descs,'다음 스테이지에서 다시 채워집니다')]:
    new=func=='BallDescription';g=Graph(RULES,func,True)
    if new:
        g.e.add_graph_input_parameter('Type',B._make_variable_type('int'))
        g.e.add_graph_output_parameter('ReturnValue',B._make_variable_type('string'));g.e.set_is_pure_function(True)
    for typ,value in enumerate(values):
        yes,no=g.branch(g.math('EqualEqual_IntInt',g.arg('Type'),typ));g.tail=yes;g.ret(value);g.tail=no
    g.ret(fallback)
g=Graph(RULES,'BallCost',True)
for typ,cost in enumerate([3,5,5,4,4]):
    yes,no=g.branch(g.math('EqualEqual_IntInt',g.arg('Type'),typ));g.tail=yes;g.ret(cost);g.tail=no
g.ret(0)

g=Graph(RULES,'OfferType',True)
g.e.add_graph_input_parameter('Slot',B._make_variable_type('int'))
g.e.add_graph_output_parameter('ReturnValue',B._make_variable_type('int'));g.e.set_is_pure_function(True)
for i in range(5):
    yes,no=g.branch(g.math('EqualEqual_IntInt',g.arg('Slot'),i));g.tail=yes;g.ret(g.get('ShopOffer'+str(i)));g.tail=no
g.ret(-1)

g=Graph(RULES,'ResetShop',True)
for i in range(5):
    draw=g.call('/Script/Engine.KismetMathLibrary:RandomIntegerInRange',Min=0,Max=4).find_output_pin('ReturnValue')
    g.set('ShopOffer'+str(i),draw)
g=Graph(RULES,'RerollOffers',True)
for i in range(5):
    yes,no=g.branch(g.math('GreaterEqual_IntInt',g.get('ShopOffer'+str(i)),0));g.tail=yes
    g.set('ShopOffer'+str(i),g.call('/Script/Engine.KismetMathLibrary:RandomIntegerInRange',Min=0,Max=4).find_output_pin('ReturnValue'))
    # Join without sampling random values on the sold-slot branch.
    join=g.e.add_set_member_variable_node('SpecialUsed');put(join.find_input_pin('SpecialUsed'),g.get('SpecialUsed'))
    put(join.find_execute_pin(),g.tail);assert no.try_create_connection(join.find_execute_pin());g.tail=join.find_then_pin()
g=Graph(RULES,'SellOffer',True)
g.e.add_graph_input_parameter('Slot',B._make_variable_type('int'))
for i in range(5):
    yes,no=g.branch(g.math('EqualEqual_IntInt',g.arg('Slot'),i));g.tail=yes;g.set('ShopOffer'+str(i),-1);g.tail=no
B.compile_blueprint(RULES)
g=Graph(RULES,'StartRun')
target=B._resolve_pin(next(p for p in B._get_node_info(g.entry.get_owning_node()).output_pins if p.name=='then').connected_pins[0])
g.entry.break_pin_links();g.action('ResetShop');put(target,g.tail)
g=Graph(RULES,'AdvanceRound')
node=next(n for n in B.find_nodes(g.g) if B._get_node_info(n).type_id=='|SetState')
tail=node.find_then_pin();target=B._resolve_pin(next(p for p in B._get_node_info(node).output_pins if p.name=='then').connected_pins[0])
tail.break_pin_links();g.tail=tail;g.action('ResetShop');put(target,g.tail)

g=Graph(HUD,'Purchase')
# Update only the type-range guard (not the five-ball budget guard).
for n in B.find_nodes(g.g):
    info=B._get_node_info(n)
    for pin in info.input_pins:
        if pin.name=='B' and pin.value=='2':put(B._resolve_pin(pin.pin_id),4)
g=Graph(HUD,'PurchaseOffer',True)
g.e.add_graph_input_parameter('Slot',B._make_variable_type('int'))
g.reject(g.math('Less_IntInt',g.arg('Slot'),0));g.reject(g.math('Greater_IntInt',g.arg('Slot'),4))
typ=g.rulecall('OfferType',Slot=g.arg('Slot')).find_output_pin('ReturnValue')
g.reject(g.math('Less_IntInt',typ,0),'이미 구매한 빈칸입니다')
g.set('PurchaseCountBefore',g.get('MaxBalls',RULES));g.action('Purchase',Type=typ)
g.reject(g.math('EqualEqual_IntInt',g.get('PurchaseCountBefore'),g.get('MaxBalls',RULES)))
g.action(CP[RULES]+':SellOffer',self=g.get('Rules'),Slot=g.arg('Slot'))
g=Graph(HUD,'RerollShop',True)
g.reject(g.math('NotEqual_IntInt',g.get('Phase'),0))
g.reject(g.get('StageStarted',RULES),'리롤은 스테이지 첫 발사 전에만 가능합니다')
g.reject(g.math('NotEqual_IntInt',g.get('State',RULES),0))
g.reject(g.math('GreaterEqual_IntInt',g.get('MaxBalls',RULES),5),'구매 완료 · 테이블로 이동하세요')
g.action(CP[RULES]+':RerollOffers',self=g.get('Rules'))
g.msg('남은 상품 리롤 완료 · 구매한 칸은 빈칸 유지')
B.compile_blueprint(HUD)

# Refresh preview always resets mass and speed, preventing effects carrying to the next ball.
materials=['MI_Cell_950_960_990','MI_Ball_Score','MI_Ball_Demolition','MI_Ball_Heavy','MI_Ball_Light']
for name,color in [('MI_Ball_Heavy',(.13,.22,.48)),('MI_Ball_Light',(.18,1.0,.78))]:
    dest='/Game/Bumpit/Materials/'+name
    mat=u.load_asset(dest) if u.EditorAssetLibrary.does_asset_exist(dest) else u.EditorAssetLibrary.duplicate_asset('/Game/Bumpit/Materials/MI_Cell_950_960_990',dest)
    assert mat
    u.MaterialEditingLibrary.set_material_instance_vector_parameter_value(mat,'Color',u.LinearColor(*color,1))
    u.EditorAssetLibrary.save_loaded_asset(mat)
g=Graph(HUD,'RefreshBall',True)
g.set('ActiveBallType',0,RULES)
yes,no=g.branch(g.math('Greater_IntInt',g.get('MaxBalls',RULES),g.get('BallsUsed',RULES)));g.tail=yes
item=g.call('/Script/Engine.KismetArrayLibrary:Array_Get',TargetArray=g.get('BallQueue',RULES),Index=g.get('BallsUsed',RULES)).find_output_pin('Item')
g.set('ActiveBallType',item,RULES)
join=g.e.add_set_member_variable_node('SpecialUsed',CP[RULES]);put(join.find_input_pin('self'),g.get('Rules'));put(join.find_input_pin('SpecialUsed'),False)
put(join.find_execute_pin(),g.tail);assert no.try_create_connection(join.find_execute_pin());g.tail=join.find_then_pin()
ball=g.e.add_get_member_variable_node('Ball',TP);put(ball.find_input_pin('self'),g.get('Table'));ball=ball.find_output_pin('Ball')
for typ,(mat,mass,speed) in enumerate(zip(materials,[1,1,1,2,.5],[1,1,1,.85,1.15])):
    yes,no=g.branch(g.math('EqualEqual_IntInt',g.get('ActiveBallType',RULES),typ));g.tail=yes
    g.action('/Script/Engine.PrimitiveComponent:SetMassScale',self=ball,InMassScale=mass)
    g.action('/Script/Engine.PrimitiveComponent:SetMaterial',self=ball,ElementIndex=0,Material='/Game/Bumpit/Materials/'+mat+'.'+mat)
    s=g.e.add_set_member_variable_node('WeightSpeedScale',TP);put(s.find_input_pin('self'),g.get('Table'));put(s.find_input_pin('WeightSpeedScale'),speed);g.exec(s)
    g.tail=no
g=Graph(TABLE,'Launch')
put(g.pin('K2Node_CallFunction_20','X'),g.math('Multiply_DoubleDouble',g.old('K2Node_CallFunction_18').find_output_pin('Speed'),g.get('WeightSpeedScale')))

# Replace only the shop click branch; table picking and obstacle choices stay unchanged.
g=Graph(HUD,'PointerInput')
g.tail=g.old('K2Node_IfThenElse_7').find_output_pin('then');g.tail.break_pin_links()
x=g.old('K2Node_PromotableOperator_1').find_output_pin('ReturnValue');y=g.old('K2Node_PromotableOperator_3').find_output_pin('ReturnValue')
for index in range(5):
    inside=g.call('InsideRect',PointX=x,PointY=y,X=750,Y=220+62*index,W=380,H=56).find_output_pin('ReturnValue')
    yes,no=g.branch(inside);g.tail=yes;g.action('PurchaseOffer',Slot=index);g.tail=no
yes,no=g.branch(g.call('InsideRect',PointX=x,PointY=y,X=750,Y=532,W=380,H=40).find_output_pin('ReturnValue'))
g.tail=yes;g.action('RerollShop')

g=Graph(HUD,'DrawShop',True)
ink='(R=0.86,G=0.79,B=0.66,A=1)';accent='(R=0.95,G=0.36,B=0.16,A=1)'
def label(text,x,y,size=1,tint=ink):g.action('Label',Caption=text,X=x,Y=y,Size=size,Tint=tint)
def join(alt):
    n=g.call('Label',Caption='',X=0,Y=0,Size=0,Tint=ink);put(n.find_execute_pin(),g.tail);assert alt.try_create_connection(n.find_execute_pin());g.tail=n.find_then_pin()
g.action('Panel',X=732,Y=103,W=421,H=580,Tint='(R=0.016,G=0.01,B=0.008,A=0.94)')
label('MARBLE SHOP',750,126,1.35,accent)
label(g.textnum('크레딧 ',g.get('Credits')),750,171)
label(g.textnum('구매 ',g.get('MaxBalls',RULES),' / 5'),990,171)
label('중복 등장 가능 · 구매한 칸은 빈칸 유지',750,199,.75)
for i in range(5):
    y=220+62*i;typ=g.rulecall('OfferType',Slot=i).find_output_pin('ReturnValue')
    yes,no=g.branch(g.math('GreaterEqual_IntInt',typ,0));g.tail=yes
    g.action('Panel',X=750,Y=y,W=380,H=56,Tint='(R=0.18,G=0.065,B=0.025,A=1)')
    label(g.rulecall('BallName',Type=typ).find_output_pin('ReturnValue'),764,y+5,.95)
    label(g.rulecall('BallDescription',Type=typ).find_output_pin('ReturnValue'),764,y+32,.75)
    label(g.textnum('구매 ',g.rulecall('BallCost',Type=typ).find_output_pin('ReturnValue')),1020,y+15,.9,accent)
    end=g.tail;g.tail=no
    g.action('Panel',X=750,Y=y,W=380,H=56,Tint='(R=0.035,G=0.025,B=0.02,A=1)')
    label('빈칸 · 구매 완료',764,y+17,.85,'(R=0.46,G=0.40,B=0.34,A=1)');join(end)
g.action('Panel',X=750,Y=532,W=380,H=40,Tint='(R=0.25,G=0.10,B=0.035,A=1)')
label('남은 상품 리롤  [무료]',820,541,.95,accent)
label(g.textnum('철거권 ',g.get('RemovalTickets',RULES),'개 · 첫 발사 전 사용'),750,582,.8)
for i in range(5):
    yes,no=g.branch(g.math('Greater_IntInt',g.get('MaxBalls',RULES),i));g.tail=yes
    typ=g.call('/Script/Engine.KismetArrayLibrary:Array_Get',TargetArray=g.get('BallQueue',RULES),Index=i).find_output_pin('Item')
    label(g.rulecall('BallName',Type=typ).find_output_pin('ReturnValue'),750+76*i,611,.65);join(no)
label(g.get('Message'),750,643,.64)
g.action('DrawSideArrow',Caption='테이블')
for bp in (RULES,TABLE,HUD):B.compile_blueprint(bp)
for bp in (RULES,TABLE,HUD):assert u.EditorAssetLibrary.save_loaded_asset(bp)
u.log('WEIGHTED_BALL_SHOP_APPLIED')
