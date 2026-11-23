"""Wire original workshop Foley into the shipped Blueprint gameplay paths."""
from pathlib import Path
import sys
import unreal as u

root = Path(__file__).parent
sys.path.insert(0,str(root))
from blueprint_graph import B, Graph, HUD, RULES, ROOT, CP, put
table = u.load_asset(ROOT+'BP_PinballTable')
tilt = u.load_asset(ROOT+'BP_TiltView')
lamp = u.load_asset(ROOT+'BP_LampFlicker')
GAME='/Script/Engine.GameplayStatics:'
MATH='/Script/Engine.KismetMathLibrary:'
SYS='/Script/Engine.KismetSystemLibrary:'
AUDIO='/Script/Engine.AudioComponent:'
PRIM='/Script/Engine.PrimitiveComponent:'
TCLASS=table.generated_class().get_path_name()
assets={}
for path in u.EditorAssetLibrary.list_assets('/Game/Bumpit/Audio/Workshop',False,False):
    obj=u.load_asset(path)
    assets[obj.get_name()[2:]]=obj
assert len(assets)==59, len(assets)
components={}
src=(root/'apply_gimmicks.py').read_text(encoding='utf-8-sig').split('with toolset_registry.tool_raising_exceptions():')[0]
exec(compile(src,'<component tools>','exec'),components)

def ret(node):
    outputs=[p for p in B._get_node_info(node).output_pins if p.type_id!='Exec']
    result=next((p for p in outputs if p.name=='ReturnValue'), outputs[0] if outputs else None)
    assert result, node.get_name()
    return B._resolve_pin(result.pin_id)
def play(g, key, volume=.85):
    return g.action(GAME+'PlaySound2D',Sound=assets[key].get_path_name(), VolumeMultiplier=volume)
def math(g,fn,**kw): return ret(g.call(MATH+fn,**kw))
def current(g): return ret(g.call(GAME+'GetTimeSeconds'))
def guard(g,cond): g.tail=g.branch(cond)[0]
def valid(g,obj):return ret(g.call(SYS+'IsValid',Object=obj))
def args(g,fields):
    for key,kind in fields:
        typ=B._make_variable_type(kind) if isinstance(kind,str) else u.BlueprintEditorLibrary.get_object_reference_type(kind.static_class())
        g.e.add_graph_input_parameter(key,typ)
def get_other(g,obj,owner,name):
    n=g.e.add_get_member_variable_node(name,owner.generated_class().get_path_name())
    put(n.find_input_pin('self'),obj)
    return n.find_output_pin(name)
def add_vars(bp,names):
    for n,k in names:
        if n not in B.list_variables(bp): B.add_variable(bp,n,k)
    B.compile_blueprint(bp)
def hook(bp,fn,host,build,out='then'):
    g=Graph(bp,fn)
    n=g.entry.get_owning_node() if host=='entry' else g.old('K2Node_'+host)
    dest=next(p for p in B._get_node_info(n).output_pins if p.name==out).connected_pins
    g.tail=n.find_output_pin(out)
    g.tail.break_pin_links()
    build(g)
    for link in dest: assert g.tail.try_create_connection(B._resolve_pin(link))
def cue(bp,fn,host,key,out='then'):
    hook(bp,fn,host,lambda g:play(g,key),out)
def event(bp,fn,host,method,out='then'):
    hook(bp,fn,host,lambda g:g.action(method),out)
def finish(bp):
    add_vars(bp,[('WorkshopSfxInstalled','bool')])
    B.compile_blueprint(bp,warnings_as_errors=True)
    assert u.EditorAssetLibrary.save_loaded_asset(bp,False)
def pending(bp): return 'WorkshopSfxInstalled' not in B.list_variables(bp)

