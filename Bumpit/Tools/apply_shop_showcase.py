"""Shop showcase: in the shop (station 2) the mouse wheel steps through everything on display - the three real
obstacles on the stock counter and the gimmick bumpers and balls on the shelves above. The camera glides to
the item in focus and the shop list scrolls with it. Safe to run repeatedly; tune the tables below.

Run with the editor closed (-culture=en matters: the Blueprint text tools need English node names):
UnrealEditor-Cmd.exe Bumpit.uproject -run=pythonscript -script=<this file> -unattended -nullrhi -culture=en

How it works (BP_BumpitHUD):
  - UpdateShopView runs first in UpdateBoard every frame. In the shop, wheel down focuses the next item and
    wheel up the previous one, wrapping round. The list's first visible row (ShopScroll) follows the focus.
  - Focusing a bumper (the first len(Stock) items) also selects it for placing. Balls come after the bumpers
    (item len(Stock) + n - 1 is ball type n). Clicking a row focuses it; clicking its price buys it.
  - Run apply_gimmicks.py first: it adds the ball stock and the purchase rules this list relies on.
  - When the focus changes (or on walking into the shop) the camera moves with MoveView to
    ShopEyes[ShopFocus] / ShopTargets[ShopFocus]; both are worked out here from where each model stands.
  - DrawShop is rebuilt as a scrolling list (SHOP_ROWS rows) with a scroll bar; DrawShowcaseName shows the
    focused item's name and what it does. Purchase takes its prices from ShopPrices, the same list the shop
    shows, so a price is set in one place.

Adding a real obstacle later: give it gameplay (stock slot, table placement), put its model on the counter and
add it to COUNTER in selection order. The gimmick items are in SHELF.
"""
import unreal
import toolset_registry
from editor_toolset.toolsets import blueprint_dsl
from editor_toolset.toolsets.blueprint import BlueprintTools as BT, ContainerType

HUD = "/Game/Bumpit/Blueprints/BP_BumpitHUD"
MAP = "/Game/Bumpit/Maps/BumpitCell"
SHOWCASE_MATERIALS = "/Game/Bumpit/Materials/Showcase"
MOOD_SURFACE = "/Game/Bumpit/Mood/M_BumpitMood"
SHELF_LABEL = "Showcase "  # map actors this script owns start with this

# Real obstacles, in selection order: name, model on the stock counter (map label), price, colour, what it does.
COUNTER = [
    ("원형 범퍼", "Stock counter 67", 3, (0.64, 0.52, 0.11), "공을 튕겨내는 기본 범퍼"),
    ("왼쪽 반사판", "Stock counter 70", 4, (0.85, 0.29, 0.03), "비스듬한 판 · 공을 옆으로 꺾음"),
    ("오른쪽 반사판", "Stock counter 73", 4, (0.62, 0.025, 0.022), "비스듬한 판 · 반대쪽으로 꺾음"),
]

# Gimmick items (gameplay in apply_gimmicks.py): name, what it does, linear colour, shape,
# shelf (0 lower, 1 upper), y along the shelf, price. The four bumpers are obstacle types 4-7 and the four
# balls ball types 1-4, in this order.
SHELF = [
    ("폭발 범퍼", "맞으면 공을 두 배로 세게 튕겨냄", (0.85, 0.12, 0.03), "Cylinder", 0, -195.0, 6),
    ("자석 범퍼", "가까이 온 공을 끌어당김", (0.05, 0.20, 0.85), "Cylinder", 0, -35.0, 6),
    ("황금 범퍼", "맞을 때마다 점수 +100", (0.95, 0.70, 0.08), "Cylinder", 0, 125.0, 5),
    ("워프 범퍼", "공을 판 맨 위로 순간이동시킴", (0.45, 0.08, 0.75), "Cylinder", 0, 285.0, 7),
    ("쇳덩이 공", "무거워서 덜 튀지만 점수 ×2", (0.35, 0.36, 0.38), "Sphere", 1, -195.0, 3),
    ("고무공", "엄청 잘 튐", (0.90, 0.22, 0.50), "Sphere", 1, -35.0, 2),
    ("행운의 공", "골 배율 2배", (0.10, 0.65, 0.15), "Sphere", 1, 125.0, 4),
    ("불꽃 공", "범퍼에 맞을 때마다 점수 2배", (0.95, 0.38, 0.03), "Sphere", 1, 285.0, 4),
]
SHELF_TOPS = (127.0, 243.0)  # top faces of the two shelf boards (Stock counter 74 and 75)
SHELF_X = -1120.0  # middle of the 30 cm deep boards
ITEM_SIZE = (26.0, 26.0, 22.0)  # cm: fits the shelf depth (balls use the width for all three)
ITEM_GLOW = 0.35  # like the bumpers on the table

