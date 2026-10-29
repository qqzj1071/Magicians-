"""Event/transaction engine for the frozen 15-deck library, exact rule arithmetic.

Own card projection and enemy changes are evaluated from a joint snapshot;
numeric attribute deltas merge, shield resources merge once, damage resolves
in waves, then bounded reactions, simultaneous execute, revival and death.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, field, fields, replace, asdict
from fractions import Fraction as Q
from hashlib import sha256
from typing import Optional
import math
import random

from cards import CARDS, DECKS, SPECIAL, STACKING, ROUTES, SHIELDS, HEALS, SUB, PARAMS, CARD_VERSION

RULE_VERSION = '1.0'
INF = 10**12
SHIELD_CONFLICT = 'proportional'

def param(name,default):return Q(str(PARAMS.get(name,default)))


def ceil(x):
    return -(-x.numerator // x.denominator) if isinstance(x,Q) else math.ceil(x)


@dataclass
class State:
    element: str
    specialization_selected: bool = True
    hp: int = 1000
    attack: int = 100 if CARD_VERSION == '1.1' else 60
    defense: int = 40 if CARD_VERSION == '1.1' else 20
    atk_debuff: int = 0
    def_debuff: int = 0
    shield: Q = Q(0)
    layers: int = 0
    seen: frozenset = frozenset()
    spec: bool = False
    route: str = ''
    contract: bool = False
    badge: bool = False
    guardian: bool = False
    ember: int = 0
    spent_ember: int = 0
    ash_credit: int = 0
    shuffles: int = 0
    ash_rebirth_claims: int = 0
    ash_return_claims: int = 0
    ash_book_checkpoint: int = 0
    tide: Q = Q(0)
    next_draw: int = 0
    next_energy: int = 0
    energy: int = 0
    next_fire: int = 100
    bonus: int = 0
    extra: Q = Q(0)
    shield_loss: Q = Q(0)
    grip_bonus: int = 0
    delay: Q = Q(0)
    permanent_delay: Q = Q(0)
    interval_factor: Q = Q(1)
    def_pen: int = 0
    shield_bonus: int = 0
    subs: tuple = ()
    shot_count: int = 0
    last_time: int = -1
    last_main: Q = Q(0)
    wind_marks: int = 0
    detonate_bonus: int = 0
    poison: int = 0
    poison_due: int = INF
    poison_generation: int = 0
    decay_extend: int = 0
    poison_guards: int = 0
    poison_next_hit: int = 0
    poison_two_hits: int = 0
    poison_repeat: int = 0
    vulnerability: int = 0
    reduce_percent: int = 0
    reduce_flat: int = 0
    temporary_shield: bool = False
    retention80: bool = False
    shield_broken: bool = False
    return_flat: int = 0
    break_vuln: int = 0
    break_draw: int = 0
    grip30: bool = False
    ember_hit80: int = 0
    heal_hit80: int = 0
    tide_bonus: int = 0
    tide_record_bonus: int = 0
    healed_before: bool = False
    rewind: tuple = ()
    revived: bool = False
    negative_guard: int = 0
    heal_block: int = 0
    window_bonus: int = 0
    window_pen: int = 0
    main_pen: int = 0
    main_def_pen: int = 0
    shield_leech: int = 0
    pre_shield: int = 0


@dataclass
class Packet:
    source: int
    raw: Q
    kind: str
    final: Q = Q(1)
    penetration: Q = Q(0)
    shield_multiplier: Q = Q(1)
    main: bool = False
    marks: int = 0
    reaction: bool = True
    reflect_coeff: Q = Q(0)
    reflect_defense: Q = Q(0)
    reflect_pen: Q = Q(0)
    wall: bool = False
    rock_return: bool = False
    actual: int = 0
    amount: int = 0
    absorbed: Q = Q(0)


def stats(states, i):
    s, enemy = states[i], states[1-i]
    a, d = s.attack-(0 if s.negative_guard else s.atk_debuff), s.defense-(0 if s.negative_guard else s.def_debuff)
    if not s.negative_guard and s.poison and enemy.element=='poison' and enemy.spec:
        ac, dc = (param('bone_attack_coeff',.8),param('bone_def_coeff',.6)) if enemy.route=='蚀骨' else (param('poison_attack_coeff',.5),param('poison_def_coeff',.3))
        a -= math.floor(2+ac*enemy.layers*s.poison)
        d -= math.floor(2+dc*enemy.layers*s.poison)
    return max(0,a), max(0,d)


def fire_factor(s):
    # All decks in this library have selected their specialization before battle.
    return 1+layer_rate(s,'fire_layer_percent',2.5)*s.layers/100 if s.element=='fire' else Q(1)


def layer_rate(s,name,default):
    """Selected specialization strengthens ordinary layers before its ability is played."""
    return param(name,default)*(1 if s.specialization_selected else Q(1,2))


def reflection_rate(s):
    if s.route=='反震岩核':return param('rock_reflect_per_layer',8)
    if s.route=='壁垒之心':return param('wall_reflect_per_layer',param('earth_reflect_per_layer',5))
    return param('earth_reflect_per_layer',5)


def ember_factor(s, consumed):
    if s.element!='fire' or not s.spec:return Q(1)
    rate=param('fire_route_ember_percent',param('ember_percent',3)) if s.route=='燃烧血统' else param('ember_percent',3)
    return 1+s.layers*rate*consumed/100


def gap(s, temporary=True):
    fixed = 50+s.permanent_delay+(s.delay if temporary else 0)
    if s.element=='fire' and s.route=='燃烧血统': fixed += 50
    if s.element=='water' and s.route=='生命之泉': fixed -= param('spring_gap_flat',4)+param('spring_gap_layer',1)*s.layers
    if s.element=='wind' and s.spec:
        fixed -= 6+param('blade_gap_per_layer',1.5)*s.layers if s.route=='疾风之刃' else 5+param('wind_gap_per_layer',1)*s.layers
    return max(1,math.floor(fixed*s.interval_factor))


def shield_pen(s, kind='missile'):
    if kind=='shield': return Q(1,2) if s.route=='大地之握' and s.spec else Q(0)
    if kind=='missile' and s.element=='wind':
        return min(Q(1),s.layers*(layer_rate(s,'wind_layer_pen',5)+(layer_rate(s,'wind_pierce_shield_per_layer',0) if s.route=='穿云箭' else 0))/100)
    return Q(0)


def heal(s, amount, record=True, record_bonus=0):
    block=0 if s.negative_guard else min(param('heal_block_cap',60),s.heal_block)
    actual = min(max(0,ceil(amount*(1-block/100))),max(0,1000-s.hp))
    s.hp += actual
    if actual: s.healed_before=True
    if record and s.element=='water' and s.spec:
        rate = param('echo_record_per_layer',7) if s.route=='潮汐回响' else param('water_record_per_layer',5)
        s.tide += actual*rate*s.layers/100*Q(100+record_bonus,100)
    return actual


def pay(s, percent):
    amount = min(max(0,s.hp-1),ceil(Q(max(0,s.hp)*percent,100)))
    s.hp -= amount
    return amount


def consume_ember(s, amount):
    if not s.spec: return 0
    n=min(s.ember,amount);s.ember-=n;s.spent_ember+=n
    if s.route=='灰烬循环':s.ash_credit+=n
    if s.route=='余烬之核':
        for _ in range(n):heal(s,(1000-s.hp)*param('core_heal_percent',5)/100)
    return n


def gain_ember(s,n):
    if s.element=='fire' and s.spec:s.ember=min(5,s.ember+n)


def shuffled(s):
    s.shuffles+=1
    if s.spec and s.route=='灰烬循环':gain_ember(s,1)


def schedule_poison(states,target,t):
    s,owner=states[target],states[1-target]
    s.poison_generation+=1
    period=max(1,ceil(Q(200//s.poison)*(1+Q(owner.decay_extend,100)))) if s.poison else 0
    if owner.route=='蚀骨':period*=2
    s.poison_due=t+period if s.poison else INF


def change_poison(states,target,delta,t):
    s,owner=states[target],states[1-target]
    old=s.poison;s.poison=max(0,s.poison+delta)
    if owner.route=='毒爆':owner.attack+=int(param('poison_growth_attack',1))*abs(old-s.poison)
    if s.poison!=old:schedule_poison(states,target,t)


def cleanse(states,i,t,poison_count=None):
    s=states[i]
    s.atk_debuff=s.def_debuff=s.vulnerability=s.heal_block=s.wind_marks=0
    if s.poison:change_poison(states,i,-min(s.poison,poison_count if poison_count is not None else s.poison),t)


def expire_draw_effects(states):
    for s in states:
        s.negative_guard=s.heal_block=s.window_bonus=s.window_pen=0


def packet(states,source,raw,kind='missile',final=None,main=False,marks=0):
    s,e=states[source],states[1-source]
    ec=reflection_rate(e)
    ec=ec*e.layers/100 if e.element=='earth' and e.spec else Q(0)
    defense=stats(states,source)[1]*Q(25 if e.route=='反震岩核' and e.spec else 50,100)
    return Packet(source,Q(raw),kind,fire_factor(s) if final is None else final,
                  shield_pen(s,'shield' if kind=='shield' else kind),
                  Q(100+s.shield_bonus+(param('wind_arrow_shield_bonus_percent',20) if s.route=='穿云箭' else 0),100) if kind=='missile' else Q(1),
                  main,marks,True,ec,defense,shield_pen(e,'shield'),
                  e.route=='壁垒之心' and e.spec,e.route=='反震岩核')


def poison_packet(states,i,multiplier=Q(1),explode=False):
    s,e=states[i],states[1-i]
    if not e.poison:return None
    a,d=stats(states,i)[0],stats(states,1-i)[1]
    raw=Q(a)*layer_rate(s,'poison_damage_per_layer',2.5)/100*s.layers*e.poison*multiplier
    if s.route=='蚀命' and not explode:raw+=1000*param('life_poison_percent',2)/100*e.poison
    return packet(states,i,raw-Q(d,2),'poison')


@dataclass
class ShieldOps:
    ordinary: Q = Q(0)
    free: Q = Q(0)
    spent: Q = Q(0)
    cut: Q = Q(0)


@dataclass
class Plan:
    source: int
    local: list
    shields: list = field(default_factory=lambda:[ShieldOps(),ShieldOps()])
    packets: list = field(default_factory=list)
    search: tuple = ()
    shuffle: bool = False
    post_return: tuple = ()
    consume_packet: int = -1
    consume_coeff: Q = Q(0)
    consume_defense: Q = Q(0)
    convert_heal_percent: Q = Q(0)


def card_plan(snapshot,i,name,t):
    c=CARDS[name]
    assert snapshot[i].energy>=c.cost,(name,snapshot[i].energy)
    states=[replace(s) for s in snapshot]
    s,e=states[i],states[1-i]
    p=Plan(i,states)
    s.energy-=c.cost
    if c.element!='generic' and name not in s.seen:
        s.layers+=c.layers;s.seen=s.seen|{name}
    s.attack+=c.attack;s.defense+=c.defense
    def addshield(n,target=i,free=False,temp=False):
        n=Q(n);ops=p.shields[target];z=states[target]
        if free or temp:ops.free+=n
        else:ops.ordinary+=n
        retained=ceil(snapshot[target].shield*Q(3,4)) if ops.ordinary else snapshot[target].shield
        z.shield=retained+ops.ordinary+ops.free-ops.spent-ops.cut
        if z.route=='大地之握':z.shield_loss=snapshot[target].shield_loss+max(Q(0),snapshot[target].shield-retained)
        if temp:z.temporary_shield=True
    def spendshield():
        n=s.shield;p.shields[i].spent+=n;s.shield=Q(0);return n
    def poison_ticks(n=1):
        if not e.poison:return
        n+=s.poison_repeat;s.poison_repeat=0
        for _ in range(n):p.packets.append(poison_packet(states,i))
    def explode(mult):
        if not e.poison:return
        n=e.poison;p.packets.append(poison_packet(states,i,mult,True));change_poison(states,1-i,-n,t)
    def shieldblast():
        if not s.spec:return
        n=spendshield();coeff=reflection_rate(s)*s.layers/100
        df=Q(25 if s.route=='反震岩核' else 50,100)*stats(states,1-i)[1]
        p.consume_packet=len(p.packets)
        p.consume_coeff=coeff;p.consume_defense=df
        p.packets.append(packet(states,i,n*coeff-df,'shield'))
        p.packets[-1].final*=param('active_shield_multiplier',1)
    if name in SPECIAL:s.spec=True
    elif name in ROUTES:
        s.route=name
        if name=='壁垒之心':p.search=('shield',5,2);s.next_energy+=1
    elif name in STACKING:pass
    elif name=='禁忌知识':pay(s,5);s.next_draw+=3;s.next_energy+=1
    elif name=='禁咒目录':p.search=('epic',5,2);s.next_energy+=1
    elif name=='魔力契约':s.contract=True
    elif name=='战神徽记':s.badge=True
    elif name=='守护者壁垒':s.guardian=True
    elif name=='时光倒流':
        a,d=stats(states,i);s.rewind=(a,d,s.hp,s.shield,t+200)
    elif name in ('元素熔炉','魔法阵核心'):
        # All legal v5 search candidates are mono-element; neither can yield a bonus.
        pass
    elif name=='通晓':s.next_draw+=2
    elif name=='灵感涌现':s.next_draw+=2;s.next_energy+=1
    elif name=='小检索':p.search=('any',3,1)
    elif name=='循环':shuffled(s);p.shuffle=True;s.next_draw+=1;s.next_energy+=1
    elif name=='拆盾弹':s.main_pen+=int(param('counter_common_pen',25))
    elif name=='断流封印':e.heal_block+=int(param('counter_heal_block',30))
    elif name=='稳固结界':s.reduce_percent+=int(param('counter_reduce',30))
    elif name=='破障法阵':s.main_pen+=int(param('counter_main_pen',60));s.main_def_pen+=int(param('counter_main_def_pen',25))
    elif name=='应急整备':
        cleanse(states,i,t,int(param('counter_clean',2)));heal(s,param('counter_heal',100));s.next_draw+=1
    elif name=='火墙':
        if s.poison or s.atk_debuff or s.def_debuff or s.vulnerability or s.heal_block or s.wind_marks:cleanse(states,i,t,int(param('fire_clean_poison',1)))
        else:addshield(param('fire_clean_shield',20))
    elif name=='烈焰附身':e.heal_block+=int(param('heal_block',25))
    elif name=='焰心屏障':s.pre_shield+=int(param('fire_pre_shield',50))
    elif name=='静水':s.shield_leech+=int(param('shield_leech',50))
    elif name=='厚土':heal(s,min(param('earth_heal_cap',60),s.shield*param('earth_heal_percent',20)/100))
    elif name=='山岳之躯':
        ratio=param('earth_convert_percent',150)/100
        n=min(math.floor(s.shield),param('earth_convert_cap',150),ceil(max(0,1000-s.hp)/ratio))
        p.shields[i].spent+=n;s.shield-=n;p.convert_heal_percent=ratio
    elif name=='疾影':s.window_bonus+=int(param('wind_window_bonus',25))
    elif name=='风之躯':cleanse(states,i,t)
    elif name=='腐骨':
        n=min(param('poison_cut_cap',80),e.shield*param('poison_cut_percent',20)/100)
        p.shields[1-i].cut+=n;e.shield-=n
    elif name=='渗骨毒素':s.window_pen+=int(param('poison_window_pen',20))
    elif name in ('火星','火苗'):pass
    elif name=='火花':s.bonus+=10
    elif name=='火种翻找':p.search=('element',2,1)
    elif name=='烈焰冲刺':s.delay-=10
    elif name=='猛火弹':s.bonus+=30
    elif name=='压实火药':s.delay+=30;s.bonus+=20
    elif name=='导火索':s.bonus+=20 if gap(s)>=75 else 10
    elif name=='余烬刻度':
        if s.layers>=6:gain_ember(s,1)
        else:s.next_draw+=1
    elif name=='高压弹仓':s.delay+=30;s.bonus+=15;gain_ember(s,1)
    elif name=='慢燃':s.delay+=50;s.bonus+=30
    elif name=='压缩爆燃':s.bonus+=10+(20 if stats(states,i)[0]>=90 else 0)+(15 if s.spec and s.ember>=2 else 0)
    elif name=='爆裂弹头':s.bonus+=20;s.ember_hit80+=int(s.spec)
    elif name=='余烬护心':
        if s.spec and s.ember:consume_ember(s,1);heal(s,Q((1000-s.hp)*15,100))
        else:addshield(10)
    elif name=='燃血':
        pay(s,5);gain_ember(s,1);s.next_draw+=1
    elif name=='灼痛':s.heal_hit80+=1
    elif name=='焚心':
        if s.spec:
            n=consume_ember(s,2)
            if n:
                for _ in range(n):heal(s,Q((1000-s.hp)*15,100))
            else:gain_ember(s,1)
    elif name=='余烬心脏':
        if s.hp<=300:gain_ember(s,2);heal(s,Q((1000-s.hp),5))
        else:gain_ember(s,1);s.next_draw+=1
    elif name=='余火':s.next_draw+=1
    elif name=='火种库':p.search=('element',4,1)
    elif name=='灰烬账本':
        if s.spec and s.spent_ember-s.ash_book_checkpoint>=int(param('ash_book_cost',2)):
            gain_ember(s,1)
            if 'ash_book_cost' in PARAMS:s.ash_book_checkpoint+=int(param('ash_book_cost',2))
        else:s.next_draw+=2
    elif name=='回火':
        shuffled(s);p.shuffle=True
        if s.spec and s.shuffles>=int(param('ash_return_shuffles',2)) and s.ash_return_claims<int(param('ash_return_cap',1000000)):
            gain_ember(s,1);s.ash_return_claims+=1
    elif name=='灰烬重生':
        shuffled(s);p.shuffle=True
        if PARAMS.get('ash_rebirth_every_play',False):s.ember=min(5,s.ember+1)
        elif s.spec and s.ash_rebirth_claims<int(param('ash_rebirth_cap',1000000)):
            gain_ember(s,1 if 'ash_rebirth_cap' in PARAMS else (2 if s.layers>=9 else 1));s.ash_rebirth_claims+=1
    elif name=='余烬引擎':shuffled(s);p.shuffle=True;s.next_draw+=2;s.energy+=2
    elif name in HEALS:
        heal(s,HEALS[name])
        if name in ('细流','潮声'):s.bonus+=10
        elif name=='潮涌':s.bonus+=25
        elif name=='生命洪流':s.delay-=15;s.bonus+=20
        elif name=='潮汐风暴' and s.spec:s.tide_bonus+=int(param('storm_tide_bonus_percent',100))
        elif name=='回响之潮' and s.spec:s.tide_bonus+=int(param('echo_tide_bonus_percent',50));s.tide_record_bonus+=int(param('echo_heal_record_bonus_percent',25))
        elif name=='水幕':s.main_pen+=int(param('water_main_pen',35))
    elif name=='泉眼':heal(s,50 if s.hp<=500 else 20)
    elif name=='水之低语':p.search=('element',2,1)
    elif name=='血刃':
        n=pay(s,4);s.attack+=10
        if s.spec:s.tide+=Q(n*5*s.layers,100)
    elif name=='血偿':
        heal(s,Q((1000-s.hp)*6,100))
        if s.spec:s.tide+=ceil(Q((1000-s.hp)*3*s.layers,1000))
    elif name in ('血怒','血潮汹涌'):
        if s.hp<=(500 if name=='血怒' else 350):s.attack+=8
        if s.spec:s.tide+=ceil(Q((1000-s.hp)*3*s.layers,1000))
    elif name=='濒死回响':
        n=pay(s,8);heal(s,60);s.bonus+=30
        if s.spec:s.tide+=Q(n*3*s.layers,100)
    elif name=='血之回响':
        n=pay(s,10);low=s.hp<=300;heal(s,Q(1000-s.hp,10))
        if low:s.bonus+=30
        if s.spec:s.tide+=Q(n*5*s.layers,100)
    elif name=='疾流':s.delay-=10
    elif name=='回流':
        s.next_draw+=1
        if gap(s)<=35:s.attack+=3
    elif name=='穿潮':s.def_pen+=40
    elif name=='连环潮':s.delay-=15;s.bonus+=15
    elif name=='泉心':s.delay-=25;s.def_pen+=60
    elif name=='奔流':s.interval_factor*=Q(9,10)
    elif name=='回潮':
        if s.healed_before:s.attack+=4
    elif name=='潮汐回廊':
        if s.spec:n=s.tide;s.tide=Q(0);heal(s,n*2,False)
    elif name in SHIELDS:
        n=110 if name=='裂岩护壁' and s.shield_broken else SHIELDS[name]
        addshield(n,free=name in ('盾脉','不坏壁垒'),temp=name in ('临时壁垒','岩潮壁垒'))
        if name=='岩甲' and s.shield>=100:s.attack+=2
        elif name=='岩壁' and snapshot[i].shield>=param('earth_wall_threshold',100):s.defense+=int(param('earth_wall_defense',2))
        elif name=='大地之盾' and s.shield>=200:s.defense+=5
        elif name=='盾之共鸣' and snapshot[i].shield>=100:addshield(50)
        elif name=='坚岩' and s.shield>=100:s.defense+=2
        elif name=='磐石' and s.shield>=200:s.attack+=4
        elif name=='裂岩护壁' and s.shield>=100:s.defense+=4
        elif name=='磐岩壁' and s.shield>=150:s.attack+=3
        elif name=='回岩':s.vulnerability+=25;e.vulnerability+=25
        elif name=='守岩':s.reduce_flat+=20
        elif name=='镜岩之心':s.reduce_percent+=30
        elif name=='碎岳之心':s.break_vuln+=30
        elif name=='回震岩甲':s.return_flat+=60
        elif name in ('碎盾术','岩核爆破','万钧碎盾'):
            shieldblast()
            if name=='岩核爆破':p.post_return=('fixed',30)
            if name=='万钧碎盾':p.post_return=('spent',Q(3,10))
    elif name=='寻岩':p.search=('shield',2,1)
    elif name=='碎岩印记':
        if s.shield_broken:s.defense+=6
    elif name=='余震':s.break_draw+=1
    elif name=='握盾':
        if s.route=='大地之握':s.grip_bonus+=100
    elif name=='不动如山':
        if s.shield>=50:s.defense+=2
    elif name=='岩核重压':
        df=Q(25 if s.route=='反震岩核' and s.spec else 50,100)*stats(states,1-i)[1]
        p.packets.append(packet(states,i,s.shield*param('heavy_shield_percent',25)/100-df,'shield'))
    elif name in SUB:
        fixed,ratio=SUB[name];marks=1
        if name=='风卷':s.delay-=5
        elif name=='疾行':s.delay-=10
        elif name=='风痕刻印':
            if s.route=='风痕' and s.spec:marks=3
            elif s.route!='风痕':s.delay-=5
        elif name=='风切' and gap(s)<=35:fixed+=8
        elif name=='顺风':s.permanent_delay-=1
        elif name=='追风':s.permanent_delay-=Q(1,2)
        elif name=='风驰' and gap(s)<=30:fixed+=12;s.delay-=5
        elif name=='追云':s.delay-=Q(15,2)
        elif name=='破风':e.def_debuff+=2
        elif name=='风蚀':e.def_debuff+=4
        elif name=='穿甲':e.def_debuff+=3;s.delay-=5
        elif name=='风神之翼':s.permanent_delay-=Q(3,2)
        elif name=='穿云破甲':e.def_debuff+=4;s.permanent_delay-=1
        s.subs+=((fixed,ratio,marks),)
    elif name=='风步':s.delay-=Q(15,2)
    elif name=='风眼':s.negative_guard=1
    elif name=='寻风':p.search=('element',2,1)
    elif name=='风痕回廊':s.subs+=((15,15,2 if s.spec and s.route=='风痕' else 1),)*2
    elif name=='裂空':
        s.permanent_delay-=Q(3,2)
        if s.spec and s.route=='风痕':s.detonate_bonus+=50
    elif name=='疾风连斩':
        s.permanent_delay-=Q(3,2)
        if gap(s)<=25:s.bonus+=20
    elif name=='裂空穿云':e.def_debuff+=4;s.shield_bonus+=30
    elif name in ('风幕','气旋护壁'):
        n=60 if name=='风幕' else 100
        addshield(n);addshield(n,1-i)
        if name=='风幕':s.delay-=10
        else:s.permanent_delay-=Q(3,2)
    elif name=='毒针':
        if e.shield>0 and e.poison==0:change_poison(states,1-i,1,t)
    elif name in ('腐蚀','毒雾','毒刺','毒瓶'):
        n={'腐蚀':11,'毒雾':10 if e.poison else 0,'毒刺':6.5,'毒瓶':19.5+(6.5 if e.poison else 0)}[name]
        if CARD_VERSION=='1.1':s.window_bonus+=int(Q(str(n))*2)
        else:s.extra+=Q({'腐蚀':14,'毒雾':12 if e.poison else 0,'毒刺':8,'毒瓶':24+(8 if e.poison else 0)}[name])
    elif name=='寻毒':p.search=('element',2,1)
    elif name=='速腐':s.poison_next_hit+=2
    elif name=='蚀刻':poison_ticks()
    elif name=='腐息':s.poison_repeat+=1
    elif name=='枯潮':
        if e.poison:change_poison(states,1-i,1,t);poison_ticks()
    elif name=='万蚀':poison_ticks(2)
    elif name=='蚀界':poison_ticks();s.poison_two_hits+=2
    elif name=='固毒':s.poison_guards+=1
    elif name=='延毒':s.decay_extend+=15
    elif name=='腐溃':
        if CARD_VERSION=='1.1':s.window_bonus+=int((Q(8)+Q(7,2)*e.poison)*2)
        else:s.extra+=10+4*e.poison
    elif name=='蚀创':
        if CARD_VERSION=='1.1':s.window_bonus+=int((Q(16)+Q(5)*e.poison)*2)
        else:s.extra+=20+6*e.poison
    elif name=='万毒蚀骨':
        a,d=stats(states,1-i)
        if CARD_VERSION=='1.1':s.window_bonus+=int((Q(4)*e.poison+Q(3,2)*(max(0,e.attack-a)+max(0,e.defense-d)))*2)
        else:s.extra+=5*e.poison+2*(max(0,e.attack-a)+max(0,e.defense-d))
    elif name=='蚀骨之触':
        e.def_debuff+=math.floor(2+Q(e.poison,2))
        amount=e.shield*min(Q(3,5),Q(8*e.poison,100));p.shields[1-i].cut+=amount;e.shield-=amount
    elif name=='毒囊':s.delay-=10
    elif name=='爆裂':s.delay-=Q(15,2)+(5 if e.poison>=3 else 0)
    elif name=='毒爆弹':explode(param('poison_burst_multiplier',Q(18,10)))
    elif name=='毒涌':
        n=min(2,e.poison);change_poison(states,1-i,-n,t);s.next_draw+=n;s.delay-=Q(15,2)
    elif name=='万毒爆':explode(param('all_poison_burst_multiplier',Q(22,10)));s.delay-=10
    elif name=='毒潮':
        n=e.poison;explode(param('poison_tide_multiplier',Q(28,10)));s.delay-=min(10,n)
    elif name=='命运检索':p.search=('any',7,3)
    elif name=='大检索':p.search=('any',5,2)
    elif name=='过牌':s.next_draw+=1
    elif name=='翻阅':s.next_draw+=1
    elif name=='洗牌':shuffled(s);p.shuffle=True
    elif name=='战术大师':s.next_energy+=1;s.bonus+=20
    elif name=='战术':s.next_energy+=1
    elif name=='整理':s.next_draw+=2;s.next_energy-=1
    elif name=='速读':s.next_draw+=1
    elif name=='翻找':p.search=('top',3,1)
    elif name=='寻物':p.search=('generic',3,1)
    elif name=='检索附魔':p.search=('enchantment',3,1)
    elif name=='重洗':shuffled(s);p.shuffle=True
    elif name=='利刃':s.attack+=2 if stats(states,i)[0]>=60 else 0
    elif name=='壁障':s.defense+=2 if s.shield>=30 else 0
    elif name=='短促':s.delay-=Q(15,2)
    elif name=='威吓':e.atk_debuff+=2
    elif name=='鼓舞':s.next_energy+=1
    elif name=='蓄能':s.bonus+=15
    elif name=='小盾':addshield(50)
    elif name=='护盾':addshield(60)
    elif name=='包扎':heal(s,25)
    elif name=='小治疗':heal(s,40)
    elif name=='风暴':s.subs+=((30,30,1),)
    elif name=='愈合之光':heal(s,110 if s.hp<=500 else 70)
    elif name=='恐惧':e.atk_debuff+=4;e.def_debuff+=2
    elif name=='削弱':e.atk_debuff+=2
    elif name=='破甲':e.def_debuff+=4
    elif name=='裂伤':e.vulnerability+=50
    elif name=='蓄势':s.bonus+=20
    elif name=='锋刃':s.attack+=3 if snapshot[i].attack>=70 else 0
    elif name=='狂战':s.attack+=6 if s.hp<=500 else 0
    elif name=='铁壁':s.defense+=3 if s.shield>=50 else 0
    elif name=='战意沸腾':s.attack+=4 if s.hp>=500 else 0
    elif name in ('战意','高温炉心'):s.attack+=4 if s.layers>=6 else 0
    elif name=='剧毒':
        (setattr(s,'window_bonus',s.window_bonus+48) if CARD_VERSION=='1.1' else setattr(s,'extra',s.extra+30))
    elif name=='疫病':
        (setattr(s,'window_bonus',s.window_bonus+64) if CARD_VERSION=='1.1' else setattr(s,'extra',s.extra+40));e.def_debuff+=2
    elif name=='穿云':s.subs+=((25,30,1),)
    elif name in ('爆燃','火舌','烈风','风刃','狂风','狂暴','不灭烈焰','洪潮','深渊','深流','洪流',
                 '岩拳','山岳','巨岩','毒龙','腐化之躯','毒牙','腐潮','永恒壁垒','破军','坚壁',
                 '攻守兼备','攻守','守势','攻击强化','防御强化'):pass
    else:raise NotImplementedError(name)
    scale=Q(str(PARAMS.get('card_effect_scales',{}).get(name,1)))
    s.bonus=snapshot[i].bonus+ceil((s.bonus-snapshot[i].bonus)*scale)
    e.vulnerability=snapshot[1-i].vulnerability+ceil((e.vulnerability-snapshot[1-i].vulnerability)*scale)
    return p


BOOL_FIELDS = {'specialization_selected','spec','contract','badge','guardian','temporary_shield','retention80',
               'shield_broken','grip30','healed_before','revived'}
MERGE_SKIP = BOOL_FIELDS | {'element','shield','shield_loss','seen','route','rewind','subs',
                            'poison_due','poison_generation'}
NUMBER_FIELDS = [f.name for f in fields(State) if f.name not in MERGE_SKIP]


def ordinary_shield(s,n):
    if n>0:
        retained=ceil(s.shield*Q(3,4))
        if s.route=='大地之握':s.shield_loss+=max(Q(0),s.shield-retained)
        s.shield=retained+n


def merge_plans(snapshot,plans,t):
    states=[replace(s) for s in snapshot]
    actual_spent=[Q(0),Q(0)]
    for i,z in enumerate(states):
        before=snapshot[i]
        for p in plans:
            local=p.local[i]
            for key in NUMBER_FIELDS:
                setattr(z,key,getattr(z,key)+getattr(local,key)-getattr(before,key))
            for key in BOOL_FIELDS:setattr(z,key,getattr(z,key) or getattr(local,key))
            z.seen=z.seen|local.seen
            if local.route!=before.route:z.route=local.route
            if local.rewind!=before.rewind:z.rewind=local.rewind
            if len(local.subs)>len(before.subs):z.subs+=local.subs[len(before.subs):]
        ordinary=sum((p.shields[i].ordinary for p in plans),Q(0))
        free=sum((p.shields[i].free for p in plans),Q(0))
        spent=sum((p.shields[i].spent for p in plans),Q(0))
        cut=sum((p.shields[i].cut for p in plans),Q(0))
        retained=ceil(before.shield*Q(3,4)) if ordinary>0 else before.shield
        # Record the actual retention loss once, separately from unrelated direct additions.
        if z.route=='大地之握':z.shield_loss+=max(Q(0),before.shield-retained)
        shield=retained+ordinary+free
        if spent+cut<=shield:
            actual_spent[i]=spent;z.shield=shield-spent-cut
        elif SHIELD_CONFLICT=='spend_first':
            actual_spent[i]=min(shield,spent);z.shield=max(Q(0),shield-spent-cut)
        elif SHIELD_CONFLICT=='cut_first':
            actual_spent[i]=min(spent,max(Q(0),shield-cut));z.shield=max(Q(0),shield-cut-spent)
        elif SHIELD_CONFLICT=='proportional':
            actual_spent[i]=shield*spent/(spent+cut);z.shield=Q(0)
        else:raise RuntimeError('Unresolved simultaneous shield consumption/deletion rule')
        deltas=[p.local[i].poison-before.poison for p in plans]
        added=sum(max(0,d) for d in deltas);removed=sum(max(0,-d) for d in deltas)
        actual_removed=min(before.poison,removed)
        z.poison=before.poison+added-actual_removed
        owner=states[1-i]
        if snapshot[1-i].route=='毒爆':owner.attack+=2*(actual_removed-removed)
    for i,z in enumerate(states):
        if z.poison!=snapshot[i].poison:schedule_poison(states,i,t)
    for p in plans:
        if p.consume_packet>=0:
            p.packets[p.consume_packet].raw=actual_spent[p.source]*p.consume_coeff-p.consume_defense
        if p.convert_heal_percent:heal(states[p.source],actual_spent[p.source]*p.convert_heal_percent)
    return states,actual_spent


@dataclass
class Reaction:
    source: int
    retaliation: Q = Q(0)
    penetration: Q = Q(0)
    return_shield: Q = Q(0)
    break_event: bool = False


def apply_wave(states,packets,t,log=None,reactions=None):
    """At most one packet per source per wave. Compute both, then write both."""
    assert len({p.source for p in packets})==len(packets)
    hp_start=[s.hp for s in states]
    life=[0,0]
    deferred_heal=[0,0]
    for p in packets:
        i=p.source;target=1-i;s,e=states[i],states[target]
        raw=p.raw
        if p.kind=='missile':
            raw=raw*Q(100+(0 if e.negative_guard else e.vulnerability),100)-e.reduce_flat
            reduction=e.reduce_percent+(15 if e.route=='壁垒之心' and e.shield>0 else 0)
            amount=max(1,ceil(raw*p.final*max(Q(0),1-Q(reduction,100))))
            if not e.negative_guard:e.vulnerability=0
            e.reduce_flat=0;e.reduce_percent=0
        elif p.kind=='shield':amount=max(0,ceil(raw*p.final))
        elif p.kind=='poison' and e.negative_guard:amount=0
        else:amount=max(1,ceil(raw*p.final))
        p.amount=amount
        old=e.shield
        if p.kind=='true':hp_damage=amount;absorbed=Q(0)
        else:
            direct=amount*p.penetration;over=amount-direct
            absorbed_basis=min(over,old/p.shield_multiplier)
            absorbed=absorbed_basis*p.shield_multiplier
            e.shield=Q(ceil(max(Q(0),old-absorbed)))
            absorbed=old-e.shield
            hp_damage=ceil(direct+over-absorbed_basis)
        life[target]+=hp_damage;p.actual=min(hp_damage,max(0,hp_start[target]));p.absorbed=absorbed
        hit=absorbed>0 or p.actual>0
        if p.reaction and reactions is not None:
            broke=old>0 and e.shield==0 and absorbed>0
            reflect=Q(0)
            if p.reflect_coeff:
                if p.wall:
                    if p.kind=='missile' and absorbed>0:reflect=max(Q(0),absorbed*p.reflect_coeff-p.reflect_defense)
                elif broke:reflect=max(Q(0),old*p.reflect_coeff-p.reflect_defense)
            if reflect or broke:
                reactions.append(Reaction(target,reflect,p.reflect_pen,
                                  Q(ceil(old*Q(1,2))) if broke and p.rock_return else Q(0),broke))
        if p.main:
            s.last_main=absorbed+p.actual
            if s.element=='poison' and s.layers and p.actual>0:
                extra=s.poison_next_hit
                if s.poison_two_hits>0:extra+=1;s.poison_two_hits-=1
                change_poison(states,target,1+extra,t)
            s.poison_next_hit=0
            if s.spec and s.route=='余烬之核' and amount>=160:gain_ember(s,1)
            if amount>=80:
                gain_ember(s,s.ember_hit80)
                deferred_heal[i]+=s.heal_hit80
            s.ember_hit80=0;s.heal_hit80=0
        if hit and p.marks and s.spec and s.route=='风痕':e.wind_marks+=p.marks
    # Routing shields above cannot alter the other direction's resource pool.
    for i,s in enumerate(states):s.hp-=life[i]
    for p in packets:
        s=states[p.source]
        if p.kind=='missile' and s.element=='water':
            rate=param('blood_lifesteal_per_layer',7) if s.spec and s.route=='血潮' else layer_rate(s,'water_lifesteal_per_layer',5)
            basis=p.actual+(p.absorbed*Q(s.shield_leech,100) if p.main else 0)
            heal(s,basis*rate*s.layers/100,record_bonus=s.tide_record_bonus)
            if p.main:s.shield_leech=0
    for i,n in enumerate(deferred_heal):
        for _ in range(n):heal(states[i],Q((1000-states[i].hp)*5,100))
    if log is not None:
        log.append(dict(t=t,phase='wave',packets=[dict(source=p.source,kind=p.kind,
                        main=p.main,raw=str(p.raw),final=str(p.final),amount=p.amount,
                        actual_life=p.actual) for p in packets],states=[brief(s) for s in states]))


def execute_auto(states,t,log=None):
    snapshot=[replace(s) for s in states]
    packets=[]
    for i,s in enumerate(snapshot):
        e=snapshot[1-i]
        if s.element!='earth' or not s.spec or s.hp<=0 or s.shield<=0 or e.hp<=0:continue
        coeff=reflection_rate(s)*s.layers/100
        defense=Q(20 if s.route=='反震岩核' else 50,100)*stats(snapshot,1-i)[1]
        p=packet(snapshot,i,s.shield*coeff-defense,'shield');p.reaction=False
        amount=max(0,ceil(p.raw*p.final))
        penetrated=amount*p.penetration
        hp_damage=ceil(penetrated+max(Q(0),amount-penetrated-e.shield))
        if hp_damage>=e.hp:
            packets.append(p);states[i].shield=Q(0);states[i].defense=0
    if packets:apply_wave(states,packets,t,log)


def finish_reactions(states,reactions,t,log=None,ordinary_used=(False,False)):
    by_source=[[],[]]
    for r in reactions:
        if r.retaliation>0:
            p=packet(states,r.source,r.retaliation,'shield')
            p.penetration=r.penetration;p.reaction=False
            by_source[r.source].append(p)
    for k in range(max(map(len,by_source),default=0)):
        packets=[seq[k] for seq in by_source if k<len(seq)]
        if packets:apply_wave(states,packets,t,log)
    returns=[Q(0),Q(0)]
    for r in reactions:
        s,e=states[r.source],states[1-r.source]
        if r.break_event:
            s.shield_broken=True
            returns[r.source]+=r.return_shield+s.return_flat
            e.vulnerability+=s.break_vuln;s.break_vuln=0
            s.next_draw+=s.break_draw;s.break_draw=0
    for i,n in enumerate(returns):
        if n>0:
            if ordinary_used[i]:states[i].shield+=n
            else:ordinary_shield(states[i],n)
    execute_auto(states,t,log)


def check_death(states,t,log=None):
    eligible=[i for i,s in enumerate(states) if s.hp<=0 and s.rewind and not s.revived and t<=s.rewind[4]]
    for i in eligible:
        s=states[i];a,d,hp,shield,_=s.rewind
        s.attack=a;s.defense=d;s.hp=hp;s.shield=shield;s.revived=True
        s.atk_debuff=0;s.def_debuff=0;s.vulnerability=0;s.poison=0;s.wind_marks=0;s.heal_block=0
        s.poison_due=INF;s.poison_generation+=1
    if eligible and log is not None:log.append(dict(t=t,phase='revival',players=eligible,states=[brief(s) for s in states]))
    return any(s.hp<=0 for s in states)


def resolve_cards(snapshot,plans,t,log=None):
    states,spent=merge_plans(snapshot,plans,t)
    # Newly granted suppression starts at the step boundary, after snapshot-planned damage.
    guards=[s.negative_guard for s in states]
    for i,s in enumerate(states):s.negative_guard=snapshot[i].negative_guard
    reactions=[]
    sequences=[[],[]]
    for p in plans:sequences[p.source]=p.packets
    for k in range(max(map(len,sequences),default=0)):
        apply_wave(states,[seq[k] for seq in sequences if k<len(seq)],t,log,reactions)
    for p in plans:
        if p.post_return and p.consume_packet>=0 and states[1-p.source].hp>0:
            kind,n=p.post_return
            states[p.source].shield+=Q(n) if kind=='fixed' else Q(ceil(spent[p.source]*n))
    ordinary_used=tuple(any(p.shields[i].ordinary>0 for p in plans) for i in range(2))
    finish_reactions(states,reactions,t,log,ordinary_used)
    for i,s in enumerate(states):s.negative_guard=guards[i]
    return states


def missile(states,i,t,base_ratio=Q(1),fixed=Q(0),main=False,marks=1,ember=0):
    s=states[i]
    a=stats(states,i)[0];d=stats(states,1-i)[1]
    pen=s.def_pen+(s.main_def_pen if main else 0)+(20 if s.route=='生命之泉' else 0)+(s.layers*layer_rate(s,'wind_pierce_def_per_layer',5) if s.route=='穿云箭' else 0)
    ignore=param('wind_arrow_ignore_percent',20) if s.route=='穿云箭' and s.spec else 0
    defense=Q(d)*max(Q(0),1-Q(pen)/100)*(1-Q(ignore,100))
    if s.route=='生命之泉':defense=Q(math.floor(defense))
    if CARD_VERSION=='1.1' and s.element=='poison' and main:
        raw=((a+Q(s.window_bonus,2))*base_ratio+fixed)*Q(100+s.bonus,100)-defense
    else:
        raw=(a*base_ratio+fixed)*Q(100+s.bonus+(s.window_bonus if main else 0),100)-defense
    f=fire_factor(s)
    if main and s.element=='fire' and s.spec:
        f*=ember_factor(s,ember)
    p=packet(states,i,raw,'missile',f,main,marks)
    if main:p.penetration=min(Q(1),p.penetration+Q(s.main_pen+s.window_pen,100))
    return p


def launch(states,due,t,log=None):
    states=[replace(s) for s in states]
    blood={};grip={};embers={};tides={};intervals={};locks={}
    for i in due:
        s=states[i]
        blood[i]=ceil(Q(pay(s,4)*80,100)) if s.route=='血潮' else 0
        if s.element=='earth' and s.layers:
            ordinary_shield(s,Q(ceil(stats(states,i)[0]*layer_rate(s,'earth_shield_per_layer',5)*s.layers/100)))
        grip[i]=Q(0)
        if s.route=='大地之握':
            grip[i]=s.shield_loss*(1+Q(s.grip_bonus,100))*param('grip_damage_percent',100)/100
            s.shield_loss=Q(0);s.grip_bonus=0
        embers[i]=s.ember if s.element=='fire' and s.spec else 0
        consume_ember(s,embers[i])
        tides[i]=s.tide if s.element=='water' and s.spec else Q(0)
        s.tide=Q(0)
        if s.element=='wind' and s.spec:s.shot_count+=1
        intervals[i]=gap(s)
    for i in due:
        s=states[i]
        if s.pre_shield:
            s.shield+=ceil(stats(states,i)[0]*Q(s.pre_shield,100));s.pre_shield=0;s.temporary_shield=True
    snapshot=[replace(s) for s in states]
    sequences=[[],[]]
    for i in due:
        s=snapshot[i];a=stats(snapshot,i)[0]
        extra=s.extra+blood[i]+grip[i]+ceil(tides[i])*Q(100+s.tide_bonus,100)
        if s.route=='疾风之刃' and s.last_time>=0:
            extra+=s.last_main*max(Q(0),1-Q(t-s.last_time)/param('blade_follow_decay_window',100))*param('blade_follow_percent',50)/100
        ratio=param('fire_route_ratio',1.8) if s.route=='燃烧血统' else Q(1)
        sequences[i].append(missile(snapshot,i,t,ratio,extra,True,1,embers[i]))
        for fixed,ratio,marks in s.subs:
            sequences[i].append(missile(snapshot,i,t,Q(ratio,100),fixed,False,marks))
        locks[i]=dict(attack=a,third=s.element=='wind' and s.spec and s.shot_count%3==0,
                      count=s.shot_count,detonate_bonus=s.detonate_bonus,
                      true_ratio=param('wind_true_percent',20)/100)
    reactions=[]
    for k in range(max(map(len,sequences),default=0)):
        apply_wave(states,[seq[k] for seq in sequences if k<len(seq)],t,log,reactions)
    true=[]
    for i in due:
        if locks[i]['third']:
            p=packet(snapshot,i,locks[i]['attack']*locks[i]['true_ratio'],'true');p.reaction=False;true.append(p)
    if true:apply_wave(states,true,t,log,reactions)
    detonations=[]
    for i in due:
        if locks[i]['third'] and states[i].route=='风痕':
            n=states[1-i].wind_marks
            if n and not states[1-i].negative_guard:
                raw=locks[i]['attack']*(param('wind_mark_first',10)*n/100+param('wind_mark_step',2)*n*(n-1)/200)*Q(100+locks[i]['detonate_bonus'],100)
                p=packet(snapshot,i,raw,'true');p.reaction=False;detonations.append(p)
                states[1-i].wind_marks=0;states[i].detonate_bonus=0
    if detonations:apply_wave(states,detonations,t,log,reactions)
    for i in due:
        s=states[i]
        if s.route=='潮汐回响' and s.spec:s.tide+=ceil(tides[i]*Q(20,100))
        s.bonus=0;s.extra=Q(0);s.delay=Q(0);s.subs=();s.def_pen=0;s.shield_bonus=0
        if CARD_VERSION=='1.1' and s.element=='poison':s.window_bonus=0
        s.tide_bonus=0;s.tide_record_bonus=0;s.main_pen=0;s.main_def_pen=0;s.last_time=t;s.next_fire=t+intervals[i]
    finish_reactions(states,reactions,t,log,tuple(i in due and snapshot[i].element=='earth' and snapshot[i].layers>0 for i in range(2)))
    for i in due:
        if states[i].temporary_shield:states[i].shield=Q(0);states[i].temporary_shield=False
    if log is not None:log.append(dict(t=t,phase='launch_end',due=due,locks={i:{k:str(v) for k,v in z.items()} for i,z in locks.items()},states=[brief(s) for s in states]))
    return states


def brief(s):
    return dict(element=s.element,hp=s.hp,attack=s.attack,defense=s.defense,
                shield=str(s.shield),layers=s.layers,spec=s.spec,route=s.route,
                ember=s.ember,tide=str(s.tide),poison=s.poison,poison_due=s.poison_due,
                energy=s.energy,next_fire=s.next_fire,shots=s.shot_count,revived=s.revived,
                negative_guard=s.negative_guard,heal_block=s.heal_block,window_bonus=s.window_bonus,
                window_pen=s.window_pen,main_pen=s.main_pen,main_def_pen=s.main_def_pen,shield_leech=s.shield_leech,
                atk_debuff=s.atk_debuff,def_debuff=s.def_debuff,wind_marks=s.wind_marks,
                vulnerability=s.vulnerability)


@dataclass(frozen=True)
class Policy:
    mode: str = 'greedy'
    horizon: int = 350
    damage: float = 1.0
    health: float = 1.0
    shield: float = .8
    defense: float = 1.0
    layer: float = 8.0
    spec: float = 100.0
    route: float = 50.0
    counterplay_value: float = 1.0
    draw: float = 12.0
    energy: float = 24.0
    search: float = 18.0
    cycle: float = 8.0
    cost_power: float = .8


BASELINE=Policy(mode='baseline')
GREEDY=Policy()


def estimate(states,i,t,horizon):
    """Public-state heuristic only; deliberately no deck or random stream input."""
    s,e=states[i],states[1-i];a,d=stats(states,i)[0],stats(states,1-i)[1]
    extra=float(s.extra)
    if s.element=='water' and s.spec:extra+=ceil(s.tide)*(1+s.tide_bonus/100)
    if s.route=='血潮':extra+=max(0,s.hp)*.032
    if s.route=='大地之握':extra+=float(s.shield_loss)*(1+s.grip_bonus/100)*float(param('grip_damage_percent',100))/100
    if s.route=='疾风之刃' and s.last_time>=0:
        extra+=float(s.last_main)*max(0,1-(s.next_fire-s.last_time)/float(param('blade_follow_decay_window',100)))*float(param('blade_follow_percent',50))/100
    ratio=float(param('fire_route_ratio',1.8)) if s.route=='燃烧血统' else 1
    pen=min(1,float(s.def_pen+s.main_def_pen+(20 if s.route=='生命之泉' else 0)+(s.layers*layer_rate(s,'wind_pierce_def_per_layer',5) if s.route=='穿云箭' else 0))/100)
    ignore=float(param('wind_arrow_ignore_percent',20))/100 if s.route=='穿云箭' and s.spec else 0
    active=s.next_fire<(t//100+1)*100
    if CARD_VERSION=='1.1' and s.element=='poison':
        raw=max(1,((a+Q(s.window_bonus,2))*ratio+extra)*(1+s.bonus/100)-d*(1-pen)*(1-ignore))
    else:
        raw=max(1,(a*ratio+extra)*(1+(s.bonus+(s.window_bonus if active else 0))/100)-d*(1-pen)*(1-ignore))
    factor=float(fire_factor(s))
    if s.element=='fire' and s.spec:
        anticipated=min(5,s.ember+max(0,(s.next_fire-t)//100))
        factor*=float(ember_factor(s,anticipated))
    first=raw*factor
    subs=sum(max(1,fixed+a*ratio/100-d*(1-pen)*(1-ignore)) for fixed,ratio,_ in s.subs)
    first+=subs
    permanent_gap=gap(s,False)
    steady=max(1,a*ratio-d*(1-(.2 if s.route=='生命之泉' else 0))*(1-ignore))*float(fire_factor(s))
    if s.element=='fire' and s.spec:
        emb=min(5,max(1,round(permanent_gap/100)))
        steady*=float(ember_factor(s,emb))
    if s.element=='wind' and s.spec:
        steady+=a*float(param('wind_true_percent',20))/300
        if s.route=='风痕':steady+=a*float(param('wind_mark_first',10)*3/100+param('wind_mark_step',2)*3/100)/3
    offense=first+max(0,horizon-gap(s))/permanent_gap*steady
    if s.element=='poison' and e.poison and not e.negative_guard:
        pd=max(1,a*float(layer_rate(s,'poison_damage_per_layer',2.5))/100*s.layers*e.poison+(10*float(param('life_poison_percent',2))*e.poison if s.route=='蚀命' else 0)-d*.5)
        offense+=pd*horizon/100
    if s.element=='earth' and s.spec:
        offense+=max(0,float(s.shield)*s.layers*float(reflection_rate(s))/100-d*(.25 if s.route=='反震岩核' else .5))
    return min(6000,offense)


def value(states,i,t,policy):
    s,e=states[i],states[1-i]
    h=min(policy.horizon,max(100,1700-t))
    incoming=estimate(states,1-i,t,100)
    urgency=1+min(2,incoming/max(100,s.hp))
    a,d=stats(states,i)
    shield_value=float(s.shield)*(1-float(shield_pen(e)))
    if s.temporary_shield:shield_value*=.65
    score=(s.hp*policy.health*urgency-e.hp*policy.damage)
    score-=float(e.shield)*(1-float(shield_pen(s)))*policy.damage*.25
    score+=shield_value*policy.shield*urgency+d*policy.defense*h/100
    score+=estimate(states,i,t,h)*policy.damage
    score+=s.layers*policy.layer+int(s.spec)*policy.spec+int(bool(s.route))*policy.route
    score+=s.next_draw*policy.draw+s.next_energy*policy.energy
    next_draw=(t//100+1)*100
    fires=0 if s.next_fire>=next_draw else 1+max(0,(next_draw-1-s.next_fire)//max(1,float(gap(s))))
    if s.next_fire-t<=h:
        score+=s.pre_shield/100*a*policy.shield*.5*policy.counterplay_value
        score+=(s.main_pen+(s.window_pen if fires else 0))/100*min(float(e.shield),max(0,a))*policy.damage*policy.counterplay_value
        if s.shield_leech and s.element=='water':
            rate=float(param('blood_lifesteal_per_layer',7) if s.spec and s.route=='血潮' else param('water_lifesteal_per_layer',5))*s.layers/100
            score+=min(max(0,1000-s.hp),float(e.shield)*s.shield_leech/100*rate)*policy.health*.6*policy.counterplay_value
    if e.heal_block and not e.negative_guard and e.element=='water':
        score+=min(1000-e.hp,max(0,stats(states,1-i)[0])*e.layers*.05)*min(.6,e.heal_block/100)*policy.damage
    if s.contract:score+=(h/100)*(policy.energy-policy.draw)
    if s.badge:score+=h/100*12
    if s.guardian:score+=h/100*6
    if s.rewind and not s.revived and t<=s.rewind[4]:score+=max(0,s.rewind[2]-s.hp*.3)*.3
    if e.hp<=0:score+=10000
    if s.hp<=0:score-=15000
    return score


def choose_queue(snapshot,i,pool,policy,t,discard=()):
    if policy.mode=='staged':
        from planner import choose
        return choose(snapshot,i,pool,policy,t,discard)
    states=[replace(s) for s in snapshot]
    remaining=list(pool);queue=[];reasons=[]
    while remaining:
        options=[]
        before=value(states,i,t,policy) if policy.mode!='baseline' else 0
        for name in remaining:
            c=CARDS[name]
            if c.cost>states[i].energy:continue
            plan=card_plan(states,i,name,t)
            after=resolve_cards(states,[plan],t)
            if policy.mode=='baseline':
                startup=not states[i].spec or not states[i].route
                if c.kind=='specialization':score=1200
                elif c.kind=='route_legendary':score=1000
                elif c.name in STACKING:score=800
                elif c.name in ('禁忌知识','禁咒目录'):score=900
                elif startup and (plan.search or plan.shuffle or after[i].next_draw>states[i].next_draw):score=650
                elif c.element!='generic' and name not in states[i].seen:score=450+c.attack
                else:score=150+3*c.attack+2*c.defense+max(0,after[i].hp-states[i].hp)+float(after[i].shield-states[i].shield)*.3
            else:
                score=value(after,i,t,policy)-before
                if plan.search:score+=policy.search*(1.5 if not states[i].spec or not states[i].route else 1)
                if plan.shuffle:score+=policy.cycle*sum(CARDS[n].rarity=='epic' for n in discard)
                score/=max(1,c.cost)**policy.cost_power
            options.append((score,name,after))
        if not options:break
        score,name,states=max(options,key=lambda x:(x[0],x[1]))
        if score<=0 and policy.mode!='baseline':break
        remaining.remove(name);queue.append(name);reasons.append(dict(card=name,score=round(score,3)))
        if any(s.hp<=0 for s in states):break
    return queue,reasons


def seed_stream(seed,identity,kind):
    return int.from_bytes(sha256(f'{seed}:{identity}:{kind}'.encode()).digest()[:8],'big')


@dataclass
class Fighter:
    deck_id: str
    pile: list
    rng: random.Random
    search_rng: random.Random
    pool: list = field(default_factory=list)
    discard: list = field(default_factory=list)
    removed: list = field(default_factory=list)
    plays: Counter = field(default_factory=Counter)
    activations: dict = field(default_factory=dict)
    wasted: int = 0
    granted: int = 0
    identity: str = ''
    phase_counts: Counter = field(default_factory=Counter)
    phase_cards: Counter = field(default_factory=Counter)
    decisions: int = 0
    lethal_predictions: int = 0
    phase_changes: list = field(default_factory=list)


def make_fighter(deck_id,seed,identity=None):
    deck=DECKS[deck_id]
    identity=identity or deck_id
    rng=random.Random(seed_stream(seed,identity,'deck'))
    p=Fighter(deck_id,[e['name'] for e in deck['entries']],rng,
              random.Random(seed_stream(seed,identity,'search')),identity=identity)
    rng.shuffle(p.pile)
    opening=[p.pile.pop(0) for _ in range(5)]
    keep=[n for n in opening if CARDS[n].ability]
    back=[n for n in opening if not CARDS[n].ability]
    if back:p.pile.extend(back);rng.shuffle(p.pile)
    p.pool=keep+[p.pile.pop(0) for _ in back]
    return p,State(deck['element'])


def draw_player(p,s,t):
    if s.element=='fire':gain_ember(s,1)
    credit=min(int(param('ash_resource_cap',2)),s.ash_credit) if s.route=='灰烬循环' else 0
    s.ash_credit=0
    s.energy=3+s.next_energy+int(s.contract)+credit
    count=5+s.next_draw-int(s.contract)+credit
    s.next_draw=0;s.next_energy=0;p.granted+=s.energy
    if t==0:return
    p.pool=[]
    for _ in range(count):
        if not p.pile:
            p.pile=p.discard;p.discard=[]
            if p.pile:p.rng.shuffle(p.pile);shuffled(s)
        if not p.pile:break
        p.pool.append(p.pile.pop(0))


def search(p,states,i,request,policy,t,log):
    mode,n,k=request
    def allowed(name):
        c=CARDS[name]
        if mode=='epic':return c.rarity in ('epic','legendary','specialization')
        if mode=='element':return c.element==states[i].element
        if mode=='shield':return name in SHIELDS or name in ('气旋护壁','风幕')
        if mode=='generic':return c.element=='generic'
        if mode=='enchantment':return c.element!='generic' and c.kind!='specialization'
        return True
    available=[n for n in p.pile if allowed(n)]
    candidates=p.pile[:n] if mode=='top' else p.search_rng.sample(available,min(n,len(available)))
    if not candidates:return
    probe=[replace(s) for s in states];probe[i].energy=3
    ranked=[]
    for name in candidates:
        q,r=choose_queue(probe,i,(name,),policy,t)
        ranked.append((r[0]['score'] if r else -100000,name))
    selected=[name for _,name in sorted(ranked,reverse=True)[:k]]
    if mode=='top':
        for name in candidates:
            if name not in selected:p.pile.remove(name);p.pile.append(name)
    for name in selected:p.pile.remove(name)
    p.pile[:0]=selected
    if log is not None:log.append(dict(t=t,phase='search',player=i,candidates=candidates,selected=selected))


def assert_state(states,players=None):
    for i,s in enumerate(states):
        assert s.hp<=1000 and s.shield>=0 and s.layers>=0 and s.poison>=0
        assert s.energy>=0 and 0<=s.ember<=5
        assert s.element!='fire' or s.spec or s.ember==0
        if players:
            p=players[i]
            assert Counter(p.pile+p.pool+p.discard+p.removed)==Counter(e['name'] for e in DECKS[p.deck_id]['entries'])


def simulate(deck_a,deck_b,seed,policy_a=BASELINE,policy_b=BASELINE,trace=False,validate=False,stream_swap=False):
    identities=(deck_a,deck_b) if deck_a!=deck_b else (deck_a+'@A',deck_b+'@B')
    streams=identities[::-1] if stream_swap else identities
    fa,sa=make_fighter(deck_a,seed,streams[0]);fb,sb=make_fighter(deck_b,seed,streams[1])
    fa.identity,fb.identity=identities
    players=[fa,fb];states=[sa,sb];policies=[policy_a,policy_b]
    log=[] if trace else None;t=0
    while True:
        if t%100==0:
            seq=[[],[]]
            for i in range(2):
                if states[i].element=='poison' and states[1-i].poison:
                    n=1+states[i].poison_repeat;states[i].poison_repeat=0
                    seq[i]=[poison_packet(states,i) for _ in range(n)]
            if any(seq):
                reactions=[]
                for k in range(max(map(len,seq))):apply_wave(states,[s[k] for s in seq if k<len(s)],t,log,reactions)
                finish_reactions(states,reactions,t,log)
                if check_death(states,t,log):break
        due_poison=[i for i,s in enumerate(states) if s.poison_due==t and s.poison>0]
        if due_poison:
            # Evaluate eligibility from common decay snapshot; apply disjoint layers.
            changes=[]
            for i in due_poison:
                owner=states[1-i]
                if owner.poison_guards>0:changes.append((i,1,True))
                elif states[i].poison==1 and owner.route=='蚀骨':changes.append((i,0,False))
                else:changes.append((i,-1,False))
            for i,delta,guard in changes:
                if guard:states[1-i].poison_guards-=1
                if delta:change_poison(states,i,delta,t)
                else:states[i].poison_due=INF
            execute_auto(states,t,log)
            if check_death(states,t,log):break
        if t%100==0:
            expire_draw_effects(states)
            for i,p in enumerate(players):draw_player(p,states[i],t)
            queues=[];reasons=[]
            for i,p in enumerate(players):
                q,r=choose_queue(states,i,tuple(p.pool),policies[i],t,tuple(p.discard));queues.append(q);reasons.append(r)
                for reason in r:
                    if 'phase' in reason:
                        phase=reason['phase'];p.phase_counts[phase]+=1;p.decisions+=1
                        p.phase_cards[phase+'|'+reason['card']]+=1
                        p.lethal_predictions+=int(reason.get('conditional_lethal',False))
                        if not p.phase_changes or p.phase_changes[-1][1]!=phase:p.phase_changes.append([t,phase])
            if log is not None:log.append(dict(t=t,phase='queues',pools=[p.pool[:] for p in players],queues=queues,reasons=reasons))
            for k in range(max(map(len,queues),default=0)):
                before=[replace(s) for s in states]
                plans=[]
                for i in range(2):
                    if k<len(queues[i]):
                        name=queues[i][k]
                        if CARDS[name].cost>states[i].energy:raise RuntimeError('Queue unexpectedly unaffordable')
                        plans.append(card_plan(before,i,name,t))
                states=resolve_cards(before,plans,t,log)
                for plan in plans:
                    i=plan.source;p=players[i];name=queues[i][k];c=CARDS[name]
                    p.pool.remove(name);p.plays[name]+=1
                    if c.ability:p.removed.append(name);p.activations[name]=t
                    else:p.discard.append(name)
                    if plan.shuffle:p.pile.extend(p.discard);p.discard=[];p.rng.shuffle(p.pile)
                    if plan.search:
                        # Enemy input remains this step's start; own card projection
                        # includes its ordered changes. No post-opponent inspection.
                        search(p,plan.local,i,plan.search,policies[i],t,log)
                if log is not None:log.append(dict(t=t,phase='card_end',step=k+1,states=[brief(s) for s in states]))
                if validate:assert_state(states,players)
                if check_death(states,t,log):break
            if any(s.hp<=0 for s in states):break
            for i,p in enumerate(players):
                p.pile.extend(p.pool);p.pool=[]
                s=states[i];n=len(queues[i])
                if s.badge and n>=3:s.attack+=2+n
                if s.guardian and n<=2:s.defense+=4-n
                p.wasted+=s.energy
            execute_auto(states,t,log)
            if check_death(states,t,log):break
            if t>=1500:
                amounts=[ceil(Q(s.hp)*(Q(5,100)+Q(t,10000))) for s in states]
                for i,n in enumerate(amounts):states[i].hp-=n
                execute_auto(states,t,log)
                if check_death(states,t,log):break
        due=[i for i,s in enumerate(states) if s.next_fire==t]
        if due:
            states=launch(states,due,t,log)
            if check_death(states,t,log):break
        if validate:assert_state(states,players)
        next_time=min((t//100+1)*100,*(s.next_fire for s in states),*(s.poison_due for s in states))
        if not next_time>t:raise RuntimeError(('Nonadvancing scheduler',t,[brief(s) for s in states]))
        t=next_time
        if t>10000:raise RuntimeError('Safety limit: no fabricated winner')
    dead=[s.hp<=0 for s in states]
    winner='draw' if all(dead) else players[dead.index(False)].identity
    result=dict(seed=seed,a=identities[0],b=identities[1],deck_a=deck_a,deck_b=deck_b,winner=winner,time=t,
                players={p.identity:dict(**brief(s),plays=dict(p.plays),activations=p.activations,
                                       wasted=p.wasted,granted=p.granted,phase_counts=dict(p.phase_counts),
                                       phase_cards=dict(p.phase_cards),
                                       phase_changes=p.phase_changes,lethal_predictions=p.lethal_predictions) for p,s in zip(players,states)})
    if trace:result['log']=log
    return result
