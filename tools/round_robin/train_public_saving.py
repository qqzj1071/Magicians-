"""Two combat-led cycles with public-broadcast and banking ablations."""
import argparse
import copy
import gzip
import hashlib
import json
import random
import shutil
import statistics as st
import time
from collections import defaultdict
from pathlib import Path
import public_saving_draft as N
import route_feasible_draft as R
T=N.T


def restore_combat(model,data):
    model.combat.stage=copy.deepcopy(data['stage']);model.combat.route=copy.deepcopy(data['route'])
    model.combat.updates=data['updates'];model.combat.accepts=data['accepts'];model.combat.experience.update(data['experience'])


def stage(label,n,model,cfg,learn,ns,raw,out):
    eps=[];start=time.time()
    for i in range(n):
        current=model if learn else copy.deepcopy(model)
        ep=T.S.simulate_episode(ns,i,current,learn,economy=N.CURRENT,namespace=out.name,config=cfg,total_rounds=14)
        ep.update(condition=label,config_hash=T.digest(cfg),information_profile='broadcast-v1' if isinstance(model,N.Learner) else 'legacy-owned-route-view')
        eps.append(ep);raw.write(json.dumps(ep,ensure_ascii=False)+'\n');raw.flush()
        print(f'{label} {i+1}/{n} D14={st.mean(p["route_dice"] for p in ep["players"]):.3f} {time.time()-start:.1f}s',flush=True)
    summary=T.summarize(eps);T.S.save(out/(label+'-summary.json'),summary)
    T.S.save(out/(label+'-final-decks.json'),[dict(episode=e['index'],players=e['players']) for e in eps])
    return eps,summary


def course_strength(new_eps,old_eps,controller,ns):
    rows=[]
    for new,old in zip(new_eps,old_eps):
        for r in (3,5,6,8,10,12,14):
            for pid in range(4):
                T.deck(old['rounds'][r-1]['players'][(pid+1)%4],'strength-enemy')
                for label,ep in [('new',new),('old',old)]:
                    T.deck(ep['rounds'][r-1]['players'][pid],'strength-own')
                    pa=controller.policy('strength-own','strength-enemy',r);pb=controller.policy('strength-enemy','strength-own',r)
                    for flip in range(2):
                        seed=T.S.seed(ns,new['index'],r,pid,flip)
                        a,b=('strength-own','strength-enemy') if not flip else ('strength-enemy','strength-own')
                        result=controller.play(a,b,seed,pa if not flip else pb,pb if not flip else pa)
                        x,y=result['players']['strength-own'],result['players']['strength-enemy']
                        margin=max(-1,min(1,(x['hp']-y['hp'])/1000))
                        rows.append(dict(episode=new['index'],round=r,pid=pid,flip=flip,seed=seed,model=label,
                                         score=T.score(result,'strength-own'),margin=margin,
                                         unused=x['wasted']/max(1,x['granted'])))
    result={k:st.mean(x['score']+.05*x['margin'] for x in rows if x['model']==k) for k in ['new','old']}
    return dict(games=len(rows),utility=result,score={k:st.mean(x['score'] for x in rows if x['model']==k) for k in ['new','old']},rows=rows)


