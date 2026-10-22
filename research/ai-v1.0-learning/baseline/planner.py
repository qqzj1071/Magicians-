"""Three-stage, public-information greedy player and conditional lethal forecast."""
from dataclasses import dataclass,replace,fields
from functools import lru_cache
import engine as E
from cards import CARDS,DECKS

PLANNER_VERSION='1.0'


@dataclass(frozen=True)
class Policy(E.Policy):
    mode: str = 'staged'
    own: str = ''
    opponent: str = ''
    core_priority: float = 280
    startup_resource: float = 55
    operation_layer: float = 24
    finish_ratio: float = 1.25
    finish_burst: float = 1.3
    panic: float = 1.3
    penetration_value: float = 1
    tempo_value: float = 1
    sustain_value: float = 1
    shield_engine: float = 1
    epic_cycle: float = 18
    budget_fit: float = 8
    basic_order: int = 0


RANGES=dict(core_priority=[40,80,140,280,450,650],startup_resource=[15,40,75,120],
    operation_layer=[8,24,45,70],finish_ratio=[.85,1.1,1.4,1.8],
    finish_burst=[.6,1,1.5,2.2],panic=[.8,1.3,2,3],
    penetration_value=[.4,1,2,3],tempo_value=[.5,1,1.8,2.8],
    sustain_value=[.4,1,1.8,2.5],shield_engine=[.4,1,1.8,2.5],
    epic_cycle=[0,18,40,70],budget_fit=[0,8,20,40],
    horizon=[180,300,450,650],damage=[.6,1,1.5,2],health=[.6,1,1.5,2],
    shield=[.3,.8,1.5,2.5],defense=[.4,1,2,3],draw=[4,12,25,40],
    energy=[12,24,40,65],search=[4,18,35,60],cost_power=[.4,.8,1,1.4],counterplay_value=[.5,1,2,3])


def initial(own,opponent):
    """Documented route priors, subsequently evaluated and mutated in training."""
    element=DECKS[own]['element'];other=DECKS[opponent]['element']
    p=Policy(own=own,opponent=opponent)
    if element=='fire':p=replace(p,finish_burst=1.5,damage=1.3,operation_layer=35)
    if element=='water':p=replace(p,sustain_value=1.5,health=1.3)
    if element=='earth':p=replace(p,shield_engine=1.8,shield=1.3,defense=1.5)
    if element=='wind':p=replace(p,tempo_value=1.8,penetration_value=1.5)
    if element=='poison':p=replace(p,operation_layer=35,horizon=450,sustain_value=1.3)
    if other=='earth':p=replace(p,penetration_value=p.penetration_value*1.5,panic=1.8)
    if other=='fire':p=replace(p,panic=1.8,core_priority=240)
    return p


def phase(states,i,t,p):
    s,e=states[i],states[1-i]
    # This is a trigger for exact projection, not a declaration of lethal.
    threat=E.estimate(states,i,t,100)
    effective=max(1,e.hp)+float(e.shield)*(1-float(E.shield_pen(s)))
    if threat*p.finish_ratio>=effective:return 'finish'
    if not s.spec or not s.route:return 'startup'
    return 'operation'


STATE_FIELDS=tuple(f.name for f in fields(E.State))


def state_key(states):return tuple(tuple(getattr(s,k) for k in STATE_FIELDS) for s in states)


