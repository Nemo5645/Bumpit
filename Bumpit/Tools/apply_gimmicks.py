"""Gimmick bumpers and two more special balls, on top of main's ball-purchase progression (Nemo5645, 11/14).
Main's rules stay as they are; this only adds to them. Safe to run repeatedly; tune the tables below.
Run apply_table_tuning.py first (obstacle sizes follow its playfield scale).

Run with the editor closed (-culture=en matters: the Blueprint text tools need English node names):
UnrealEditor-Cmd.exe Bumpit.uproject -run=pythonscript -script=<this file> -unattended -nullrhi -culture=en

Obstacles: main lets the player pick one obstacle for free each round from three cards. There are now seven
(Stock has 7 slots), shown three at a time - the mouse wheel or a click scrolls the list:
  0 round bumper, 1 left deflector, 2 right deflector (main's)  -> obstacle types 1-3 on the table
  3 Blast  - after the bounce the ball's speed is multiplied by BlastBoost          -> type 4
  4 Magnet - pulls the balls towards it inside MagnetRadius (every tick)            -> type 5
  5 Gold   - each bounce adds GoldHits extra bumper hits                            -> type 6
  6 Warp   - moves the ball to a random spot near the top of the table              -> type 7
The gimmick bumpers bounce like round bumpers and work on the split ball too.

Balls: main's IDs 0-4 keep their meaning. Added to the shop draw:
  5 Rubber - walls give back RUBBER_BOUNCE of the speed
  6 Lucky  - goal (lane) multiplier x LUCKY_LANE_FACTOR
"""
import unreal
import toolset_registry
from editor_toolset.toolsets import blueprint_dsl
from editor_toolset.toolsets.blueprint import BlueprintTools as BT, ContainerType

TABLE = "/Game/Bumpit/Blueprints/BP_PinballTable"
HUD = "/Game/Bumpit/Blueprints/BP_BumpitHUD"
RULES = "/Game/Bumpit/Blueprints/BP_RoundRules"
MATERIALS = "/Game/Bumpit/Materials"
PARENT_MATERIAL = "/Game/Bumpit/Mood/M_BumpitMood"  # what main's ball and cell colours are made from

# --- Bumpers ----------------------------------------------------------------------------------------------
# component, tag, card name, material name, colour, glow; obstacle types 4, 5, 6, 7 in this order
GIMMICK_BUMPERS = [
    ("BlastBumpers", "Blast", "폭발 범퍼", "MI_Gimmick_Blast", (0.95, 0.20, 0.03), 0.7),
    ("MagnetBumpers", "Magnet", "자석 범퍼", "MI_Gimmick_Magnet", (0.16, 0.32, 0.95), 0.5),
    ("GoldBumpers", "Gold", "황금 범퍼", "MI_Gimmick_Gold", (1.00, 0.78, 0.12), 0.9),
    ("WarpBumpers", "Warp", "워프 범퍼", "MI_Gimmick_Warp", (0.62, 0.22, 0.95), 0.6),
]
BASE_OBSTACLES = [  # main's three cards, as main draws them
    ("원형 범퍼", (0.64, 0.52, 0.11)),
    ("왼쪽 반사판", (0.85, 0.29, 0.03)),
    ("오른쪽 반사판", (0.62, 0.025, 0.022)),
]
STOCK_SLOTS = len(BASE_OBSTACLES) + len(GIMMICK_BUMPERS)  # 7
BLAST_BOOST = 1.8
GOLD_HITS = 4
MAGNET_RADIUS = 130.0  # cm
MAGNET_STRENGTH = 1600.0  # cm/s^2 at the magnet, fading to 0 at the radius
WARP_X, WARP_Y = 300.0, 220.0  # table space: near the top rail, anywhere across +-WARP_Y

# --- Balls ------------------------------------------------------------------------------------------------
RUBBER, LUCKY = 5, 6
BALL_TYPES = 7  # IDs 0-6 in the shop draw
RUBBER_BOUNCE = 0.95
LUCKY_LANE_FACTOR = 2
# id: name, description, price, material, colour, glow, mass scale, launch speed scale
NEW_BALLS = {
    RUBBER: ("고무공", "벽 반발 95%", 4, "MI_Ball_Rubber", (0.95, 0.35, 0.62), 0.3, 1.0, 1.0),
    LUCKY: ("행운의 공", "골 배율 2배", 5, "MI_Ball_Lucky", (0.30, 0.95, 0.30), 0.6, 1.0, 1.0),
}

# Same as apply_table_tuning.py: the playfield grew from 577 to 623 cm across, and so did what's on it.
PLAYFIELD_SCALE = (335.0 + 288.0) / (289.0 + 288.0)
OBSTACLE_SCALE = 0.3 * PLAYFIELD_SCALE  # round bumpers were 0.3 (30 cm)
OBSTACLE_Z = 15.0 * PLAYFIELD_SCALE  # standing on the bed