# Camera relative to a model. The counter and shelves face +X, so the camera stands in front at +X.
COUNTER_VIEW = (300.0, 110.0)  # distance in front, height above the model's centre
SHELF_VIEW = (170.0, 25.0)  # closer and nearly level: the items are small, and this passes under the shelf sign
# The shop panel covers the right ~40% of the screen. Looking from +X, screen-right is -Y; aiming this
# fraction of the distance towards -Y puts the model left of centre, clear of the panel.
SCREEN_SHIFT = 0.15
FOV = 45.0  # the overall shop view uses 53

# Shop list layout, in the HUD's 1200 x 740 canvas. PointerInput's click test uses the same row grid.
SHOP_ROWS = 4
ROW_Y0, ROW_STEP, ROW_H = 233, 82, 70
TRACK = SHOP_ROWS * ROW_STEP - (ROW_STEP - ROW_H)
PANEL = "(R=0.016,G=0.01,B=0.008,A=0.86)"
ROW = "(R=0.05,G=0.026,B=0.018,A=0.9)"
DIM = "(R=0.12,G=0.06,B=0.035,A=1)"
ACCENT = "(R=0.95,G=0.36,B=0.16,A=1)"
TEXT = "(R=0.86,G=0.79,B=0.66,A=1)"
SUB = "(R=0.56,G=0.46,B=0.36,A=1)"
GOLD = "(R=0.92,G=0.62,B=0.22,A=1)"


def make_node(graph, type_id, pos, declaring_class=None):
    """Node factory for the DSL. Headless, the editor's node list has none of a Blueprint's own
    variables or functions, so "|GetX", "|SetX" and "|Func" are built with the member-node calls."""
    if not type_id.startswith("|"):
        return BT.create_node(graph, type_id, pos, declaring_class)
    name = type_id[1:]
    editor = unreal.BlueprintGraphEditor.get_graph_editor(graph)
    node = None
    if name.startswith("Get"):
        node = editor.add_get_member_variable_node(name[3:])
    elif name.startswith("Set"):
        node = editor.add_set_member_variable_node(name[3:])
    if node is None:
        bp = unreal.Blueprint.cast(graph.get_outer())
        node = editor.add_call_function_node(f"{bp.generated_class().get_path_name()}:{name}")
    if node is None:
        raise RuntimeError(f"Could not make a node for {type_id}")
    node.set_node_pos(pos)
    return node


# Calls to the HUD's own functions name their pins (:Eye ...): built headless they carry a "self" pin first,
# so positional arguments would land one pin off.
UPDATE_SHOP_VIEW = f"""
(fn UpdateShopView ()
  (if (!= (|GetStation) 2)
    (|SetShopShown -1)
    (else
      (bind pc (HUD|GetOwningPlayerController))
      (bind count (Utilities|Array|Length (|GetShopEyes)))
      (if (> count 0)
        (if (or (== (|GetShopShown) -1) (!= (|GetSelected) (|GetShopSelected)))
          (|SetShopFocus (|GetSelected)))
        (if (Game|Player|WasInputKeyJustPressed pc "MouseScrollDown")
          (|SetShopFocus (Math|Integer|%(Integer) (+ (|GetShopFocus) 1) count)))
        (if (Game|Player|WasInputKeyJustPressed pc "MouseScrollUp")
          (|SetShopFocus (Math|Integer|%(Integer) (+ (|GetShopFocus) (- count 1)) count)))
        (if (< (|GetShopFocus) (|GetShopScroll))
          (|SetShopScroll (|GetShopFocus)))
        (if (>= (|GetShopFocus) (+ (|GetShopScroll) {SHOP_ROWS}))
          (|SetShopScroll (+ (- (|GetShopFocus) {SHOP_ROWS}) 1)))
        (if (< (|GetShopFocus) (Utilities|Array|Length (|GetStock)))
          (|SetSelected (|GetShopFocus)))
        (|SetShopSelected (|GetSelected))
        (if (and (!= (|GetShopFocus) (|GetShopShown)) (Utilities|Array|IsValidIndex (|GetShopEyes) (|GetShopFocus)))
          (|SetShopShown (|GetShopFocus))
          (|MoveView :Eye (Utilities|Array|Get(acopy) (|GetShopEyes) (|GetShopFocus)) :Target (Utilities|Array|Get(acopy) (|GetShopTargets) (|GetShopFocus)) :Fov (|GetShopFov)))))))
"""

