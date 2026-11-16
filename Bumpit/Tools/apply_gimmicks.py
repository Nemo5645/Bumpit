"""Gimmick bumpers and special balls. Safe to run repeatedly; tune the tables below.
Run this first, then apply_shop_showcase.py (the shop list reads the ball stock this script adds).

Run with the editor closed (-culture=en matters: the Blueprint text tools need English node names):
UnrealEditor-Cmd.exe Bumpit.uproject -run=pythonscript -script=<this file> -unattended -nullrhi -culture=en

Bumpers (obstacle types 4-7; 1-3 are the round bumper and the two deflectors). Each is an instanced mesh on
BP_PinballTable with one hidden instance per hex cell, like the round bumpers, and bounces like a round bumper:
  4 Blast  - after the bounce the ball's speed is multiplied by BlastBoost
  5 Magnet - pulls the ball towards it inside MagnetRadius (MagnetPull, every tick)
  6 Gold   - each bounce adds GoldHits extra hits (25 points each, before the lane multiplier)
  7 Warp   - moves the ball to a random spot near the top of the table
SetObstacle calls SetGimmicks first, so placing, removing and breaking cells all work for the new types.

Balls (ball types 1-4; 0 is the normal ball, always available). Bought in the shop into BallStock, chosen on
the machine screen with Q / E, used up one per launch:
  1 Heavy  - mass x3, walls only give back 15% of the speed, score x2
  2 Rubber - walls give back 95% of the speed
  3 Lucky  - lane multiplier x2
  4 Fire   - every bumper hit counts twice
The wall bounce is worked out in BallWallHit (the engine's physical-material override isn't callable from
Blueprint here); the score effects are multipliers spliced into BP_BumpitHUD.Settle.

Machine screen: the inventory is a scrolling list (wheel or click). Q / E step through every ball; the ball
waiting in the lane takes the chosen ball's colour (faded if it hasn't been bought) and the message line names
it. A ball not bought can't be launched - Space neither charges nor fires until a bought ball is chosen.

Obstacle sizes follow PLAYFIELD_SCALE, which must match apply_table_tuning.py (run that one before this).
"""
import unreal
import toolset_registry
from editor_toolset.toolsets import blueprint_dsl
from editor_toolset.toolsets.blueprint import BlueprintTools as BT, ContainerType

TABLE = "/Game/Bumpit/Blueprints/BP_PinballTable"
HUD = "/Game/Bumpit/Blueprints/BP_BumpitHUD"
RULES = "/Game/Bumpit/Blueprints/BP_RoundRules"
SHOWCASE_MI = "/Game/Bumpit/Materials/Showcase/MI_Showcase_{:02d}"  # made by apply_shop_showcase.py

# --- Bumpers ----------------------------------------------------------------------------------------------
GIMMICK_BUMPERS = [  # component, tag, shelf material index; obstacle types 4, 5, 6, 7 in this order
    ("BlastBumpers", "Blast", 0),
    ("MagnetBumpers", "Magnet", 1),
    ("GoldBumpers", "Gold", 2),
    ("WarpBumpers", "Warp", 3),
]
BLAST_BOOST = 1.8
GOLD_HITS = 4
MAGNET_RADIUS = 130.0  # cm
MAGNET_STRENGTH = 1600.0  # cm/s^2 at the magnet, fading to 0 at the radius
WARP_X, WARP_Y = 300.0, 220.0  # table space: near the top rail, anywhere across +-WARP_Y
STOCK_SLOTS = 7  # round bumper, two deflectors, four gimmick bumpers

# --- Balls ------------------------------------------------------------------------------------------------
BALL_NAMES = ["기본 공", "쇳덩이 공", "고무공", "행운의 공", "불꽃 공"]
BALL_MATERIALS = ["/Game/Bumpit/Materials/MI_Cell_950_960_990"] + [SHOWCASE_MI.format(i) for i in (4, 5, 6, 7)]
BALL_MASS = [1.0, 3.0, 1.0, 1.0, 1.0]
BALL_BOUNCE = [-1.0, 0.15, 0.95, -1.0, -1.0]  # share of speed a wall gives back; -1 leaves it to the engine
BALL_HIT_FACTOR = [1, 1, 1, 1, 2]
BALL_LANE_FACTOR = [1, 1, 1, 2, 1]
BALL_SCORE_FACTOR = [1, 2, 1, 1, 1]
FADE_TO_GREY = 0.6  # a ball not bought yet: its colour this far towards grey, and barely glowing
FADED_MI = "/Game/Bumpit/Materials/Showcase/MI_BallFaded_{:02d}"