# --- Machine screen cards (main's layout: three 122-high cards from y 290, 130 apart) ---------------------
INV_ROWS = 3
INV_Y0, INV_STEP, INV_H = 290, 130, 122
PANEL = "(R=0.016,G=0.010,B=0.008,A=0.86)"
SEL = "(R=0.95,G=0.06,B=0.05,A=1)"
FRAME = "(R=0.30,G=0.15,B=0.07,A=1)"
TEXT = "(R=0.86,G=0.79,B=0.66,A=1)"
SUB = "(R=0.56,G=0.46,B=0.36,A=1)"
ACCENT = "(R=0.95,G=0.36,B=0.16,A=1)"


# --- Node helpers -----------------------------------------------------------------------------------------
BPS = {}
DECLARING = {}


def class_path(bp):
    return bp.generated_class().get_path_name()


def members(bp):
    names = set(str(n) for n in unreal.BlueprintEditorLibrary.list_member_variable_names(bp, False))
    sub = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    lib = unreal.SubobjectDataBlueprintFunctionLibrary
    for handle in sub.k2_gather_subobject_data_for_blueprint(bp):
        obj = lib.get_object(sub.k2_find_subobject_data_from_handle(handle))
        if obj:
            names.add(obj.get_name().replace("_GEN_VARIABLE", ""))
    return names


def make_node(graph, type_id, pos, declaring_class=None):
    """Node factory for the DSL. Headless, the editor's node list has none of the Blueprints' own variables
    or functions, so "|GetX", "|SetX" and "|Func" are built with the member-node calls - on this Blueprint
    first, then on the other game Blueprints (those carry a "self" pin: pass :self <target>)."""
    if not type_id.startswith("|") or type_id.endswith("..."):  # "|AddReturnNode..." is the editor's own
        if declaring_class is None and type_id in DECLARING:
            declaring_class = DECLARING[type_id].static_class()
        return BT.create_node(graph, type_id, pos, declaring_class)
    name = type_id[1:]
    owner = unreal.Blueprint.cast(graph.get_outer())
    order = [owner] + [bp for bp in BPS.values() if bp.get_path_name() != owner.get_path_name()]
    editor = unreal.BlueprintGraphEditor.get_graph_editor(graph)
    node = None
    if name[:3] in ("Get", "Set"):
        for bp in order:
            if name[3:] in members(bp):
                path = "" if bp is owner else class_path(bp)
                node = (editor.add_get_member_variable_node(name[3:], path) if name.startswith("Get")
                        else editor.add_set_member_variable_node(name[3:], path))
                if node:
                    break
    if node is None:
        for bp in order:
            node = editor.add_call_function_node(f"{class_path(bp)}:{name}")
            if node:
                break
    if node is None:
        raise RuntimeError(f"Could not make a node for {type_id}")
    node.set_node_pos(pos)
    return node


def infos_of(graph):
    return BT.get_node_infos(BT.find_nodes(graph))


def pin(info, name):
    return next(p for p in list(info.input_pins) + list(info.output_pins) if p.name == name)


def value_out(info):
    return next(p for p in info.output_pins if p.type_id != "Exec")


def transpile(graph, code):
    blueprint_dsl.Transpiler(
        graph, make_node, BT.connect_pins, BT._get_node_info, BT.set_pin_value,
        lambda g: BT.find_nodes(g), delete_node_fn=BT.delete_node,
        find_node_types_fn=lambda f: BT.find_node_types(graph, f),
    ).transpile(code)


def function(bp, name, params, code):
    """Creates or rebuilds a function with no return value. params: [(name, type or class), ...]."""
    if name in [g.get_name() for g in BT.list_graphs(bp)]:
        graph = BT.get_graph(bp, name)
        for node in BT.find_nodes(graph):
            if isinstance(node, unreal.K2Node_FunctionResult):
                raise RuntimeError(f"{name} returns a value; use rebuild_returning")
            if not isinstance(node, unreal.K2Node_FunctionEntry):
                BT.delete_node(node)
    else:
        graph = BT.add_function_graph(bp, name)
        for pname, ptype in params:
            if isinstance(ptype, str):
                BT.add_function_param(graph, pname, ptype, True)
            else:
                BT.add_object_function_param(graph, pname, ptype.static_class(), True)
    transpile(graph, code)


def rebuild_returning(bp, name, code):
    """Rebuilds an existing function that returns a value, keeping its signature (so every caller stays
    wired). The DSL needs a result node to exist to know the function returns something, so one old result
    node is kept while the new body is written, then removed."""
    graph = BT.get_graph(bp, name)
    keep = None
    for node in BT.find_nodes(graph):
        if isinstance(node, unreal.K2Node_FunctionEntry):
            continue
        if isinstance(node, unreal.K2Node_FunctionResult) and keep is None:
            keep = node
            continue
        BT.delete_node(node)
    if keep is None:
        raise RuntimeError(f"{name} has no result node")
    for p in BT._get_node_info(keep).input_pins:  # cut the kept node loose
        for c in list(p.connected_pins):
            BT.break_pins(c, p.pin_id)
    transpile(graph, code)
    results = [n for n in BT.find_nodes(graph) if isinstance(n, unreal.K2Node_FunctionResult)]
    if len(results) > 1:
        BT.delete_node(keep)