DRAW_SHOWCASE_NAME = f"""
(fn DrawShowcaseName ()
  (if (Utilities|Array|IsValidIndex (|GetShowcaseNames) (|GetShopFocus))
    (|Panel :X 50.0 :Y 560.0 :W 470.0 :H 122.0 :Tint "{PANEL}")
    (|Label :Caption (Utilities|Array|Get(acopy) (|GetShowcaseNames) (|GetShopFocus)) :X 68.0 :Y 570.0 :Size 1.2 :Tint "{TEXT}")
    (|Label :Caption (Utilities|Array|Get(acopy) (|GetShowcaseInfo) (|GetShopFocus)) :X 68.0 :Y 610.0 :Size 0.9 :Tint "{SUB}")
    (if (< (|GetShopFocus) (Utilities|Array|Length (|GetStock)))
      (|Label :Caption "범퍼 · 사서 기계에서 배치   ·   휠 ▲▼" :X 68.0 :Y 645.0 :Size 0.85 :Tint "{GOLD}")
      (else
        (|Label :Caption "공 · 사서 기계에서 Q / E로 고르기   ·   휠 ▲▼" :X 68.0 :Y 645.0 :Size 0.85 :Tint "{GOLD}")))))
"""

DRAW_SHOP = f"""
(fn DrawShop ()
  (|DrawShowcaseName)
  (|Panel :X 732.0 :Y 103.0 :W 421.0 :H 560.0 :Tint "{PANEL}")
  (|Label :Caption "WORKSHOP" :X 750.0 :Y 131.0 :Size 1.8 :Tint "{TEXT}")
  (|Label :Caption (Utilities|String|BuildString(Integer) "" "보유 크레딧  " (|GetCredits)) :X 750.0 :Y 188.0 :Size 1.08 :Tint "{GOLD}")
  (for row (range {SHOP_ROWS})
    (bind item (+ row (|GetShopScroll)))
    (bind y (+ {ROW_Y0}.0 (* (Math|Conversions|ToFloat(Integer) row) {ROW_STEP}.0)))
    (if (< item (Utilities|Array|Length (|GetShowcaseNames)))
      (|Panel :X 750.0 :Y y :W 380.0 :H {ROW_H}.0 :Tint "{ROW}")
      (if (== item (|GetShopFocus))
        (|Panel :X 750.0 :Y y :W 5.0 :H {ROW_H}.0 :Tint "{ACCENT}")
        (else
          (|Panel :X 750.0 :Y y :W 5.0 :H {ROW_H}.0 :Tint "{DIM}")))
      (|Label :Caption (Utilities|Array|Get(acopy) (|GetShowcaseNames) item) :X 768.0 :Y (+ y 7.0) :Size 1.13 :Tint "{TEXT}")
      (if (< item (Utilities|Array|Length (|GetStock)))
        (|Label :Caption (Utilities|String|BuildString(Integer) "" "보관함  " (Utilities|Array|Get(acopy) (|GetStock) item)) :X 768.0 :Y (+ y 39.0) :Size 0.82 :Tint "{SUB}")
        (else
          (|Label :Caption (Utilities|String|BuildString(Integer) "" "공 보관함  " (Utilities|Array|Get(acopy) (|GetBallStock) (+ (- item (Utilities|Array|Length (|GetStock))) 1))) :X 768.0 :Y (+ y 39.0) :Size 0.82 :Tint "{SUB}")))
      (|Panel :X 1010.0 :Y (+ y 10.0) :W 109.0 :H 50.0 :Tint "{DIM}")
      (|Label :Caption (Utilities|String|BuildString(Integer) "" "구매  " (Utilities|Array|Get(acopy) (|GetShopPrices) item)) :X 1027.0 :Y (+ y 19.0) :Size 1.0 :Tint "{GOLD}")))
  (if (> (Utilities|Array|Length (|GetShowcaseNames)) {SHOP_ROWS})
    (|Panel :X 1137.0 :Y {ROW_Y0}.0 :W 6.0 :H {TRACK}.0 :Tint "{DIM}")
    (|Panel :X 1137.0 :Y (+ {ROW_Y0}.0 (/ (* {TRACK}.0 (Math|Conversions|ToFloat(Integer) (|GetShopScroll))) (Math|Conversions|ToFloat(Integer) (Utilities|Array|Length (|GetShowcaseNames))))) :W 6.0 :H (/ {TRACK * SHOP_ROWS}.0 (Math|Conversions|ToFloat(Integer) (Utilities|Array|Length (|GetShowcaseNames)))) :Tint "{ACCENT}"))
  (|Label :Caption (|GetMessage) :X 750.0 :Y 565.0 :Size 0.99 :Tint "{TEXT}")
  (|Label :Caption "[1] 기계   ·   휠 ▲▼ 넘기기" :X 750.0 :Y 615.0 :Size 1.0 :Tint "{ACCENT}")
  (|DrawTableArrow))
"""


