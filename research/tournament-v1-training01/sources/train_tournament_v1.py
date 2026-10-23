"""Ten fixed-rule cycles; four self-play branches, gated updates, sealed tests."""
import argparse
import copy
import gzip
import hashlib
import json
import multiprocessing
import shutil
import statistics as st
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import strategic_tournament_ai as I
import survival_tournament as Q
import train_survival as R
S=Q.S


def worker(job):
    label,ids,model,table,cfg,learn,namespace=job;I.install();eps=[]
    for i in ids:eps.append(Q.simulate(label,i,model if learn else copy.deepcopy(model),table,cfg,learn,namespace))
    return eps,model


def merge_cells(models,scope):
    dictionaries=[getattr(m.combat,scope) for m in models]
    return {cell:{k:st.mean(d.get(cell,{}).get(k,0) for d in dictionaries)
                  for k in set().union(*(d.get(cell,{}) for d in dictionaries))}
            for cell in set().union(*dictionaries)}


def batch(executor,label,n,model,table,cfg,learn,namespace,raw,out):
    start=time.time();origin=copy.deepcopy(model);models=[];eps=[]
    futures=[executor.submit(worker,(label,list(range(j,n,4)),copy.deepcopy(model),table,cfg,learn,namespace)) for j in range(min(4,n))]
    for f in futures:
        records,m=f.result();eps+=records;models.append(m)
    eps.sort(key=lambda e:e['index'])
    for ep in eps:raw.write(json.dumps(ep,ensure_ascii=False)+'\n')
    raw.flush()
    if learn:
        model.w={k:st.mean(m.w[k] for m in models) for k in model.w}
        model.updates+=sum(m.updates-origin.updates for m in models)
        model.terminal_updates+=sum(m.terminal_updates-origin.terminal_updates for m in models)
        for scope in ('stage','route','context','matchup'):setattr(model.combat,scope,merge_cells(models,scope))
        for field in ('updates','accepts','games'):
            setattr(model.combat,field,getattr(origin.combat,field)+sum(getattr(m.combat,field)-getattr(origin.combat,field) for m in models))
        for field in ('experience','support'):
            base=Counter(getattr(origin.combat,field));combined=Counter(base)
            for m in models:combined.update(Counter(getattr(m.combat,field))-base)
            setattr(model.combat,field,combined)
        model.combat.log=[]
        for m in models:model.combat.log.extend(m.combat.log)
    summary=Q.summarize(eps);S.save(out/(label+'-summary.json'),summary)
    print(f'{label}: {n} rooms {time.time()-start:.1f}s',flush=True)
    return eps,summary


def probe_worker(job):
    ep,new,old,namespace=job;I.install();rows=[]
    for row in ep['rounds']:
        if row['round'] not in (3,6,9,12,15,17):continue
        ps=row['players']
        if len(ps)<2:continue
        for p in ps:Q.deck(p,'probe-'+str(p['pid']))
        # Reuse an actual announced living matchup, never a hidden future deck.
        pair=next((b for b in row['battles'] if not b['ghost']),None)
        if not pair:continue
        a='probe-'+str(pair['a']);b='probe-'+str(pair['b']);r=row['round']
        for flip in (0,1):
            first,second=(a,b) if not flip else (b,a);seed=S.seed(namespace,ep['index'],r,flip)
            enemy=old.policy(b,a,r)
            for label,ctrl in [('new',new),('old',old)]:
                own=ctrl.policy(a,b,r)
                result=ctrl.play(first,second,seed,own if not flip else enemy,enemy if not flip else own)
                x=result['players'][a]
                rows.append(dict(room=ep['index'],round=r,flip=flip,condition=label,score=Q.T.score(result,a),
                    plays=sum(x['plays'].values()),waste=x['wasted']/max(1,x['granted'])))
    return rows


