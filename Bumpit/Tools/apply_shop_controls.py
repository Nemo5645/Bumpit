"""Paid escalating rerolls and Q to rotate unplayed purchased balls. Run once."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from blueprint_graph import *

assert 'RerollCost' not in B.list_variables(RULES), 'Already applied'
rulesvar('RerollCost','int',5)
B.add_variable(HUD,'CycleSavedType','int')
B.compile_blueprint(HUD)

def prepend(g,fn):
    info=B._get_node_info(g.entry.get_owning_node())
    links=next(p for p in info.output_pins if p.name=='then').connected_pins
    targets=[B._resolve_pin(p) for p in links]
    g.entry.break_pin_links()
    fn()
    for target in targets: assert g.tail.try_create_connection(target)

g=Graph(RULES,'ResetShop')
prepend(g,lambda:g.set('RerollCost',5))
B.compile_blueprint(RULES)
g=Graph(HUD,'RerollShop',True)
g.reject(g.math('NotEqual_IntInt',g.get('Phase'),0))
g.reject(g.get('StageStarted',RULES),'리롤은 스테이지 첫 발사 전에만 가능합니다')
g.reject(g.math('NotEqual_IntInt',g.get('State',RULES),0))
g.reject(g.math('GreaterEqual_IntInt',g.get('MaxBalls',RULES),5),'구매 완료 · 테이블로 이동하세요')
g.reject(g.math('Less_IntInt',g.get('Credits'),g.get('RerollCost',RULES)),'크레딧이 부족합니다')
g.set('Credits',g.math('Subtract_IntInt',g.get('Credits'),g.get('RerollCost',RULES)))
g.action(CP[RULES]+':RerollOffers',self=g.get('Rules'))
g.set('RerollCost',g.math('Add_IntInt',g.get('RerollCost',RULES),5),RULES)
g.msg('리롤 완료 · 구매한 칸은 빈칸 유지')

g=Graph(HUD,'CycleBall',True)
g.reject(g.math('NotEqual_IntInt',g.get('Phase'),0))
g.reject(g.math('NotEqual_IntInt',g.get('State',RULES),0))
g.reject(g.math('Less_IntInt',g.get('Station'),1))
g.reject(g.math('Greater_IntInt',g.get('Station'),2))
g.reject(g.get('Charging'))
g.reject(g.get('Blending'))
g.reject(g.get('Looking'))
g.reject(g.math('Greater_DoubleDouble',g.get('Power'),0))
g.reject(g.math('LessEqual_IntInt',g.math('Subtract_IntInt',g.get('MaxBalls',RULES),g.get('BallsUsed',RULES)),1),'바꿀 수 있는 남은 공이 없습니다')
g.set('CycleSavedType',g.call('/Script/Engine.KismetArrayLibrary:Array_Get',TargetArray=g.get('BallQueue',RULES),Index=g.get('BallsUsed',RULES)).find_output_pin('Item'))
g.action('/Script/Engine.KismetArrayLibrary:Array_Remove',TargetArray=g.get('BallQueue',RULES),IndexToRemove=g.get('BallsUsed',RULES))
g.action('/Script/Engine.KismetArrayLibrary:Array_Add',TargetArray=g.get('BallQueue',RULES),NewItem=g.get('CycleSavedType'))
g.action('RefreshBall')
g.msg('발사할 공 변경 · Q로 다음 공 선택')
B.compile_blueprint(HUD)

g=Graph(HUD,'HandleBallSwitchInput',True)
pc=g.call('/Script/Engine.HUD:GetOwningPlayerController').find_output_pin('ReturnValue')
g.reject(g.math('Not_PreBool',g.call('/Script/Engine.PlayerController:WasInputKeyJustPressed',self=pc,Key='Q').find_output_pin('ReturnValue')))
g.action('CycleBall')
B.compile_blueprint(HUD)
g=Graph(HUD,'UpdateBoard')
prepend(g,lambda:g.action('HandleBallSwitchInput'))

g=Graph(HUD,'DrawShop')
label=next(n for n in B.find_nodes(g.g) if any(p.name=='Caption' and '남은 상품 리롤' in p.value for p in B._get_node_info(n).input_pins))
put(label.find_input_pin('Caption'),g.textnum('리롤  [',g.get('RerollCost',RULES),' 크레딧]'))
put(label.find_input_pin('X'),800)

# Add a hint within the existing launch panel between launch text and power bar.
g=Graph(HUD,'DrawBallSwitchHint',True)
g.reject(g.math('NotEqual_IntInt',g.get('Phase'),0))
g.action('Label',Caption='Q  공 바꾸기 · 발사 전',X=901,Y=201,Size=.76,Tint='(R=0.95,G=0.70,B=0.30,A=1)')
B.compile_blueprint(HUD)
g=Graph(HUD,'DrawTable')
# Draw after the panel background, before its first title.
panel=g.old('K2Node_CallFunction_0')
links=next(p for p in B._get_node_info(panel).output_pins if p.name=='then').connected_pins
targets=[B._resolve_pin(p) for p in links]
g.tail=panel.find_then_pin();g.tail.break_pin_links();g.action('DrawBallSwitchHint')
for target in targets:assert g.tail.try_create_connection(target)
for bp in (RULES,HUD):
 B.compile_blueprint(bp)
 assert u.EditorAssetLibrary.save_loaded_asset(bp)
u.log('SHOP_CONTROLS_APPLIED')
