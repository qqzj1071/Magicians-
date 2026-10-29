"""Three uniform-pool construction/combat learning cycles, sealed evaluation."""
import argparse
import copy
import gzip
import hashlib
import json
import random
import shutil
import statistics as st
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import simulate_shared_draft as S
import dice_draft_agent as A
import joint_draft_combat as J
from shared_draft_pool import assert_uniform_counts
from draft_economy import CURRENT
from optimize_dice_draft import summarize,digest

OLD_VECTOR=A.vector


def vector(p,ns,did=None):
    v=OLD_VECTOR(p,ns,did);target=S.TARGET_NAMES[did or A.reference(p,ns)]
    for rarity in ('epic','rare'):
        cards={n for n in target if S.C.CARDS[n].rarity==rarity and S.C.CARDS[n].element!='generic'}
        v['route_'+rarity]=len(cards&set(ns))/max(1,len(cards))
    return v


class JointLearner(A.Learner):
    def __init__(self):
        super().__init__();self.combat=J.CombatLearner()
        self.w.update(dice=28.,progress=3.5,main=10.,core=3.5,layer=.6,route_epic=2.,route_rare=1.)

    def update(self,p,battle_reward):
        # Same bounded credit scheme, with the explicit new route-rare/epic terms.
        extra={k:self.w.pop(k) for k in ('route_epic','route_rare')}
        super().update(p,battle_reward)
        for k,v in extra.items():
            signed=sum(f.get(k,0) for f in p.decisions)
            self.w[k]=max(.25,min(4.,v+.025*battle_reward*signed))


def install():
    A.vector=vector;A.install()


def config():
    frozen=S.C.ROOT/'releases/deckbuilding-v1.0/probabilities.json'
    if frozen.exists():
        cfg=json.loads(frozen.read_text(encoding='utf-8'));assert_uniform_counts(cfg);return cfg
    cfg=json.loads((S.C.ROOT/'docs/deckbuilding/construction-baseline-v2.json').read_text(encoding='utf-8'))
    cfg.update(status='growth_v4_uniform_joint_training_candidate',economy_profile=CURRENT,
               card_copy_overrides={},pre_progress_weight_per_card=0,
               post_specialization_enchantment_share=.65,
               nonlegendary_copy_uniformity='same rarity and same enchantment/generic category must have equal copies; hard constraint')
    cfg['free_purchase']={'rounds_1_to_3':['common'],'rounds_4_to_6':['common','rare'],'scope':'one_per_round_both_faces'}
    cfg['deletions']={'rounds_1_to_3':[0,[]],'rounds_4_to_6':[1,[0]],'rounds_7_plus':[2,[0,1]]}
    cfg['unresolved_policy']='Uniform six-bucket pool. Joint construction/combat research, not tournament certification.'
    assert_uniform_counts(cfg);return cfg


def stage(label,n,model,cfg,learn,ns,raw,out):
    eps=[];start=time.time()
    for i in range(n):
        ep=S.simulate_episode(ns,i,model if learn else copy.deepcopy(model),learn,economy=CURRENT,
                             namespace=out.name,config=cfg,total_rounds=14)
        ep.update(condition=label,config_hash=digest(cfg));eps.append(ep)
        raw.write(json.dumps(ep,ensure_ascii=False)+'\n');raw.flush()
        print(f'{label} {i+1}/{n} D14={st.mean(p["route_dice"] for p in ep["players"]):.3f} {time.time()-start:.1f}s',flush=True)
    result=summarize(eps);S.save(out/(label+'-summary.json'),result)
    S.save(out/(label+'-final-decks.json'),[dict(episode=e['index'],players=e['players']) for e in eps])
    return eps,result


def deck(p,did):
    S.C.DECKS[did]=dict(id=did,element=p['spec'] or S.TARGETS[p['target']]['element'],
        specialization_selected=bool(p['spec']),route=p['route'],entries=[dict(name=n,quantity=1) for n in p['names']])


def score(result,a):return .5 if result['winner']=='draw' else float(result['winner']==a)


