"""Table tuning: launch power, a rounded top-right corner in place of the 45-degree deflector, a narrow launch
lane against the outer rail, and a playfield widened into the space the old lane took - with the cells, goals,
obstacles and ball scaled up to match. Safe to run repeatedly (every value is set from the original layout,
so nothing grows twice); tune the tables below. Run this before apply_gimmicks.py.

Run with the editor closed:
UnrealEditor-Cmd.exe Bumpit.uproject -run=pythonscript -script=<this file> -unattended -nullrhi -culture=en

Table space: +X is the top of the table, -X the goals; the launch lane runs up the right side (+Y).

Launch: the table is tilted 18 degrees, so the ball loses about 300 cm/s per second climbing the ~600 cm lane.
With the ball running along the outer rail it meets the corner tangentially and rides it round instead of
bouncing off, so a strong launch turns into distance along the top.

Lane and playfield: the lane used to be 68 cm wide (divider face y=289..299 to the outer rail at y=367). It is
now a LANE_WIDTH channel against the outer rail, with the divider right next to it, and the playfield grows
from y = -288..289 (577 cm) to -288..335 (623 cm). Everything laid out across it is scaled by the same factor,
anchored at the left rail: hex cells (HexCenter, PickCell's cell size, the grid mesh), goal pockets and their
dividers, goal judging (BallStatus), lane labels, obstacle sizes (SetObstacle, ReflectBumper's centre height)
and the ball. Gate and lane-stall checks follow the new lane line.
"""
import math
import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BT

TABLE = "/Game/Bumpit/Blueprints/BP_PinballTable"
RULES = "/Game/Bumpit/Blueprints/BP_RoundRules"

# --- Launch ---------------------------------------------------------------------------------------------
LAUNCH_BASE = 760.0  # cm/s at zero power (original 780)
LAUNCH_RANGE = 360.0  # added at full power (original 400): 760-1120 cm/s
RAIL_KICK = 1000.0  # BP_RoundRules: re-launch of a ball stuck in the lane (original 1100)

# --- Lane -------------------------------------------------------------------------------------------------
OUTER = 367.0  # inner face of the lane's outer rail
LANE_WIDTH = 22.0  # channel the ball runs up, against the outer rail
DIVIDER = 10.0  # lane divider thickness (as before)
LEFT = -288.0  # inner face of the left rail
OLD_RIGHT = 289.0  # the playfield's old right edge (the old divider's face)
RIGHT = OUTER - LANE_WIDTH - DIVIDER  # 335: the playfield's new right edge
SCALE = (RIGHT - LEFT) / (OLD_RIGHT - LEFT)  # 623 / 577 = 1.0797
BALL_SCALE = 0.18 * SCALE  # the ball was 18 cm; 19.4 cm leaves 1.3 cm each side in the channel
OLD_LANE_FILL = "LaneFill"  # the filler wall an earlier version used to narrow the lane; removed


def across(y):
    """Old playfield y -> new: stretched by SCALE away from the left rail."""
    return LEFT + (y - LEFT) * SCALE


# --- Rounded corner ---------------------------------------------------------------------------------------
CORNER = (350.0, OUTER)  # inner faces of the top rail (x) and the lane's outer rail (y)
RADIUS = 72.0  # also rounds the playfield's top-right corner, below the lane exit
SEGMENTS = 48  # straight pieces along the quarter circle (was 12: fast balls rattled on the corners between them)
THICKNESS = 10.0
WALL_Z = 15.0  # same height and depth as the rails
WALL_SCALE_Z = 0.54
PREFIX = "TopArc"
TEMPLATE = "UpperRail"  # the new pieces copy this rail's mesh, material, collision and physics material
OLD = "Deflector"

# Literal values in the table's and rules' graphs: (graph, [(original, new), ...]).
LANE_LINES = [-224.0, -160.0, -96.0, -32.0, 32.0, 96.0, 160.0, 224.0]  # BallStatus: borders between goals
RETUNE = {
    TABLE: [
        ("PickCell", [(33.774990748, 33.774990748 * SCALE), (39.0, 39.0 * SCALE)]),  # hex cell half sizes
        ("SetObstacle", [(0.3, 0.3 * SCALE), (0.12, 0.12 * SCALE), (0.63, 0.63 * SCALE), (15.0, 15.0 * SCALE)]),
        ("ReflectBumper", [(15.0, 15.0 * SCALE)]),  # bumper centre height
        ("BallStatus", [(t, across(t)) for t in LANE_LINES] + [(288.0, RIGHT)]),  # goal borders, lane edge
        ("GoalLabelLocal", [(-256.0, across(-256.0)), (64.0, 64.0 * SCALE)]),
        ("EventGraph", [(280.0, RIGHT - 5.0)]),  # gate shuts once the ball is past the lane line
        ("ShouldCloseGate", [(280.0, RIGHT - 5.0)]),
        ("MaybeSplit", [(280.0, RIGHT - 5.0)]),  # split ball (main): no split while still in the launch lane
    ],
    RULES: [
        ("CreateLaneLabels", [(-256.0, across(-256.0)), (64.0, 64.0 * SCALE)]),
    ],
}


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


