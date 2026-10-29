"""Three survival-learning phases; cheap trace screening + real validation.

Trace screening is explicitly approximate (fixed fights). Only actual dynamic
tournaments provide final duration/survival claims. Independent sealed seeds.
"""
import argparse
import copy
import gzip
import hashlib
import json
import math
import multiprocessing
import random
import shutil
import statistics as st
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import survival_tournament as Q
A=Q.A;T=Q.T;S=Q.S


def make_table(base,n,late,nlate,m17=65):
    table={}
    for r in range(1,21):
        if r<=3:v=(min(base,1),min(n,.3))
        elif r<=6:v=(min(base,2),min(n,.5))
        elif r<=12:v=(base,n)
        elif r<=15:v=(late,nlate)
        elif r==16:v=(max(late,25),max(nlate,1.5))
        elif r==17:v=(max(late,35,m17),max(nlate,2.))
        else:v=(max(late,m17,85)+10*(r-18),round(max(nlate,2.5)+.1*(r-18),1))
        table[str(r)]=list(v)
    Q.validate_table(table);return table


def initial_model():
    path=S.C.ROOT/'research/shared-draft-v5-saving01/previous-model.json'
    return A.Learner(json.loads(path.read_text(encoding='utf-8')))


def worker(job):
    label,indices,model,table,cfg,learn,namespace=job;A.install();eps=[]
    for i in indices:eps.append(Q.simulate(label,i,model if learn else copy.deepcopy(model),table,cfg,learn,namespace))
    return eps,model


def batch(executor,label,n,model,table,cfg,learn,namespace,raw,out):
    start=time.time();jobs=[]
    for j in range(min(4,n)):
        ids=list(range(j,n,4));jobs.append((label,ids,copy.deepcopy(model),table,cfg,learn,namespace))
    futures=[executor.submit(worker,j) for j in jobs];eps=[];models=[]
    for future in futures:
        episodes,trained=future.result();eps+=episodes;models.append(trained)
        print(f'{label}: {len(eps)}/{n} rooms {time.time()-start:.1f}s',flush=True)
    eps.sort(key=lambda e:e['index'])
    for ep in eps:raw.write(json.dumps(ep,ensure_ascii=False)+'\n')
    raw.flush();summary=Q.summarize(eps);S.save(out/(label+'-summary.json'),summary)
    if learn:
        # Four independent online learners, averaged once at the phase boundary.
        for k in model.w:model.w[k]=st.mean(m.w[k] for m in models)
        model.updates+=sum(m.updates-model.updates for m in models)
        for scope in ('stage','route'):
            origin=getattr(model.combat,scope)
            for cell in origin:
                keys=set().union(*(getattr(m.combat,scope)[cell] for m in models))
                origin[cell]={k:st.mean(getattr(m.combat,scope)[cell].get(k,0) for m in models) for k in keys}
        old_updates=model.combat.updates;old_accepts=model.combat.accepts
        model.combat.updates+=sum(m.combat.updates-old_updates for m in models)
        model.combat.accepts+=sum(m.combat.accepts-old_accepts for m in models)
        prior_experience=Counter(model.combat.experience)
        merged=Counter(prior_experience)
        for m in models:merged.update(Counter(m.combat.experience)-prior_experience)
        model.combat.experience=merged
        old_log=len(model.combat.log)
        for m in models:model.combat.log.extend(m.combat.log[old_log:])
    return eps,summary


def traces(eps):
    result=[]
    for ep in eps:
        rounds=[]
        for row in ep['rounds']:
            battles=[]
            for b in row['battles']:
                if b['ghost']:continue
                a,c=b['a'],b['b']
                res=b['result'];winner=res['winner'];win=-1 if winner=='draw' else a if winner=='survivor-'+str(a) else c
                x=max(1,max(v['hp'] for v in res['players'].values()))
                battles.append((a,c,win,math.log(x)))
            rounds.append(battles)
        result.append(rounds)
    return result


def replay(trace,table):
    strong=alive=ends=end_observed=0;n=len(trace)
    for rounds in trace:
        hp=[100]*4;finished=False;h12=h15=None;saw18=False
        for r,battles in enumerate(rounds,1):
            if not finished:
                m,k=Q.parameters(table,r)
                for a,b,w,loghp in battles:
                    # Fixed schedule approximation: when one is eliminated,
                    # surviving side faces its recorded frozen counterpart.
                    if hp[a]<=0 and hp[b]<=0:continue
                    if w<0:
                        if hp[a]>0:hp[a]-=m
                        if hp[b]>0:hp[b]-=m
                    elif w==a:
                        if hp[b]>0:hp[b]-=m+math.floor(loghp*k)
                    elif hp[a]>0:hp[a]-=m+math.floor(loghp*k)
                finished=sum(v>0 for v in hp)<=1
            if r==12:h12=sum(v>40 for v in hp)/4
            if r==15:h15=sum(v>0 for v in hp)/4
            if r==18:ends+=finished;end_observed+=1;saw18=True
        strong+=h12 if h12 is not None else sum(v>40 for v in hp)/4
        alive+=h15 if h15 is not None else sum(v>0 for v in hp)/4
        if not saw18 and finished:ends+=1;end_observed+=1
    return dict(strong12=strong/n,alive15=alive/n,ended18=ends/max(1,end_observed),
                end_observed=end_observed,end_censored=n-end_observed)