# --- Map: shelf items -------------------------------------------------------------------------------------
def shelf_material(index, colour):
    name = f"MI_Showcase_{index:02d}"
    path = f"{SHOWCASE_MATERIALS}/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        mi = unreal.load_asset(path)
    else:
        mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, SHOWCASE_MATERIALS, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mel = unreal.MaterialEditingLibrary
    mel.set_material_instance_parent(mi, unreal.load_asset(MOOD_SURFACE))
    mel.set_material_instance_vector_parameter_value(mi, "Color", unreal.LinearColor(colour[0], colour[1], colour[2], 1.0))
    mel.set_material_instance_scalar_parameter_value(mi, "Glow", ITEM_GLOW)
    mel.update_material_instance(mi)
    unreal.EditorAssetLibrary.save_loaded_asset(mi)
    return mi


def place_shelf_items():
    unreal.EditorLoadingAndSavingUtils.load_map(MAP)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in actors.get_all_level_actors():
        if actor.get_actor_label().startswith(SHELF_LABEL):
            actors.destroy_actor(actor)
    for i, (name, _, colour, shape, shelf, y, _price) in enumerate(SHELF):
        sx, sy, sz = ITEM_SIZE if shape != "Sphere" else (ITEM_SIZE[0],) * 3
        location = unreal.Vector(SHELF_X, y, SHELF_TOPS[shelf] + sz / 2)
        item = actors.spawn_actor_from_class(unreal.StaticMeshActor, location, unreal.Rotator(0.0, 0.0, 0.0))
        item.set_actor_label(f"{SHELF_LABEL}{i:02d} {name}")
        part = item.static_mesh_component
        part.set_static_mesh(unreal.load_asset(f"/Engine/BasicShapes/{shape}.{shape}"))
        part.set_material(0, shelf_material(i, colour))
        part.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        item.set_actor_scale3d(unreal.Vector(sx / 100.0, sy / 100.0, sz / 100.0))
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()


def showcase_data():
    by_label = {a.get_actor_label(): a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()}
    entries = [(name, label, COUNTER_VIEW, price, colour, info) for name, label, price, colour, info in COUNTER]
    entries += [(item[0], f"{SHELF_LABEL}{i:02d} {item[0]}", SHELF_VIEW, item[6], item[2], item[1]) for i, item in enumerate(SHELF)]
    data = {"names": [], "eyes": [], "targets": [], "info": [], "colours": []}
    data["prices"] = []
    for name, label, (distance, height), price, colour, info in entries:
        data["prices"].append(price)
        if label not in by_label:
            raise RuntimeError(f"No '{label}' in {MAP} for {name}")
        centre, _ = by_label[label].get_actor_bounds(False)
        target = unreal.Vector(centre.x, centre.y - SCREEN_SHIFT * distance, centre.z)
        data["names"].append(name)
        data["info"].append(info)
        data["colours"].append(unreal.LinearColor(colour[0], colour[1], colour[2], 1.0))
        data["targets"].append(target)
        data["eyes"].append(unreal.Vector(centre.x + distance, target.y, centre.z + height))
    return data