def set_launch(bp):
    graph = BT.get_graph(bp, "GetLaunchSpeed")
    infos = {i.node.get_name(): i for i in BT.get_node_infos(BT.find_nodes(graph))}
    for info in infos.values():
        if info.type_id != "Math|Float|MakeLiteralFloat":
            continue
        out = next(p for p in info.output_pins if p.name == "ReturnValue")
        target = infos[out.connected_pins[0].node.get_name()].type_id
        value = LAUNCH_RANGE if target == "Math|Float|float*float" else LAUNCH_BASE
        BT.set_pin_value(next(p for p in info.input_pins if p.name == "Value").pin_id, str(value))


def build_corner(bp):
    sub, root_context, found = subobjects(bp)
    for name, (handle, _) in list(found.items()):
        if name == OLD or name.startswith(PREFIX):
            sub.delete_subobject(root_context, handle, bp)
    sub, root_context, found = subobjects(bp)
    template = found[TEMPLATE][1]
    parent = found["DefaultSceneRoot"][0]
    cx, cy = CORNER[0] - RADIUS, CORNER[1] - RADIUS
    step = math.pi / 2 / SEGMENTS
    length = 2.0 * RADIUS * math.tan(step / 2) * 1.15  # a little overlap so the inner face has no gaps
    for i in range(SEGMENTS):
        theta = (i + 0.5) * step  # 0 = along the top rail, 90 degrees = along the lane's outer rail
        r = RADIUS + THICKNESS / 2
        params = unreal.AddNewSubobjectParams(parent_handle=parent, new_class=unreal.StaticMeshComponent, blueprint_context=bp)
        handle, reason = sub.add_new_subobject(params)
        if not unreal.SubobjectDataBlueprintFunctionLibrary.is_handle_valid(handle):
            raise RuntimeError(f"Could not add corner piece {i}: {reason}")
        sub.rename_subobject(handle, unreal.Text(f"{PREFIX}{i:02d}"))
        piece = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(sub.k2_find_subobject_data_from_handle(handle))
        piece.set_editor_property("static_mesh", template.static_mesh)
        piece.set_editor_property("override_materials", template.get_editor_property("override_materials"))
        piece.set_editor_property("body_instance", template.get_editor_property("body_instance"))
        piece.set_editor_property("relative_location", unreal.Vector(cx + r * math.cos(theta), cy + r * math.sin(theta), WALL_Z))
        piece.set_editor_property("relative_rotation", unreal.Rotator(roll=0.0, pitch=0.0, yaw=math.degrees(theta) + 90.0))
        piece.set_editor_property("relative_scale3d", unreal.Vector(length / 100.0, THICKNESS / 100.0, WALL_SCALE_Z))


def move(part, x=None, y=None, sx=None, sy=None, sz=None):
    loc, sc = part.relative_location, part.relative_scale3d
    part.set_editor_property("relative_location", unreal.Vector(loc.x if x is None else x, loc.y if y is None else y, loc.z))
    part.set_editor_property("relative_scale3d", unreal.Vector(sc.x if sx is None else sx, sc.y if sy is None else sy, sc.z if sz is None else sz))


def lay_out_lane_and_field(bp):
    sub, root_context, found = subobjects(bp)
    if OLD_LANE_FILL in found:
        sub.delete_subobject(root_context, found[OLD_LANE_FILL][0], bp)
        sub, root_context, found = subobjects(bp)
    part = lambda name: found[name][1]
    divider_y = RIGHT + DIVIDER / 2
    move(part("LaneDivider"), y=divider_y, sy=DIVIDER / 100.0)
    move(part("LaunchGate"), y=divider_y)
    ball_y = OUTER - LANE_WIDTH / 2
    move(part("Ball"), y=ball_y, sx=BALL_SCALE, sy=BALL_SCALE, sz=BALL_SCALE)
    if "SplitBall" in found:  # main's split ball: same size as the ball (it waits off the table at z -3000)
        move(part("SplitBall"), sx=BALL_SCALE, sy=BALL_SCALE, sz=BALL_SCALE)
    move(part("LauncherMark"), y=ball_y)
    for k in range(9):  # goal pockets: the original layout was y = -256 + 64k, 54 cm wide
        move(part(f"Goal{k}"), y=across(-256.0 + 64.0 * k), sy=0.54 * SCALE)
    for k in range(1, 9):  # dividers between them: y = -288 + 64k
        move(part(f"GoalDivider{k}"), y=across(-288.0 + 64.0 * k))
    move(part("HexGrid"), x=0.0, y=across(0.0), sx=SCALE, sy=SCALE)

    reset = [i for i in BT.get_node_infos(BT.find_nodes(BT.get_graph(bp, "ResetBall"))) if i.type_id == "Math|Vector|MakeVector"]
    if len(reset) != 1:
        raise RuntimeError(f"Expected one MakeVector in ResetBall, found {len(reset)}")
    BT.set_pin_value(next(p for p in reset[0].input_pins if p.name == "Y").pin_id, str(ball_y))