def setup_table():
    add_vars(table,[('LastRailSound','float'),('LastMagnetPullSound','float'),('MagnetSoundStrength','float')])
    channels=[('Charge','01_Charge'),('Roll','09_Roll'),('Magnet','17_Magnet'),('Rotor','24_Motor'),('Room','51_Workshop')]
    for name,key in channels:
        c=components['add_component'](table,'Foley'+name,u.AudioComponent)
        c.set_editor_property('sound',assets[key])
        c.set_editor_property('auto_activate',name=='Room')
        c.set_editor_property('allow_spatialization',False)
        c.set_editor_property('volume_multiplier',.56 if name=='Room' else 1.)
    B.compile_blueprint(table)
    for name,_ in channels[:-1]:
        g=Graph(table,'Mix'+name+'Loop')
        args(g,[('Level','float'),('Pitch','float')])
        c=g.get('Foley'+name)
        active,off=g.branch(g.math('Greater_DoubleDouble',g.arg('Level'),.015))
        running=ret(g.call(AUDIO+'IsPlaying',self=c))
        g.tail=off
        guard(g,running)
        g.action(AUDIO+'Stop',self=c)
        g.tail=active
        g.action(AUDIO+'SetVolumeMultiplier',self=c,NewVolumeMultiplier=g.arg('Level'))
        g.action(AUDIO+'SetPitchMultiplier',self=c,NewPitchMultiplier=g.arg('Pitch'))
        guard(g,g.math('Not_PreBool',running))
        g.action(AUDIO+'Play',self=c)
    B.compile_blueprint(table)
    g=Graph(table,'UpdateWorkshopLoops')
    args(g,[('Charging','bool'),('Power','float'),('Playing','bool')])
    def select(flag,yes,no):
        return math(g,'SelectFloat',A=yes,B=no,bPickA=flag)
    g.action('MixChargeLoop',Level=select(g.arg('Charging'),.85,0),Pitch=math(g,'MapRangeClamped',Value=g.arg('Power'),InRangeA=0,InRangeB=1,OutRangeA=.72,OutRangeB=1.72))
    v=math(g,'VSize',A=g.get('IncomingVelocity'))
    split_speed=math(g,'VSize',A=g.get('SplitVelocity'))
    v=math(g,'FMax',A=v,B=select(g.get('SplitSpawned'),split_speed,0))
    roll=math(g,'MapRangeClamped',Value=v,InRangeA=20,InRangeB=850,OutRangeA=0,OutRangeB=.65)
    g.action('MixRollLoop',Level=select(g.arg('Playing'),roll,0),Pitch=math(g,'MapRangeClamped',Value=v,InRangeA=0,InRangeB=900,OutRangeA=.70,OutRangeB=1.5))
    elapsed=g.math('Subtract_DoubleDouble',current(g),g.get('LastMagnetPullSound'))
    near=g.math('BooleanAND',g.arg('Playing'),g.math('Less_DoubleDouble',elapsed,.12))
    g.action('MixMagnetLoop',Level=select(near,g.get('MagnetSoundStrength'),0),Pitch=1)
    rotor=ret(g.call('/Script/Engine.KismetArrayLibrary:Array_Contains',TargetArray=g.get('ActionTypes'),ItemToFind=10))
    g.action('MixRotorLoop',Level=select(g.math('BooleanAND',rotor,g.arg('Playing')),.65,0),Pitch=1)
    g=Graph(table,'WorkshopRailHit')
    args(g,[('Other',u.PrimitiveComponent),('Impulse','Vector'),('Normal','Vector')])
    g.reject(ret(g.call('/Script/Engine.ActorComponent:ComponentHasTag',self=g.arg('Other'),Tag='Bumper')))
    up=ret(g.call('/Script/Engine.Actor:GetActorUpVector'))
    dot=math(g,'Dot_VectorVector',A=up,B=g.arg('Normal'))
    guard(g,math(g,'InRange_FloatFloat',Value=dot,Min=-.72,Max=.72))
    mag=math(g,'VSize',A=g.arg('Impulse'))
    g.reject(g.math('Less_DoubleDouble',mag,1.0))
    g.reject(g.math('Less_DoubleDouble',g.math('Subtract_DoubleDouble',current(g),g.get('LastRailSound')),.045))
    g.set('LastRailSound',current(g))
    rules=g.get('ActiveRules')
    guard(g,valid(g,rules))
    typ=get_other(g,rules,RULES,'ActiveBallType')
    volume=math(g,'MapRangeClamped',Value=mag,InRangeA=1,InRangeB=750,OutRangeA=.22,OutRangeB=.90)
    for val,key in [(5,'26_Rubber'),(3,'27_Heavy'),(4,'27_Light')]:
        yes,no=g.branch(g.math('EqualEqual_IntInt',typ,val));g.tail=yes;play(g,key,volume);g.tail=no
    play(g,'03_Rail',volume)
    g=Graph(table,'WorkshopPocket')
    args(g,[('Lane','int')])
    lost,goal=g.branch(g.math('Less_IntInt',g.arg('Lane'),0))
    g.tail=lost;play(g,'05_Drain');g.tail=goal
    rules=g.get('ActiveRules')
    guard(g,valid(g,rules))
    n=g.call(CP[RULES]+':LaneMultiplier',self=rules,Lane=g.arg('Lane'))
    if any(p.type_id=='Exec' for p in B._get_node_info(n).input_pins): g.exec(n)
    mult=ret(n)
    for cutoff,key in [(10,'04_PocketX10'),(5,'04_PocketX5'),(2,'04_PocketX2')]:
        yes,no=g.branch(g.math('GreaterEqual_IntInt',mult,cutoff));g.tail=yes;play(g,key);g.tail=no
    play(g,'04_PocketX1')
    g=Graph(table,'WorkshopComboExpired')
    guard(g,g.math('GreaterEqual_IntInt',g.get('BumperComboCount'),8))
    play(g,'12_ComboEnd',.57)
    g=Graph(table,'WorkshopComboExtras')
    count=g.get('BumperComboCount')
    guard(g,g.math('GreaterEqual_IntInt',count,8))
    g.action(SYS+'K2_SetTimer',FunctionName='WorkshopComboExpired',Time=.85)
    milestone,other=g.branch(g.math('EqualEqual_IntInt',g.math('Percent_IntInt',count,8),0))
    g.tail=milestone;play(g,'13_Milestone',.66);g.tail=other
    guard(g,g.math('GreaterEqual_IntInt',g.get('BumperComboCount'),17));play(g,'11_Overdrive',.44)
    g=Graph(table,'WorkshopHitAccent')
    args(g,[('Other',u.PrimitiveComponent)])
    for name in ('LeftBumpers','RightBumpers'):
        yes,no=g.branch(g.math('EqualEqual_ObjectObject',g.arg('Other'),g.get(name)))
        g.tail=yes;play(g,'06_Plate',.7);g.tail=no
    rules=g.get('ActiveRules')
    guard(g,valid(g,rules))
    typ=get_other(g,rules,RULES,'ActiveBallType')
    for val,key in [(1,'28_Boost'),(6,'28_Lucky')]:
        yes,no=g.branch(g.math('EqualEqual_IntInt',typ,val));g.tail=yes;play(g,key,.48);g.tail=no
    g=Graph(table,'WorkshopDashEmpty')
    args(g,[('Cell','int')])
    types=g.call('/Script/Engine.KismetArrayLibrary:Array_Get',TargetArray=g.get('ActionTypes'),Index=g.arg('Cell')).find_output_pin('Item')
    guard(g,g.math('EqualEqual_IntInt',types,8))
    play(g,'22_DashEmpty')
    g=Graph(table,'WorkshopRefill')
    guard(g,ret(g.call('/Script/Engine.KismetArrayLibrary:Array_Contains',TargetArray=g.get('ActionTypes'),ItemToFind=8)))
    play(g,'23_DashRefill',.55)
    B.compile_blueprint(table,warnings_as_errors=True)
    cue(table,'Launch','CallFunction_22','02_Plunger')
    cue(table,'EventGraph','CallFunction_15','07_Gate')
    for i in [0,1]:
        def wall(g,i=i):
            ev=g.old('K2Node_ComponentBoundEvent_'+str(i))
            normal=g.call(GAME+'BreakHitResult',Hit=ev.find_output_pin('Hit')).find_output_pin('ImpactNormal')
            g.action('WorkshopRailHit',Other=ev.find_output_pin('OtherComp'),Impulse=ev.find_output_pin('NormalImpulse'),Normal=normal)
        hook(table,'EventGraph','ComponentBoundEvent_'+str(i),wall)
    def copyrail(g):
        normal=g.call(GAME+'BreakHitResult',Hit=g.arg('Hit')).find_output_pin('ImpactNormal')
        g.action('WorkshopRailHit',Other=g.arg('Other'),Impulse=g.arg('Impulse'),Normal=normal)
    hook(table,'CopyHit','IfThenElse_1',copyrail,'else')
    for host,var in [('VariableSet_1','PrimaryLane'),('VariableSet_4','SplitLane')]:
        hook(table,'CheckBall',host,lambda g,v=var:g.action('WorkshopPocket',Lane=g.get(v)))
    hook(table,'TickCopies','VariableSet_2',lambda g:g.action('WorkshopPocket',Lane=ret(g.old('K2Node_CallFunction_5'))))
    for host,key in [('VariableSet_5','14_Blast'),('VariableSet_6','15_Gold'),('VariableSet_9','16_Warp')]:
        cue(table,'ApplyGimmick',host,key)
    cue(table,'CopyHit','CallArrayFunction_1','15_Gold')
    cue(table,'ProcessActionBall','CallFunction_29','18_Dash')
    hook(table,'ProcessActionBall','IfThenElse_3',lambda g:g.action('WorkshopDashEmpty',Cell=g.old('K2Node_MacroInstance_0').find_output_pin('Index')),'else')
    cue(table,'SpawnTileCopy','VariableSet_0','19_Copy')
    cue(table,'SpawnTileCopy','CallFunction_21','21_CopySpent')
    cue(table,'SpinnerHit','CallFunction_3','20_SpinnerHit')
    cue(table,'MaybeSplit','VariableSet_0','25_Split')
    event(table,'ResetActionRound','entry','WorkshopRefill')
    event(table,'PlayBumperNote','CallFunction_5','WorkshopComboExtras')
    hook(table,'SpawnBumperHitFX','entry',lambda g:g.action('WorkshopHitAccent',Other=g.arg('OtherComp')))
    def magnet(g):
        dist=ret(g.old('K2Node_CallFunction_16'))
        level=math(g,'MapRangeClamped',Value=dist,InRangeA=0,InRangeB=g.get('MagnetRadius'),OutRangeA=.88,OutRangeB=.05)
        g.set('MagnetSoundStrength',level);g.set('LastMagnetPullSound',current(g))
    hook(table,'PullBall','CallFunction_19',magnet)
    finish(table)
