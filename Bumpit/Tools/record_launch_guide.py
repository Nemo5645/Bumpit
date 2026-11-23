"""Records the playfield paths the launch guide draws (Tools/launch_guide_paths.json). Rerun it when the table,
the ball or SpawnX / SpawnY change, then rerun apply_launch_guide.py. The exit-speed mapping (LaunchExitMin/Max,
LaunchCurve, WeightSpeedScale) can change without it: the paths are indexed by exit speed.

Run with the editor closed:
UnrealEditor.exe Bumpit.uproject -ExecutePythonScript=<this file> -unattended -culture=en

In PIE it spawns one empty, tilted BP_PinballTable per exit speed (20-900 cm/s, every 20), launches each with
LaunchExitMin = LaunchExitMax = that speed (a fixture setter compiled in memory, never saved), and records the
ball from the moment ApplyLaunchPower hands it back to physics at the top of the corner: every DT s for STEPS steps, stopping at the left
rail or the goals. From there the path is the same on every run (checked 2026-11-23: two runs, 0.0 cm apart).
"""
import json
import sys
import time
import traceback
from pathlib import Path
import unreal as u

u.EditorPythonScripting.set_keep_python_script_alive(True)
sys.path.insert(0, 'C:/T.C.P/Bumpit_Mood/Bumpit/Tools')
from blueprint_graph import B, Graph
TABLE = u.load_asset('/Game/Bumpit/Blueprints/BP_PinballTable')
g = Graph(TABLE, 'TestSetExit', True)
g.e.add_graph_input_parameter('Value', B._make_variable_type('float'))
g.set('LaunchExitMin', g.arg('Value'))
g.set('LaunchExitMax', g.arg('Value'))
B.compile_blueprint(TABLE)

OUT = Path(__file__).with_name('launch_guide_paths.json')
DT, STEPS = 0.04, 55  # 2.2 s: up the lane top, round the corner and on
SPAWN = (338.0, 295.0)  # where ApplyLaunchPower hands the ball back to physics: (RideCX + RideRadius, RideCY)
SPEEDS = [20.0 * k for k in range(1, 46)]  # 20-900, every 20
RECORD_SECONDS = 6.0  # launch, hidden time and the corner ride take up to ~2.5 s before the recorded part
editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
level = u.get_editor_subsystem(u.LevelEditorSubsystem)
table_class = u.load_class(None, '/Game/Bumpit/Blueprints/BP_PinballTable.BP_PinballTable_C')
state = {'rigs': None, 'start': None, 'paths': {}, 'done': False}
deadline = time.monotonic() + 150


def tick(delta):
    if state['done']:
        return
    try:
        world = editor.get_game_world()
        if not world:
            if time.monotonic() > deadline: raise TimeoutError('PIE did not start')
            return
        now = u.GameplayStatics.get_time_seconds(world)
        if state['rigs'] is None:
            if now < 1.0:
                return
            gameplay = u.get_default_object(u.GameplayStatics)
            scale = u.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT
            state['rigs'] = []
            for i, v in enumerate(SPEEDS):
                tf = u.Transform(location=u.Vector(0, 3000 + 1500 * i, 0), rotation=u.Rotator(roll=0, pitch=18, yaw=0))
                a = gameplay.call_method('BeginDeferredActorSpawnFromClass', (world, table_class, tf, u.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN, None, scale))
                state['rigs'].append((v, gameplay.call_method('FinishSpawningActor', (a, tf, scale))))
            state['spawned'] = now
            return
        if state['start'] is None:
            if now - state['spawned'] < 0.3:
                return
            for v, rig in state['rigs']:
                rig.call_method('TestSetExit', (v,))
                rig.call_method('Launch', (0.5,))
                state['paths'][str(v)] = []
            state['start'] = now
        t = now - state['start']
        for v, rig in state['rigs']:
            ball = rig.get_editor_property('Ball')
            p = rig.get_actor_transform().inverse_transform_location(ball.get_world_location())
            state['paths'][str(v)].append([round(t, 4), round(p.x, 2), round(p.y, 2), bool(rig.get_editor_property('PowerPending'))])
        if t > RECORD_SECONDS:
            finish(None)
    except Exception:
        finish(traceback.format_exc())


def resample(rows):
    """Table-space (x, y) from the spawn spot, every DT s; stops at the left rail (y -277, or where the ball turns
    back off it) or the goals (x -330)."""
    i = next(j for j, r in enumerate(rows) if not r[3])
    t0 = rows[i][0] - (rows[i + 1][0] - rows[i][0])  # the spawn happened during the frame before this sample
    out, j = [SPAWN], i
    for k in range(1, STEPS + 1):
        t = t0 + k * DT
        while j + 1 < len(rows) - 1 and rows[j + 1][0] < t:
            j += 1
        a, b = rows[j], rows[j + 1]
        f = min(max((t - a[0]) / max(b[0] - a[0], 1e-6), 0.0), 1.0)
        x, y = a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f
        if len(out) > 1 and y > out[-1][1] + 0.5:
            break  # bounced off the left rail between two samples: the path ends at the last point before it
        out.append((round(x, 2), round(y, 2)))
        if y < -277.0 or x < -330.0:
            break
    return out


def finish(error):
    state['done'] = True
    if error is None:
        paths = {k: resample(v) for k, v in state['paths'].items()}
        OUT.write_text(json.dumps({'dt': DT, 'steps': STEPS, 'speeds': SPEEDS, 'spawn': SPAWN,
                                   'paths': [paths[str(v)] for v in SPEEDS]}), encoding='utf8')
    else:
        u.log_error(error)
    u.log('LAUNCH_GUIDE_PATHS_RECORDED ' + str(error))
    u.unregister_slate_post_tick_callback(handle)
    level.editor_request_end_play()
    u.SystemLibrary.quit_editor()


u.EditorLoadingAndSavingUtils.load_map('/Game/Bumpit/Maps/BumpitCell')
handle = u.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