@lru_cache(maxsize=4096)
def _forecast(key,t,window):
    st=[E.State(**dict(zip(STATE_FIELDS,values))) for values in key]
    end=t+window;now=t;count=0;crossed=False
    while count<24:
        next_draw=(now//100+1)*100
        event=min(*(s.next_fire for s in st),*(s.poison_due for s in st),next_draw)
        if event>end:break
        if event<now:raise RuntimeError('Forecast scheduler moved backward')
        now=event;count+=1
        if now%100==0 and now!=t:
            crossed=True
            seq=[[],[]]
            for j in range(2):
                if st[j].element=='poison' and st[1-j].poison:
                    n=1+st[j].poison_repeat;st[j].poison_repeat=0
                    seq[j]=[E.poison_packet(st,j) for _ in range(n)]
            reactions=[]
            for k in range(max(map(len,seq),default=0)):
                E.apply_wave(st,[z[k] for z in seq if k<len(z)],now,reactions=reactions)
            E.finish_reactions(st,reactions,now)
            if E.check_death(st,now):break
        due=[j for j,s in enumerate(st) if s.poison>0 and s.poison_due==now]
        changes=[]
        for j in due:
            owner=st[1-j]
            if owner.poison_guards>0:changes.append((j,1,True))
            elif st[j].poison==1 and owner.route=='蚀骨':changes.append((j,0,False))
            else:changes.append((j,-1,False))
        for j,n,guard in changes:
            if guard:st[1-j].poison_guards-=1
            if n:E.change_poison(st,j,n,now)
            else:st[j].poison_due=E.INF
        E.execute_auto(st,now,None)
        if E.check_death(st,now):break
        if now%100==0 and now!=t:
            E.expire_draw_effects(st)
            for s in st:
                if s.element=='fire':E.gain_ember(s,1)
            if now>=1500:
                amounts=[E.ceil(E.Q(s.hp)*(E.Q(5,100)+E.Q(now,10000))) for s in st]
                for j,n in enumerate(amounts):st[j].hp-=n
                E.execute_auto(st,now,None)
                if E.check_death(st,now):break
        due=[j for j,s in enumerate(st) if s.next_fire==now]
        if due:
            st=E.launch(st,due,now)
            if E.check_death(st,now):break
        # Stop after one current own/opponent firing cycle, or at the fixed cap.
        if now==end:break
    return tuple(s.hp for s in st),tuple(float(s.shield) for s in st),now,crossed,count<24


def forecast(states,t,window=120):
    """Exact arithmetic/events with NO additional cards; always conditional on that assumption."""
    if any(s.hp<=0 for s in states):
        states=[replace(s) for s in states]
        terminal=E.check_death(states,t)
        if terminal:
            return tuple(s.hp for s in states),tuple(float(s.shield) for s in states),t,False,True
    return _forecast(state_key(states),t,window)


def stage_policy(st,i,t,p,stage):
    s,e=st[i],st[1-i]
    risk=E.estimate(st,1-i,t,100)/max(100,s.hp+float(s.shield)*(1-float(E.shield_pen(e))))
    if stage=='startup':
        q=replace(p,spec=p.spec+p.core_priority,route=p.route+p.core_priority,
                  draw=p.draw*1.4,search=p.search*1.5)
    elif stage=='operation':q=replace(p,layer=p.layer+p.operation_layer)
    else:q=replace(p,damage=p.damage*p.finish_burst,horizon=min(p.horizon,200))
    if risk>.6:q=replace(q,health=q.health*p.panic,shield=q.shield*p.panic)
    return q,risk


def choose(snapshot,i,pool,p,t,discard=()):
    if p.basic_order:
        queue,reasons=E.choose_queue(snapshot,i,pool,E.BASELINE,t,discard)
        projected=[replace(s) for s in snapshot]
        for name,reason in zip(queue,reasons):
            reason['phase']=phase(projected,i,t,p)
            reason['conditional_lethal']=False
            projected=E.resolve_cards(projected,[E.card_plan(projected,i,name,t)],t)
            E.check_death(projected,t)
        return queue,reasons
    states=[replace(s) for s in snapshot];remaining=list(pool);queue=[];reasons=[]
    while remaining:
        stage=phase(states,i,t,p);q,risk=stage_policy(states,i,t,p,stage)
        before=E.value(states,i,t,q);s,e=states[i],states[1-i];options=[]
        for name in remaining:
            c=CARDS[name]
            if c.cost>s.energy:continue
            plan=E.card_plan(states,i,name,t);after=E.resolve_cards(states,[plan],t)
            # Real play checks revival/death immediately after this complete card transaction.
            E.check_death(after,t)
            z=after[i];score=E.value(after,i,t,q)-before
            if plan.search:score+=q.search*(1.7 if stage=='startup' else 1)
            if stage=='startup' and not(c.kind in ('specialization','route_legendary')):
                if plan.search or plan.shuffle or z.next_draw>s.next_draw:
                    score+=p.startup_resource
            if stage=='operation' and c.element==s.element and name not in s.seen:
                score+=p.operation_layer
            if plan.shuffle:
                score+=p.epic_cycle*sum(CARDS[n].rarity=='epic' for n in discard)*(1.5 if stage=='finish' else 1)
            # Separate penetration from raw damage: shield penetration bypasses earth reactions.
            score+=(z.def_pen-s.def_pen)*p.penetration_value*(1+E.stats(states,1-i)[1]/40)
            score+=float(E.gap(s)-E.gap(z))*p.tempo_value
            score+=max(0,z.hp-s.hp)*(p.sustain_value-1)
            if s.element=='earth':score+=float(z.shield-s.shield)*(p.shield_engine-1)*.3
            available=z.energy
            fits=sum(1 for n in remaining if n!=name and CARDS[n].cost<=available)
            score+=p.budget_fit*min(2,fits)
            score/=max(1,c.cost)**q.cost_power
            options.append([score,name,after,False,False])
        if not options:break
        options.sort(key=lambda z:(z[0],z[1]),reverse=True)
        # Exact forward check is reserved for lethal, imminent death and shield retaliation.
        tactical=stage=='finish' or risk>.7 or (e.element=='earth' and e.spec and e.shield>0) or bool(s.negative_guard or s.pre_shield or s.shield_leech)
        if tactical:
            base_hp,_,_,_,_=forecast(states,t)
            for option in options[:2]:
                hp,_,_,crossed,complete=forecast(option[2],t)
                safe_kill=complete and hp[1-i]<=0 and hp[i]>0
                dead=complete and hp[i]<=0
                option[3]=safe_kill;option[4]=crossed
                option[0]+=((base_hp[1-i]-hp[1-i])*q.damage+(hp[i]-base_hp[i])*q.health)*.5
                if safe_kill:option[0]+=20000
                if dead and hp[1-i]>0:option[0]-=20000
        score,name,after,lethal,crossed=max(options,key=lambda z:(z[0],z[1]))
        if score<=0:break
        # Only the winning card is committed; reevaluate marginal values and stages afterward.
        states=after;remaining.remove(name);queue.append(name)
        reasons.append(dict(card=name,score=round(score,3),phase=stage,
            conditional_lethal=lethal,forecast_crosses_draw=crossed,emergency=risk>.7))
        if any(s.hp<=0 for s in states):break
    return queue,reasons