def setup_hud():
    add_vars(HUD,[('LastStepSound','float'),('NextStepRight','bool')])
    g=Graph(HUD,'WorkshopSteps')
    args(g,[('Motion','float')])
    guard(g,g.math('Greater_DoubleDouble',g.arg('Motion'),.01))
    guard(g,g.math('Greater_DoubleDouble',g.math('Subtract_DoubleDouble',current(g),g.get('LastStepSound')),.34))
    g.set('LastStepSound',current(g))
    g.set('NextStepRight',g.math('Not_PreBool',g.get('NextStepRight')))
    a,b=g.branch(g.get('NextStepRight'));g.tail=a;play(g,'53_Step1',.74);g.tail=b;play(g,'53_Step2',.74)
    g=Graph(HUD,'WorkshopMix')
    t=g.get('Table');guard(g,valid(g,t))
    g.action(TCLASS+':UpdateWorkshopLoops',self=t,Charging=g.get('Charging'),Power=g.get('Power'),Playing=g.math('EqualEqual_IntInt',g.get('Phase'),1))
    g=Graph(HUD,'WorkshopStation')
    args(g,[('Destination','int')])
    guard(g,g.math('NotEqual_IntInt',g.arg('Destination'),g.get('Station')))
    play(g,'49_Move',.7)
    guard(g,g.math('EqualEqual_IntInt',g.arg('Destination'),3))
    play(g,'50_CRT',.77)
    B.compile_blueprint(HUD,warnings_as_errors=True)
    event(HUD,'UpdateBoard','entry','WorkshopMix')
    hook(HUD,'Walk','CallFunction_25',lambda g:g.action('WorkshopSteps',Motion=ret(g.old('K2Node_CallFunction_16'))))
    hook(HUD,'Walk','CallFunction_30',lambda g:g.action('WorkshopSteps',Motion=ret(g.old('K2Node_CallFunction_16'))))
    def station(g):
        n=g.old('K2Node_VariableSet_0')
        pin=next(p for p in B._get_node_info(n).input_pins if p.name=='Station')
        g.action('WorkshopStation',Destination=B._resolve_pin(pin.connected_pins[0]))
    hook(HUD,'Visit','entry',station)
    for fn,host,key in [
        ('Purchase','VariableSet_3','40_Buy'),('PurchaseOffer','VariableSet_0','41_Denied'),
        ('RerollShop','CallFunction_1','42_Reroll'),('ChooseObstacle','VariableSet_3','43_Pick'),
        ('EditCell','VariableSet_3','44_Place'),('EditCell','VariableSet_1','45_Remove'),
        ('CycleBall','CallFunction_0','46_Cycle'),('NextStage','CallFunction_2','39_Ready'),
        ('Settle','VariableSet_0','32_ScoreTick')]:
        cue(HUD,fn,host,key)
    for fn,hosts,key in [('Purchase',[0,1,2],'41_Denied'),('RerollShop',[3,4,5],'41_Denied'),('EditCell',[2,4,5,6,7,9],'47_Locked'),('UpdateInventory',[3,4],'48_Scroll')]:
        for num in hosts: cue(HUD,fn,'VariableSet_'+str(num),key)
    finish(HUD)

