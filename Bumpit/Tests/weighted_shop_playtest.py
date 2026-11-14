"""PIE integration tests for five offers, persistent sold slots and ball physics."""
from pathlib import Path
source=(Path(__file__).parent/'ball_progression_playtest.py').read_text(encoding='utf-8-sig')
source=source.split("u.EditorLoadingAndSavingUtils.load_map")[0]
source=source.replace("'ball_progression.json'","'weighted_shop.json'").replace('All progression and physical split-ball assertions passed','Weighted balls and persistent-slot rerolls passed')
exec(compile(source,__file__,'exec'))

def offers(r):return [call(r,'OfferType',i) for i in range(5)]
def draw_until(h,r,slot,typ):
    for _ in range(150):
        if call(r,'OfferType',slot)==typ:return
        call(h,'RerollShop')
    raise AssertionError('Expected type never appeared in random offers')

def exercise(h):
    r=p(h,'Rules');t=p(h,'Table');ball=p(t,'Ball')
    check(len(offers(r))==5 and all(0<=v<=4 for v in offers(r)),'New stage initializes five valid offers')
    seen=set();duplicate=False;initialcredits=p(h,'Credits')
    for _ in range(60):
        call(h,'RerollShop');items=offers(r);seen.update(items)
        duplicate |= len(set(items))<len(items)
    check(seen==set(range(5)),'All five ball types appear in random stock')
    check(duplicate,'Independent draws allow duplicate ball offers')
    check(p(h,'Credits')==initialcredits and p(r,'MaxBalls')==0 and list(p(r,'BallQueue'))==[],'Free reroll does not alter credits or purchased balls')
    for slot,typ in enumerate([0,3,4]):
        draw_until(h,r,slot,typ)
        before=p(h,'Credits');call(h,'PurchaseOffer',slot)
        check(p(h,'Credits')==before-[3,4,4][slot] and offers(r)[slot]==-1,'Purchase consumes only the selected offer')
        queue=list(p(r,'BallQueue'));credits=p(h,'Credits')
        call(h,'PurchaseOffer',slot)
        check(p(h,'Credits')==credits and list(p(r,'BallQueue'))==queue,'An empty slot cannot be bought twice')
        for _ in range(10):call(h,'RerollShop')
        check(offers(r)[:slot+1]==[-1]*(slot+1),'Reroll never refills previously purchased slots')
        check(list(p(r,'BallQueue'))==queue,'Reroll preserves purchase order and types')
    check(list(p(r,'BallQueue'))==[0,3,4],'Normal, heavy and light balls queue in purchase order')
    remaining=offers(r);call(h,'PurchaseOffer',3)
    check(p(h,'Credits')==1 and offers(r)==remaining,'Insufficient credits leave the offer intact')
    call(h,'PurchaseOffer',-1);call(h,'PurchaseOffer',5)
    check(offers(r)==remaining,'Invalid slot indices cannot change inventory')
    normalmass=0;normalspeed=0
    for i,typ in enumerate([0,3,4]):
        call(h,'ChooseObstacle',0);call(h,'StartRound')
        check(p(r,'ActiveBallType')==typ and p(h,'Phase')==1,'Queued weight variant launches')
        mass=ball.get_mass();speed=ball.get_physics_linear_velocity().length()
        if i==0:normalmass=mass;normalspeed=speed
        else:
            ratio=2.0 if typ==3 else .5;speedratio=.85 if typ==3 else 1.15
            check(abs(mass/normalmass-ratio)<.02,f'Type {typ} has the intended physical mass')
            check(abs(speed/normalspeed-speedratio)<.02,f'Type {typ} has the intended launch speed')
        stock=offers(r);credits=p(h,'Credits');call(h,'RerollShop');call(h,'PurchaseOffer',4)
        check(offers(r)==stock and p(h,'Credits')==credits,'Purchase and reroll are blocked after launch')
        call(h,'Settle',list(p(r,'Multipliers')).index(10))
        if i<2:call(h,'NextStage')
    call(r,'TickClearShow',10.0);call(r,'TickCoins',10.0)
    check(all(0<=v<=4 for v in offers(r)) and p(r,'MaxBalls')==0,'Next stage refills every slot and resets purchase count')
    check(abs(ball.get_mass()/normalmass-1)<.02 and p(t,'WeightSpeedScale')==1,'Normal preview resets the previous weight effect')
    for slot in range(5):
        draw_until(h,r,slot,0);call(h,'PurchaseOffer',slot)
    check(p(r,'MaxBalls')==5 and offers(r)==[-1]*5,'All five slots can be purchased, reaching the cap')
    credits=p(h,'Credits');queue=list(p(r,'BallQueue'));call(h,'RerollShop')
    check(offers(r)==[-1]*5 and p(h,'Credits')==credits and list(p(r,'BallQueue'))==queue,'Reroll with all slots sold leaves the shop empty')
    call(h,'PurchaseOffer',0)
    check(p(r,'MaxBalls')==5 and p(h,'Credits')==credits,'Five-ball cap cannot be bypassed through an empty slot')
    # Keep generator contract used by the shared asynchronous PIE runner.
    if False:yield

u.EditorLoadingAndSavingUtils.load_map('/Game/Bumpit/Maps/BumpitCell')
handle=u.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