# Same as apply_table_tuning.py: the playfield grew from 577 to 623 cm across, and so did what's on it.
PLAYFIELD_SCALE = (335.0 + 288.0) / (289.0 + 288.0)
OBSTACLE_SCALE = 0.3 * PLAYFIELD_SCALE  # round bumpers were 0.3 (30 cm)
OBSTACLE_Z = 15.0 * PLAYFIELD_SCALE  # standing on the bed

# --- Machine screen inventory -----------------------------------------------------------------------------
INV_ROWS = 3
INV_Y0, INV_STEP, INV_H = 290, 130, 122
PANEL = "(R=0.016,G=0.010,B=0.008,A=0.86)"
SEL = "(R=0.95,G=0.06,B=0.05,A=1)"
FRAME = "(R=0.30,G=0.15,B=0.07,A=1)"
TEXT = "(R=0.86,G=0.79,B=0.66,A=1)"
SUB = "(R=0.56,G=0.46,B=0.36,A=1)"
GOLD = "(R=0.92,G=0.62,B=0.22,A=1)"
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
    if not type_id.startswith("|"):
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


def function(bp, name, params, code):
    """Creates or rebuilds a function with no return value. params: [(name, type or class), ...]."""
    if name in [g.get_name() for g in BT.list_graphs(bp)]:
        graph = BT.get_graph(bp, name)
        for node in BT.find_nodes(graph):
            if isinstance(node, unreal.K2Node_FunctionResult):
                raise RuntimeError(f"{name} returns a value; it can't be rebuilt whole")
            if not isinstance(node, unreal.K2Node_FunctionEntry):
                BT.delete_node(node)
    else:
        graph = BT.add_function_graph(bp, name)
        for pname, ptype in params:
            if isinstance(ptype, str):
                BT.add_function_param(graph, pname, ptype, True)
            else:
                BT.add_object_function_param(graph, pname, ptype.static_class(), True)
    blueprint_dsl.Transpiler(
        graph, make_node, BT.connect_pins, BT._get_node_info, BT.set_pin_value,
        lambda g: BT.find_nodes(g), delete_node_fn=BT.delete_node,
        find_node_types_fn=lambda f: BT.find_node_types(graph, f),
    ).transpile(code)


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


def insert_call(bp, graph_name, host_pred, callee, args=(), after=None):
    """Calls `callee` right after the exec output `after` of the node matched by host_pred (default "then"),
    passing host output pins as arguments: args = [(callee pin, host pin), ...]. Skips if already there."""
    graph = BT.get_graph(bp, graph_name)
    calls = [i for i in infos_of(graph) if i.type_id == f"|{callee}"]
    for extra in calls[1:]:  # an earlier version could add a second call; cut extras out of the chain
        for source in pin(extra, "execute").connected_pins:
            for target in pin(extra, "then").connected_pins:
                BT.connect_pins(source, target)
        BT.delete_node(extra.node)
    if calls:
        return
    host = next(i for i in infos_of(graph) if host_pred(i))
    out = pin(host, after or "then")
    nxt = [BT._get_node_info(c.node) for c in out.connected_pins]
    existing = {i.node.get_name() for i in infos_of(graph)}
    make_node(graph, f"|{callee}", unreal.IntPoint(host.position.x + 200, host.position.y + 260))
    call = next(i for i in infos_of(graph) if i.node.get_name() not in existing)
    BT.connect_pins(out.pin_id, pin(call, "execute").pin_id)
    for n in nxt:
        BT.connect_pins(pin(call, "then").pin_id, pin(n, "execute").pin_id)
    for callee_pin, host_pin in args:
        BT.connect_pins(pin(host, host_pin).pin_id, pin(BT._get_node_info(call.node), callee_pin).pin_id)


