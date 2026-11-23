"""Original workshop Foley and arcade cues, rendered as mono PCM for Unreal."""
import wave
from pathlib import Path
import numpy as np

RATE = 48000
OUT = Path(__file__).resolve().parents[1] / 'SoundSources' / 'Workshop'
OUT.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(8724)
def time(s): return np.arange(round(RATE*s))/RATE
def tone(hz,d=.15,end=None,metal=.12):
    t=time(d)
    phase=2*np.pi*(hz*t+(0 if end is None else (end-hz)*t*t/(2*d)))
    return (np.sin(phase)+metal*np.sin(phase*2.73)+.10*np.sin(phase*4.16))*np.exp(-4*t/d)*np.minimum(t/.002,1)
def hiss(d,center,width):
    t=time(d)
    f=np.fft.rfftfreq(len(t),1/RATE)
    spec=np.fft.rfft(rng.normal(size=len(t)))*np.exp(-.5*((f-center)/width)**2)
    a=np.fft.irfft(spec,n=len(t))
    return a/max(.01,np.max(np.abs(a)))*np.exp(-2*t/d)*np.minimum(t/.002,1)
def mix(*events):
    y=np.zeros(max(round(s*RATE)+len(a) for s,a in events))
    for s,a in events:
        i=round(s*RATE);y[i:i+len(a)]+=a
    return y
def hit(f,d=.17,bright=1500):
    return mix((0,tone(f,d,f*.37)),(.002,.52*hiss(d*.4,bright,bright*.42)),(.008,.28*tone(f*4.8,d*.7)))
def brass(f,d=.38):
    return mix((0,tone(f,d,metal=.31)),(.004,.44*tone(f*1.46,d*.83)),(0,.22*hiss(.024,3300,1200)))
def notes(fs,step=.085,dec=.20):
    return mix(*[(i*step,brass(f,dec)) for i,f in enumerate(fs)])
def scatter(n,span,source):
    return mix(*[(span*(i/n)**1.24,source(i)*(.65+.35*rng.random())) for i in range(n)])
def loop(d,freqs,noiseHz=0):
    t=time(d)
    y=sum(amp*np.sin(2*np.pi*round(f*d)*t/d + .7*j) for j,(f,amp) in enumerate(freqs))
    if noiseHz:
        f=np.fft.rfftfreq(len(t),1/RATE)
        n=np.fft.irfft(np.fft.rfft(rng.normal(size=len(t)))*np.exp(-.5*((f-noiseHz)/(.38*noiseHz))**2),n=len(t))
        y+=.24*n/(.001+np.max(abs(n)))
    return y*(.80+.20*np.cos(2*np.pi*3*t/d))
def save(name,a,level=.75,periodic=False):
    a=np.tanh(a*1.35)
    if not periodic:
        a[-min(len(a),480):]*=np.linspace(1,0,min(len(a),480))
        a[0]=0
    a*=level/max(abs(a))
    with wave.open(str(OUT/(name+'.wav')),'wb') as w:
        w.setparams((1,2,RATE,0,'NONE',''));w.writeframes(np.round(a*32767).astype('<i2').tobytes())

# High priority. Looped mechanisms are balanced below transients.
save('01_Charge',loop(1,[(96,.5),(192,.25),(387,.12),(960,.08)],610),.28,True)
save('02_Plunger',mix((0,hit(160,.26)),(.013,.68*brass(510,.11)),(.039,.52*hiss(.17,740,410))))
save('03_Rail',hit(342,.12,2340),.56)
for mult,fs in [(1,[330]),(2,[330,440]),(5,[330,440,554]),(10,[330,440,554,740])]:
    save(f'04_PocketX{mult}',mix((0,hit(114,.15)),(.035,.8*notes(fs,.055))))
