"""Companion to apply_action_tiles.py; executed in its namespace."""
code(HUD,'EnsureObstacleOffers',[],'''
 (if (Native|IsValid (|GetRules))
  (if (|GetChoicePending :self (|GetRules))
   (if (or (!= (|GetOfferStage) (|GetCurrentRound :self (|GetRules))) (or (!= (|GetOfferRound) (|GetBallsUsed :self (|GetRules))) (!= (Utilities|Array|Length (|GetObstacleOffers)) 3)))
    (Utilities|Array|Clear (|GetOfferPool))
    (Utilities|Array|Clear (|GetObstacleOffers))
    (for i (range 10) (Utilities|Array|Add (|GetOfferPool) i))
    (for i (range 3)
     (|SetOfferDrawIndex (Math|Random|RandomIntegerInRange 0 (- (Utilities|Array|Length (|GetOfferPool)) 1)))
     (Utilities|Array|Add (|GetObstacleOffers) (Utilities|Array|Get(acopy) (|GetOfferPool) (|GetOfferDrawIndex)))
     (Utilities|Array|RemoveIndex (|GetOfferPool) (|GetOfferDrawIndex)))
    (|SetOfferStage (|GetCurrentRound :self (|GetRules)))
    (|SetOfferRound (|GetBallsUsed :self (|GetRules))))))''')
B.compile_blueprint(HUD)
g=Graph(HUD,'ChooseObstacle')
# Extend valid kinds and reject anything outside this round's actual three offers.
helper['set_literals'](HUD,'ChooseObstacle',helper['GREATER'],'B',6,9)
targets=[B._resolve_pin(p) for p in next(p for p in B._get_node_info(g.entry.get_owning_node()).output_pins if p.name=='then').connected_pins]
g.entry.break_pin_links();g.action('EnsureObstacleOffers')
contains=g.call('/Script/Engine.KismetArrayLibrary:Array_Contains',TargetArray=g.get('ObstacleOffers'),ItemToFind=g.arg('Type')).find_output_pin('ReturnValue')
g.reject(g.math('Not_PreBool',contains),'이번 라운드의 카드 3개 중에서 선택하세요')
for t in targets:assert g.tail.try_create_connection(t)
# Keep the selected stock card visible after the offer panel switches to inventory.
chosen=next(n for n in B.find_nodes(g.g) if B._get_node_info(n).type_id=='|SetSelected')
code(HUD,'FocusObstacleStock',[],'''(|SetInvScroll (select (< (|GetSelected) 7) (|GetSelected) 7))''')
B.compile_blueprint(HUD)
helper['insert_after'](g.g,B._get_node_info(chosen),'FocusObstacleStock')
code(HUD,'ChooseOffer',[('Row','int')],'''
 (if (and (>= Row 0) (< Row 3))
  (if (|GetChoicePending :self (|GetRules))
   (|EnsureObstacleOffers)
   (|ChooseObstacle :Type (Utilities|Array|Get(acopy) (|GetObstacleOffers) Row))
   (else (|SetSelected (+ Row (|GetInvScroll))))))''')
B.compile_blueprint(HUD)

g=Graph(HUD,'PointerInput')
def literal_number(p):
 if not p.value and not p.connected_pins:return 0
 if p.value:
  try:return int(float(p.value))
  except ValueError:pass
 for src in p.connected_pins:
  for q in B._get_node_info(src.node).input_pins:
   if q.name in ('Value','A','B'):
    try:return literal_number(q)
    except ValueError:pass
 raise ValueError('No literal row in '+p.name)
for n in list(B.find_nodes(g.g)):
 info=B._get_node_info(n)
 if info.type_id!='|ChooseObstacle':continue
 source=pin(info,'Type').connected_pins[0]
 sourceinfo=B._get_node_info(source.node)
 row=literal_number(pin(sourceinfo,'B'))
 call=g.call('ChooseOffer',Row=row)
 for p in info.input_pins:
  if p.name=='execute':
   for source in p.connected_pins:assert B._resolve_pin(source).try_create_connection(call.find_execute_pin())
 for p in info.output_pins:
  if p.name=='then':
   for target in p.connected_pins:assert call.find_then_pin().try_create_connection(B._resolve_pin(target))
 B.delete_node(n)