def is_entry(i):
    return isinstance(i.node, unreal.K2Node_FunctionEntry)


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
    _, _, found = subobjects(table)
    round_bumpers = found["RoundBumpers"][1]
    cells = [round_bumpers.get_instance_transform(i, False) for i in range(round_bumpers.get_instance_count())]
    for name, tag, mi in GIMMICK_BUMPERS:
        part = add_component(table, name, unreal.InstancedStaticMeshComponent)
        part.set_editor_property("static_mesh", round_bumpers.static_mesh)
        part.set_editor_property("body_instance", round_bumpers.get_editor_property("body_instance"))
        part.set_editor_property("override_materials", [unreal.load_asset(SHOWCASE_MI.format(mi))])
        part.set_editor_property("component_tags", list(round_bumpers.component_tags) + [unreal.Name(tag)])
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
    (bind c (|HexCenter :Index Index))""" + "".join(hide_or_show(name, 4 + i) for i, (name, _, _) in enumerate(GIMMICK_BUMPERS)) + """
    (if (== Type 5)
      (Utilities|Array|AddUnique (|GetMagnetCells) Index)
      (else
        (Utilities|Array|RemoveItem (|GetMagnetCells) Index)))))
"""

APPLY_GIMMICK = f"""
(fn ApplyGimmick (Comp)
  (bind now (Utilities|Time|GetGameTimeinSeconds))
  (if (> (- now (|GetLastGimmickTime)) 0.1)
    (if (Components|ComponentHasTag Comp "Blast")
      (|SetLastGimmickTime now)
      (|SetIncomingVelocity (* (Physics|GetPhysicsLinearVelocity (|GetBall)) (|GetBlastBoost)))
      (Physics|SetPhysicsLinearVelocity (|GetBall) (|GetIncomingVelocity) false))
    (if (Components|ComponentHasTag Comp "Gold")
      (|SetLastGimmickTime now)
      (|SetHits (+ (|GetHits) (|GetGoldHits))))
    (if (Components|ComponentHasTag Comp "Warp")
      (|SetLastGimmickTime now)
      (Transformation|SetWorldLocation (|GetBall) (Math|Transform|TransformLocation (Transformation|GetActorTransform) (Math|Vector|MakeVector {WARP_X} (Math|Random|RandomFloatinRange -{WARP_Y} {WARP_Y}) 12.0)) false true))))
"""

MAGNET_PULL = """
(fn MagnetPull ()
  (if (and (Physics|IsSimulatingPhysics (|GetBall)) (> (Utilities|Array|Length (|GetMagnetCells)) 0))
    (for i (range (Utilities|Array|Length (|GetMagnetCells)))
      (bind d (- (Math|Transform|TransformLocation (Transformation|GetActorTransform) (|HexCenter :Index (Utilities|Array|Get(acopy) (|GetMagnetCells) i))) (Transformation|GetWorldLocation (|GetBall))))
      (bind dist (Math|Vector|VectorLength d))
      (if (and (< dist (|GetMagnetRadius)) (> dist 1.0))
        (Physics|AddForce (|GetBall) (* (/ d dist) (* (|GetMagnetStrength) (- 1.0 (/ dist (|GetMagnetRadius))))) "None" true)))))
"""

SHOW_BALL_CHOICE = """
(fn ShowBallChoice (BallType Owned)
  (if (Utilities|Array|IsValidIndex (|GetBallMaterials) BallType)
    (if Owned
      (Rendering|Material|SetMaterial (|GetBall) 0 (Utilities|Array|Get(acopy) (|GetBallMaterials) BallType))
      (else
        (Rendering|Material|SetMaterial (|GetBall) 0 (Utilities|Array|Get(acopy) (|GetBallFadedMaterials) BallType))))))
"""

APPLY_BALL_TYPE = """
(fn ApplyBallType (BallType)
  (|SetActiveBallType BallType)
  (if (Utilities|Array|IsValidIndex (|GetBallMass) BallType)
    (Physics|SetMassScale (|GetBall) "None" (Utilities|Array|Get(acopy) (|GetBallMass) BallType))
    (Rendering|Material|SetMaterial (|GetBall) 0 (Utilities|Array|Get(acopy) (|GetBallMaterials) BallType))))
