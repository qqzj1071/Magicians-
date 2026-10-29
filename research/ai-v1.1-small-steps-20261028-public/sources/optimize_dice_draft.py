"""Three sequential, audited small pool adjustments with a sealed final test."""
import argparse
import copy
import gzip
import hashlib
import json
import random
import shutil
import statistics
import time
from collections import Counter
from pathlib import Path
import simulate_shared_draft as S
import dice_draft_agent as A
from draft_economy import CURRENT
from shared_draft_pool import CFG,copies,assert_uniform_counts

# Preserve the original experimental baseline after publishing a tuned candidate.
BASE=json.loads((S.C.ROOT/'releases/deckbuilding-v1.0/probabilities.json').read_text(encoding='utf-8'))
FREQUENCY=Counter(n for d in S.TARGET_NAMES.values() for n in d)
GUARDED=['rarities','first_face_legendary_guarantees','second_face_legendary_guarantees',
         'legendary_types','legendary_copy_counts','hard_caps','first_face_guaranteed_route_target',
         'guaranteed_slot_indices_zero_based','refresh_slot_mapping']


def initial_config():
    c=copy.deepcopy(BASE);c['economy_profile']=CURRENT
    c['free_purchase']={'rounds_1_to_3':['common'],'rounds_4_to_6':['common','rare'],'scope':'one_per_round_both_faces'}
    c['deletions']={'rounds_1_to_3':[0,[]],'rounds_4_to_6':[1,[0]],'rounds_7_plus':[2,[0,1]]}
    c['pre_progress_weight_per_card']=0;c['card_copy_overrides']={}
    return c


def guard(c,previous):
    assert_uniform_counts(c)
    for key in GUARDED:assert c[key]==BASE[key],key
    assert all(S.C.CARDS[n].rarity in ('common','rare','epic') for n in c.get('card_copy_overrides',{}))
    assert .6<=c['post_specialization_enchantment_share']<=.7
    assert .1<=c['refresh_bought_element_admission']<=.2
    assert 0<=c['pre_progress_weight_per_card']<=.25
    assert sum(c['pre_specialization_enchantment_count'].values())==1
    for name,card in S.C.CARDS.items():
        if card.rarity=='specialization':continue
        if card.rarity=='legendary':assert copies(card,c)==copies(card,BASE)
        else:
            assert -1<=copies(card,c)-copies(card,BASE)<=2
            assert abs(copies(card,c)-copies(card,previous))<=1


def propose(previous,diagnostic,phase):
    c=copy.deepcopy(previous);changes=[]
    if diagnostic['spec_by5']<.85:
        distribution={'2':.1,'3':.65,'4':.25} if phase==2 else {'2':.05,'3':.6,'4':.35}
        c['pre_specialization_enchantment_count']=distribution
        c['pre_progress_weight_per_card']=min(.25,previous.get('pre_progress_weight_per_card',0)+.15)
        c['refresh_bought_element_admission']=min(.2,previous['refresh_bought_element_admission']+.05)
        changes.append('Early specialization coverage below 85%: slightly increase distinct elements and progress-weighted appearance; retain one-per-element hard limit.')
    if diagnostic['main_recall14_mean']<.9:
        c['post_specialization_enchantment_share']=min(.7,round(previous['post_specialization_enchantment_share']+.05,2))
        changes.append('Main-core coverage below 90%: increase main-element share without changing rarity or legendary odds.')
    c['card_copy_overrides']={}
    if diagnostic['main_recall14_mean']<.9:
        for rarity in ('rare','epic'):
            old=previous['nonlegendary_copy_counts'][rarity]['enchantment']
            c['nonlegendary_copy_counts'][rarity]['enchantment']=min(BASE['nonlegendary_copy_counts'][rarity]['enchantment']+2,old+1)
    changes.append('Uniform rarity/category buckets only; no reference-frequency or per-card copy overrides.')
    guard(c,previous)
    return c,changes