def add_variables(bp, wanted, category):
    existing = set(str(v) for v in BT.list_variables(bp))
    for name, kind, container in wanted:
        if name in existing:
            continue
        if isinstance(kind, str):
            BT.add_variable(bp, name, kind, container_type=container)
        else:
            BT.add_object_variable(bp, name, kind.static_class(), container_type=container)
        BT.set_variable_category(bp, name, category)


def insert_after(graph, host, callee, args=(), literals=()):
    """Puts a call to `callee` right after `host` (on its "then"), unless host's "then" already leads to it.
    args = [(callee pin, source PinID)], literals = [(callee pin, value)]."""
    out = pin(host, "then")
    nxt = [BT._get_node_info(c.node) for c in out.connected_pins]
    if any(n.type_id == f"|{callee}" for n in nxt):
        return False
    existing = {i.node.get_name() for i in infos_of(graph)}
    make_node(graph, f"|{callee}", unreal.IntPoint(host.position.x + 200, host.position.y + 260))
    call = next(i for i in infos_of(graph) if i.node.get_name() not in existing)
    BT.connect_pins(out.pin_id, pin(call, "execute").pin_id)
    for n in nxt:
        BT.connect_pins(pin(call, "then").pin_id, pin(n, "execute").pin_id)
    call = BT._get_node_info(call.node)
    for callee_pin, source in args:
        BT.connect_pins(source, pin(call, callee_pin).pin_id)
    for callee_pin, value in literals:
        BT.set_pin_value(pin(call, callee_pin).pin_id, value)
    return True


def insert_call(bp, graph_name, host_pred, callee, args=()):
    """Calls `callee` once, right after the node matched by host_pred, passing host output pins as
    arguments: args = [(callee pin, host pin)]. Extra copies (from older runs) are cut out of the chain."""
    graph = BT.get_graph(bp, graph_name)
    calls = [i for i in infos_of(graph) if i.type_id == f"|{callee}"]
    for extra in calls[1:]:
        for source in pin(extra, "execute").connected_pins:
            for target in pin(extra, "then").connected_pins:
                BT.connect_pins(source, target)
        BT.delete_node(extra.node)
    if calls:
        return
    host = next(i for i in infos_of(graph) if host_pred(i))
    insert_after(graph, host, callee, [(c, pin(host, h).pin_id) for c, h in args])


def is_entry(i):
    return isinstance(i.node, unreal.K2Node_FunctionEntry)


GREATER = ("Utilities|Operators|Greater(>)", "Math|Integer|integer>integer")
RANDOM_INT = ("Math|Random|RandomIntegerInRange",)


def set_literals(bp, graph_name, node_types, pin_name, old, new):
    """Sets pin `pin_name` on nodes of any of `node_types` from `old` to `new` (only pins still holding
    `old`; a rerun finds nothing left to change)."""
    wanted = {t.lower() for t in node_types}
    changed = 0
    for info in infos_of(BT.get_graph(bp, graph_name)):
        if info.type_id.lower() not in wanted:
            continue
        p = next((p for p in info.input_pins if p.name == pin_name), None)
        if p is None or p.connected_pins:
            continue
        try:
            if abs(float(p.value) - old) < 1e-6:
                BT.set_pin_value(p.pin_id, str(new))
                changed += 1
        except ValueError:
            pass
    unreal.log(f"BUMPIT_LITERAL {bp.get_name()}.{graph_name} {pin_name} {old}->{new}: {changed}")
    return changed


def colour_material(name, colour, glow):
    """A colour of main's M_BumpitMood, like main's MI_Ball_* and MI_Cell_* (Color, Glow, Roughness)."""
    mel = unreal.MaterialEditingLibrary
    path = f"{MATERIALS}/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        mi = unreal.load_asset(path)
    else:
        mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, MATERIALS, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, unreal.load_asset(PARENT_MATERIAL))
    mel.set_material_instance_vector_parameter_value(mi, "Color", unreal.LinearColor(*colour, 1.0))
    mel.set_material_instance_scalar_parameter_value(mi, "Glow", glow)
    mel.set_material_instance_scalar_parameter_value(mi, "Roughness", 0.82)
    mel.update_material_instance(mi)
    unreal.EditorAssetLibrary.save_loaded_asset(mi)
    return mi


def mat_path(name):
    return f"{MATERIALS}/{name}.{name}"


# --- Table ------------------------------------------------------------------------------------------------
def subobjects(bp):
    sub = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    lib = unreal.SubobjectDataBlueprintFunctionLibrary
    found = {}
    handles = sub.k2_gather_subobject_data_for_blueprint(bp)
    for handle in handles:
        obj = lib.get_object(sub.k2_find_subobject_data_from_handle(handle))
        if obj:
            found.setdefault(obj.get_name().replace("_GEN_VARIABLE", ""), (handle, obj))
    return sub, handles[0], found


