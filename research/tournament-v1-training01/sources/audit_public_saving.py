"""Replay stock/money, reconstruct every broadcast and audit frozen comparisons."""
import argparse
import gzip
import json
from collections import Counter
import audit_dice_optimization as inventory
import cards as C
from shared_draft_pool import assert_uniform_counts

START=['攻击强化','攻击强化','防御强化','防御强化','护盾','检索附魔','短促','重洗']
SPECIAL={c.element:n for n,c in C.CARDS.items() if c.kind=='specialization'}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);args=ap.parse_args();inventory.main()
    out=C.ROOT/'research'/args.run;exp=json.loads((out/'experiment.json').read_text(encoding='utf-8'));n=exp['args']
    cfg=json.loads((out/'selected-config.json').read_text(encoding='utf-8'));assert_uniform_counts(cfg)
    assert not cfg.get('card_copy_overrides');counts=Counter();expected_trials=set()
    with gzip.open(out/'episodes.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            ep=json.loads(line)
            if ep['condition'].endswith('-train'):
                for row in ep['rounds']:
                    for b in row['battles']:
                        expected_trials.update((b['seed'],f'draft-p{pid}') for pid in (b['a'],b['b']))
            if ep['information_profile']!='broadcast-v1':continue
            counts['public_courses']+=1;decks=[Counter(START) for _ in range(4)]
            state={str(pid):dict(spec='',route='') for pid in range(4)};release={};seq=0
            for row in ep['rounds']:
                r=row['round'];events=iter(row['broadcasts'])

                def buy(pid,act):
                    nonlocal seq
                    if act.get('replaced'):decks[pid][act['replaced']]-=1
                    decks[pid][act['name']]+=1
                    spec=state[str(pid)]['spec']
                    if not spec:
                        hist=Counter()
                        for name,q in decks[pid].items():
                            if C.CARDS[name].element!='generic' and C.CARDS[name].kind!='specialization':hist[C.CARDS[name].element]+=q
                        eligible=[e for e,v in hist.items() if v>=3]
                        if eligible:
                            spec=row['players'][pid]['spec'];assert spec in eligible;decks[pid][SPECIAL[spec]]+=1
                    route=next((name for name,q in decks[pid].items() if q and C.CARDS[name].kind=='route_legendary'),'')
                    for key,value in [('spec',spec),('route',route)]:
                        if state[str(pid)][key]==value:continue
                        old=state[str(pid)][key];ev=next(events);seq+=1
                        assert ev['seq']==seq and ev['round']==r and ev['pid']==pid and ev['kind']==key
                        assert ev['previous']==old and ev['value']==value and ev['receivers']==[0,1,2,3]
                        if key=='route' and old:release[old]=r+1
                        state[str(pid)][key]=value;counts['broadcasts']+=1;counts['retargets']+=len(ev['retargets'])
                phases={}
                for pid,p in enumerate(row['points']):
                    first=[];second=[];deleted=[];refresh=False
                    for act in p['actions']:
                        if act['kind']=='refresh':refresh=True
                        elif act['kind']=='buy':(second if refresh else first).append(act)
                        elif act['kind']=='delete':deleted.append(act)
                    phases[pid]=(first,second,deleted)
                    decisions=[x for x in row['finance'] if x['pid']==pid and x['kind']=='refresh_decision']
                    assert len(decisions)<=1
                    if decisions:
                        decision=decisions[0]
                        assert decision['refresh']==refresh
                        assert decision['points']==p['income']-sum(a['cost'] for a in first)
                        assert decision['slots']==8-len(first)
                        if refresh:counts['approved_refreshes']+=1
                        else:counts['skipped_refreshes']+=1
                    else:assert not refresh
                for pid in range(4):
                    for act in phases[pid][0]:buy(pid,act)
                for pid in [(r-1+i)%4 for i in range(4)]:
                    for act in phases[pid][1]:buy(pid,act)
                for pid in range(4):
                    for act in phases[pid][2]:decks[pid][act['name']]-=1
                    assert +decks[pid]==Counter(row['players'][pid]['names'])
                assert next(events,None) is None
                assert row['public_state']==dict(players=state,release_round=release)
    seen=set();local_accepts=0
    for phase in (1,2):
        rows=json.loads((out/f'phase{phase}-combat-training.json').read_text(encoding='utf-8'))
        assert len(rows)==n['train']*56
        for row in rows:
            key=(row['seed'],row['own']);assert key in expected_trials and key not in seen;seen.add(key)
            assert row['accepted']==(row['gain']>.0025);local_accepts+=row['accepted']
    assert seen==expected_trials
    comparison_games=0
    for name in ['phase1-strength-validation.json','phase2-strength-validation.json','phase1-combat-validation.json',
                 'phase2-combat-validation.json','final-controller-bank.json','early-saving-probe.json']:
        rows=json.loads((out/name).read_text(encoding='utf-8'))['rows'];keys=Counter()
        for x in rows:keys[(x['episode'],x['pid'],x['round'],x['flip'],x['seed'])]+=1
        assert all(v==2 for v in keys.values());comparison_games+=len(rows)
    if not (out/'final-matrix.json').exists():
        print(json.dumps(dict(scope='preflight_only_matrix_pending',broadcasts=counts['broadcasts'],
                             retargets=counts['retargets'],combat_trials=len(seen),comparison_games=comparison_games)))
        return
    rows=json.loads((out/'final-matrix.json').read_text(encoding='utf-8'))['rows'];keys=Counter()
    for x in rows:keys[(x['episode'],x['pid'],x['opponent'],x['flip'],x['seed'])]+=1
    assert all(v==6 for v in keys.values())
    history=json.loads((out/'history.json').read_text(encoding='utf-8'))
    for h in history:
        assert h['draft_accepted']==(h['strength']['utility']['new']>=h['strength']['utility']['old'] and
                 h['after']['spec_by5']>=max(.75,h['before']['spec_by5']-.1))
        assert h['combat_accepted']==(h['combat']['new']>=h['combat']['old'])
    audit=json.loads((out/'audit.json').read_text(encoding='utf-8'));course=audit['counts']['course_battles']
    audit['public_saving']=dict(**dict(counts),combat_trials=len(seen),local_acceptances=local_accepts,
        comparison_games=comparison_games,matrix_games=len(rows),total_games=course+len(seen)+comparison_games+len(rows),
        event_order_and_four_receivers_replayed=True,no_rarity_or_legendary_change=True,
        battle_utility_not_dice_selection=True,paired_seeds_verified=True)
    (out/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(audit['public_saving']))


if __name__=='__main__':main()