# --- HUD --------------------------------------------------------------------------------------------------
def add_variables(hud):
    existing = set(str(v) for v in BT.list_variables(hud))
    wanted = (("ShopEyes", "Vector", ContainerType.ARRAY), ("ShopTargets", "Vector", ContainerType.ARRAY),
              ("ShowcaseNames", "string", ContainerType.ARRAY), ("ShowcaseInfo", "string", ContainerType.ARRAY),
              ("ShowcaseColors", "LinearColor", ContainerType.ARRAY), ("ShopPrices", "int", ContainerType.ARRAY),
              ("ShopFov", "float", None), ("ShopFocus", "int", None), ("ShopShown", "int", None),
              ("ShopSelected", "int", None), ("ShopScroll", "int", None))
    for name, kind, container in wanted:
        if name not in existing:
            BT.add_variable(hud, name, kind, container_type=container)
            BT.set_variable_category(hud, name, "Shop showcase")


def write_function(hud, name, code):
    if name in [g.get_name() for g in BT.list_graphs(hud)]:
        graph = BT.get_graph(hud, name)
        for node in BT.find_nodes(graph):
            if isinstance(node, unreal.K2Node_FunctionResult):
                raise RuntimeError(f"{name} returns a value; it can't be rewritten whole")
            if not isinstance(node, unreal.K2Node_FunctionEntry):
                BT.delete_node(node)
    else:
        graph = BT.add_function_graph(hud, name)
    blueprint_dsl.Transpiler(
        graph, make_node, BT.connect_pins, BT._get_node_info, BT.set_pin_value,
        lambda g: BT.find_nodes(g), delete_node_fn=BT.delete_node,
        find_node_types_fn=lambda f: BT.find_node_types(graph, f),
    ).transpile(code)


def infos_of(graph):
    return {i.node.get_name(): i for i in BT.get_node_infos(BT.find_nodes(graph))}


def pin(info, name):
    return next(p for p in list(info.input_pins) + list(info.output_pins) if p.name == name)


def value_out(info):
    return next(p for p in info.output_pins if p.type_id != "Exec")


def call_first(hud, host, callee):
    """Makes `host` call `callee` exactly once: at its very start if it isn't called yet. Extra calls (an
    earlier version of this script could add a second one) are cut out of the exec chain."""
    graph = BT.get_graph(hud, host)
    infos = BT.get_node_infos(BT.find_nodes(graph))
    calls = [i for i in infos if i.type_id == f"|{callee}"]
    for extra in calls[1:]:
        for source in pin(extra, "execute").connected_pins:
            for target in pin(extra, "then").connected_pins:
                BT.connect_pins(source, target)
        BT.delete_node(extra.node)
    if calls:
        return
    entry = next(i for i in infos if isinstance(i.node, unreal.K2Node_FunctionEntry))
    then = pin(entry, "then")
    first = BT._get_node_info(then.connected_pins[0].node)
    make_node(graph, f"|{callee}", unreal.IntPoint(entry.position.x + 150, entry.position.y + 220))
    call = next(i for i in BT.get_node_infos(BT.find_nodes(graph)) if i.type_id == f"|{callee}")
    BT.connect_pins(then.pin_id, pin(call, "execute").pin_id)
    BT.connect_pins(pin(call, "then").pin_id, pin(first, "execute").pin_id)


BOARD_HEAD = ("UpdateShopView", "UpdateInventory")  # what UpdateBoard runs first, in this order