def fixed_deck_bank(eps,new,old,ns,rounds=(3,6,8,10,12,14)):
    rows=[]
    for ep in eps:
        for r in rounds:
            ps=ep['rounds'][r-1]['players']
            for pid,p in enumerate(ps):
                other=(pid+1)%4;deck(p,'probe-own');deck(ps[other],'probe-opponent')
                for flip in range(2):
                    a,b=('probe-own','probe-opponent') if not flip else ('probe-opponent','probe-own')
                    seed=S.seed(ns,ep['index'],r,pid,flip)
                    enemy=old.policy('probe-opponent','probe-own',r)
                    for label,model in [('new',new),('old',old)]:
                        own=model.policy('probe-own','probe-opponent',r)
                        result=model.play(a,b,seed,own if not flip else enemy,enemy if not flip else own)
                        state=result['players']['probe-own']
                        rows.append(dict(episode=ep['index'],round=r,pid=pid,flip=flip,model=label,
                            score=score(result,'probe-own'),seed=seed,
                            unused=state['wasted']/max(1,state['granted']),plays=sum(state['plays'].values()),
                            activations=state['activations']))
    return dict(games=len(rows),new=st.mean(x['score'] for x in rows if x['model']=='new'),
                old=st.mean(x['score'] for x in rows if x['model']=='old'),rows=rows)