"""

BALL_WALL_HIT = """
(fn BallWallHit (Comp NormalImpulse)
  (bind now (Utilities|Time|GetGameTimeinSeconds))
  (bind bounce (Utilities|Array|Get(acopy) (|GetBallBounce) (|GetActiveBallType)))
  (if (and (>= bounce 0.0) (and (not (Components|ComponentHasTag Comp "RoundBumper")) (> (- now (|GetLastBounceTime)) 0.05)))
    (bind n (Math|Vector|Normalize NormalImpulse))
    (bind v (|GetIncomingVelocity))
    (bind dot (Math|Vector|DotProduct v n))
    (if (and (< dot 0.0) (< (Math|Float|Absolute(Float) (Math|Vector|DotProduct n (Transformation|GetActorUpVector))) 0.7))
      (|SetLastBounceTime now)
      (|SetIncomingVelocity (- v (* n (* dot (+ 1.0 bounce)))))
      (Physics|SetPhysicsLinearVelocity (|GetBall) (|GetIncomingVelocity) false))))
"""


def apply_table(table):
    build_table_parts(table)
    add_variables(table, [
        ("MagnetCells", "int", ContainerType.ARRAY), ("LastGimmickTime", "float", None), ("LastBounceTime", "float", None),
        ("ActiveBallType", "int", None), ("BlastBoost", "float", None), ("GoldHits", "int", None),
        ("MagnetRadius", "float", None), ("MagnetStrength", "float", None),
        ("BallMass", "float", ContainerType.ARRAY), ("BallBounce", "float", ContainerType.ARRAY),
        ("BallMaterials", unreal.MaterialInterface, ContainerType.ARRAY),
        ("BallFadedMaterials", unreal.MaterialInterface, ContainerType.ARRAY),
    ], "Gimmicks")
    BT.compile_blueprint(table)
    function(table, "SetGimmicks", [("Index", "int"), ("Type", "int")], SET_GIMMICKS)
    function(table, "ApplyGimmick", [("Comp", unreal.PrimitiveComponent)], APPLY_GIMMICK)
    function(table, "MagnetPull", [], MAGNET_PULL)
    function(table, "ApplyBallType", [("BallType", "int")], APPLY_BALL_TYPE)
    function(table, "ShowBallChoice", [("BallType", "int"), ("Owned", "bool")], SHOW_BALL_CHOICE)
    function(table, "BallWallHit", [("Comp", unreal.PrimitiveComponent), ("NormalImpulse", "Vector")], BALL_WALL_HIT)
    BT.compile_blueprint(table)
    insert_call(table, "SetObstacle", is_entry, "SetGimmicks", [("Index", "Index"), ("Type", "Type")])
    hit = lambda i: isinstance(i.node, unreal.K2Node_ComponentBoundEvent)
    insert_call(table, "EventGraph", hit, "BallWallHit", [("Comp", "OtherComp"), ("NormalImpulse", "NormalImpulse")])
    insert_call(table, "EventGraph", lambda i: i.type_id == "|ReflectBumper", "ApplyGimmick")
    events = BT.get_graph(table, "EventGraph")
    reflect_call = next(i for i in infos_of(events) if i.type_id == "|ApplyGimmick")
    if not len(pin(reflect_call, "Comp").connected_pins):
        BT.connect_pins(pin(next(i for i in infos_of(events) if hit(i)), "OtherComp").pin_id, pin(reflect_call, "Comp").pin_id)
    tick = lambda i: isinstance(i.node, unreal.K2Node_Event) and "Tick" in i.node.get_node_title()
    insert_call(table, "EventGraph", tick, "MagnetPull")
    BT.compile_blueprint(table, warnings_as_errors=True)
    cdo = BT.get_default_object(table)
    for name, value in (("BlastBoost", BLAST_BOOST), ("GoldHits", GOLD_HITS), ("MagnetRadius", MAGNET_RADIUS),
                        ("MagnetStrength", MAGNET_STRENGTH), ("BallMass", BALL_MASS), ("BallBounce", BALL_BOUNCE),
                        ("BallMaterials", [unreal.load_asset(p) for p in BALL_MATERIALS]),
                        ("BallFadedMaterials", faded_ball_materials())):
        cdo.set_editor_property(name, value)


def faded_ball_materials():
    """A paler, greyer copy of each special ball's material, for balls not bought yet. Index 0 (the normal
    ball, always owned) keeps its own material."""
    mel = unreal.MaterialEditingLibrary
    out = [unreal.load_asset(BALL_MATERIALS[0])]
    for i, path in enumerate(BALL_MATERIALS[1:], start=1):
        source = unreal.load_asset(path)
        colour = mel.get_material_instance_vector_parameter_value(source, "Color")
        grey = 0.5
        faded = unreal.LinearColor(colour.r + (grey - colour.r) * FADE_TO_GREY, colour.g + (grey - colour.g) * FADE_TO_GREY,
                                   colour.b + (grey - colour.b) * FADE_TO_GREY, 1.0)
        target = FADED_MI.format(i)
        if unreal.EditorAssetLibrary.does_asset_exist(target):
            mi = unreal.load_asset(target)
        else:
            folder, name = target.rsplit("/", 1)
            mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                name, folder, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        mel.set_material_instance_parent(mi, source.get_editor_property("parent"))
        mel.set_material_instance_vector_parameter_value(mi, "Color", faded)
        mel.set_material_instance_scalar_parameter_value(mi, "Glow", 0.03)
        mel.update_material_instance(mi)
        unreal.EditorAssetLibrary.save_loaded_asset(mi)
        out.append(mi)
    return out


# --- HUD --------------------------------------------------------------------------------------------------
PURCHASE = """
(fn Purchase (Type)
  (bind owned (Utilities|Array|Length (|GetStock)))
  (bind locked (|IsBoardLocked :self (|GetRules)))
  (if (and (== (|GetPhase) 0) (Utilities|Array|IsValidIndex (|GetShopPrices) Type))
    (if (and (< Type owned) locked)
      (|SetMessage "판 잠김")
      (elif (< (|GetCredits) (Utilities|Array|Get(acopy) (|GetShopPrices) Type))
        (|SetMessage "크레딧 부족")
        (else
          (|SetCredits (- (|GetCredits) (Utilities|Array|Get(acopy) (|GetShopPrices) Type)))
          (if (< Type owned)
            (Utilities|Array|SetArrayElem (|GetStock) Type (+ (Utilities|Array|Get(acopy) (|GetStock) Type) 1))
            (|SetSelected Type)
            (|SetMessage "빈 칸 선택")
            (else
              (Utilities|Array|SetArrayElem (|GetBallStock) (+ (- Type owned) 1) (+ (Utilities|Array|Get(acopy) (|GetBallStock) (+ (- Type owned) 1)) 1))
              (|SetSelectedBall (+ (- Type owned) 1))
              (|SetMessage "공 구매 · 기계에서 Q / E"))))))))