def scale_hex_centres(bp):
    """HexCenter returned the cell centre for the old layout; it now returns centre * SCALE moved to the new
    middle, so every caller (placing, picking, bumper bounces, magnets) follows the bigger grid."""
    graph = BT.get_graph(bp, "HexCenter")
    infos = BT.get_node_infos(BT.find_nodes(graph))
    result = next(i for i in infos if isinstance(i.node, unreal.K2Node_FunctionResult))
    ret = next(p for p in result.input_pins if p.type_id != "Exec")
    source = ret.connected_pins[0]
    if BT._get_node_info(source.node).type_id.startswith("Math|Vector|vector+"):
        return  # already wrapped
    pos = result.position
    mul = BT.create_node(graph, "Utilities|Operators|Multiply", unreal.IntPoint(pos.x - 400, pos.y + 160))
    BT.connect_pins(source, next(p for p in BT._get_node_info(mul).input_pins if p.name == "A").pin_id)
    BT.set_pin_value(next(p for p in BT._get_node_info(mul).input_pins if p.name == "B").pin_id, f"{SCALE:.6f}, {SCALE:.6f}, 1.0")
    add = BT.create_node(graph, "Utilities|Operators|Add", unreal.IntPoint(pos.x - 200, pos.y + 160))
    out = next(p for p in BT._get_node_info(mul).output_pins if p.type_id != "Exec")
    BT.connect_pins(out.pin_id, next(p for p in BT._get_node_info(add).input_pins if p.name == "A").pin_id)
    BT.set_pin_value(next(p for p in BT._get_node_info(add).input_pins if p.name == "B").pin_id, f"0.0, {across(0.0):.6f}, 0.0")
    BT.connect_pins(next(p for p in BT._get_node_info(add).output_pins if p.type_id != "Exec").pin_id, ret.pin_id)


def retune(bp, graph_name, pairs):
    """Sets literal pins holding an original value to the new one; pins already holding a new value are left."""
    if graph_name not in [g.get_name() for g in BT.list_graphs(bp)]:
        unreal.log(f"BUMPIT_RETUNE {bp.get_name()}.{graph_name}: no such graph, skipped")
        return
    changed = 0
    for info in BT.get_node_infos(BT.find_nodes(BT.get_graph(bp, graph_name))):
        for p in info.input_pins:
            try:
                value = float(p.value)
            except ValueError:
                continue
            if any(abs(value - new) < 1e-3 for _, new in pairs):
                continue
            for old, new in pairs:
                if abs(value - old) < 1e-3 * max(1.0, abs(old)):
                    BT.set_pin_value(p.pin_id, f"{new:.6f}")
                    changed += 1
                    break
    unreal.log(f"BUMPIT_RETUNE {bp.get_name()}.{graph_name}: {changed} values")


MAP = "/Game/Bumpit/Maps/BumpitCell"
PREVIEW_LABEL = "Pinball table preview"
# BP_BumpitHUD.InitializeBoard spawns the real table here when the game starts.
TABLE_SPAWN = (unreal.Vector(0.0, 0.0, 0.0), unreal.Rotator(roll=0.0, pitch=18.0, yaw=0.0))


def place_preview():
    """The table only exists once the game runs, so the map gets an editor-only copy to look at and edit
    against. It is hidden in game and has no collision, so it never meets the real table's ball."""
    unreal.EditorLoadingAndSavingUtils.load_map(MAP)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in actors.get_all_level_actors():
        if actor.get_actor_label() == PREVIEW_LABEL:
            actors.destroy_actor(actor)
    cls = unreal.load_class(None, TABLE + ".BP_PinballTable_C")
    preview = actors.spawn_actor_from_class(cls, TABLE_SPAWN[0], TABLE_SPAWN[1])
    preview.set_actor_label(PREVIEW_LABEL)
    preview.set_editor_property("is_editor_only_actor", True)
    preview.set_actor_hidden_in_game(True)
    for part in preview.get_components_by_class(unreal.PrimitiveComponent):
        part.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()


table = unreal.load_asset(TABLE)
rules = unreal.load_asset(RULES)
set_launch(table)
build_corner(table)
lay_out_lane_and_field(table)
scale_hex_centres(table)
for path, graphs in RETUNE.items():
    bp = table if path == TABLE else rules
    for graph_name, pairs in graphs:
        retune(bp, graph_name, pairs)
unreal.BlueprintEditorLibrary.compile_blueprint(table)
rules_cdo = BT.get_default_object(rules)
rules_cdo.set_editor_property("RailKick", RAIL_KICK)
rules_cdo.set_editor_property("LaunchRailY", RIGHT)  # stall check: a ball at or right of this is in the lane
unreal.BlueprintEditorLibrary.compile_blueprint(rules)
unreal.EditorAssetLibrary.save_loaded_asset(table)
unreal.EditorAssetLibrary.save_loaded_asset(rules)
place_preview()
unreal.log(f"BUMPIT_TABLE_TUNING_APPLIED scale={SCALE:.4f}")