save('05_Drain',mix((0,hit(168,.29)),(.045,hiss(.35,480,280)),(.19,.53*hit(79,.25))))
save('14_Blast',mix((0,hit(115,.36)),(0,hiss(.19,290,220)),(.024,.62*brass(408,.16))))
save('15_Gold',notes([1045,1569,1318],.044,.32))
save('16_Warp',mix((0,tone(1070,.17,155,.5)),(.15,hiss(.12,1230,550)),(.195,tone(290,.28,1450,.45))))
save('18_Dash',mix((0,hit(174,.09)),(.009,hiss(.22,1780,950)),(.012,tone(218,.2,1135,.45))))
save('19_Copy',mix((0,hit(430,.085)),(.033,brass(568,.22)),(.082,brass(849,.27))))
save('20_SpinnerHit',mix((0,hit(270,.15)),(.019,.55*hit(570,.075)),(.056,.31*hit(680,.07))))
save('25_Split',mix((0,hit(485,.08)),(.025,tone(505,.21,291)),(.048,tone(620,.26,1120))))
save('29_Tilt',mix((0,hit(91,.31,680)),(.032,.55*hit(181,.19)),(.09,.29*hiss(.14,470,220))))
save('30_Blackout',mix((0,hit(281,.09)),(.035,tone(645,.74,42,.6)),(.055,hiss(.38,1450,1110))))
counter = mix((0,hit(880,.045,2550)),(.014,.34*tone(1319,.045)))
save('32_ScoreTick',mix(*[(delay,counter*level) for delay,level in ((0,.74),(.052,.79),(.112,.84),(.188,.89),(.29,1.0))]),.48)
save('33_Clear',mix((0,notes([311,392,466,622,784],.098,.39)),(.39,.52*brass(466,.59))))
save('34_Fail',mix((0,notes([392,370,294,196],.14,.30)),(.41,.45*hit(76,.42))))
save('40_Buy',mix((0,hit(285,.10)),(.032,brass(988,.39)),(.068,.43*brass(1479,.32))))
save('41_Denied',notes([156,139],.095,.115),.52)
save('42_Reroll',scatter(5,.24,lambda i:hiss(.085,1350+190*i,880)),.62)
save('43_Pick',mix((0,hiss(.10,1760,940)),(.031,notes([494,659],.055,.14))),.61)
save('44_Place',mix((0,hit(218,.17)),(.033,.75*hit(480,.09,2500))))
# Medium priority.
save('06_Plate',mix((0,hit(415,.16)),(.008,.7*brass(775,.19))),.61)
save('07_Gate',mix((0,hiss(.09,985,590)),(.041,hit(301,.13))),.57)
save('08_Relaunch',mix((0,hit(291,.09)),(.088,hit(165,.20))),.67)
save('11_Overdrive',mix((0,brass(932,.14)),(.032,.64*brass(1175,.18))),.49)
save('17_Magnet',loop(2,[(82,.62),(164,.3),(250,.15),(415,.09)]),.26,True)
save('21_CopySpent',mix((0,hiss(.17,1680,540)),(.015,tone(905,.18,320))),.38)
save('26_Rubber',tone(295,.21,80,.05),.61)
save('31_TiltWarning',notes([554,554],.14,.12),.56)
save('35_CoinShower',scatter(12,.81,lambda i:brass(rng.uniform(950,1910),.25)),.65)
save('36_Banner',mix((0,hit(160,.20)),(.026,.55*brass(587,.26))))
save('37_Shuffle',mix(*[(i*.026+i*i*.0022,hit(630-13*i,.056)) for i in range(10)]),.52)
save('38_GameOver',mix((0,notes([294,247,220,147],.19,.44)),(.57,hit(78,.49))))
save('38_Restart',notes([196,294,392],.11,.23))
save('45_Remove',scatter(5,.18,lambda i:hit(510/(1+.36*i),.12,1800-190*i)),.66)
save('46_Cycle',mix((0,hit(250,.095)),(.037,brass(510,.13))),.52)
save('47_Locked',hit(126,.115,770),.45)
save('49_Move',mix((0,hiss(.24,440,230)),(.045,.45*hiss(.19,1040,480))),.44)
save('50_CRT',mix((0,hit(330,.085)),(.025,hiss(.27,2400,1300)),(.063,tone(1510,.38,1760))),.50)
save('51_Workshop',loop(4,[(60,.35),(120,.22),(245,.08),(411,.03)],390),.14,True)
# Low priority.
save('09_Roll',loop(1.5,[(54,.19),(73,.12),(179,.06)],540),.24,True)
save('12_ComboEnd',tone(530,.28,210,.34),.43)
save('13_Milestone',notes([740,932,1244],.037,.18),.53)
save('22_DashEmpty',hit(177,.07,680),.38)
save('23_DashRefill',notes([392,494,587],.049,.09),.40)
save('24_Motor',loop(2,[(46,.35),(92,.2),(276,.1)],830),.19,True)
save('27_Heavy',hit(106,.21,980),.68)
save('27_Light',hit(550,.079,2640),.43)
save('28_Boost',brass(1047,.15),.39)
save('28_Lucky',notes([988,1245],.038,.17),.40)
save('39_Ready',notes([247,370],.087,.18),.51)
save('48_Scroll',hit(550,.044,1150),.31)
save('52_Flicker',scatter(3,.07,lambda i:hiss(.036,2400-270*i,1300)),.32)
for i in (1,2):
    save(f'53_Step{i}',mix((0,hit(93+12*i,.16,470)),(.037,hiss(.098,570+100*i,380))),.40)

