"""PIE integration tests for the gimmick bumpers (obstacle cards 3-6) and balls 5 (rubber) and 6 (lucky),
added by Tools/apply_gimmicks.py on top of main's ball-purchase progression. Same runner as the other tests;
it plays through the real flow (buy balls, pick a card each round, place it, launch, settle).

Launch editor with -ExecutePythonScript=<this file> -unattended -nullrhi.
The editor exits after writing Saved/Tests/gimmick.json."""
from pathlib import Path
source=(Path(__file__).parent/'ball_progression_playtest.py').read_text(encoding='utf-8-sig')
source=source.split("u.EditorLoadingAndSavingUtils.load_map")[0]
source=source.replace("'ball_progression.json'","'gimmick.json'").replace('All progression and physical split-ball assertions passed','Gimmick bumpers and new balls passed')
exec(compile(source,__file__,'exec'))

GIMMICKS=[('BlastBumpers',20),('MagnetBumpers',21),('GoldBumpers',22),('WarpBumpers',23)]  # cards 3-6

def hidden(part,cell):
    return part.get_instance_transform(cell,False).translation.z<-1000

def wait(seconds):
    """Gimmicks ignore a second hit within 0.1 s; let game time pass between them."""
    until=time.monotonic()+seconds
    while time.monotonic()<until:yield

def exercise(h):
    r=p(h,'Rules');t=p(h,'Table');ball=p(t,'Ball')
    parts={name:p(t,name) for name,_ in GIMMICKS}
    check(len(p(h,'Stock'))==7 and list(p(h,'ObstacleNames'))[3:]==['폭발 범퍼','자석 범퍼','황금 범퍼','워프 범퍼'],'Seven obstacle cards: main three, then four gimmick bumpers')
    check(all(part.get_instance_count()==48 and all(hidden(part,c) for c in range(48)) for part in parts.values()),'Every gimmick bumper has a hidden instance per cell')
    for _ in range(4):call(h,'Purchase',0)
    check(p(r,'MaxBalls')==4,'Four balls bought for four gimmick rounds')
    lane=list(p(r,'Multipliers')).index(10)
    for k,(name,cell) in enumerate(GIMMICKS):
        card=3+k
        check(p(r,'ChoicePending'),f'Round {k+1} offers a free pick')
        call(h,'ChooseObstacle',card)
        check(p(h,'Stock')[card]==1 and p(h,'Selected')==card,f'Card {card} is a free pick')
        call(h,'EditCell',cell,False)
        check(p(h,'CellTypes')[cell]==card+1 and p(h,'Stock')[card]==0,f'Card {card} places obstacle type {card+1}')
        check(not hidden(parts[name],cell) and all(hidden(o,cell) for n,o in parts.items() if n!=name),f'{name} appears in its cell')
        if name=='MagnetBumpers':
            check(list(p(t,'MagnetCells'))==[21],'The magnet cell is tracked for the pull')
        call(h,'StartRound')
        check(p(h,'Phase')==1,f'Round {k+1} launches')
        yield from wait(.15)
        if name=='BlastBumpers':
            v=u.MathLibrary.transform_direction(t.get_actor_transform(),u.Vector(-200,150,0))
            ball.set_physics_linear_velocity(v)
            call(t,'ApplyGimmick',parts[name],ball,False)
            check(abs(ball.get_physics_linear_velocity().length()/v.length()-p(t,'BlastBoost'))<.03,'Blast bumper multiplies the ball speed')
        if name=='GoldBumpers':
            hits=p(t,'Hits');call(t,'ApplyGimmick',parts[name],ball,False)
            check(p(t,'Hits')==hits+p(t,'GoldHits'),'Gold bumper adds bonus hits to the ball')
            yield from wait(.15)
            split_hits=p(t,'SplitHits');call(t,'ApplyGimmick',parts[name],p(t,'SplitBall'),True)
            check(p(t,'SplitHits')==split_hits+p(t,'GoldHits'),'Gold bumper adds bonus hits to the split ball')
        if name=='WarpBumpers':
            call(t,'ApplyGimmick',parts[name],ball,False)
            local=u.MathLibrary.inverse_transform_location(t.get_actor_transform(),ball.get_world_location())
            check(abs(local.x-300)<1 and abs(local.y)<=220.5,'Warp bumper moves the ball near the top of the table')
        call(h,'Settle',lane)
        if k<3:call(h,'NextStage')
    check(p(r,'State')==1 and p(r,'RemovalTickets')==2,'Four gimmick rounds clear the stage')
    call(r,'TickClearShow',10.0);call(r,'TickCoins',10.0)
    check(list(p(h,'CellTypes'))[20:24]==[4,5,6,7],'Gimmick bumpers stay on the board into the next stage')
    call(h,'EditCell',21,True)
    check(p(h,'CellTypes')[21]==0 and hidden(parts['MagnetBumpers'],21) and list(p(t,'MagnetCells'))==[],'Demolishing a magnet hides it and stops its pull')
    # Balls 5 and 6, bought through main's shop rules and launched in purchase order.
    check([call(r,'BallName',i) for i in (5,6)]==['고무공','행운의 공'] and [call(r,'BallCost',i) for i in (5,6)]==[4,5],'Balls 5 and 6 have names and prices')
    check(call(r,'BallName',4)=='가벼운 공' and call(r,'BallName',7)=='구매 완료' and call(r,'BallCost',7)==0,'Main ball tables and the empty-slot entry are unchanged')
    credits=p(h,'Credits');call(h,'Purchase',7)
    check(p(h,'Credits')==credits and p(r,'MaxBalls')==0,'Ball IDs past 6 cannot be bought')
    call(h,'Purchase',5)
    check(p(r,'ActiveBallType')==5 and ball.get_material(0).get_name()=='MI_Ball_Rubber' and p(t,'WeightSpeedScale')==1,'Rubber ball is next: its colour, normal weight')
    call(h,'Purchase',6)
    check(list(p(r,'BallQueue'))==[5,6] and p(h,'Credits')==credits-9,'Rubber and lucky balls queue in purchase order at 4 + 5')
    lane=list(p(r,'Multipliers')).index(10)  # a new stage shuffles the goal multipliers
    call(h,'ChooseObstacle',0);call(h,'StartRound')
    check(p(r,'ActiveBallType')==5 and p(h,'Phase')==1,'Rubber ball launches')
    check(call(r,'LaneMultiplier',lane)==10,'Rubber ball keeps the goal multiplier')
    call(h,'Settle',lane);call(h,'NextStage')
    call(h,'ChooseObstacle',0);call(h,'StartRound')
    check(p(r,'ActiveBallType')==6 and ball.get_material(0).get_name()=='MI_Ball_Lucky','Lucky ball launches with its colour')
    check(call(r,'LaneMultiplier',lane)==20 and call(r,'ScoreBall',0,lane)==2000,'Lucky ball doubles the goal multiplier')
    before=p(h,'TotalPoints');call(h,'Settle',lane)
    check(p(h,'TotalPoints')-before==2000,'Lucky ball scores double in the real settlement')
    check(p(t,'RubberBounce')==.95,'Rubber ball wall bounce is set')

u.EditorLoadingAndSavingUtils.load_map('/Game/Bumpit/Maps/BumpitCell')
handle=u.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