"""

OWNED = "(or (== (|GetSelectedBall) 0) (> (Utilities|Array|Get(acopy) (|GetBallStock) (|GetSelectedBall)) 0))"

START_ROUND = f"""
(fn StartRound ()
  (if (== (|GetPhase) 0)
    (if (not {OWNED})
      (|SetCharging false)
      (|SetPower 0.0)
      (|SetMessage "구매하지 않은 공 · Q / E로 바꾸기")
      (else
        (|SetActiveBall (|GetSelectedBall))
        (if (> (|GetSelectedBall) 0)
          (Utilities|Array|SetArrayElem (|GetBallStock) (|GetSelectedBall) (- (Utilities|Array|Get(acopy) (|GetBallStock) (|GetSelectedBall)) 1)))
        (if (<= (Utilities|Array|Get(acopy) (|GetBallStock) (|GetSelectedBall)) 0)
          (|SetSelectedBall 0))
        (|ApplyBallType :self (|GetTable) :BallType (|GetActiveBall))
        (|Launch :self (|GetTable) :Power (|GetPower))
        (|SetCharging false)
        (|SetPhase 1)
        (|SetMessage "구슬 이동")))))
"""

STEP_BALL = """
(fn StepBall (Step)
  (bind n (Utilities|Array|Length (|GetBallStock)))
  (if (> n 0)
    (|SetSelectedBall (Math|Integer|%(Integer) (+ (|GetSelectedBall) Step) n))))
