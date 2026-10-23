"""Inventory audit plus independent joint-training/evaluation record checks."""
import argparse
import gzip
import json
from collections import Counter
import audit_dice_optimization as inventory
import cards as C
from shared_draft_pool import assert_uniform_counts


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);args=ap.parse_args()
    inventory.main()
    out=C.ROOT/'research'/args.run;exp=json.loads((out/'experiment.json').read_text(encoding='utf-8'));n=exp['args']
    cfg=json.loads((out/'selected-config.json').read_text(encoding='utf-8'));buckets=assert_uniform_counts(cfg)
    assert not cfg.get('card_copy_overrides')
    expected={};episodes=0
    with gzip.open(out/'episodes.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            ep=json.loads(line);episodes+=1
            if ep['condition'].endswith('-train'):
                for r in ep['rounds']:
                    for b in r['battles']:
                        for pid in [b['a'],b['b']]:expected[(b['seed'],f'draft-p{pid}')]=r['players'][pid]['route']
    seen=set();accepted=0
    for phase in range(1,4):
        rows=json.loads((out/f'phase{phase}-combat-training.json').read_text(encoding='utf-8'))
        assert len(rows)==n['train']*56
        for x in rows:
            key=(x['seed'],x['own']);assert key in expected and key not in seen;seen.add(key)
            assert bool(expected[key])==bool(x['route'])
            assert len(x['changes'])==2 and x['accepted']==(x['gain']>.0025)
            accepted+=x['accepted']
    assert seen==set(expected)
    bank_games=0
    for path in [*(out.glob('phase*-combat-validation.json')),out/'final-controller-bank.json']:
        data=json.loads(path.read_text(encoding='utf-8'));pairs=Counter()
        for x in data['rows']:pairs[(x['episode'],x['round'],x['pid'],x['flip'],x['seed'])]+=1
        assert all(v==2 for v in pairs.values());bank_games+=len(data['rows'])
    matrix=json.loads((out/'final-matrix.json').read_text(encoding='utf-8'))
    pairs=Counter((x['episode'],x['pid'],x['opponent'],x['flip'],x['seed']) for x in matrix['rows'])
    assert len(matrix['rows'])==n['final']*4*15*2*4 and all(v==4 for v in pairs.values())
    for row in matrix['calibration']:
        assert row['scores'][row['selected']]==max(row['scores'].values())
    generic=json.loads((out/'final-generic-probe.json').read_text(encoding='utf-8'))['rows']
    assert len(generic)==n['final']*4*15*2
    assert set((x['episode'],x['pid'],x['opponent'],x['flip'],x['seed']) for x in generic)==set(pairs)
    result=json.loads((out/'audit.json').read_text(encoding='utf-8'))
    course=episodes*28;calibration=len(matrix['calibration'])*12
    result['joint_training']=dict(uniform_buckets=buckets,episodes=episodes,combat_candidate_updates=len(seen),
        local_acceptances=accepted,course_games=course,unilateral_trial_games=len(seen),
        fixed_deck_comparison_games=bank_games,matrix_games=len(matrix['rows']),
        portfolio_calibration_games=calibration,generic_probe_games=len(generic),
        total_games=course+len(seen)+bank_games+len(matrix['rows'])+calibration+len(generic),
        matched_seed_policy_comparisons=True,training_trial_seeds_match_real_courses=True,
        uniform_bucket_hard_constraint=True)
    (out/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result['joint_training']))


if __name__=='__main__':main()