def add_component(bp, name, cls):
    """Returns the component, adding it if missing. An existing one is kept (and updated by the caller):
    deleting and re-adding it would cut every graph node that reads it."""
    sub, root, found = subobjects(bp)
    if name in found:
        return found[name][1]
    params = unreal.AddNewSubobjectParams(parent_handle=found["DefaultSceneRoot"][0], new_class=cls, blueprint_context=bp)
    handle, reason = sub.add_new_subobject(params)
    if not unreal.SubobjectDataBlueprintFunctionLibrary.is_handle_valid(handle):
        raise RuntimeError(f"Could not add {name}: {reason}")
    sub.rename_subobject(handle, unreal.Text(name))
    return unreal.SubobjectDataBlueprintFunctionLibrary.get_object(sub.k2_find_subobject_data_from_handle(handle))


def build_table_parts(table):
    """One instanced mesh per gimmick bumper, a hidden instance per hex cell - same as main's round bumpers,
    whose mesh, collision and tags (Bumper, RoundBumper) they copy, plus their own tag."""
    _, _, found = subobjects(table)
    round_bumpers = found["RoundBumpers"][1]
    cells = [round_bumpers.get_instance_transform(i, False) for i in range(round_bumpers.get_instance_count())]
    for name, tag, _, material, colour, glow in GIMMICK_BUMPERS:
        part = add_component(table, name, unreal.InstancedStaticMeshComponent)
        part.set_editor_property("static_mesh", round_bumpers.static_mesh)
        part.set_editor_property("body_instance", round_bumpers.get_editor_property("body_instance"))
        part.set_editor_property("override_materials", [colour_material(material, colour, glow)])
        part.set_editor_property("component_tags", [t for t in round_bumpers.component_tags] + [unreal.Name(tag)])
        part.clear_instances()
        for transform in cells:
            part.add_instance(transform, False)


def hide_or_show(component, type_id):
    s = f"{OBSTACLE_SCALE:.5f}"
    cell = "(Math|Vector|MakeVector (.x c) (.y c) {z})"
    transform = f"(Math|Transform|MakeTransform {cell} (Math|Rotator|MakeRotator 0.0 0.0 0.0) (Math|Vector|MakeVector {s} {s} {s}))"
    update = f"(Components|InstancedStaticMesh|UpdateInstanceTransform (|Get{component}) Index {transform} false true true)"
    return f"""
    (if (== Type {type_id})
      {update.format(z=f"{OBSTACLE_Z:.3f}")}
      (else
        {update.format(z="-3000.0")}))"""


SET_GIMMICKS = """
(fn SetGimmicks (Index Type)
  (if (and (>= Index 0) (< Index 48))
    (bind c (|HexCenter :Index Index))""" + "".join(hide_or_show(g[0], 4 + i) for i, g in enumerate(GIMMICK_BUMPERS)) + """
    (if (== Type 5)
      (Utilities|Array|AddUnique (|GetMagnetCells) Index)
      (else
        (Utilities|Array|RemoveItem (|GetMagnetCells) Index)))))
"""

# After main's ReflectBumper on either ball. Split = the hit was the split ball (its hits are SplitHits).
APPLY_GIMMICK = f"""
(fn ApplyGimmick (Comp TargetBall Split)
  (bind now (Utilities|Time|GetGameTimeinSeconds))
  (if (> (- now (|GetLastGimmickTime)) 0.1)
    (if (Components|ComponentHasTag Comp "Blast")
      (|SetLastGimmickTime now)
      (Physics|SetPhysicsLinearVelocity TargetBall (* (Physics|GetPhysicsLinearVelocity TargetBall) (|GetBlastBoost)) false))
    (if (Components|ComponentHasTag Comp "Gold")
      (|SetLastGimmickTime now)
      (if Split
        (|SetSplitHits (+ (|GetSplitHits) (|GetGoldHits)))
        (else
          (|SetHits (+ (|GetHits) (|GetGoldHits))))))
    (if (Components|ComponentHasTag Comp "Warp")
      (|SetLastGimmickTime now)
      (Transformation|SetWorldLocation TargetBall (Math|Transform|TransformLocation (Transformation|GetActorTransform) (Math|Vector|MakeVector {WARP_X} (Math|Random|RandomFloatinRange -{WARP_Y} {WARP_Y}) 12.0)) false true))))
"""

PULL_BALL = """
(fn PullBall (TargetBall)
  (if (Physics|IsSimulatingPhysics TargetBall)
    (for i (range (Utilities|Array|Length (|GetMagnetCells)))
      (bind d (- (Math|Transform|TransformLocation (Transformation|GetActorTransform) (|HexCenter :Index (Utilities|Array|Get(acopy) (|GetMagnetCells) i))) (Transformation|GetWorldLocation TargetBall)))
      (bind dist (Math|Vector|VectorLength d))
      (if (and (< dist (|GetMagnetRadius)) (> dist 1.0))
        (Physics|AddForce TargetBall (* (/ d dist) (* (|GetMagnetStrength) (- 1.0 (/ dist (|GetMagnetRadius))))) "None" true)))))
"""

