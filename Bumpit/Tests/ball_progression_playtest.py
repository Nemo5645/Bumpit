"""Integration test using the map's real GameMode/HUD and compiled Blueprints.

Launch editor with -ExecutePythonScript=<this file> -unattended -nullrhi.
The editor exits after writing Saved/Tests/ball_progression.json.
"""
import json
import time
import traceback
from pathlib import Path
import unreal as u
u.EditorPythonScripting.set_keep_python_script_alive(True)

editor=u.get_editor_subsystem(u.UnrealEditorSubsystem)
level=u.get_editor_subsystem(u.LevelEditorSubsystem)
checks=[]
def check(condition,message):
    assert condition,message
    checks.append(message)
def p(obj,name): return obj.get_editor_property(name)
def call(obj,name,*args): return obj.call_method(name,tuple(args))

def exercise(h):
    r=p(h,'Rules');t=p(h,'Table')
    check(p(h,'Credits')==12 and p(r,'MaxBalls')==0,'Fresh game has 12 credits and no purchased balls')
    call(h,'StartRound')
    check(p(h,'Phase')==0,'Cannot launch without a purchased ball')
    call(h,'ChooseObstacle',0)
    check(sum(p(h,'Stock'))==0,'Cannot claim a choice before purchasing a ball')
    for _ in range(3): call(h,'Purchase',0)
    check(p(h,'Credits')==3 and p(r,'MaxBalls')==3 and sum(p(h,'Stock'))==0,'Shop buys three balls, not obstacles')
    call(h,'StartRound')
    check(p(h,'Phase')==0,'Cannot launch before choosing an obstacle')
    call(h,'ChooseObstacle',-1);call(h,'ChooseObstacle',3)
    check(p(r,'ChoicePending'),'Invalid choices do not consume the choice')
    for i in range(3):
        check(p(r,'ChoicePending'),f'Round {i+1} offers a fresh choice')
        call(h,'ChooseObstacle',i)
        before=list(p(h,'Stock'))
        call(h,'ChooseObstacle',(i+1)%3)
        check(list(p(h,'Stock'))==before,f'Round {i+1} cannot claim twice')
        call(h,'EditCell',i,False)
        check(p(h,'CellTypes')[i]==i+1,f'Round {i+1} can place selected obstacle')
        call(h,'EditCell',i,False);call(h,'EditCell',i,True)
        check(p(h,'CellTypes')[i]==i+1,'Existing obstacles cannot be freely picked up')
        call(h,'StartRound')
        check(p(h,'Phase')==1 and p(r,'StageStarted'),f'Round {i+1} launches')
        credits=p(h,'Credits');call(h,'Purchase',0)
        check(p(h,'Credits')==credits and p(r,'MaxBalls')==3,'Mid-stage purchases are rejected')
        winning_lane=list(p(r,'Multipliers')).index(10)
        call(h,'Settle',winning_lane)
        count=p(r,'BallsUsed');score=p(h,'TotalPoints');tickets=p(r,'RemovalTickets')
        call(h,'Settle',8)
        check(p(r,'BallsUsed')==count and p(h,'TotalPoints')==score and p(r,'RemovalTickets')==tickets,'Duplicate settlement is ignored')
        check(count==i+1,'Each launch consumes exactly one round')
        if i<2:
            check(p(r,'State')==0 and p(r,'RemovalTickets')==0,'Stage does not end early after reaching target')
            call(h,'NextStage')
            check(p(r,'CurrentRound')==1 and p(h,'Stage')==1 and p(h,'Phase')==0,'Next ball stays in the same stage')
    check(p(r,'State')==1 and p(r,'RemovalTickets')==2,'Purchased third ball finishes stage and grants two tickets')
    # Run the actual existing completion animation, which advances automatically.
    call(r,'TickClearShow',10.0)
    check(p(r,'CurrentRound')==2 and p(r,'MaxBalls')==0 and not p(r,'StageStarted'),'Completion starts a fresh shopping budget')
    check(list(p(h,'CellTypes'))[:3]==[1,2,3],'Stage transition preserves every placed obstacle')
    call(r,'TickCoins',10.0)
    check(p(h,'Station')==2,'Completion animation returns to shop')
    call(h,'EditCell',-1,True);call(h,'EditCell',47,True)
    check(p(r,'RemovalTickets')==2,'Invalid or empty cells do not consume tickets')
    call(h,'EditCell',0,True);call(h,'EditCell',1,True);call(h,'EditCell',2,True)
    check(p(r,'RemovalTickets')==0 and list(p(h,'CellTypes'))[:3]==[0,0,3],'Exactly two obstacles can be demolished')
    check(sum(p(h,'Stock'))==0,'Demolition does not refund obstacle stock')
    call(h,'Purchase',0);call(h,'ChooseObstacle',1);call(h,'StartRound')
    call(h,'Settle',list(p(r,'Multipliers')).index(10))
    check(p(r,'State')==1 and p(r,'BallsUsed')==1,'One purchased ball produces a one-round stage')
    call(r,'TickClearShow',10.0);call(r,'TickCoins',10.0)
    check(p(r,'RemovalTickets')==2,'Each cleared stage grants another two tickets')
    for typ in (1,2,0,0,0): call(h,'Purchase',typ)
    check(p(r,'MaxBalls')==5,'Stage can contain more than the old four-round limit')
    check(list(p(r,'BallQueue'))==[1,2,0,0,0],'Mixed purchases preserve FIFO launch order')
    credits=p(h,'Credits')
    call(h,'Purchase',0);call(h,'Purchase',1);call(h,'Purchase',2)
    check(p(r,'MaxBalls')==5 and p(h,'Credits')==credits,'All ball types share the five-ball purchase cap')
    for i in range(5):
        call(h,'ChooseObstacle',0)
        if i==1:call(h,'EditCell',19,False)
        call(h,'StartRound')
        check(p(r,'ActiveBallType')==[1,2,0,0,0][i],'Launch consumes the correct purchased ball type')
        lane=list(p(r,'Multipliers')).index(10)
        check(call(r,'ScoreBall',0,lane)==1000,'Special ball never doubles the base score')
        check(call(r,'ScoreBall',4,lane)==(3000 if i==0 else 2000),'Only bumper-earned points receive the x2 bonus')
        if i==1:
            ball=p(t,'Ball');extra=p(t,'SplitBall');transform=t.get_actor_transform()
            center=call(t,'HexCenter',19)+u.Vector(0,0,15)
            ball.set_world_location(u.MathLibrary.transform_location(transform,center+u.Vector(-70,12,0)),False,True)
            ball.set_enable_gravity(False)
            ball.set_physics_linear_velocity(u.MathLibrary.transform_direction(transform,u.Vector(280,0,0)))
            until=time.monotonic()+3
            while not p(t,'SplitSpawned') and time.monotonic()<until:yield
            check(p(t,'SplitSpawned') and extra.is_simulating_physics(),'Actual bumper collision spawns a second physical ball')
            check(call(t,'HitCount')>=1,'The original bounce still scores a bumper hit')
            call(t,'MaybeSplit',t.get_actor_forward_vector())
            check(len([c for c in t.get_components_by_class(u.StaticMeshComponent) if c.is_simulating_physics()])==2,'Further bounces cannot create more than two balls')
            ball.set_physics_linear_velocity(u.Vector());extra.set_physics_linear_velocity(u.Vector())
            extra.set_enable_gravity(False)
            ball.set_world_location(u.MathLibrary.transform_location(transform,u.Vector(0,-400,0)),False,True)
            extra.set_world_location(u.MathLibrary.transform_location(transform,u.Vector(0,0,15)),False,True)
            check(call(t,'CheckBall')==-1 and p(t,'PrimaryDone'),'Round waits for the second ball after the first drains')
            rounds=p(r,'BallsUsed');call(h,'Settle',-2)
            check(p(r,'BallsUsed')==rounds and p(h,'Phase')==1,'Early settlement cannot consume a split round')
            extra.set_world_location(u.MathLibrary.transform_location(transform,u.Vector(0,-400,0)),False,True)
            check(call(t,'CheckBall')==-2 and p(t,'SplitDone'),'Two drained balls finish one round')
            ball.set_enable_gravity(True);extra.set_enable_gravity(True)
        call(h,'Settle',-2)
        check(p(r,'BallsUsed')==i+1,'A split pair consumes exactly one purchased ball')
        if i<4:
            call(h,'NextStage')
            call(h,'EditCell',2,True)
            check(p(r,'RemovalTickets')==2 and p(h,'CellTypes')[2]==3,'Demolition is blocked between rounds after first launch')
    check(p(r,'State')==2 and p(r,'RemovalTickets')==2,'Failed five-round stage does not grant clear rewards')

deadline=time.monotonic()+90
done=False
scenario=None
def tick(delta):
    global done,scenario
    if done:return
    try:
        world=editor.get_game_world()
        if world:
            pc=u.GameplayStatics.get_player_controller(world,0)
            h=pc.get_hud() if pc else None
            if h and p(h,'Rules'):
                if scenario is None:scenario=exercise(h)
                try:next(scenario)
                except StopIteration:finish(True,'All progression and physical split-ball assertions passed')
                return
        if time.monotonic()>deadline: raise TimeoutError('PIE did not initialize')
    except Exception:
        finish(False,traceback.format_exc())
def finish(ok,message):
    global done
    done=True
    out=Path(u.Paths.project_saved_dir())/'Tests'/'ball_progression.json'
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({'passed':ok,'message':message,'checks':checks},ensure_ascii=False,indent=2),encoding='utf8')
    u.log('BALL_PROGRESSION_TEST '+str(ok)+' '+message)
    u.unregister_slate_post_tick_callback(handle)
    level.editor_request_end_play()
    u.SystemLibrary.quit_editor()

u.EditorLoadingAndSavingUtils.load_map('/Game/Bumpit/Maps/BumpitCell')
handle=u.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