def probe(executor,eps,new,old,namespace,out,label):
    rows=[]
    for f in [executor.submit(probe_worker,(e,copy.deepcopy(new.combat),copy.deepcopy(old.combat),namespace)) for e in eps]:rows+=f.result()
    means={k:st.mean(x['score'] for x in rows if x['condition']==k) for k in ('new','old')}
    gains={stage:st.mean(x['score']*(1 if x['condition']=='new' else -1) for x in rows if I.stage(x['round'])==stage)*2
           for stage in {I.stage(x['round']) for x in rows}}
    S.save(out/(label+'.json'),dict(rows=rows,means=means,stage_gains=gains))
    return dict(means=means,stage_gains=gains,games=len(rows))


def mixed_worker(job):
    index,new,old,table,cfg,namespace=job;I.install()
    k=(index%3)+1;start=(index//3)%4;new_ids={(start+j)%4 for j in range(k)}
    actors={pid:copy.deepcopy(new if pid in new_ids else old) for pid in range(4)}
    ep=Q.simulate('mixed-final',index,copy.deepcopy(old),table,cfg,False,namespace,seat_models=actors)
    ep['new_seats']=sorted(new_ids);ep['expected_new_champion_share']=k/4
    ep['new_champion_share']=sum(p['pid'] in new_ids for p in ep['champions'])/len(ep['champions'])
    return ep


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',default='tournament-v1-training01')
    ap.add_argument('--cycles',type=int,default=10);ap.add_argument('--train',type=int,default=8)
    ap.add_argument('--validate',type=int,default=4);ap.add_argument('--final',type=int,default=32);args=ap.parse_args()
    out=S.C.ROOT/'research'/args.run
    if out.exists():raise FileExistsError(out)
    (out/'sources').mkdir(parents=True);release=S.C.ROOT/'releases/deckbuilding-v1.0'
    manifest=json.loads((release/'manifest.json').read_text(encoding='utf-8'))
    for name,h in manifest['sha256'].items():assert hashlib.sha256((release/name).read_bytes()).hexdigest()==h
    cfg=json.loads((release/'probabilities.json').read_text(encoding='utf-8'))
    table=json.loads((release/'damage.json').read_text(encoding='utf-8'))['table']
    saved=json.loads((release/'initial-ai.json').read_text(encoding='utf-8'));I.install()
    model=I.Learner(saved);initial=copy.deepcopy(model);history=[]
    hashes={}
    for p in Path(__file__).parent.iterdir():
        if p.suffix=='.py' or p.name=='policies.json':shutil.copyfile(p,out/'sources'/p.name);hashes[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
    S.save(out/'experiment.json',dict(args=vars(args),source_hashes=hashes,card_sha256=hashlib.sha256(S.C.CARD_LIBRARY_PATH.read_bytes()).hexdigest(),
        release_manifest_sha256=hashlib.sha256((release/'manifest.json').read_bytes()).hexdigest(),
        rules='frozen deckbuilding-v1.0',training_updates='ten bounded self-play cycles; independent per-cycle validation; sealed final never tunes',
        gate=dict(draft_external_score_gain=.01,max_spec_drop=.05,combat_paired_gain=.01,max_stage_drop=.05),
        terminal_rule='last simultaneous elimination remains co-champions'))
    S.save(out/'config.json',cfg);S.save(out/'selected-table.json',dict(table=table));S.save(out/'initial-model.json',I.dump(model))
    with ProcessPoolExecutor(max_workers=4) as executor,gzip.open(out/'episodes.jsonl.gz','wt',encoding='utf-8') as raw:
        for phase in range(1,args.cycles+1):
            previous=copy.deepcopy(model);candidate=copy.deepcopy(model);candidate.enable_training()
            trained,ts=batch(executor,f'p{phase}-train',args.train,candidate,table,cfg,True,out.name+f'-learn-{phase}',raw,out)
            S.save(out/f'p{phase}-learning.json',dict(combat=candidate.combat.log,terminal_updates=candidate.terminal_updates))
            before,bs=batch(executor,f'p{phase}-before',args.validate,previous,table,cfg,False,out.name+f'-validation-{phase}',raw,out)
            after,ass=batch(executor,f'p{phase}-after',args.validate,candidate,table,cfg,False,out.name+f'-validation-{phase}',raw,out)
            bb=R.benchmark(executor,before,previous,previous,out.name+f'-matrix-{phase}',out,f'p{phase}-before-matrix')
            ab=R.benchmark(executor,after,candidate,previous,out.name+f'-matrix-{phase}',out,f'p{phase}-after-matrix')
            fixed=probe(executor,before,candidate,previous,out.name+f'-probe-{phase}',out,f'p{phase}-combat-probe')
            draft_ok=ab['old_combat']-bb['old_combat']>=.01 and ass['spec_by5']>=bs['spec_by5']-.05
            combat_ok=fixed['means']['new']-fixed['means']['old']>=.01 and min(fixed['stage_gains'].values())>=-.05
            model=copy.deepcopy(candidate)
            if not draft_ok:
                model.w=copy.deepcopy(previous.w);model.prior=copy.deepcopy(previous.prior);model.updates=previous.updates
                model.draft_strategy_enabled=previous.draft_strategy_enabled
            if not combat_ok:model.combat=copy.deepcopy(previous.combat)
            candidate.combat.log=[];model.combat.log=[]
            entry=dict(phase=phase,training=ts,before=bs,after=ass,benchmark_before=bb,benchmark_after=ab,
                fixed_probe=fixed,draft_accepted=draft_ok,combat_accepted=combat_ok,weights=model.w,
                draft_reason='external_champion_gain_and_specialization_guard' if draft_ok else 'insufficient_external_gain_or_specialization_regression',
                combat_reason='paired_actual_deck_gain_with_stage_guard' if combat_ok else 'insufficient_or_stage_specific_gain')
            history.append(entry);S.save(out/'training-history.json',history);S.save(out/f'phase{phase}-model.json',I.dump(model))
            print(f'PHASE {phase}/{args.cycles} draft={draft_ok} combat={combat_ok} external={ab["old_combat"]-bb["old_combat"]:+.4f} fixed={fixed["means"]["new"]-fixed["means"]["old"]:+.4f}',flush=True)
        S.save(out/'selected-model.json',I.dump(model))
        # Selection is sealed before any final result is generated.
        S.save(out/'release-selection.json',dict(chosen_folder='.',basis='training and validation only',
            model_sha256=hashlib.sha256((out/'selected-model.json').read_bytes()).hexdigest(),
            table_sha256=hashlib.sha256((out/'selected-table.json').read_bytes()).hexdigest()))
        baseline,bs=batch(executor,'baseline-final',args.final,initial,table,cfg,False,out.name+'-sealed',raw,out)
        final,fs=batch(executor,'sealed-final',args.final,model,table,cfg,False,out.name+'-sealed',raw,out)
        # Paired construction randomness is covered in phase validation; these
        # disjoint final labels supply separate tournament populations.
        matrix=R.benchmark(executor,final,model,initial,out.name+'-sealed-matrix',out,'champion-matrix',True)
        baseline_matrix=R.benchmark(executor,baseline,initial,initial,out.name+'-sealed-baseline-matrix',out,'baseline-matrix',True)
        fixed=probe(executor,baseline,model,initial,out.name+'-sealed-probe',out,'final-combat-probe')
        mixed=[]
        for f in [executor.submit(mixed_worker,(i,model,initial,table,cfg,out.name+'-sealed-mixed')) for i in range(24)]:
            e=f.result();mixed.append(e);raw.write(json.dumps(e,ensure_ascii=False)+'\n')
        raw.flush();S.save(out/'mixed-summary.json',dict(rooms=24,mean_new_champion_share=st.mean(e['new_champion_share'] for e in mixed),
            mean_expected_share=st.mean(e['expected_new_champion_share'] for e in mixed),
            rows=[dict(index=e['index'],new_seats=e['new_seats'],share=e['new_champion_share'],expected=e['expected_new_champion_share']) for e in mixed]))
        S.save(out/'summary.json',dict(final=fs,baseline=bs,matrix=matrix,baseline_matrix=baseline_matrix,fixed_probe=fixed,cycles=args.cycles))
        print('FINAL '+json.dumps(fs),flush=True)


if __name__=='__main__':multiprocessing.freeze_support();main()
