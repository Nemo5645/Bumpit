from pathlib import Path
import unreal as u, sys
sys.path.insert(0,str(Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir()))/'Tools'))
from blueprint_graph import *
from editor_toolset.toolsets.actor import ActorTools as A
table=u.load_asset(ROOT+'BP_PinballTable')
tp=ROOT+'BP_PinballTable.BP_PinballTable_C'
materials=['MI_Cell_950_960_990','MI_Ball_Score','MI_Ball_Demolition','MI_Ball_Heavy','MI_Ball_Light','MI_Ball_Rubber','MI_Ball_Lucky']
ys=[230,140,50,-40,-130]
def rv(n):return n.find_output_pin('ReturnValue')
def vec(x,y,z):return f'(X={x},Y={y},Z={z})'
def hook(g,node,do):
    pin=node.find_then_pin()
    links=next(p for p in B._get_node_info(node).output_pins if p.name=='then').connected_pins
    dest=[B._resolve_pin(p) for p in links]
    pin.break_pin_links();g.tail=pin;do()
    for p in dest:assert g.tail.try_create_connection(p)
def param(g,name,kind):g.e.add_graph_input_parameter(name,B._make_variable_type(kind))
def compile(bp):
    B.compile_blueprint(bp)
    assert 'ERROR' not in str(bp.get_editor_property('status')).upper()
assert 'ShopFocusKey' not in B.list_variables(HUD)
for i,y in enumerate(ys):
    c=A.add_component(table,u.StaticMeshComponent.static_class(),f'ShopMarble{i}')
    c.set_static_mesh(u.load_asset('/Engine/BasicShapes/Sphere'))
    c.set_absolute(True,True,True)
    c.set_editor_property('relative_location',u.Vector(-1110,y,148))
    c.set_editor_property('relative_scale3d',u.Vector(.42,.42,.42))
    c.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
    c.set_editor_property('generate_overlap_events',False)
    c.set_visibility(False)
    B.add_variable(HUD,f'ShopDisplayKey{i}','int')
compile(table)
B.add_variable(HUD,'ShopFocusKey','int')
B.add_variable(HUD,'ShopSliding','bool')
compile(HUD)
for i in range(5):
    g=Graph(HUD,f'SyncMarble{i}')
    typ=rv(g.rulecall('OfferType',Slot=i))
    key=g.math('Add_IntInt',typ,2)
    g.reject(g.math('EqualEqual_IntInt',key,g.get(f'ShopDisplayKey{i}')))
    g.set(f'ShopDisplayKey{i}',key)
    comp=g.e.add_get_member_variable_node(f'ShopMarble{i}',tp)
    put(comp.find_input_pin('self'),g.get('Table'))
    mesh=comp.find_output_pin(f'ShopMarble{i}')
    g.action('/Script/Engine.SceneComponent:SetVisibility',self=mesh,bNewVisibility=g.math('GreaterEqual_IntInt',typ,0))
    for k,mat in enumerate(materials):
        yes,no=g.branch(g.math('EqualEqual_IntInt',typ,k));g.tail=yes
        g.action('/Script/Engine.PrimitiveComponent:SetMaterial',self=mesh,ElementIndex=0,Material=f'/Game/Bumpit/Materials/{mat}.{mat}')
        g.tail=no
g=Graph(HUD,'ShopPointerKey')
g.e.add_graph_output_parameter('ReturnValue',B._make_variable_type('int'));g.e.set_is_pure_function(True)
pt=g.call('ClickedHudPoint')
for i in range(5):
    hit=rv(g.call('InsideRect',PointX=pt.find_output_pin('PointX'),PointY=pt.find_output_pin('PointY'),X=750,Y=220+62*i,W=380,H=56))
    yes,no=g.branch(g.math('BooleanAND',hit,g.math('GreaterEqual_IntInt',rv(g.rulecall('OfferType',Slot=i)),0)));g.tail=yes;g.ret(i+1);g.tail=no
g.ret(0)
compile(HUD)
g=Graph(HUD,'AimShopCamera')
param(g,'Key','int')
g.set('ShopFocusKey',g.arg('Key'))
g.set('ShopSliding',True)
overview=(vec(-537,75,193),vec(-1110,-55,140),53)
def move(g,eye,target,fov):
    g.action('MoveView',Eye=eye,Target=target,Fov=fov)
    g.set('Blending',False)
for i,y in enumerate(ys):
    yes,no=g.branch(g.math('EqualEqual_IntInt',g.arg('Key'),i+1));g.tail=yes
    move(g,vec(-956,y,177),vec(-1110,y-34,148),42)
    g.tail=no
move(g,*overview)
compile(HUD)
g=Graph(HUD,'TickShopDisplay')
param(g,'Delta','float')
g.reject(g.math('NotEqual_IntInt',g.get('Station'),2))
for i in range(5):g.action(f'SyncMarble{i}')
g.reject(g.get('Blending'))
g.reject(g.get('Looking'))
key=rv(g.call('ShopPointerKey'))
yes,no=g.branch(g.math('NotEqual_IntInt',key,g.get('ShopFocusKey')));g.tail=yes
g.action('AimShopCamera',Key=key)
join=g.e.add_branch_node();put(join.find_input_pin('Condition'),g.get('ShopSliding'));put(join.find_execute_pin(),g.tail);assert no.try_create_connection(join.find_execute_pin())
g.tail=join.find_output_pin('then')
g.set('Blending',True);g.action('UpdateView',Delta=g.arg('Delta'));g.set('ShopSliding',g.get('Blending'));g.set('Blending',False)
compile(HUD)
g=Graph(HUD,'UpdateBoard')
node=next(n for n in g.nodes.values() if B._get_node_info(n).type_id=='|UpdateView')
hook(g,node,lambda:g.action('TickShopDisplay',Delta=g.arg('Delta')))
g=Graph(HUD,'Visit')
hook(g,g.entry.get_owning_node(),lambda:(g.set('ShopFocusKey',0),g.set('ShopSliding',False)))
for n in g.nodes.values():
    if B._get_node_info(n).type_id=='|MoveView':
        eye=n.find_input_pin('Eye')
        items=next(p.connected_pins for p in B._get_node_info(n).input_pins if p.name=='Eye')
        src=B._resolve_pin(items[0]).get_owning_node()
        if any(p.name=='X' and float(p.value)==-537 for p in B._get_node_info(src).input_pins):
            put(eye,overview[0]);put(n.find_input_pin('Target'),overview[1])
compile(HUD)
for bp in (table,HUD):assert u.EditorAssetLibrary.save_loaded_asset(bp)
u.log('SHOP_DISPLAY_OK')