def calibrate(eps,previous=None):
    trace=traces(eps);early=[]
    for base in range(2,8):
        for z in range(3,17):
            n=z/10;table=make_table(base,n,max(base,15),max(n,1.5));stats=replay(trace,table)
            early.append((abs(stats['strong12']-.7),base,n,stats))
    _,base,n,_=min(early,key=lambda x:x[:3]);choices=[]
    for late in range(max(base,6),40):
        for nk in [max(n,.8),max(n,1.2),max(n,1.6),max(n,2.)]:
            for m17 in (40,55,70,85,100):
                table=make_table(base,n,late,nk,m17);stats=replay(trace,table)
                loss=abs(stats['strong12']-.7)*4+abs(stats['alive15']-.5)*4+max(0,.985-stats['ended18'])*20
                choices.append((loss,m17,late,nk,table,stats))
    best=min(choices,key=lambda x:x[:4])
    return best[4],dict(method='fixed-fight trace screening only; must validate actual dynamic tournaments',
        replay=best[5],objective=best[0],rooms=len(eps))


def benchmark_worker(job):
    ep,controller,old,namespace,all_routes=job;A.install();rows=[]
    for p in ep['champions']:
        did='champion';Q.deck(p,did);rid=T.J.ROUTE_ID.get(p['route'],p['target'])
        ids=list(S.TARGETS) if all_routes else list(dict.fromkeys([list(S.TARGETS)[(ep['index']*3+j*5)%15] for j in range(3)]+[rid]))
        for oid in ids:
            S.C.DECKS['standard']=copy.deepcopy(S.TARGETS[oid]);pb=old.policy('standard',did,ep['end_round'])
            for flip in range(2):
                seed=S.seed(namespace,ep['index'],p['pid'],oid,flip)
                a,b=(did,'standard') if not flip else ('standard',did)
                for condition,ctrl,full in [('candidate',controller,False),('old_combat',old,False),('full_reference',controller,True)]:
                    if full:S.C.DECKS[did]=copy.deepcopy(S.TARGETS[rid])
                    else:Q.deck(p,did)
                    pa=ctrl.policy(did,'standard',ep['end_round'])
                    result=ctrl.play(a,b,seed,pa if not flip else pb,pb if not flip else pa)
                    state=result['players'][did]
                    rows.append(dict(room=ep['index'],pid=p['pid'],round=ep['end_round'],opponent=oid,flip=flip,seed=seed,
                        condition=condition,score=T.score(result,did),hp=state['hp'],plays=sum(state['plays'].values()),
                        granted=state['granted'],wasted=state['wasted'],duration=result['time']))
    return rows


def benchmark(executor,eps,model,old,namespace,out,label,all_routes=False):
    rows=[];start=time.time()
    futures=[executor.submit(benchmark_worker,(ep,copy.deepcopy(model.combat),copy.deepcopy(old.combat),namespace,all_routes)) for ep in eps]
    for i,f in enumerate(futures):
        rows+=f.result()
        if (i+1)%8==0:print(f'{label} {i+1}/{len(eps)} {time.time()-start:.1f}s',flush=True)
    means={key:st.mean(x['score'] for x in rows if x['condition']==key) for key in ('candidate','old_combat','full_reference')}
    S.save(out/(label+'.json'),dict(rows=rows,means=means,games=len(rows),all_routes=all_routes));return means