MAGNET_PULL = """
(fn MagnetPull ()
  (if (> (Utilities|Array|Length (|GetMagnetCells)) 0)
    (|PullBall :TargetBall (|GetBall))
    (|PullBall :TargetBall (|GetSplitBall))))
"""

# Rubber ball: the wall bounce is worked out here (the physical-material override isn't callable from
# Blueprint). Only the main ball can be a rubber ball; main's split ball comes from the split ball type.
BALL_WALL_HIT = f"""
(fn BallWallHit (Comp NormalImpulse)
  (bind now (Utilities|Time|GetGameTimeinSeconds))
  (if (and (== (|GetActiveBallType :self (|GetActiveRules)) {RUBBER}) (and (not (Components|ComponentHasTag Comp "RoundBumper")) (> (- now (|GetLastBounceTime)) 0.05)))
    (bind n (Math|Vector|Normalize NormalImpulse))
    (bind v (|GetIncomingVelocity))
    (bind dot (Math|Vector|DotProduct v n))
    (if (and (< dot 0.0) (< (Math|Float|Absolute(Float) (Math|Vector|DotProduct n (Transformation|GetActorUpVector))) 0.7))
      (|SetLastBounceTime now)
      (|SetIncomingVelocity (- v (* n (* dot (+ 1.0 (|GetRubberBounce))))))
      (Physics|SetPhysicsLinearVelocity (|GetBall) (|GetIncomingVelocity) false))))
"""
# ActiveRules is set by the HUD's CreateRoundRules when the game starts, before any ball can hit anything.


def bound_event(graph, component):
    for info in infos_of(graph):
        if isinstance(info.node, unreal.K2Node_ComponentBoundEvent):
            try:
                name = str(info.node.get_editor_property("component_property_name"))
            except Exception:
                name = info.node.get_node_title().split("(")[-1].rstrip(")")
            if name == component:
                return info
    raise RuntimeError(f"No hit event for {component}")


def wire_gimmicks_after_reflect(table):
    """After each of main's ReflectBumper calls (one per ball), ApplyGimmick on the same ball."""
    graph = BT.get_graph(table, "EventGraph")
    events = {"|GetBall": bound_event(graph, "Ball"), "|GetSplitBall": bound_event(graph, "SplitBall")}
    for info in infos_of(graph):
        if info.type_id != "|ReflectBumper":
            continue
        source = pin(info, "TargetBall").connected_pins[0]
        getter = BT._get_node_info(source.node).type_id
        if getter not in events:
            raise RuntimeError(f"ReflectBumper target is {getter}")
        insert_after(graph, info, "ApplyGimmick",
                     [("Comp", pin(events[getter], "OtherComp").pin_id), ("TargetBall", source)],
                     [("Split", "true" if getter == "|GetSplitBall" else "false")])


def apply_table(table):
    build_table_parts(table)
    add_variables(table, [
        ("MagnetCells", "int", ContainerType.ARRAY), ("LastGimmickTime", "float", None),
        ("LastBounceTime", "float", None), ("BlastBoost", "float", None), ("GoldHits", "int", None),
        ("MagnetRadius", "float", None), ("MagnetStrength", "float", None), ("RubberBounce", "float", None),
    ], "Gimmicks")
    BT.compile_blueprint(table)
    function(table, "SetGimmicks", [("Index", "int"), ("Type", "int")], SET_GIMMICKS)
    function(table, "ApplyGimmick", [("Comp", unreal.PrimitiveComponent), ("TargetBall", unreal.PrimitiveComponent),
                                     ("Split", "bool")], APPLY_GIMMICK)
    function(table, "PullBall", [("TargetBall", unreal.PrimitiveComponent)], PULL_BALL)
    function(table, "BallWallHit", [("Comp", unreal.PrimitiveComponent), ("NormalImpulse", "Vector")], BALL_WALL_HIT)
    BT.compile_blueprint(table)
    function(table, "MagnetPull", [], MAGNET_PULL)
    BT.compile_blueprint(table)
    insert_call(table, "SetObstacle", is_entry, "SetGimmicks", [("Index", "Index"), ("Type", "Type")])
    events = BT.get_graph(table, "EventGraph")
    ball_hit = bound_event(events, "Ball")
    insert_call(table, "EventGraph", lambda i: i.node == ball_hit.node, "BallWallHit",
                [("Comp", "OtherComp"), ("NormalImpulse", "NormalImpulse")])
    wire_gimmicks_after_reflect(table)
    tick = lambda i: isinstance(i.node, unreal.K2Node_Event) and "Tick" in i.node.get_node_title()
    insert_call(table, "EventGraph", tick, "MagnetPull")
    BT.compile_blueprint(table, warnings_as_errors=True)
    cdo = BT.get_default_object(table)
    for name, value in (("BlastBoost", BLAST_BOOST), ("GoldHits", GOLD_HITS), ("MagnetRadius", MAGNET_RADIUS),
                        ("MagnetStrength", MAGNET_STRENGTH), ("RubberBounce", RUBBER_BOUNCE)):
        cdo.set_editor_property(name, value)