# Wheel/click inventory selection is enabled only after the one free choice.
old=helper['UPDATE_INVENTORY']
old=old.replace('(if (== (|GetStation) 1)','(if (and (== (|GetStation) 1) (not (|GetChoicePending :self (|GetRules))))',1)
fn(HUD,'UpdateInventory',[],old)
insert(HUD,'UpdateBoard',entry,'EnsureObstacleOffers')
helper['STOCK_SLOTS']=10;helper['stock_slots'](HUD)

PANEL=helper['PANEL'];TEXT=helper['TEXT'];SUB=helper['SUB'];ACCENT=helper['ACCENT'];SEL=helper['SEL'];FRAME=helper['FRAME']
code(HUD,'DrawBumperSlots',[],f'''
 (|EnsureObstacleOffers)
 (for row (range 3)
  (bind pending (|GetChoicePending :self (|GetRules)))
  (bind item (select pending (Utilities|Array|Get(acopy) (|GetObstacleOffers) row) (+ row (|GetInvScroll))))
  (bind y (+ 290.0 (* (Math|Conversions|ToFloat(Integer) row) 130.0)))
  (if (Utilities|Array|IsValidIndex (|GetStock) item)
   (|Panel :X 886.0 :Y y :W 295.0 :H 122.0 :Tint "{PANEL}")
   (|Frame :X 886.0 :Y y :W 295.0 :H 122.0 :Line 2.0 :Tint "{FRAME}")
   (if (and (not pending) (== item (|GetSelected))) (|Frame :X 886.0 :Y y :W 295.0 :H 122.0 :Line 4.0 :Tint "{SEL}"))
   (|Panel :X 902.0 :Y (+ y 18.0) :W 64.0 :H 64.0 :Tint (Utilities|Array|Get(acopy) (|GetObstacleTints) item))
   (|Label :Caption (Utilities|Array|Get(acopy) (|GetObstacleNames) item) :X 980.0 :Y (+ y 16.0) :Size 0.98 :Tint "{TEXT}")
   (|Label :Caption (Utilities|Array|Get(acopy) (|GetObstacleDescriptions) item) :X 980.0 :Y (+ y 47.0) :Size 0.61 :Tint "{SUB}")
   (if pending
    (|Label :Caption "무료 · 3개 중 1개 선택" :X 980.0 :Y (+ y 82.0) :Size 0.73 :Tint "{ACCENT}")
    (else
     (|Label :Caption (Utilities|String|BuildString(Integer) "" "보관함: " (Utilities|Array|Get(acopy) (|GetStock) item) "개") :X 980.0 :Y (+ y 75.0) :Size 0.8 :Tint "{SUB}")
     (|Label :Caption "휠: 종류 변경 · 클릭: 선택" :X 980.0 :Y (+ y 101.0) :Size 0.57 :Tint "{SUB}")))))
 (|DrawTiltCount) (|DrawSideArrow :Caption "상점") (|DrawLiveScore)''')
B.compile_blueprint(HUD)
cdo=B.get_default_object(HUD)
cdo.set_editor_property('ObstacleNames',list(cdo.get_editor_property('ObstacleNames'))+['대쉬 발판','복사 판','회전 발판'])
cdo.set_editor_property('ObstacleTints',list(cdo.get_editor_property('ObstacleTints'))+[u.LinearColor(.05,.65,1,1),u.LinearColor(.8,.1,1,1),u.LinearColor(1,.45,.04,1)])
cdo.set_editor_property('ObstacleDescriptions',['공을 반사','왼쪽으로 반사','오른쪽으로 반사','충돌 속도 증가','주변 공을 당김','범퍼 점수 추가','위쪽으로 순간이동','화살표로 가속 · 라운드당 3회','통과 시 복사 · 사용 후 소멸','계속 회전하며 공을 반사'])
cdo.set_editor_property('OfferStage',-1);cdo.set_editor_property('OfferRound',-1)