def order_board_head(hud):
    """Rewires the start of UpdateBoard as entry -> UpdateShopView -> UpdateInventory -> the rest, whatever
    state it is in. apply_gimmicks.py and apply_shop_showcase.py each insert one of these calls, and reruns
    in a different order once left UpdateInventory wired back into UpdateShopView: an endless loop, with
    the rest of UpdateBoard (walking, charging, launching, clicks) cut off. Same function in both scripts."""
    graph = BT.get_graph(hud, "UpdateBoard")

    def exec_pins(info, direction):
        pins = info.input_pins if direction == "in" else info.output_pins
        return [p for p in pins if "exec" in p.type_id.lower()]

    infos = BT.get_node_infos(BT.find_nodes(graph))
    entry = next(i for i in infos if isinstance(i.node, unreal.K2Node_FunctionEntry))
    head = [next((i for i in infos if i.type_id == f"|{name}"), None) for name in BOARD_HEAD]
    head = [i for i in head if i is not None]
    head_keys = {i.node.get_path_name() for i in head}
    by_key = {i.node.get_path_name(): i for i in infos}

    # The rest of UpdateBoard: the first node after the head calls, or, if the head wiring loops or
    # dead-ends, the one exec chain that nothing runs any more.
    rest, seen, cur = None, set(), entry
    while cur is not None and rest is None:
        seen.add(cur.node.get_path_name())
        nxt = [c.node.get_path_name() for p in exec_pins(cur, "out") if p.name == "then" for c in p.connected_pins]
        cur = None
        for k in nxt:
            if k not in head_keys:
                rest = by_key[k]
            elif k not in seen:
                cur = by_key[k]
    if rest is None:
        orphans = [i for i in infos
                   if i.node.get_path_name() not in head_keys and i is not entry
                   and exec_pins(i, "in") and not any(p.connected_pins for p in exec_pins(i, "in"))
                   and any(p.connected_pins for p in exec_pins(i, "out"))]
        if len(orphans) != 1:
            raise RuntimeError(f"UpdateBoard: cannot tell where the rest starts ({[o.type_id for o in orphans]})")
        rest = orphans[0]

    # Unhook the entry and the head calls, then chain them in order.
    # Re-read each node right before cutting: cutting one end of a wire also clears the other end.
    for node in [entry.node] + [i.node for i in head]:
        for p in exec_pins(BT._get_node_info(node), "out"):
            for c in list(p.connected_pins):
                BT.break_pins(p.pin_id, c)
    for node in [i.node for i in head]:
        for p in exec_pins(BT._get_node_info(node), "in"):
            for c in list(p.connected_pins):
                BT.break_pins(c, p.pin_id)
    chain = [entry] + [BT._get_node_info(i.node) for i in head] + [BT._get_node_info(rest.node)]
    for a, b in zip(chain, chain[1:]):
        out = next(p for p in exec_pins(BT._get_node_info(a.node), "out") if p.name == "then")
        inp = next(p for p in exec_pins(BT._get_node_info(b.node), "in") if p.name == "execute")
        BT.connect_pins(out.pin_id, inp.pin_id)
    unreal.log(f"BUMPIT_BOARD_HEAD entry -> {' -> '.join(i.type_id for i in chain[1:])}")


def prices_from_list(hud):
    """Purchase picked its price with Select(Type == 0 ? 3 : 4). It now reads ShopPrices[Type]."""
    graph = BT.get_graph(hud, "Purchase")
    infos = infos_of(graph)
    selects = [i for i in infos.values() if i.type_id == "Utilities|Select"]
    if not selects:
        return  # already done
    select = selects[0]
    entry = next(i for i in infos.values() if isinstance(i.node, unreal.K2Node_FunctionEntry))
    consumers = list(value_out(select).connected_pins)
    pos = select.position
    get = BT._get_node_info(BT.create_node(graph, "Utilities|Array|Get(acopy)", unreal.IntPoint(pos.x, pos.y)))
    prices = BT._get_node_info(make_node(graph, "|GetShopPrices", unreal.IntPoint(pos.x - 220, pos.y)))
    BT.connect_pins(value_out(prices).pin_id, pin(get, "Array").pin_id)
    get = BT._get_node_info(get.node)
    BT.connect_pins(pin(entry, "Type").pin_id, next(p for p in get.input_pins if p.name != "Array").pin_id)
    get = BT._get_node_info(get.node)
    for target in consumers:
        BT.connect_pins(value_out(get).pin_id, target)
    sources = [c.node for name in ("Option 0", "Option 1", "Index") for c in pin(select, name).connected_pins]
    BT.delete_node(select.node)
    for node in sources:
        BT.delete_node(node)


