"""Central free round choices and per-piece hex inventory. Run in UE editor, outside PIE."""
import sys,math,json,traceback
import unreal as u
from pathlib import Path
project_dir=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir()))
sys.path.insert(0,str(project_dir/'Tools'))
report_dir=project_dir/'Saved'/'Tests' if Path(__file__).parent.name=='Tools' else Path(__file__).parent
report_dir.mkdir(parents=True,exist_ok=True)
from blueprint_graph import *
h={}
exec(compile((Path(sys.path[0])/'apply_gimmicks.py').read_text(encoding='utf-8-sig').split('with toolset_registry.tool_raising_exceptions():')[0],'<helpers>','exec'),h)
h['BPS'].update(hud=HUD,rules=RULES)
oldlang=u.InternationalizationLibrary.get_current_language()
u.InternationalizationLibrary.set_current_language('en',False)
scope=h['toolset_registry'].tool_raising_exceptions();scope.__enter__()
installed='ObstacleUIVersion' in B.list_variables(HUD) and B.get_default_object(HUD).get_editor_property('ObstacleUIVersion')==1
def code(name,params,body):
 if installed and name not in ('ObstacleUILine','DrawBumperSlots'):return
 u.log('OBSTACLE_UI_BUILD '+name)
 h['function'](HUD,name,params,'(fn '+name+' ('+' '.join(n for n,t in params)+') '+body+')')
 B.compile_blueprint(HUD,warnings_as_errors=True)
def returning(name,params,kind,body):
 if installed and name!='HandleObstacleUI':return
 u.log('OBSTACLE_UI_BUILD '+name)
 g=Graph(HUD,name)
 if len(B.find_nodes(g.g))==1:
  for n,t in params:g.e.add_graph_input_parameter(n,B._make_variable_type(t))
  g.e.add_graph_output_parameter('ReturnValue',B._make_variable_type(kind));g.ret(False if kind=='bool' else 0)
 h['rebuild_returning'](HUD,name,'(fn '+name+' ('+' '.join(n for n,t in params)+') '+body+')')
 B.compile_blueprint(HUD,warnings_as_errors=True)
def arr(n,i):return f'(Utilities|Array|Get(acopy) (|Get{n}) {i})'
P='(R=0.035,G=0.018,B=0.013,A=0.98)';F=h['FRAME'];T=h['TEXT'];S=h['SUB'];A='(R=1,G=0.55,B=0.20,A=1)'
def label(text,x,y,size=.8,tint=T,center=False):
 return f'(|'+('LabelCentered :CenterX' if center else 'Label :X')+f' {x} :Y {y} :Caption {text} :Size {size} :Tint "{tint}")'