def summarize(episodes):
    result=dict(episodes=len(episodes),players=4*len(episodes),battles=sum(x['combat_count'] for x in episodes))
    for r in [5,6,12,13,14]:
        ps=[ep['rounds'][r-1]['players'][i] for ep in episodes for i in range(4)]
        result[f'dice{r}_mean']=statistics.mean(p['route_dice'] for p in ps)
        result[f'dice{r}_ge80']=sum(p['route_dice']>=.8 for p in ps)/len(ps)
        result[f'nearest_dice{r}_mean']=statistics.mean(p['nearest_dice_score'] for p in ps)
        result[f'main_recall{r}_mean']=statistics.mean(p['route_main_recall'] for p in ps)
        result[f'joint{r}_ge80']=sum(p['route_dice']>=.8 and p['route_main_recall']>=.8 for p in ps)/len(ps)
        result[f'mean_size{r}']=statistics.mean(p['size'] for p in ps)
    ps=[p for ep in episodes for p in ep['players']]
    result.update(spec_by5=sum(0<p['spec_round']<=5 for p in ps)/len(ps),
                  spec_by6=sum(0<p['spec_round']<=6 for p in ps)/len(ps),
                  unspecialized=sum(not p['spec'] for p in ps),
                  average_cost=statistics.mean(p['average_cost'] for p in ps),
                  mean_elements=statistics.mean(ep['elements'] for ep in episodes),
                  element_histogram=dict(Counter(p['spec'] for p in ps)),
                  route_histogram=dict(Counter(p['route'] for p in ps)),
                  resource_means={k:statistics.mean(p['resources'][k] for p in ps) for k in ['draw','search','shuffle']},
                  mean_foreign=statistics.mean(p['foreign_count'] for p in ps),
                  mean_free_purchases=statistics.mean(p['free_purchases'] for p in ps),
                  mean_deletes=statistics.mean(p['deletes'] for p in ps),
                  mean_delete_points=statistics.mean(p['deletion_points'] for p in ps),
                  route_changes=sum(p['route_changes'] for p in ps),
                  generic_denials=sum(p['denied_generic'] for p in ps),
                  max_route_dice=max(p['route_dice'] for p in ps),
                  max_nearest_dice=max(p['nearest_dice_score'] for p in ps),
                  pool_stats=dict(sum((Counter(ep['pool_stats']) for ep in episodes),Counter())))
    result['selection_objective']=result['dice14_mean']+.3*result['dice14_ge80']+.25*result['joint14_ge80']+.2*result['main_recall14_mean']+.1*result['spec_by5']
    return result


def stage(label,count,model,cfg,learn,namespace,raw,out):
    episodes=[];start=time.time()
    for index in range(count):
        ep=S.simulate_episode(namespace,index,model if learn else copy.deepcopy(model),learn,
                              economy=CURRENT,namespace=out.name,config=cfg,total_rounds=14)
        ep['condition']=label;ep['config_hash']=digest(cfg);episodes.append(ep)
        raw.write(json.dumps(ep,ensure_ascii=False)+'\n');raw.flush()
        print(f'{label} {index+1}/{count} D14={statistics.mean(p["route_dice"] for p in ep["players"]):.3f} {time.time()-start:.1f}s',flush=True)
    result=summarize(episodes);S.save(out/(label+'-summary.json'),result)
    S.save(out/(label+'-final-decks.json'),[dict(episode=ep['index'],players=ep['players']) for ep in episodes])
    return episodes,result


