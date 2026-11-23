"""Migrate movement_fix Blueprints to purchased-ball stages (UE 5.8, editor closed).

Run UnrealEditor-Cmd project -run=pythonscript -script=<this file> -culture=en
-unattended -nullrhi. All runtime logic is compiled into the two Blueprint assets.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from blueprint_graph import *

assert 'ChooseObstacle' not in {x.get_name() for x in B.list_graphs(HUD)}, 'Migration already applied; edit the migrated assets directly.'
for name,kind,value in [('StageStarted','bool',False), ('ChoicePending','bool',True), ('RemovalTickets','int',0), ('BallPrice','int',3)]:
    rulesvar(name,kind,value)
B.get_default_object(RULES).set_editor_property('MaxBalls',0)

# A stage buys its complete launch budget before its first launch.
g=Graph(HUD,'Purchase',True)
g.reject(g.math('NotEqual_IntInt',g.get('Phase'),0))
g.reject(g.get('StageStarted',RULES),'구슬 구매는 스테이지 시작 전에만 가능합니다')
g.reject(g.math('NotEqual_IntInt',g.get('State',RULES),0))
g.reject(g.math('Less_IntInt',g.get('Credits'),g.get('BallPrice',RULES)),'크레딧 부족')
g.set('Credits',g.math('Subtract_IntInt',g.get('Credits'),g.get('BallPrice',RULES)))
g.set('MaxBalls',g.math('Add_IntInt',g.get('MaxBalls',RULES),1),RULES)
g.msg(g.textnum('구슬 ',g.get('MaxBalls',RULES),'개 구매 · 테이블에서 장애물을 선택하세요'))

# Selecting a card grants one item once per round; unplaced stock carries over.
g=Graph(HUD,'ChooseObstacle',True)
g.e.add_graph_input_parameter('Type',B._make_variable_type('int'))
g.reject(g.math('NotEqual_IntInt',g.get('Phase'),0))
g.reject(g.math('Less_IntInt',g.arg('Type'),0))
g.reject(g.math('Greater_IntInt',g.arg('Type'),2))
g.reject(g.math('LessEqual_IntInt',g.get('MaxBalls',RULES),g.get('BallsUsed',RULES)),'상점에서 구슬을 먼저 구매하세요')
g.reject(g.math('Not_PreBool',g.get('ChoicePending',RULES)),'이번 라운드의 장애물은 이미 선택했습니다')
# Array get/set use engine spawners so their wildcard pins specialize to int.
arr=g.get('Stock')
read=g.call('/Script/Engine.KismetArrayLibrary:Array_Get',TargetArray=arr,Index=g.arg('Type'))
g.action('/Script/Engine.KismetArrayLibrary:Array_Set',TargetArray=arr,Index=g.arg('Type'),Item=g.math('Add_IntInt',read.find_output_pin('Item'),1),bSizeToFit=False)
g.set('Selected',g.arg('Type'))
g.set('ChoicePending',False,RULES)
g.msg('장애물 선택 완료 · 빈 칸에 배치 후 SPACE 발사')
B.compile_blueprint(HUD)

# Keep original launch physics, but protect all launch entry points.
g=Graph(HUD,'StartRound')
old=g.old('K2Node_IfThenElse_0').find_execute_pin()
g.entry.break_pin_links()
g.reject(g.math('NotEqual_IntInt',g.get('Phase'),0))
g.set('Charging',False)
g.reject(g.math('LessEqual_IntInt',g.get('MaxBalls',RULES),g.get('BallsUsed',RULES)),'상점에서 구슬을 구매하세요')
g.reject(g.get('ChoicePending',RULES),'장애물 3개 중 하나를 먼저 선택하세요')
g.set('StageStarted',True,RULES)
put(old,g.tail)

# Only an active launch can settle; duplicate events cannot grant score or tickets.
g=Graph(HUD,'Settle')
original=g.old('K2Node_CallFunction_0').find_execute_pin()
g.entry.break_pin_links()
g.reject(g.math('NotEqual_IntInt',g.get('Phase'),1))
put(original,g.tail)

# Build access opens between balls. Demolition has a separate stage-start gate.
g=Graph(RULES,'IsBoardLocked',True)
g.ret(g.math('NotEqual_IntInt',g.get('Phase',HUD),0))
g=Graph(RULES,'IsCellLocked',True)
g.ret(g.math('NotEqual_IntInt',g.get('Phase',HUD),0))
g=Graph(HUD,'EditCell')
occupied=g.old('K2Node_IfThenElse_1').find_output_pin('then')
occupied.break_pin_links(); g.tail=occupied
g.reject(g.math('Not_PreBool',g.arg('Remove')),'철거하려면 우클릭하세요')
g.reject(g.get('StageStarted',RULES),'철거권은 스테이지 첫 발사 전에만 사용 가능합니다')
g.reject(g.math('LessEqual_IntInt',g.get('RemovalTickets',RULES),0),'철거권이 없습니다')
g.set('RemovalTickets',g.math('Subtract_IntInt',g.get('RemovalTickets',RULES),1),RULES)
put(g.old('K2Node_CallArrayFunction_1').find_execute_pin(),g.tail)
put(g.pin('K2Node_VariableSet_1','Message'),'철거 완료 · 철거권 1개 사용')
# Do not let placement precede the required choice.
empty=g.old('K2Node_IfThenElse_1').find_output_pin('else')
empty.break_pin_links(); g.tail=empty
g.reject(g.get('ChoicePending',RULES),'오른쪽 장애물 카드 3개 중 하나를 선택하세요')
put(g.old('K2Node_IfThenElse_2').find_execute_pin(),g.tail)

# Stage completion grants tickets once. AdvanceRound no longer destroys obstacles.
g=Graph(RULES,'RecordBall')
passed=next(n for n in g.nodes.values() if n.get_class().get_name()=='K2Node_VariableSet' and any(p.name=='State' and p.value=='1' for p in B._get_node_info(n).input_pins))
links=passed.find_then_pin()
info=B._get_node_info(passed)
nextid=next(p for p in info.output_pins if p.name=='then').connected_pins[0]
nextpin=B._resolve_pin(nextid)
links.break_pin_links();g.tail=links
g.set('RemovalTickets',g.math('Add_IntInt',g.get('RemovalTickets'),2))
put(nextpin,g.tail)

g=Graph(RULES,'AdvanceRound')
put(g.old('K2Node_VariableSet_2').find_execute_pin(),g.old('K2Node_VariableSet_0').find_then_pin())
put(g.old('K2Node_VariableSet_4').find_execute_pin(),g.old('K2Node_VariableSet_3').find_then_pin())
tail=g.old('K2Node_VariableSet_7').find_then_pin();tail.break_pin_links();g.tail=tail
g.set('MaxBalls',0);g.set('StageStarted',False);g.set('ChoicePending',True)
put(g.old('K2Node_CallFunction_7').find_execute_pin(),g.tail)

g=Graph(HUD,'NextStage')
# Both a new ball and a new stage require a fresh choice.
n=next(n for n in g.nodes.values() if B._get_node_info(n).type_id=='|SetPhase')
tail=n.find_then_pin(); info=B._get_node_info(n)
target=B._resolve_pin(next(p for p in info.output_pins if p.name=='then').connected_pins[0])
tail.break_pin_links();g.tail=tail;g.set('ChoicePending',True,RULES);put(target,g.tail)
stage=next(n for n in g.nodes.values() if B._get_node_info(n).type_id=='|SetStage')
put(stage.find_input_pin('Stage'),g.get('CurrentRound',RULES))

g=Graph(RULES,'NextStation')
# The first ball goes to the shop, subsequent balls return to the table.
put(g.old('K2Node_Select_0').find_input_pin('Index'),g.get('StageStarted'))
g=Graph(RULES,'ReadyMessage',True)
yes,no=g.branch(g.get('StageStarted'))
g.tail=yes;g.ret('다음 라운드 · 장애물 3개 중 하나를 선택하세요')
g.tail=no;g.ret('구슬 구매 · 첫 발사 전 철거권 사용 가능')

# Table cards: intercept UI clicks before the world-cell ray cast.
g=Graph(HUD,'PointerInput')
tail=g.old('K2Node_IfThenElse_10').find_output_pin('then');tail.break_pin_links();g.tail=tail
x=g.old('K2Node_PromotableOperator_1').find_output_pin('ReturnValue')
y=g.old('K2Node_PromotableOperator_3').find_output_pin('ReturnValue')
for index in range(3):
    inside=g.call('InsideRect',PointX=x,PointY=y,X=886,Y=290+130*index,W=295,H=122).find_output_pin('ReturnValue')
    yes,no=g.branch(inside);g.tail=yes
    click,other=g.branch(g.arg('Click'));g.tail=click
    g.action('ChooseObstacle',Type=index)
    g.tail=no
put(g.old('K2Node_IfThenElse_11').find_execute_pin(),g.tail)
# Shop has a single purchase row, whole row clickable.
put(g.old('K2Node_MacroInstance_0').find_input_pin('LastIndex'),0)
put(g.old('K2Node_CallFunction_24').find_execute_pin(),g.old('K2Node_IfThenElse_8').find_output_pin('then'))

# Shop drawing in the existing warm HUD style.
g=Graph(HUD,'DrawShop',True)
bg='(R=0.016,G=0.01,B=0.008,A=0.94)'
ink='(R=0.86,G=0.79,B=0.66,A=1)'
accent='(R=0.95,G=0.36,B=0.16,A=1)'
def label(text,x,y,size=1,tint=ink): g.action('Label',Caption=text,X=x,Y=y,Size=size,Tint=tint)
g.action('Panel',X=732,Y=103,W=421,H=560,Tint=bg)
label('MARBLE SHOP',750,131,1.5,accent)
label(g.textnum('크레딧  ',g.get('Credits')),750,183,1.1)
g.action('Panel',X=750,Y=233,W=380,H=70,Tint='(R=0.18,G=0.065,B=0.025,A=1)')
label('구슬 1개 구매',768,246,1.1)
label(g.textnum('',g.get('BallPrice',RULES),' 크레딧'),1000,262,.9)
label(g.textnum('구매 구슬 / 전체 라운드  ',g.get('MaxBalls',RULES)),750,330,1.05)
label(g.textnum('남은 구슬  ',g.math('Subtract_IntInt',g.get('MaxBalls',RULES),g.get('BallsUsed',RULES))),750,371)
label(g.textnum('철거권  ',g.get('RemovalTickets',RULES),'개'),750,417)
label('첫 발사 후 구슬 추가 구매 불가',750,461,.9)
label('매 라운드 테이블에서 장애물 1개 선택',750,494,.9)
label('철거권: 첫 발사 전 장애물 우클릭',750,527,.9)
label(g.get('Message'),750,574,.75)
g.action('DrawSideArrow',Caption='테이블')

g=Graph(HUD,'DrawTable')
put(g.pin('K2Node_CallFunction_9','Caption'),'좌클릭 배치 · 우클릭 철거권')
g=Graph(HUD,'InitializeBoard')
put(g.pin('K2Node_VariableSet_11','Message'),'상점에서 구슬 구매 후 테이블에서 장애물 선택')
g=Graph(RULES,'ContinueLabel')
put(g.pin('K2Node_FunctionResult_1','ReturnValue'),'다음 스테이지 · 철거권 +2  [SPACE]')
put(g.pin('K2Node_FunctionResult_3','ReturnValue'),'다음 라운드 · 장애물 선택  [SPACE]')
g=Graph(RULES,'StatusLine')
put(g.pin('K2Node_CallFunction_1','Prefix'),'스테이지 ')

# Choice UI explicitly distinguishes the free reward from stored items.
g=Graph(HUD,'DrawSlot')
g.tail=g.old('K2Node_CallFunction_13').find_then_pin()
yes,no=g.branch(g.get('ChoicePending',RULES))
g.tail=yes
g.action('Label',Caption='클릭: 무료 선택',X=1002,Y=g.math('Add_DoubleDouble',g.old('K2Node_PromotableOperator_1').find_output_pin('ReturnValue'),94),Size=.78,Tint='(R=0.95,G=0.36,B=0.16,A=1)')
g.tail=no
g.action('Label',Caption='선택 완료 · 보관함 사용',X=1002,Y=g.math('Add_DoubleDouble',g.old('K2Node_PromotableOperator_1').find_output_pin('ReturnValue'),94),Size=.72,Tint='(R=0.56,G=0.46,B=0.36,A=1)')
g=Graph(HUD,'DrawTable')
put(g.pin('K2Node_CallFunction_6','Caption'),g.textnum('철거권 ',g.get('RemovalTickets',RULES),'개 · 첫 발사 전 사용'))
put(g.pin('K2Node_CallFunction_6','Size'),.82)

for bp in (RULES,HUD):
    B.compile_blueprint(bp)
for bp in (RULES,HUD):
    assert u.EditorAssetLibrary.save_loaded_asset(bp)
u.log('BALL_PROGRESSION_APPLIED')
