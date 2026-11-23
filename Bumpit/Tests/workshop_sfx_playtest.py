"""Exercise shop and table sound hooks in PIE and record the game master bus."""
from pathlib import Path
import time
import traceback
import unreal as u

project=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir()))
level=u.get_editor_subsystem(u.LevelEditorSubsystem)
editor=u.get_editor_subsystem(u.UnrealEditorSubsystem)
u.EditorPythonScripting.set_keep_python_script_alive(True)
def call(o,n,*args): return o.call_method(n,tuple(args))
def prop(o,n): return o.get_editor_property(n)
def wait(seconds):
    end=time.monotonic()+seconds
    while time.monotonic()<end: yield

def exercise(h,world):
    table=prop(h,'Table')
    rules=prop(h,'Rules')
    assert prop(table,'FoleyRoom').is_playing()
    call(table,'UpdateWorkshopLoops',True,.2,False)
    charge=prop(table,'FoleyCharge')
    assert charge.is_playing()
    call(table,'UpdateWorkshopLoops',False,.2,False)
    assert not charge.is_playing()
    u.AudioMixerLibrary.start_recording_output(world,12.)
    yield from wait(.3)
    for _ in range(120):
        if call(rules,'OfferType',0)==0: break
        call(rules,'RerollOffers')
    assert call(rules,'OfferType',0)==0
    credits=prop(h,'Credits')
    call(h,'PurchaseOffer',0)
    assert prop(h,'Credits')<credits
    yield from wait(.48)
    call(h,'PurchaseOffer',0)
    yield from wait(.45)
    call(h,'Visit',1)
    yield from wait(.5)
    call(h,'EnsureObstacleOffers')
    call(h,'ChooseOffer',0)
    call(h,'EditCell',20,False)
    yield from wait(.4)
    call(h,'TestWorkshopHold',True)
    for i in range(20):
        call(h,'AdvanceCharge',.026)
        call(h,'WorkshopMix')
        yield
    assert prop(table,'FoleyCharge').is_playing()
    call(h,'StartRound')
    assert prop(h,'Phase')==1
    limit=time.monotonic()+7
    while prop(table,'LaunchStage')!=0 and time.monotonic()<limit: yield
    assert prop(table,'LaunchStage')==0
    assert not charge.is_playing()
    ball=prop(table,'Ball')
    ball.set_enable_gravity(False)
    xf=table.get_actor_transform()
    for kind in (1,6,4):
        call(table,'SetObstacle',19,kind)
        target=call(table,'HexCenter',19)+u.Vector(-58,0,13)
        ball.set_world_location(u.MathLibrary.transform_location(xf,target),False,True)
        ball.set_physics_linear_velocity(u.MathLibrary.transform_direction(xf,u.Vector(400,0,0)))
        before=prop(table,'Hits')
        until=time.monotonic()+2.
        while prop(table,'Hits')==before and time.monotonic()<until:yield
        assert prop(table,'Hits')>before,(kind,prop(h,'Phase'),ball.is_simulating_physics(),ball.get_world_location(),prop(table,'Hits'))
        ball.set_world_location(u.MathLibrary.transform_location(xf,u.Vector(0,-120,25)),False,True)
        ball.set_physics_linear_velocity(u.Vector())
        yield from wait(.31)
    lane=list(prop(rules,'Multipliers')).index(10)
    call(h,'Settle',lane)
    yield from wait(.9)
    output=project/'AudioPreviews'
    u.AudioMixerLibrary.stop_recording_output(world,u.AudioRecordingExportType.WAV_FILE,'workshop_gameplay',str(output))
    yield from wait(.5)
    assert (output/'workshop_gameplay.wav').stat().st_size>100000
    u.log('WORKSHOP_PLAYTEST_PASS')
scenario=None
deadline=time.monotonic()+100
def tick(delta):
    global scenario
    try:
        world=editor.get_game_world()
        if world and scenario is None:
            pc=u.GameplayStatics.get_player_controller(world,0)
            hud=pc.get_hud() if pc else None
            if hud and prop(hud,'Table'):scenario=exercise(hud,world)
        if time.monotonic()>deadline:raise TimeoutError()
        if scenario is not None:next(scenario)
        return
    except StopIteration:pass
    except Exception:u.log_error(traceback.format_exc())
    u.unregister_slate_post_tick_callback(handle)
    level.editor_request_end_play()
    u.SystemLibrary.quit_editor()
import sys
sys.path.insert(0,str(project/'Tools'))
from blueprint_graph import B, HUD, Graph
g=Graph(HUD,'TestWorkshopHold',True)
g.e.add_graph_input_parameter('Value',B._make_variable_type('bool'))
g.set('Charging',g.arg('Value'))
B.compile_blueprint(HUD)  # PIE-only control, never save the test function.
u.EditorLoadingAndSavingUtils.load_map('/Game/Bumpit/Maps/BumpitCell')
handle=u.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()