def dump(model):return dict(construction_profile='survival-v6',draft=model.w,prior=model.prior,updates=model.updates,combat=model.combat.dump())


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--probe',type=int,default=24)
    ap.add_argument('--train',type=int,default=12);ap.add_argument('--validate',type=int,default=12)
    ap.add_argument('--final',type=int,default=200);args=ap.parse_args();out=S.C.ROOT/'research'/args.run
    if out.exists():raise FileExistsError(out)
    out.mkdir();(out/'sources').mkdir();cfg=T.config();cfg['status']='survival-v6-candidate';A.install();model=initial_model();initial=copy.deepcopy(model)
    source_names=['train_survival.py','survival_tournament.py','tournament_draft.py','public_baseline_inference.py',
        'route_feasible_draft.py','train_joint_draft.py','joint_draft_combat.py','dice_draft_agent.py','simulate_shared_draft.py',
        'shared_draft_pool.py','shared_draft_combat.py','draft_economy.py','construction_templates.py','engine.py','planner.py','cards.py','policies.json']
    hashes={}
    for name in source_names:
        src=Path(__file__).parent/name;shutil.copyfile(src,out/'sources'/name);hashes[name]=hashlib.sha256(src.read_bytes()).hexdigest()
    S.save(out/'experiment.json',dict(args=vars(args),source_hashes=hashes,card_sha256=hashlib.sha256(S.C.CARD_LIBRARY_PATH.read_bytes()).hexdigest(),
        targets=dict(strong12=.7,alive15=.5,ended18=.98),statistical_unit='four-player room; survivor HP carried after terminal round',
        training='three phases, four independent online branches averaged once per phase; no extra learning on final seeds',
        champion_rule='simultaneous final elimination gives co-champions',ghost='eliminated snapshot, no shop/HP/pool ownership',
        prior_checkpoint='shared-draft-v5-saving01/previous-model.json'))
    S.save(out/'config.json',cfg);S.save(out/'initial-model.json',dump(model));history=[]
    # Cheap full-length calibration supply: no elimination before R19, but
    # ordinary cards/AI/battles remain real. This is NOT final tournament evidence.
    gentle={str(r):[1,0.] if r<=18 else [100+10*(r-19),0.] for r in range(1,21)}
    with ProcessPoolExecutor(max_workers=4) as executor,gzip.open(out/'episodes.jsonl.gz','wt',encoding='utf-8') as raw:
        probe,_=batch(executor,'calibration-probe',args.probe,model,gentle,cfg,False,out.name,raw,out)
        library=probe;table,screen=calibrate(library);S.save(out/'phase1-table.json',dict(table=table,screen=screen))
        for phase in (1,2,3):
            previous=copy.deepcopy(model);candidate=copy.deepcopy(model)
            # Only prior validation influences these proposals; no final seeds.
            changes=[]
            if history:
                diag=history[-1]['after']
                if diag['spec_by5']<.85:
                    candidate.w['specialization_jump']*=1.1;candidate.w['bank']*=.85
                    changes.append('specialization below85%: threshold weight+10%, banking-15%')
                else:
                    candidate.w['next_counter']*=1.1
                    changes.append('early specialization adequate: public-opponent counter weight+10%')
            trained,ts=batch(executor,f'p{phase}-train',args.train,candidate,table,cfg,True,out.name,raw,out)
            before,bs=batch(executor,f'p{phase}-before',args.validate,previous,table,cfg,False,out.name+'-validation-'+str(phase),raw,out)
            after,ass=batch(executor,f'p{phase}-after',args.validate,candidate,table,cfg,False,out.name+'-validation-'+str(phase),raw,out)
            bbench=benchmark(executor,before,previous,previous,out.name+'-validation-matrix-'+str(phase),out,f'p{phase}-before-matrix')
            abench=benchmark(executor,after,candidate,previous,out.name+'-validation-matrix-'+str(phase),out,f'p{phase}-after-matrix')
            draft_ok=abench['old_combat']>=bbench['old_combat'] and ass['spec_by5']>=max(.75,bs['spec_by5']-.1)
            combat_ok=abench['candidate']>=abench['old_combat']
            model=copy.deepcopy(candidate)
            if not draft_ok:model.w=copy.deepcopy(previous.w);model.updates=previous.updates
            if not combat_ok:model.combat=copy.deepcopy(previous.combat)
            entry=dict(phase=phase,table=table,screen=screen,changes=changes,training=ts,before=bs,after=ass,
                benchmark_before=bbench,benchmark_after=abench,draft_accepted=draft_ok,combat_accepted=combat_ok,weights=model.w)
            history.append(entry);S.save(out/'history.json',history);S.save(out/f'phase{phase}-model.json',dump(model))
            print(f'PHASE {phase} draft={draft_ok} combat={combat_ok} before={bs} after={ass}',flush=True)
            library+=trained+after
            if phase<3:
                table,screen=calibrate(library);S.save(out/f'phase{phase+1}-table.json',dict(table=table,screen=screen))
        # Third phase's independently simulated duration evidence diagnoses the
        # proposed table. A final screening pass is calibration, never final-test tuning.
        table,screen=calibrate(library);S.save(out/'selected-table.json',dict(table=table,screen=screen))
        S.save(out/'selected-model.json',dump(model))
        final,fs=batch(executor,'sealed-final',args.final,model,table,cfg,False,out.name+'-sealed',raw,out)
        matrix=benchmark(executor,final,model,initial,out.name+'-sealed-champion',out,'champion-matrix',True)
        S.save(out/'summary.json',dict(history=history,final=fs,matrix=matrix,table=table,screen=screen))
        print('FINAL '+json.dumps(fs),flush=True)


if __name__=='__main__':
    multiprocessing.freeze_support();main()