"""

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
        (|SetInvScroll (+ (- (|GetSelected) {INV_ROWS}) 1))))
    (if (== (|GetPhase) 0)
      (if (Game|Player|WasInputKeyJustPressed pc "E")
        (|StepBall :Step 1))
      (if (Game|Player|WasInputKeyJustPressed pc "Q")
        (|StepBall :Step (- (Utilities|Array|Length (|GetBallStock)) 1)))
      (if (and (not {OWNED}) (|GetCharging))
        (|SetCharging false)
        (|SetPower 0.0))
      (if (!= (+ (* (|GetSelectedBall) 2) (Math|Conversions|ToInteger(Boolean) {OWNED})) (|GetShownBall))
        (|SetShownBall (+ (* (|GetSelectedBall) 2) (Math|Conversions|ToInteger(Boolean) {OWNED})))
        (|ShowBallChoice :self (|GetTable) :BallType (|GetSelectedBall) :Owned {OWNED})
        (if (== (|GetSelectedBall) 0)
          (|SetMessage (Utilities|String|Append "공: " (Utilities|Array|Get(acopy) (|GetBallNames) 0)))
          (elif {OWNED}
            (|SetMessage (Utilities|String|BuildString(Integer) (Utilities|String|Append "공: " (Utilities|Array|Get(acopy) (|GetBallNames) (|GetSelectedBall))) "  ×" (Utilities|Array|Get(acopy) (|GetBallStock) (|GetSelectedBall)) ""))
            (else
              (|SetMessage (Utilities|String|Append (Utilities|String|Append "공: " (Utilities|Array|Get(acopy) (|GetBallNames) (|GetSelectedBall))) "  · 미보유")))))))))
"""
# ShownBall holds ball x 2 + owned, so buying the ball on screen also refreshes its look.

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
      (|Panel :X 902.0 :Y (+ y 18.0) :W 86.0 :H 86.0 :Tint (Utilities|Array|Get(acopy) (|GetShowcaseColors) item))
      (|Label :Caption (Utilities|Array|Get(acopy) (|GetShowcaseNames) item) :X 1002.0 :Y (+ y 30.0) :Size 1.05 :Tint "{TEXT}")
      (|Label :Caption (Utilities|String|BuildString(Integer) "" "보관함: " (Utilities|Array|Get(acopy) (|GetStock) item) "개") :X 1002.0 :Y (+ y 68.0) :Size 1.0 :Tint "{SUB}")))
  (if (> (Utilities|Array|Length (|GetStock)) {INV_ROWS})
    (|Panel :X 1185.0 :Y {INV_Y0}.0 :W 5.0 :H {INV_ROWS * INV_STEP - (INV_STEP - INV_H)}.0 :Tint "{FRAME}")
    (|Panel :X 1185.0 :Y (+ {INV_Y0}.0 (/ (* {INV_ROWS * INV_STEP - (INV_STEP - INV_H)}.0 (Math|Conversions|ToFloat(Integer) (|GetInvScroll))) (Math|Conversions|ToFloat(Integer) (Utilities|Array|Length (|GetStock))))) :W 5.0 :H (/ {(INV_ROWS * INV_STEP - (INV_STEP - INV_H)) * INV_ROWS}.0 (Math|Conversions|ToFloat(Integer) (Utilities|Array|Length (|GetStock)))) :Tint "{ACCENT}"))
  (|DrawTiltCount)
  (|DrawSideArrow :Caption "상점")
  (|DrawLiveScore))