def scrolled_item(graph, index_out, pos):
    """Adds (row index + ShopScroll) and returns that sum's output pin."""
    add = BT.create_node(graph, "Utilities|Operators|Add", pos)
    scroll = BT._get_node_info(make_node(graph, "|GetShopScroll", unreal.IntPoint(pos.x - 200, pos.y + 80)))
    info = BT._get_node_info(add)
    BT.connect_pins(index_out.pin_id, pin(info, "A").pin_id)
    info = BT._get_node_info(add)
    BT.connect_pins(value_out(scroll).pin_id, pin(info, "B").pin_id)
    return value_out(BT._get_node_info(add))


def remap_pointer_rows(hud):
    """PointerInput tested the three shop rows as item 0-2. Rows now show item (row + ShopScroll), there are
    SHOP_ROWS of them, and clicking a row's name focuses it instead of selecting it outright."""
    graph = BT.get_graph(hud, "PointerInput")
    infos = infos_of(graph)
    loops = [i for i in infos.values() if i.type_id.endswith("ForLoop")]
    if len(loops) != 1:
        raise RuntimeError(f"Expected one ForLoop in PointerInput, found {len(loops)}")
    loop = loops[0]
    BT.set_pin_value(pin(loop, "LastIndex").pin_id, str(SHOP_ROWS - 1))
    index_out = pin(loop, "Index")
    loop_name = loop.node.get_name()

    purchase = next(i for i in infos.values() if i.type_id == "|Purchase")
    if [c.node.get_name() for c in pin(purchase, "Type").connected_pins] == [loop_name]:
        item = scrolled_item(graph, index_out, unreal.IntPoint(purchase.position.x - 250, purchase.position.y + 120))
        BT.connect_pins(item.pin_id, pin(purchase, "Type").pin_id)

    for select in [i for i in infos.values() if i.type_id == "|SetSelected"]:
        if [c.node.get_name() for c in pin(select, "Selected").connected_pins] != [loop_name]:
            continue
        pos = select.position
        focus = BT._get_node_info(make_node(graph, "|SetShopFocus", unreal.IntPoint(pos.x, pos.y + 160)))
        for source in pin(select, "execute").connected_pins:
            BT.connect_pins(source, pin(focus, "execute").pin_id)
        for target in pin(select, "then").connected_pins:
            BT.connect_pins(pin(focus, "then").pin_id, target)
        item = scrolled_item(graph, index_out, unreal.IntPoint(pos.x - 250, pos.y + 280))
        BT.connect_pins(item.pin_id, pin(BT._get_node_info(focus.node), "ShopFocus").pin_id)
        BT.delete_node(select.node)


with toolset_registry.tool_raising_exceptions():
    place_shelf_items()
    data = showcase_data()
    hud = unreal.load_asset(HUD)
    add_variables(hud)
    BT.compile_blueprint(hud)
    write_function(hud, "UpdateShopView", UPDATE_SHOP_VIEW)
    write_function(hud, "DrawShowcaseName", DRAW_SHOWCASE_NAME)
    BT.compile_blueprint(hud)  # new functions can only be called once they exist on the compiled class
    write_function(hud, "DrawShop", DRAW_SHOP)
    call_first(hud, "UpdateBoard", "UpdateShopView")
    order_board_head(hud)
    prices_from_list(hud)
    remap_pointer_rows(hud)
    BT.compile_blueprint(hud, warnings_as_errors=True)
    cdo = BT.get_default_object(hud)
    cdo.set_editor_property("ShopEyes", data["eyes"])
    cdo.set_editor_property("ShopTargets", data["targets"])
    cdo.set_editor_property("ShowcaseNames", data["names"])
    cdo.set_editor_property("ShowcaseInfo", data["info"])
    cdo.set_editor_property("ShowcaseColors", data["colours"])
    cdo.set_editor_property("ShopPrices", data["prices"])
    cdo.set_editor_property("ShopFov", FOV)
    for name, value in (("ShopFocus", 0), ("ShopShown", -1), ("ShopSelected", -1), ("ShopScroll", 0)):
        cdo.set_editor_property(name, value)
    unreal.EditorAssetLibrary.save_loaded_asset(hud)
unreal.log(f"BUMPIT_SHOP_SHOWCASE_APPLIED items={len(data['names'])}")