def digest(cfg):return hashlib.sha256(json.dumps(cfg,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def compare_decks(left,right,namespace):
    rows=[]
    for ea,eb in zip(left,right):
        for pa,pb in zip(ea['players'],eb['players']):
            for name,p in [('new',pa),('control',pb)]:
                S.C.DECKS['dice-'+name]=dict(element=p['spec'] or S.TARGETS[p['target']]['element'],specialization_selected=bool(p['spec']),
                    entries=[dict(name=n,quantity=1) for n in p['names']])
            for flip in range(2):
                a,b=('dice-new','dice-control') if flip==0 else ('dice-control','dice-new')
                result=S.battle(a,b,S.seed(namespace,ea['index'],pa['pid'],flip),S.E.GREEDY,S.E.GREEDY)
                rows.append(dict(episode=ea['index'],pid=pa['pid'],flip=flip,seed=result['seed'],winner=result['winner'],
                     score=.5 if result['winner']=='draw' else float(result['winner']=='dice-new')))
    return dict(n=len(rows),score=statistics.mean(x['score'] for x in rows),rows=rows)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--train',type=int,default=12)
    ap.add_argument('--validate',type=int,default=8);ap.add_argument('--final',type=int,default=15);args=ap.parse_args()
    out=S.C.ROOT/'research'/args.run
    if out.exists():raise FileExistsError(out)
    out.mkdir(parents=True);(out/'sources').mkdir()
    files=['optimize_dice_draft.py','dice_draft_agent.py','draft_economy.py','simulate_shared_draft.py','shared_draft_pool.py',
           'shared_draft_combat.py','construction_templates.py','engine.py','cards.py','learning_core.py']
    hashes={}
    for name in files:
        path=Path(__file__).parent/name;shutil.copyfile(path,out/'sources'/name);hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    S.save(out/'experiment.json',dict(args=vars(args),source_hashes=hashes,card_sha256=hashlib.sha256(S.C.CARD_LIBRARY_PATH.read_bytes()).hexdigest(),
         objective='actual-route Dice >=80% and main recall >=80% at 12-14; majority specialized before round6',
         adaptation='three small nonlegendary/element-config changes using validation only; final seeds sealed',
         economy=CURRENT,second_deletion_cost=1,rounds=14,no_additional_round14_legendary_guarantee=True,
         scope='four remain active; 14-round construction curriculum, no elimination',
         learning='marginal-Dice state objective plus online battle/dense-progress reward; artificial structure remains'))
    S.save(out/'reference-decks.json',list(S.TARGETS.values()))
    A.install()
    # Shuffled, balanced preferences, without forcing anyone's actual element.
    S.IDS=list(S.IDS);random.Random('dice-balanced-preferences-v1').shuffle(S.IDS)
    cfg=initial_config();initial=copy.deepcopy(cfg);model=A.Learner();history=[];updates=0
    initial_model=copy.deepcopy(model)
    with gzip.open(out/'episodes.jsonl.gz','wt',encoding='utf-8') as raw:
        for phase in range(1,4):
            before=copy.deepcopy(model);previous=copy.deepcopy(cfg)
            if phase==1:proposal=copy.deepcopy(cfg);changes=['New gift/deletion rules; unchanged starting pool and element settings.']
            else:proposal,changes=propose(cfg,history[-1]['accepted_summary'],phase)
            S.save(out/f'phase{phase}-config.json',proposal);S.save(out/f'phase{phase}-previous-config.json',previous)
            ns=f'validation-{phase}'
            base_eps,base_summary=stage(f'p{phase}-before',args.validate,before,previous,False,ns,raw,out)
            if phase>1:
                _,pool_only=stage(f'p{phase}-pool-only',args.validate,before,proposal,False,ns,raw,out)
            else:pool_only=base_summary
            candidate=copy.deepcopy(before);old_updates=candidate.updates
            stage(f'p{phase}-train',args.train,candidate,proposal,True,f'train-{phase}',raw,out)
            updates+=candidate.updates-old_updates
            learned_eps,learned_summary=stage(f'p{phase}-after',args.validate,candidate,proposal,False,ns,raw,out)
            accepted=learned_summary['selection_objective']>=base_summary['selection_objective']
            if accepted:cfg=proposal;model=candidate;accepted_summary=learned_summary
            else:accepted_summary=base_summary
            history.append(dict(phase=phase,changes=changes,before=base_summary,pool_only=pool_only,after=learned_summary,
                                accepted=accepted,accepted_summary=accepted_summary,config_delta_objective=pool_only['selection_objective']-base_summary['selection_objective'],
                                learning_delta_objective=learned_summary['selection_objective']-pool_only['selection_objective']))
            S.save(out/f'phase{phase}-weights.json',dict(before=before.w,candidate=candidate.w,accepted=model.w,total_training_updates=updates))
            S.save(out/'optimization-history.json',history)
            print(f'PHASE {phase} accepted={accepted} spec5={learned_summary["spec_by5"]:.1%} dice14={learned_summary["dice14_mean"]:.1%} hit={learned_summary["dice14_ge80"]:.1%}',flush=True)
        S.save(out/'selected-config.json',cfg);S.save(out/'selected-weights.json',dict(weights=model.w,total_training_updates=updates,selected_model_updates=model.updates))
        selected_eps,selected_summary=stage('final-selected',args.final,model,cfg,False,'final-sealed',raw,out)
        base_eps,base_summary=stage('final-baseline-pool',args.final,model,initial,False,'final-sealed',raw,out)
        prior_eps,prior_summary=stage('final-prior-agent',args.final,initial_model,cfg,False,'final-sealed',raw,out)
    comparisons={}
    references=[]
    for ep in selected_eps:
        players=[]
        for p in ep['players']:
            did=A.ROUTE_ID.get(p['route'],p['target']);d=S.TARGETS[did]
            players.append(dict(spec=d['element'],route=d['route'],target=did,names=list(S.TARGET_NAMES[did].elements())))
        references.append(dict(index=ep['index'],players=players))
    for label,control in [('vs-baseline-pool',base_eps),('vs-prior-agent',prior_eps),('vs-reference',references)]:
        comparisons[label]=compare_decks(selected_eps,control,args.run+label)
        S.save(out/(label+'-battles.json'),comparisons[label])
    summary=dict(history=history,final_selected=selected_summary,final_baseline_pool=base_summary,final_prior=prior_summary,
                 comparisons={k:{x:v[x] for x in ['n','score']} for k,v in comparisons.items()},training_parameter_updates=updates,
                 selected_config_hash=digest(cfg),majority_dice14=selected_summary['dice14_ge80']>.5,
                 majority_joint14=selected_summary['joint14_ge80']>.5)
    S.save(out/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