"""


def drop_old_wheel(hud):
    """UpdateBoard opened with Selected = NextSelection(...), the old 3-slot wheel and click handling on the
    machine screen. UpdateInventory does that now, so that step goes."""
    graph = BT.get_graph(hud, "UpdateBoard")
    for info in infos_of(graph):
        if info.type_id != "|SetSelected":
            continue
        sources = [BT._get_node_info(c.node) for c in pin(info, "Selected").connected_pins]
        if not sources or sources[0].type_id != "|NextSelection":
            continue
        for src in pin(info, "execute").connected_pins:
            for dst in pin(info, "then").connected_pins:
                BT.connect_pins(src, dst)
        BT.delete_node(info.node)
        BT.delete_node(sources[0].node)


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


def stock_slots(hud):
    graph = BT.get_graph(hud, "InitializeBoard")
    for info in infos_of(graph):
        if info.type_id == "Utilities|Array|Resize":
            target = BT._get_node_info(pin(info, "TargetArray").connected_pins[0].node)
            if target.type_id == "|GetStock":
                BT.set_pin_value(pin(info, "Size").pin_id, str(STOCK_SLOTS))


def ball_factor(graph, source, factor_array, pos):
    """Returns the output pin of (source * factor_array[ActiveBall])."""
    mul = BT.create_node(graph, "Utilities|Operators|Multiply", pos)
    arr = BT._get_node_info(make_node(graph, f"|Get{factor_array}", unreal.IntPoint(pos.x - 420, pos.y + 90)))
    ball = BT._get_node_info(make_node(graph, "|GetActiveBall", unreal.IntPoint(pos.x - 420, pos.y + 170)))
    get = BT.create_node(graph, "Utilities|Array|Get(acopy)", unreal.IntPoint(pos.x - 200, pos.y + 110))
    BT.connect_pins(value_out(arr).pin_id, pin(BT._get_node_info(get), "Array").pin_id)
    info = BT._get_node_info(get)
    BT.connect_pins(value_out(ball).pin_id, next(p for p in info.input_pins if p.name != "Array").pin_id)
    BT.connect_pins(source, pin(BT._get_node_info(mul), "A").pin_id)
    BT.connect_pins(value_out(BT._get_node_info(get)).pin_id, pin(BT._get_node_info(mul), "B").pin_id)
    return value_out(BT._get_node_info(mul))


def score_factors(hud):
    """Settle: RoundScore(Scored, Hits x hit factor, Multiplier x lane factor) x score factor."""
    graph = BT.get_graph(hud, "Settle")
    score = next(i for i in infos_of(graph) if i.type_id == "|RoundScore")
    hits_src = pin(score, "Hits").connected_pins[0]
    if "Multiply" in BT._get_node_info(hits_src.node).type_id or "*" in BT._get_node_info(hits_src.node).type_id:
        return  # already done
    pos = score.position
    BT.connect_pins(ball_factor(graph, hits_src, "BallHitFactor", unreal.IntPoint(pos.x - 300, pos.y + 200)).pin_id, pin(score, "Hits").pin_id)
    mult_src = pin(score, "Multiplier").connected_pins[0]
    BT.connect_pins(ball_factor(graph, mult_src, "BallLaneFactor", unreal.IntPoint(pos.x - 300, pos.y + 420)).pin_id, pin(score, "Multiplier").pin_id)
    consumers = list(value_out(score).connected_pins)
    total = ball_factor(graph, value_out(score).pin_id, "BallScoreFactor", unreal.IntPoint(pos.x + 300, pos.y + 200))
    for target in consumers:
        BT.connect_pins(total.pin_id, target)


def apply_hud(hud):
    add_variables(hud, [
        ("BallStock", "int", ContainerType.ARRAY), ("BallNames", "string", ContainerType.ARRAY),
        ("BallHitFactor", "int", ContainerType.ARRAY), ("BallLaneFactor", "int", ContainerType.ARRAY),
        ("BallScoreFactor", "int", ContainerType.ARRAY), ("SelectedBall", "int", None), ("ShownBall", "int", None),
        ("ActiveBall", "int", None), ("InvScroll", "int", None),
    ], "Balls")
    BT.compile_blueprint(hud)
    function(hud, "StepBall", [("Step", "int")], STEP_BALL)
    BT.compile_blueprint(hud)
    function(hud, "UpdateInventory", [], UPDATE_INVENTORY)
    function(hud, "Purchase", [], PURCHASE)
    function(hud, "StartRound", [], START_ROUND)
    function(hud, "DrawBumperSlots", [], DRAW_BUMPER_SLOTS)
    BT.compile_blueprint(hud)
    insert_call(hud, "UpdateBoard", is_entry, "UpdateInventory")
    drop_old_wheel(hud)
    order_board_head(hud)
    stock_slots(hud)
    score_factors(hud)
    BT.compile_blueprint(hud, warnings_as_errors=True)
    cdo = BT.get_default_object(hud)
    for name, value in (("BallStock", [0] * len(BALL_NAMES)), ("BallNames", BALL_NAMES),
                        ("BallHitFactor", BALL_HIT_FACTOR), ("BallLaneFactor", BALL_LANE_FACTOR),
                        ("BallScoreFactor", BALL_SCORE_FACTOR), ("SelectedBall", 0), ("ShownBall", -1),
                        ("ActiveBall", 0), ("InvScroll", 0)):
        cdo.set_editor_property(name, value)


with toolset_registry.tool_raising_exceptions():
    BPS.update(table=unreal.load_asset(TABLE), hud=unreal.load_asset(HUD), rules=unreal.load_asset(RULES))
    DECLARING["Rendering|Material|SetMaterial"] = unreal.PrimitiveComponent
    apply_table(BPS["table"])
    apply_hud(BPS["hud"])
    for bp in (BPS["table"], BPS["hud"]):
        unreal.EditorAssetLibrary.save_loaded_asset(bp)
unreal.log("BUMPIT_GIMMICKS_APPLIED")