def matrix(finals,models,out):
    rows=[];start=time.time();ids=list(T.S.TARGETS);initial=models['legacy'].combat
    for selected in finals['selected']:
        i=selected['index']
        for pid,p in enumerate(selected['players']):
            rid=T.J.ROUTE_ID.get(p['route'],p['target'])
            opponents=list(dict.fromkeys([ids[(i*4+pid+j*5)%15] for j in range(3)]+[rid]))
            for oid in opponents:
                T.S.C.DECKS['matrix-enemy']=copy.deepcopy(T.S.TARGETS[oid])
                for label,condition,ctrl in [('selected','selected',models['selected'].combat),
                    ('same_cards_old_combat','selected',models['legacy'].combat),
                    ('legacy','legacy',models['legacy'].combat),('no_saving','no_saving',models['selected'].combat),
                    ('initial_new','initial_new',models['initial_new'].combat),('full_reference',None,models['selected'].combat)]:
                    if condition:T.deck(finals[condition][i]['players'][pid],'matrix-own')
                    else:T.S.C.DECKS['matrix-own']=copy.deepcopy(T.S.TARGETS[rid])
                    pa=ctrl.policy('matrix-own','matrix-enemy',14);pb=initial.policy('matrix-enemy','matrix-own',14)
                    for flip in range(2):
                        seed=T.S.seed(out.name,'sealed-matrix',i,pid,oid,flip)
                        a,b=('matrix-own','matrix-enemy') if not flip else ('matrix-enemy','matrix-own')
                        result=ctrl.play(a,b,seed,pa if not flip else pb,pb if not flip else pa)
                        x=result['players']['matrix-own']
                        rows.append(dict(episode=i,pid=pid,opponent=oid,flip=flip,seed=seed,model=label,
                            score=T.score(result,'matrix-own'),unused=x['wasted']/max(1,x['granted']),
                            granted=x['granted'],duration=result['time'],plays=sum(x['plays'].values())))
        print(f'final matrix {i+1}/{len(finals["selected"])} {time.time()-start:.1f}s',flush=True)
    T.S.save(out/'final-matrix.json',dict(rows=rows,scope='three rotating standards plus selected-route standard per player, deduplicated; roster fixed across controls'))
    return {k:dict(n=sum(x['model']==k for x in rows),score=st.mean(x['score'] for x in rows if x['model']==k)) for k in sorted(set(x['model'] for x in rows))}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--train',type=int,default=8)
    ap.add_argument('--validate',type=int,default=4);ap.add_argument('--final',type=int,default=8);args=ap.parse_args()
    out=T.S.C.ROOT/'research'/args.run
    if out.exists():raise FileExistsError(out)
    out.mkdir();(out/'sources').mkdir();cfg=T.config();cfg['status']='growth_v5_public_saving_candidate'
    previous=T.S.C.ROOT/'research/shared-draft-v4-joint01/selected-model.json';saved=json.loads(previous.read_text(encoding='utf-8'))
    shutil.copyfile(previous,out/'previous-model.json')
    files=['train_public_saving.py','public_saving_draft.py','route_feasible_draft.py','train_joint_draft.py',
        'joint_draft_combat.py','dice_draft_agent.py','shared_draft_pool.py','shared_draft_combat.py',
        'simulate_shared_draft.py','draft_economy.py','construction_templates.py','engine.py','planner.py','cards.py','policies.json','learning_core.py','optimize_dice_draft.py']
    hashes={}
    for name in files:
        path=Path(__file__).parent/name;shutil.copyfile(path,out/'sources'/name);hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    T.S.save(out/'experiment.json',dict(args=vars(args),source_hashes=hashes,
        card_sha256=hashlib.sha256(T.S.C.CARD_LIBRARY_PATH.read_bytes()).hexdigest(),
        previous_model_sha256=hashlib.sha256(previous.read_bytes()).hexdigest(),
        phases=2,selection='real course battle utility, early-specialization guard; Dice not a selection objective',
        constraints='fixed uniform buckets, unchanged rarity/legendary/economy; no future offers; four remain active'))
    T.S.save(out/'reference-decks.json',list(T.S.TARGETS.values()));T.S.save(out/'selected-config.json',cfg)
    T.S.save(out/'phase1-previous-config.json',cfg)
    N.install();model=N.Learner();restore_combat(model,saved['combat']);initial=copy.deepcopy(model);history=[]
    T.S.IDS=list(T.S.IDS);random.Random('public-saving-balanced-preferences').shuffle(T.S.IDS)
    with gzip.open(out/'episodes.jsonl.gz','wt',encoding='utf-8') as raw:
        for phase in (1,2):
            old=copy.deepcopy(model);candidate=copy.deepcopy(model);offset=len(candidate.combat.log);changes=[]
            if phase==2:
                diag=history[-1]['after']
                if diag['spec_by5']<.85:
                    candidate.w['bank']*=.9;candidate.w['progress']*=1.1
                    changes.append('Validation specialization below85%: reduce banking pressure10%, increase progress10%.')
                else:
                    candidate.w['energy']*=1.1;candidate.w['draw_capacity']*=1.1
                    changes.append('Early specialization adequate: increase projected energy/draw weight10%; do not raise Dice.')
            T.S.save(out/f'phase{phase}-proposal.json',dict(changes=changes,weights=candidate.w))
            stage(f'p{phase}-train',args.train,candidate,cfg,True,f'train-{phase}',raw,out)
            before,before_s=stage(f'p{phase}-before',args.validate,old,cfg,False,f'validation-{phase}',raw,out)
            after,after_s=stage(f'p{phase}-after',args.validate,candidate,cfg,False,f'validation-{phase}',raw,out)
            strength=course_strength(after,before,copy.deepcopy(old.combat),f'{out.name}-strength-{phase}')
            combat=T.fixed_deck_bank(after,candidate.combat,copy.deepcopy(old.combat),f'{out.name}-combat-{phase}')
            T.S.save(out/f'phase{phase}-strength-validation.json',strength);T.S.save(out/f'phase{phase}-combat-validation.json',combat)
            draft_ok=strength['utility']['new']>=strength['utility']['old'] and after_s['spec_by5']>=max(.75,before_s['spec_by5']-.1)
            combat_ok=combat['new']>=combat['old'];model=copy.deepcopy(candidate)
            if not draft_ok:model.w=copy.deepcopy(old.w);model.updates=old.updates
            if not combat_ok:model.combat=copy.deepcopy(old.combat)
            T.S.save(out/f'phase{phase}-combat-training.json',candidate.combat.log[offset:])
            history.append(dict(phase=phase,before=before_s,after=after_s,changes=changes,draft_accepted=draft_ok,
                combat_accepted=combat_ok,strength={k:strength[k] for k in ['games','utility','score']},
                combat={k:combat[k] for k in ['games','new','old']},weights=model.w,combat_checkpoint=model.combat.dump()))
            T.S.save(out/'history.json',history)
            print(f'PHASE {phase} draft={draft_ok} combat={combat_ok} strength={strength["utility"]}',flush=True)
        T.S.save(out/'selected-model.json',dict(construction_profile='public-saving-v1',draft=model.w,combat=model.combat.dump(),draft_updates=model.updates))
        # Legacy and all new-agent controls share sealed construction seed names.
        legacy=T.JointLearner();legacy.w=saved['draft'];restore_combat(legacy,saved['combat'])
        R.install();legacy_eps,legacy_s=stage('final-legacy',args.final,legacy,cfg,False,'sealed-final',raw,out)
        N.install();eps,final_s=stage('final-selected',args.final,model,cfg,False,'sealed-final',raw,out)
        no_save=copy.deepcopy(model);no_save.saving=False
        no_eps,no_s=stage('final-no-saving',args.final,no_save,cfg,False,'sealed-final',raw,out)
        init_eps,init_s=stage('final-initial-new',args.final,initial,cfg,False,'sealed-final',raw,out)
    bank=T.fixed_deck_bank(eps,model.combat,copy.deepcopy(legacy.combat),out.name+'-sealed-bank')
    T.S.save(out/'final-controller-bank.json',bank)
    result=matrix(dict(selected=eps,legacy=legacy_eps,no_saving=no_eps,initial_new=init_eps),
                  dict(selected=model,legacy=legacy,initial_new=initial),out)
    T.S.save(out/'summary.json',dict(history=history,final=final_s,legacy=legacy_s,no_saving=no_s,initial_new=init_s,
                                   matrix=result,controllers={k:bank[k] for k in ['games','new','old']}))
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