def panel(x,y,w,ht,tint=P):return f'(|Panel :X {x} :Y {y} :W {w} :H {ht} :Tint "{tint}")'
def frame(x,y,w,ht,tint=F,line=1.5):return f'(|Frame :X {x} :Y {y} :W {w} :H {ht} :Tint "{tint}" :Line {line})'
try:
 h['add_variables'](HUD,[('InventoryPieces','int',h['ContainerType'].ARRAY),('InventoryPage','int',None),('InventorySelected','int',None),('ObstacleUIVersion','int',None)],'Obstacle UI')
 B.compile_blueprint(HUD)
 # Native line drawing shares the existing HUD coordinate transform.
 g=Graph(HUD,'ObstacleUILine',True)
 if 'X1' not in [p.name for p in B._get_node_info(g.entry.get_owning_node()).output_pins]:
  for n,t in [('X1','float'),('Y1','float'),('X2','float'),('Y2','float'),('Tint','LinearColor'),('Thickness','float')]:g.e.add_graph_input_parameter(n,B._make_variable_type(t))
 B.compile_blueprint(HUD)
 old_factory=h['make_node']
 def factory(graph,type_id,pos,declaring_class=None):
  native={'Native|DrawLine':'/Script/Engine.HUD:DrawLine','Math|Float|Abs':'/Script/Engine.KismetMathLibrary:Abs'}
  if type_id in native:
   node=u.BlueprintGraphEditor.get_graph_editor(graph).add_call_function_node(native[type_id]);node.set_node_pos(pos);return node
  return old_factory(graph,type_id,pos,declaring_class)
 h['make_node']=factory
 code('ObstacleUILine',[(n,'LinearColor' if n=='Tint' else 'float') for n in ['X1','Y1','X2','Y2','Tint','Thickness']],'''(bind ox (|GetOffsetX)) (bind oy (|GetOffsetY))
 (Native|DrawLine :StartScreenX (+ ox (* X1 (|GetScaleHUD))) :StartScreenY (+ oy (* Y1 (|GetScaleHUD)))
 :EndScreenX (+ ox (* X2 (|GetScaleHUD))) :EndScreenY (+ oy (* Y2 (|GetScaleHUD))) :LineColor Tint :LineThickness (* Thickness (|GetScaleHUD)))''')
 code('ObstacleStroke',[(n,'LinearColor' if n=='Tint' else 'float') for n in ['X','Y','R','AX','AY','BX','BY','Thickness','Tint']],'''
 (|ObstacleUILine :X1 (+ X (* R AX)) :Y1 (+ Y (* R AY)) :X2 (+ X (* R BX)) :Y2 (+ Y (* R BY)) :Thickness Thickness :Tint Tint)''')
 def line(x1,y1,x2,y2,th=2,tint='Tint'):
  return f'(|ObstacleStroke :X X :Y Y :R R :AX {x1:.5f} :AY {y1:.5f} :BX {x2:.5f} :BY {y2:.5f} :Thickness {th} :Tint {tint})'
 def ring(cx,cy,r,segments=20):
  return ' '.join(line(cx+r*math.cos(i*2*math.pi/segments),cy+r*math.sin(i*2*math.pi/segments),cx+r*math.cos((i+1)*2*math.pi/segments),cy+r*math.sin((i+1)*2*math.pi/segments),3) for i in range(segments))
 params=[('X','float'),('Y','float'),('R','float'),('Tint','LinearColor')]
 code('ObstacleHex',params,' '.join(line(math.cos(math.radians(30+i*60)),math.sin(math.radians(30+i*60)),math.cos(math.radians(90+i*60)),math.sin(math.radians(90+i*60))) for i in range(6)))
 icons=[ring(0,0,.72)+ring(0,0,.42),line(-.65,.55,.65,-.55,6),line(-.65,-.55,.65,.55,6),ring(0,0,.45)+' '.join(line(.58*math.cos(i*math.pi/4),.58*math.sin(i*math.pi/4),.95*math.cos(i*math.pi/4),.95*math.sin(i*math.pi/4),3) for i in range(8)),line(-.6,-.65,-.6,.35,6)+line(-.6,.35,0,.65,6)+line(0,.65,.6,.35,6)+line(.6,.35,.6,-.65,6),ring(0,0,.75)+line(0,-.45,0,.45,4)+line(-.3,0,.3,0,4),ring(-.3,-.15,.55)+ring(.3,.15,.55),line(-.8,0,.8,0,5)+line(.8,0,.2,-.6,5)+line(.8,0,.2,.6,5),line(-.65,-.75,-.65,.75,5)+line(.65,-.75,.65,.75,5)+ring(-.18,0,.22)+ring(.3,0,.22),line(-.75,-.35,.75,.35,7)+ring(0,0,.2)+line(.1,-.85,.65,-.65,3)+line(.65,-.65,.35,-.45,3)]
 for i,icon in enumerate(icons):code('ObstacleIcon'+str(i),params,icon)
 code('ObstacleIcon',[('Type','int')]+params,' '.join(f'(if (== Type {i}) (|ObstacleIcon{i} :X X :Y Y :R R :Tint Tint))' for i in range(10)))
 code('RebuildObstacleInventory',[],f'''
 (Utilities|Array|Clear (|GetInventoryPieces))
 (for kind (range (Utilities|Array|Length (|GetStock)))
  (for count (range {arr('Stock','kind')}) (Utilities|Array|Add (|GetInventoryPieces) kind)))
 (bind total (Utilities|Array|Length (|GetInventoryPieces)))
 (if (< total 1) (|SetInventoryPage 0) (|SetInventorySelected -1)
  (else
   (if (>= (* (|GetInventoryPage) 12) total) (|SetInventoryPage 0))
   (if (not (Utilities|Array|IsValidIndex (|GetInventoryPieces) (|GetInventorySelected))) (|SetInventorySelected -1))
   (if (>= (|GetInventorySelected) 0)
    (if (!= {arr('InventoryPieces','(|GetInventorySelected)')} (|GetSelected)) (|SetInventorySelected -1)))
   (for i (range total)
    (if (and (< (|GetInventorySelected) 0) (== {arr('InventoryPieces','i')} (|GetSelected))) (|SetInventorySelected i)))))''')
 code('FocusObstacleStock',[],'''(|SetInventorySelected -1) (|RebuildObstacleInventory)
 (if (>= (|GetInventorySelected) 0) (|SetInventoryPage (/ (|GetInventorySelected) 12)))''')
 returning('ObstacleModalOpen',[],'bool','''(return (and (== (|GetPhase) 0) (and (|GetChoicePending :self (|GetRules)) (> (|GetMaxBalls :self (|GetRules)) (|GetBallsUsed :self (|GetRules))))))''')
 # Explicit coordinates are also used by input, so hitboxes and visuals cannot drift.
 slots=[(932+(i%3)*84+(18 if (i//3)%2 else 0),365+(i//3)*65) for i in range(12)]
 draw=panel(886,290,295,382)+frame(886,290,295,382)+label('"보유 기물"',904,305,1.0)+label('(Utilities|String|BuildString(Integer) "" "" (Utilities|Array|Length (|GetInventoryPieces)) "개")',1118,309,.75)
 draw+='(bind (clicked px py) (|ClickedHudPoint))'
 for i,(x,y) in enumerate(slots):
  idx=f'(+ (* (|GetInventoryPage) 12) {i})';item=arr('InventoryPieces',idx)
  draw+=f'''(if (Utilities|Array|IsValidIndex (|GetInventoryPieces) {idx})
   (|ObstacleHex :X {x} :Y {y} :R 32.0 :Tint "{F}")
   (if (== (|GetInventorySelected) {idx}) (|ObstacleHex :X {x} :Y {y} :R 34.0 :Tint "{A}"))
   (|ObstacleIcon :Type {item} :X {x} :Y {y} :R 19.0 :Tint {arr('ObstacleTints',item)}))'''
 draw+=f'''(if (== (Utilities|Array|Length (|GetInventoryPieces)) 0)
 {label('"보유한 기물이 없습니다"',1033,420,.78,center=True)}
 {label('"매 라운드 1개를 선택하세요"',1033,452,.66,S,True)})'''
 draw+=label('"< 이전"',904,609,.68)+label('"다음 >"',1110,609,.68)
 draw+=label('(Utilities|String|BuildString(Integer) "" "" (+ (|GetInventoryPage) 1) " 페이지")',1033,609,.66,S,True)
 draw+=f'''(if (Utilities|Array|IsValidIndex (|GetInventoryPieces) (|GetInventorySelected))
 {label(arr('ObstacleNames','(|GetSelected)'),1033,641,.74,center=True)})'''
 modal=panel(0,0,1200,750,'(R=0,G=0,B=0,A=0.62)')+label('"이번 라운드의 기물을 선택하세요"',600,88,1.25,center=True)+label('"무료 · 3개 중 1개 · 선택한 기물은 보관함에 추가됩니다"',600,123,.7,S,True)
 for row,x in enumerate([98,440,782]):
  item=arr('ObstacleOffers',str(row));cx=x+160
  modal+=f'''(if (Utilities|Array|IsValidIndex (|GetObstacleOffers) {row})
   {panel(x,165,320,418)} {frame(x,165,320,418)}
   (if (|InsideRect :PointX px :PointY py :X {x} :Y 165.0 :W 320.0 :H 418.0) {frame(x,165,320,418,A,3)})
   {panel(x+60,195,200,170,'(R=0.018,G=0.010,B=0.008,A=1)')}
   (|ObstacleIcon :Type {item} :X {cx} :Y 280.0 :R 58.0 :Tint {arr('ObstacleTints',item)})
   {label(arr('ObstacleNames',item),cx,393,1.1,center=True)}
   {label(arr('ObstacleDescriptions',item),cx,445,.70,S,True)}
   {panel(x+30,510,260,43,'(R=0.14,G=0.065,B=0.025,A=1)')}
   {label('"무료로 선택"',cx,519,.82,A,True)})'''
 code('DrawBumperSlots',[],f'(|EnsureObstacleOffers) (|RebuildObstacleInventory) {draw} (|DrawTiltCount) (|DrawSideArrow :Caption "상점") (|DrawLiveScore) (if (|ObstacleModalOpen) {modal})')
 code('UpdateInventory',[],'''(if (and (== (|GetStation) 1) (not (|ObstacleModalOpen)))
 (|RebuildObstacleInventory)
 (bind pc (HUD|GetOwningPlayerController))
 (bind (clicked px py) (|ClickedHudPoint))
 (if (|InsideRect :PointX px :PointY py :X 886.0 :Y 290.0 :W 295.0 :H 382.0)
 (if (and (Game|Player|WasInputKeyJustPressed pc "MouseScrollDown") (< (* (+ (|GetInventoryPage) 1) 12) (Utilities|Array|Length (|GetInventoryPieces)))) (|SetInventoryPage (+ (|GetInventoryPage) 1)))
 (if (and (Game|Player|WasInputKeyJustPressed pc "MouseScrollUp") (> (|GetInventoryPage) 0)) (|SetInventoryPage (- (|GetInventoryPage) 1)))))''')
 hit='''(if (!= (|GetStation) 1) (return false))
 (if (or (|GetLooking) (|GetBlending)) (return false))
 (|RebuildObstacleInventory)
 (if (|ObstacleModalOpen)
  (if Click
 '''
 for row,x in enumerate([98,440,782]):hit+=f'''(if (|InsideRect :PointX PX :PointY PY :X {x} :Y 165.0 :W 320.0 :H 418.0) (|ChooseOffer :Row {row}) (return true))'''
 hit+=''' ) (return true))
 (if (|InsideRect :PointX PX :PointY PY :X 886.0 :Y 290.0 :W 295.0 :H 382.0)
  (if (and Click (== (|GetPhase) 0))'''
 for i,(x,y) in enumerate(slots):
  idx=f'(+ (* (|GetInventoryPage) 12) {i})'
  # Exact pointy hex containment: |dx| <= sqrt(3)/2 R, |dy| <= R - |dx|/sqrt(3).
  hit+=f'''(if (Utilities|Array|IsValidIndex (|GetInventoryPieces) {idx})
   (if (and (<= (Math|Float|Abs ( - PX {x}.0)) 27.7128) (<= (Math|Float|Abs (- PY {y}.0)) (- 32.0 (* (Math|Float|Abs (- PX {x}.0)) 0.57735))))
    (|SetInventorySelected {idx}) (|SetSelected {arr('InventoryPieces',idx)}) (|SetMessage "기물 선택 완료 · 빈 육각 칸을 클릭해 배치") (return true)))'''
 hit+='''(if (and (> (|GetInventoryPage) 0) (|InsideRect :PointX PX :PointY PY :X 896.0 :Y 598.0 :W 90.0 :H 35.0)) (|SetInventoryPage (- (|GetInventoryPage) 1)) (return true))
 (if (and (< (* (+ (|GetInventoryPage) 1) 12) (Utilities|Array|Length (|GetInventoryPieces))) (|InsideRect :PointX PX :PointY PY :X 1090.0 :Y 598.0 :W 90.0 :H 35.0)) (|SetInventoryPage (+ (|GetInventoryPage) 1)) (return true))) (return true)) (return false)'''
 returning('HandleObstacleUI',[('PX','float'),('PY','float'),('Click','bool')],'bool',hit)
 # Intercept before legacy side-card/world handlers. Return value captures pending state before selection.
 g=Graph(HUD,'PointerInput')
 if not any(B._get_node_info(n).type_id=='|HandleObstacleUI' for n in B.find_nodes(g.g)):
  targets=list(next(p for p in B._get_node_info(g.entry.get_owning_node()).output_pins if p.name=='then').connected_pins)
  g.entry.break_pin_links();g.tail=g.entry
  xy=g.call('ClickedHudPoint')
  call=g.action('HandleObstacleUI',PX=xy.find_output_pin('PointX'),PY=xy.find_output_pin('PointY'),Click=g.arg('Click'))
  yes,no=g.branch(call.find_output_pin('ReturnValue'))
  for dst in targets:assert no.try_create_connection(B._resolve_pin(dst))
 # Older interrupted migrations can leave the original entry guard disconnected.
 guard=g.old('K2Node_IfThenElse_0')
 handler=next(n for n in B.find_nodes(g.g) if B._get_node_info(n).type_id=='|HandleObstacleUI')
 branch=next(p for p in B._get_node_info(handler).output_pins if p.name=='then').connected_pins[0].node
 put(guard.find_execute_pin(),branch.find_output_pin('else'))
 B.compile_blueprint(HUD,warnings_as_errors=True)
 B.get_default_object(HUD).set_editor_property('ObstacleUIVersion',1)
 assert u.EditorAssetLibrary.save_loaded_asset(HUD)
 (report_dir/'obstacle_ui_result.json').write_text(json.dumps({'passed':True,'asset':HUD.get_path_name()}))
except Exception:
 (report_dir/'obstacle_ui_result.json').write_text(json.dumps({'passed':False,'error':traceback.format_exc()}))
 raise
finally:
 scope.__exit__(None,None,None)
 u.InternationalizationLibrary.set_current_language(oldlang,False)