def setup_rules():
    g=Graph(RULES,'WorkshopTiltWarning')
    remaining=g.call('TiltsLeft')
    if any(p.type_id=='Exec' for p in B._get_node_info(remaining).input_pins): g.exec(remaining)
    guard(g,g.math('EqualEqual_IntInt',ret(remaining),1))
    play(g,'31_TiltWarning')
    B.compile_blueprint(RULES)
    event(RULES,'OnBallStalled','VariableSet_0','WorkshopTiltWarning')
    for fn,host,key in [
        ('OnBallStalled','CallFunction_6','08_Relaunch'),('OnBallStalled','VariableSet_2','30_Blackout'),
        ('RecordBall','VariableSet_5','33_Clear'),('RecordBall','VariableSet_8','34_Fail'),
        ('RecordBall','VariableSet_3','38_GameOver'),
        ('TickCoins','CallFunction_3','35_CoinShower'),('Banner','entry','36_Banner'),
        ('ShuffleLanes','entry','37_Shuffle')]:
        cue(RULES,fn,host,key)
    hook(RULES,'RestartGame','entry',lambda g:g.action(GAME+'SpawnSound2D',Sound=assets['38_Restart'].get_path_name(),VolumeMultiplier=.75,bPersistAcrossLevelTransition=True))
    finish(RULES)

if pending(table): setup_table()
if pending(HUD): setup_hud()
if pending(RULES): setup_rules()
if pending(tilt):
    cue(tilt,'Shake','entry','29_Tilt');finish(tilt)
if pending(lamp):
    cue(lamp,'Flicker','VariableSet_1','52_Flicker',);finish(lamp)
u.log('WORKSHOP_SFX_INSTALLED')