# --- Round rules: balls 5 and 6 in main's ball tables -----------------------------------------------------
def chain(values, fallback, i=0):
    """main's (if (== Type 0) (return a) (elif (== Type 1) (return b) ... (else (return fallback))))"""
    if i == len(values):
        return f"(else\n  (return {fallback}))"
    return f"({'if' if i == 0 else 'elif'} (== Type {i})\n  (return {values[i]})\n  {chain(values, fallback, i + 1)})"


def quoted(s):
    return '"' + s + '"'


# main's values for IDs 0-4, then ours.
BALL_NAME = ["일반공", "범퍼 강화공", "분열공", "무거운 공", "가벼운 공"] + [NEW_BALLS[i][0] for i in (RUBBER, LUCKY)]
BALL_COST = [3, 5, 5, 4, 4] + [NEW_BALLS[i][2] for i in (RUBBER, LUCKY)]
BALL_DESCRIPTION = ["기본 구슬", "범퍼 충돌 점수만 2배", "첫 반사 때 공이 2개로 분열", "질량 2배 · 발사 속도 85%",
                    "질량 0.5배 · 발사 속도 115%"] + [NEW_BALLS[i][1] for i in (RUBBER, LUCKY)]

LANE_MULTIPLIER = f"""
(fn LaneMultiplier (Lane)
  (bind luck (select (== (|GetActiveBallType) {LUCKY}) {LUCKY_LANE_FACTOR} 1))
  (if (Utilities|Array|IsValidIndex (|GetMultipliers) Lane)
    (return (* (Utilities|Array|Get(acopy) (|GetMultipliers) Lane) luck))
    (else
      (return luck))))
"""


def apply_rules(rules):
    rebuild_returning(rules, "BallName", "(fn BallName (Type)\n  " + chain([quoted(s) for s in BALL_NAME], quoted("구매 완료")) + ")")
    rebuild_returning(rules, "BallCost", "(fn BallCost (Type)\n  " + chain([str(c) for c in BALL_COST], "0") + ")")
    rebuild_returning(rules, "BallDescription", "(fn BallDescription (Type)\n  " + chain(
        [quoted(s) for s in BALL_DESCRIPTION], quoted("다음 스테이지에서 다시 채워집니다")) + ")")
    rebuild_returning(rules, "LaneMultiplier", LANE_MULTIPLIER)
    for graph in ("ResetShop", "RerollOffers"):  # the shop draws IDs 0..BALL_TYPES-1
        set_literals(rules, graph, RANDOM_INT, "Max", 4, BALL_TYPES - 1)
    BT.compile_blueprint(rules, warnings_as_errors=True)


# --- HUD --------------------------------------------------------------------------------------------------
UPDATE_INVENTORY = f"""
(fn UpdateInventory ()
  (if (== (|GetStation) 1)
    (bind pc (HUD|GetOwningPlayerController))
    (bind count (Utilities|Array|Length (|GetStock)))
    (if (> count 0)
      (if (Game|Player|WasInputKeyJustPressed pc "MouseScrollDown")
        (|SetSelected (Math|Integer|%(Integer) (+ (|GetSelected) 1) count)))
      (if (Game|Player|WasInputKeyJustPressed pc "MouseScrollUp")
        (|SetSelected (Math|Integer|%(Integer) (+ (|GetSelected) (- count 1)) count)))
      (bind (clicked px py) (|ClickedHudPoint))
      (if clicked
        (for row (range {INV_ROWS})
          (if (and (< (+ row (|GetInvScroll)) count) (|InsideRect :PointX px :PointY py :X 886.0 :Y (+ {INV_Y0}.0 (* (Math|Conversions|ToFloat(Integer) row) {INV_STEP}.0)) :W 295.0 :H {INV_H}.0))
            (|SetSelected (+ row (|GetInvScroll))))))
      (if (< (|GetSelected) (|GetInvScroll))
        (|SetInvScroll (|GetSelected)))
      (if (>= (|GetSelected) (+ (|GetInvScroll) {INV_ROWS}))
        (|SetInvScroll (+ (- (|GetSelected) {INV_ROWS}) 1))))))
"""