def final_matrix(eps,model,out):
    """Fixed opponents and actual cards; calibration-selected finite policy benchmark.

    Full reference counterpart is evaluated with the same adaptive controller.
    Its opponent roster and seeds are exactly the actual deck's roster/seeds.
    """
    rows=[];calibration=[];start=time.time();initial=J.CombatLearner()
    for ep in eps:
        for p in ep['players']:
            deck(p,'eval-actual')
            rid=J.ROUTE_ID.get(p['route'],p['target']);S.C.DECKS['eval-full']=copy.deepcopy(S.TARGETS[rid])
            # Public known deck policy selection on separate seeds, three fixed
            # representative opponents. It never chooses on evaluation outcomes.
            modes=['greedy','generic','historical','adaptive'];scores={}
            for mode in modes:
                values=[]
                for j in [0,5,10]:
                    oid=list(S.TARGETS)[(j+ep['index'])%15];S.C.DECKS['eval-enemy']=copy.deepcopy(S.TARGETS[oid])
                    pa=model.policy('eval-actual','eval-enemy',14,mode);pb=initial.policy('eval-enemy','eval-actual',14,'historical')
                    result=model.play('eval-actual','eval-enemy',S.seed(out.name,'portfolio-calibration',ep['index'],p['pid'],j),pa,pb)
                    values.append(score(result,'eval-actual'))
                scores[mode]=st.mean(values)
            selected=max(modes,key=lambda k:(scores[k],k=='adaptive'))
            calibration.append(dict(episode=ep['index'],pid=p['pid'],scores=scores,selected=selected))
            for oid in S.TARGETS:
                S.C.DECKS['eval-enemy']=copy.deepcopy(S.TARGETS[oid])
                for flip in range(2):
                    seed=S.seed(out.name,'sealed-matrix',ep['index'],p['pid'],oid,flip)
                    # Stable identities hold card draws constant across policies.
                    for label,mode,source in [('adaptive','adaptive','actual'),('historical','historical','actual'),
                                              ('portfolio',selected,'actual'),('full_reference','adaptive','full')]:
                        S.C.DECKS['eval-own']=copy.deepcopy(S.C.DECKS['eval-'+source])
                        own=model.policy('eval-own','eval-enemy',14,mode)
                        enemy=initial.policy('eval-enemy','eval-own',14,'historical')
                        a,b=('eval-own','eval-enemy') if not flip else ('eval-enemy','eval-own')
                        result=model.play(a,b,seed,own if not flip else enemy,enemy if not flip else own)
                        x=result['players']['eval-own'];core=[n for n in p['names'] if S.C.CARDS[n].kind in ('specialization','route_legendary')]
                        rows.append(dict(episode=ep['index'],pid=p['pid'],route=p['route'],opponent=oid,flip=flip,
                            model=label,mode=mode,score=score(result,'eval-own'),seed=seed,
                            unused=x['wasted']/max(1,x['granted']),plays=sum(x['plays'].values()),
                            core_complete=bool(core) and all(n in x['activations'] for n in core)))
        print(f'final matrix {ep["index"]+1}/{len(eps)} {time.time()-start:.1f}s',flush=True)
    S.save(out/'final-matrix.json',dict(rows=rows,calibration=calibration))
    return {k:dict(n=sum(x['model']==k for x in rows),score=st.mean(x['score'] for x in rows if x['model']==k),
                   unused=st.mean(x['unused'] for x in rows if x['model']==k)) for k in ['adaptive','historical','portfolio','full_reference']}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--train',type=int,default=8)
    ap.add_argument('--validate',type=int,default=4);ap.add_argument('--final',type=int,default=12);args=ap.parse_args()
    out=S.C.ROOT/'research'/args.run
    if out.exists():raise FileExistsError(out)
    out.mkdir();(out/'sources').mkdir();cfg=config();install()
    files=['train_joint_draft.py','joint_draft_combat.py','dice_draft_agent.py','shared_draft_pool.py',
           'shared_draft_combat.py','simulate_shared_draft.py','draft_economy.py','construction_templates.py',
           'engine.py','planner.py','cards.py','policies.json','learning_core.py','optimize_dice_draft.py']
    hashes={}
    for f in files:
        path=Path(__file__).parent/f;shutil.copyfile(path,out/'sources'/f);hashes[f]=hashlib.sha256(path.read_bytes()).hexdigest()
    S.save(out/'experiment.json',dict(args=vars(args),source_hashes=hashes,card_sha256=hashlib.sha256(S.C.CARD_LIBRARY_PATH.read_bytes()).hexdigest(),
        constraints='six uniform buckets; unchanged legendary/rarity/economy; fixed four players no elimination',
        learning='8 training rooms per cycle; actual-card unilateral combat mutations for both sides; dense/outcome draft updates',
        transfer='historical route and matchup priors; no old deck performance claims',
        final_policy_selection='calibration seeds only, no evaluation-result selection'))
    S.save(out/'reference-decks.json',list(S.TARGETS.values()));S.save(out/'phase1-previous-config.json',cfg)
    S.save(out/'selected-config.json',cfg);model=JointLearner();history=[]
    S.IDS=list(S.IDS);random.Random('joint-balanced-route-preferences').shuffle(S.IDS)
    attempted=0
    with gzip.open(out/'episodes.jsonl.gz','wt',encoding='utf-8') as raw:
        for phase in range(1,4):
            old=copy.deepcopy(model);candidate=copy.deepcopy(model);offset=len(candidate.combat.log)
            stage(f'p{phase}-train',args.train,candidate,cfg,True,f'train-{phase}',raw,out)
            attempted+=candidate.combat.updates-old.combat.updates
            before,before_s=stage(f'p{phase}-before',args.validate,old,cfg,False,f'validation-{phase}',raw,out)
            after,after_s=stage(f'p{phase}-after',args.validate,candidate,cfg,False,f'validation-{phase}',raw,out)
            bank=fixed_deck_bank(after,candidate.combat,old.combat,f'{out.name}-validation-bank-{phase}')
            S.save(out/f'phase{phase}-combat-validation.json',bank)
            combat_accept=bank['new']>=bank['old']
            draft_accept=after_s['selection_objective']>=before_s['selection_objective']
            model=copy.deepcopy(candidate)
            if not combat_accept:model.combat=copy.deepcopy(old.combat)
            if not draft_accept:model.w=copy.deepcopy(old.w);model.updates=old.updates
            S.save(out/f'phase{phase}-combat-training.json',candidate.combat.log[offset:])
            item=dict(phase=phase,before=before_s,after=after_s,combat_validation={k:bank[k] for k in ['games','new','old']},
                      combat_accepted=combat_accept,draft_accepted=draft_accept,
                      attempted_combat_updates=attempted,checkpoint=dict(draft=model.w,combat=model.combat.dump()))
            history.append(item);S.save(out/'history.json',history)
            print(f'PHASE {phase} combat={combat_accept} draft={draft_accept} score={bank["new"]:.3f}/{bank["old"]:.3f}',flush=True)
        S.save(out/'selected-model.json',dict(draft=model.w,combat=model.combat.dump()))
        eps,final_s=stage('final-selected',args.final,model,cfg,False,'sealed-final',raw,out)
    bank=fixed_deck_bank(eps,model.combat,J.CombatLearner(),out.name+'-sealed-bank')
    S.save(out/'final-controller-bank.json',bank)
    matrix=final_matrix(eps,model.combat,out)
    S.save(out/'summary.json',dict(history=history,final=final_s,controllers={k:bank[k] for k in ['games','new','old']},
                                 matrix=matrix,attempted_combat_updates=attempted,
                                 experiment='three cycles; six uniform buckets; all final seeds sealed'))
    print(json.dumps(dict(final=final_s,matrix=matrix),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
