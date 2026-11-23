"""Show an animated, uncapped physical-hit streak on the table HUD."""
import sys
from pathlib import Path
import unreal as u

sys.path.insert(0, str(Path(__file__).parent))
from blueprint_graph import B, Graph, HUD, ROOT, put

table = u.load_asset(ROOT + 'BP_PinballTable')
mathlib = '/Script/Engine.KismetMathLibrary:'
clock = '/Script/Engine.GameplayStatics:GetTimeSeconds'

def insert_after(g, anchor, append):
    dest = next(p for p in B._get_node_info(anchor).output_pins if p.name == 'then').connected_pins
    g.tail = anchor.find_then_pin()
    g.tail.break_pin_links()
    append()
    for pin in dest:
        put(B._resolve_pin(pin), g.tail)

if 'BumperComboCount' not in B.list_variables(table):
    B.add_variable(table, 'BumperComboCount', 'int')
    B.compile_blueprint(table)
g = Graph(table, 'PlayBumperNote')
nodes = [B._get_node_info(n) for n in B.find_nodes(g.g)]
if not any(n.type_id == '|SetBumperComboCount' for n in nodes):
    def advance():
        first = g.math('EqualEqual_IntInt', g.get('BumperNoteIndex'), 0)
        next_count = g.math('Add_IntInt', g.get('BumperComboCount'), 1)
        value = g.call(mathlib+'SelectInt', A=1, B=next_count, bPickA=first)
        g.set('BumperComboCount', value.find_output_pin('ReturnValue'))
    insert_after(g, next(n.node for n in nodes if n.type_id == '|SetLastBumperNoteTime'), advance)
B.compile_blueprint(table, warnings_as_errors=True)

g = Graph(HUD, 'DrawBumperCombo', True)
def field(name):
    node = g.e.add_get_member_variable_node(name, table.generated_class().get_path_name())
    put(node.find_input_pin('self'), g.get('Table'))
    return node.find_output_pin(name)
def calc(name, **args):
    return g.call(mathlib + name, **args).find_output_pin('ReturnValue')
def clamp(v, cap=1.0):
    return calc('FClamp', Value=v, Min=0.0, Max=cap)
def add(a,b):
    node = B.create_node(g.g, 'Utilities|Operators|Add', u.IntPoint(600, 400))
    inputs = [('A',a),('B',b)]
    for pin,value in sorted(inputs,key=lambda item: not isinstance(item[1], u.BlueprintGraphPin)):
        put(node.find_input_pin(pin),value)
    return node.find_output_pin('ReturnValue')
def sub(a,b): return g.math('Subtract_DoubleDouble', a,b)
def mul(a,b): return g.math('Multiply_DoubleDouble', a,b)
def tint(r,green,b,a): return calc('MakeColor',R=r,G=green,B=b,A=a)
def label(text,x,y,size,color):
    g.action('Label', Caption=text, X=x,Y=y,Size=size,Tint=color)

g.reject(g.math('NotEqual_IntInt', g.get('Phase'), 1))
count = field('BumperComboCount')
g.reject(g.math('Less_IntInt', count, 2))
age = sub(g.call(clock).find_output_pin('ReturnValue'), field('LastBumperNoteTime'))
g.reject(g.math('GreaterEqual_DoubleDouble', age, .85))
# A fresh kick on each hit, with a short damped sideways wobble and upward travel.
kick = clamp(sub(1.0,mul(age,5.0)))
alpha = clamp(mul(sub(.85,age),4.6))
tier = clamp(calc('Conv_IntToDouble', InInt=count), 24.0)
size = add(add(2.5,mul(tier,.078)),mul(kick,1.15))
x = add(72.0,mul(mul(kick,8.0),calc('Sin', A=mul(age,85.0))))
y = sub(add(284.0,mul(kick,20.0)),mul(tier,.85))
digits = g.textnum('',count)
label(digits,add(x,3.0),add(y,4.0),size,tint(.075,.022,.01,alpha))
label(digits,x,y,size,tint(1.0,.77,.31,alpha))
label('COMBO',73.0,add(y,add(mul(size,18.5),16.0)),.94,tint(1.0,.58,.26,alpha))
B.compile_blueprint(HUD, warnings_as_errors=True)
g = Graph(HUD, 'DrawTable')
if not any(B._get_node_info(n).type_id=='|DrawBumperCombo' for n in B.find_nodes(g.g)):
    insert_after(g,g.old('K2Node_CallFunction_0'),lambda: g.action('DrawBumperCombo'))
B.compile_blueprint(HUD, warnings_as_errors=True)
for bp in (HUD,table):
    assert u.EditorAssetLibrary.save_loaded_asset(bp,False)
u.log('COMBO_HUD_INSTALLED')