BAR_H = INV_ROWS * INV_STEP - (INV_STEP - INV_H)
DRAW_BUMPER_SLOTS = f"""
(fn DrawBumperSlots ()
  (for row (range {INV_ROWS})
    (bind item (+ row (|GetInvScroll)))
    (bind y (+ {INV_Y0}.0 (* (Math|Conversions|ToFloat(Integer) row) {INV_STEP}.0)))
    (if (< item (Utilities|Array|Length (|GetStock)))
      (|Panel :X 886.0 :Y y :W 295.0 :H {INV_H}.0 :Tint "{PANEL}")
      (if (== item (|GetSelected))
        (|Frame :X 886.0 :Y y :W 295.0 :H {INV_H}.0 :Line 4.0 :Tint "{SEL}")
        (else
          (|Frame :X 886.0 :Y y :W 295.0 :H {INV_H}.0 :Line 2.0 :Tint "{FRAME}")))
      (|Panel :X 902.0 :Y (+ y 18.0) :W 86.0 :H 86.0 :Tint (Utilities|Array|Get(acopy) (|GetObstacleTints) item))
      (|Label :Caption (Utilities|Array|Get(acopy) (|GetObstacleNames) item) :X 1002.0 :Y (+ y 30.0) :Size 1.12 :Tint "{TEXT}")
      (|Label :Caption (Utilities|String|BuildString(Integer) "" "보관함: " (Utilities|Array|Get(acopy) (|GetStock) item) "개") :X 1002.0 :Y (+ y 68.0) :Size 1.0 :Tint "{SUB}")
      (if (|GetChoicePending :self (|GetRules))
        (|Label :Caption "클릭: 무료 선택" :X 1002.0 :Y (+ y 94.0) :Size 0.78 :Tint "{ACCENT}")
        (else
          (|Label :Caption "선택 완료 · 보관함 사용" :X 1002.0 :Y (+ y 94.0) :Size 0.72 :Tint "{SUB}")))))
  (if (> (Utilities|Array|Length (|GetStock)) {INV_ROWS})
    (|Panel :X 1185.0 :Y {INV_Y0}.0 :W 5.0 :H {BAR_H}.0 :Tint "{FRAME}")
    (|Panel :X 1185.0 :Y (+ {INV_Y0}.0 (/ (* {BAR_H}.0 (Math|Conversions|ToFloat(Integer) (|GetInvScroll))) (Math|Conversions|ToFloat(Integer) (Utilities|Array|Length (|GetStock))))) :W 5.0 :H (/ {BAR_H * INV_ROWS}.0 (Math|Conversions|ToFloat(Integer) (Utilities|Array|Length (|GetStock)))) :Tint "{ACCENT}"))
  (|DrawTiltCount)
  (|DrawSideArrow :Caption "상점")
  (|DrawLiveScore))
"""


def refresh_branch(type_id, mass, material, speed):
    return (f"(Physics|SetMassScale ball \"None\" {mass})\n"
            f"      (Rendering|Material|SetMaterial ball 0 \"{material}\")\n"
            f"      (|SetWeightSpeedScale :self (|GetTable) :WeightSpeedScale {speed})")


def refresh_ball_code():
    """main's RefreshBall, with branches for balls 5 and 6 after main's five."""
    branches = [  # main's: mass scale, material, launch speed scale
        (1.0, mat_path("MI_Cell_950_960_990"), 1.0),
        (1.0, mat_path("MI_Ball_Score"), 1.0),
        (1.0, mat_path("MI_Ball_Demolition"), 1.0),
        (2.0, mat_path("MI_Ball_Heavy"), 0.85),
        (0.5, mat_path("MI_Ball_Light"), 1.15),
    ] + [(NEW_BALLS[i][6], mat_path(NEW_BALLS[i][3]), NEW_BALLS[i][7]) for i in (RUBBER, LUCKY)]
    body = ""
    for i in reversed(range(len(branches))):
        mass, material, speed = branches[i]
        inner = refresh_branch(i, mass, material, speed)
        body = (f"({'if' if i == 0 else 'elif'} (== (|GetActiveBallType :self (|GetRules)) {i})\n      {inner}"
                + (f"\n      {body}" if body else "") + ")")
    return f"""
(fn RefreshBall ()
  (bind ball (|GetBall :self (|GetTable)))
  (|SetActiveBallType :self (|GetRules) :ActiveBallType 0)
  (if (> (|GetMaxBalls :self (|GetRules)) (|GetBallsUsed :self (|GetRules)))
    (|SetActiveBallType :self (|GetRules) :ActiveBallType (Utilities|Array|Get(acopy) (|GetBallQueue :self (|GetRules)) (|GetBallsUsed :self (|GetRules)))))
  (|SetSpecialUsed :self (|GetRules) :SpecialUsed false)
  {body})
"""


def drop_old_wheel(hud):
    """main's UpdateBoard opens with Selected = NextSelection(...), the old 3-card wheel and click handling.
    UpdateInventory does that now for the 7-card list, so that step goes."""
    graph = BT.get_graph(hud, "UpdateBoard")
    for info in infos_of(graph):
        if not info.type_id.endswith("|SetSelected"):
            continue
        sources = [BT._get_node_info(c.node) for c in pin(info, "Selected").connected_pins]
        if not sources or sources[0].type_id != "|NextSelection":
            continue
        for src in pin(info, "execute").connected_pins:
            for dst in pin(info, "then").connected_pins:
                BT.connect_pins(src, dst)
        BT.delete_node(info.node)
        BT.delete_node(sources[0].node)


BOARD_HEAD = ("UpdateInventory",)  # what UpdateBoard runs first, in this order


def order_board_head(hud):
    """Rewires the start of UpdateBoard as entry -> UpdateInventory -> the rest, whatever state it is in
    (an older Mood version once left these calls wired in a circle: an endless loop)."""
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
    for node in [entry.node] + [i.node for i in head]:
        for p in exec_pins(BT._get_node_info(node), "out"):
            for c in list(p.connected_pins):
                BT.break_pins(p.pin_id, c)
    for node in [i.node for i in head]:
        for p in exec_pins(BT._get_node_info(node), "in"):
            for c in list(p.connected_pins):
                BT.break_pins(c, p.pin_id)
    chain_nodes = [entry] + [BT._get_node_info(i.node) for i in head] + [BT._get_node_info(rest.node)]
    for a, b in zip(chain_nodes, chain_nodes[1:]):
        out = next(p for p in exec_pins(BT._get_node_info(a.node), "out") if p.name == "then")
        inp = next(p for p in exec_pins(BT._get_node_info(b.node), "in") if p.name == "execute")
        BT.connect_pins(out.pin_id, inp.pin_id)
    unreal.log(f"BUMPIT_BOARD_HEAD entry -> {' -> '.join(i.type_id for i in chain_nodes[1:])}")


def remap_choice_cards(hud):
    """PointerInput: main's card clicks call ChooseObstacle(0/1/2) by card position. With the list scrolled,
    card k is obstacle k + InvScroll."""
    graph = BT.get_graph(hud, "PointerInput")
    for info in infos_of(graph):
        if info.type_id != "|ChooseObstacle":
            continue
        type_pin = pin(info, "Type")
        if type_pin.connected_pins:
            continue  # already remapped
        row = int(float(type_pin.value or 0))
        add = BT.create_node(graph, "Utilities|Operators|Add", unreal.IntPoint(info.position.x - 260, info.position.y + 140))
        scroll = BT._get_node_info(make_node(graph, "|GetInvScroll", unreal.IntPoint(info.position.x - 480, info.position.y + 140)))
        BT.connect_pins(value_out(scroll).pin_id, pin(BT._get_node_info(add), "A").pin_id)
        BT.set_pin_value(pin(BT._get_node_info(add), "B").pin_id, str(row))
        BT.connect_pins(value_out(BT._get_node_info(add)).pin_id, type_pin.pin_id)


def stock_slots(hud):
    graph = BT.get_graph(hud, "InitializeBoard")
    for info in infos_of(graph):
        if info.type_id == "Utilities|Array|Resize":
            target = BT._get_node_info(pin(info, "TargetArray").connected_pins[0].node)
            if target.type_id == "|GetStock":
                BT.set_pin_value(pin(info, "Size").pin_id, str(STOCK_SLOTS))


def apply_hud(hud):
    for i in (RUBBER, LUCKY):
        name, _, _, material, colour, glow, _, _ = NEW_BALLS[i]
        colour_material(material, colour, glow)
    add_variables(hud, [
        ("InvScroll", "int", None), ("ObstacleNames", "string", ContainerType.ARRAY),
        ("ObstacleTints", "LinearColor", ContainerType.ARRAY),
    ], "Gimmicks")
    BT.compile_blueprint(hud)
    function(hud, "UpdateInventory", [], UPDATE_INVENTORY)
    function(hud, "DrawBumperSlots", [], DRAW_BUMPER_SLOTS)
    function(hud, "RefreshBall", [], refresh_ball_code())
    BT.compile_blueprint(hud)
    insert_call(hud, "UpdateBoard", is_entry, "UpdateInventory")
    drop_old_wheel(hud)
    order_board_head(hud)
    remap_choice_cards(hud)
    stock_slots(hud)
    set_literals(hud, "ChooseObstacle", GREATER, "B", 2, STOCK_SLOTS - 1)
    set_literals(hud, "Purchase", GREATER, "B", 4, BALL_TYPES - 1)
    BT.compile_blueprint(hud, warnings_as_errors=True)
    cdo = BT.get_default_object(hud)
    names = [n for n, _ in BASE_OBSTACLES] + [g[2] for g in GIMMICK_BUMPERS]
    tints = [unreal.LinearColor(*c, 1.0) for _, c in BASE_OBSTACLES] + [unreal.LinearColor(*g[4], 1.0) for g in GIMMICK_BUMPERS]
    for name, value in (("ObstacleNames", names), ("ObstacleTints", tints), ("InvScroll", 0)):
        cdo.set_editor_property(name, value)


with toolset_registry.tool_raising_exceptions():
    BPS.update(table=unreal.load_asset(TABLE), hud=unreal.load_asset(HUD), rules=unreal.load_asset(RULES))
    DECLARING["Rendering|Material|SetMaterial"] = unreal.PrimitiveComponent
    apply_table(BPS["table"])
    apply_rules(BPS["rules"])
    apply_hud(BPS["hud"])
    for bp in BPS.values():
        unreal.EditorAssetLibrary.save_loaded_asset(bp)
unreal.log("BUMPIT_GIMMICKS_APPLIED")
