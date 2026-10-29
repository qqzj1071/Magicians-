"""Additional v1 fixed-rule, rollback and explainability audit."""
import gzip
import hashlib
import json
from pathlib import Path
import strategic_tournament_ai as I
import survival_tournament as Q
S=Q.S


def main():
    out=S.C.ROOT/'research/tournament-v1-training01'
    read=lambda n:json.loads((out/n).read_text(encoding='utf-8'))
    exp=read('experiment.json');release=S.C.ROOT/'releases/deckbuilding-v1.0'
    assert hashlib.sha256((release/'manifest.json').read_bytes()).hexdigest()==exp['release_manifest_sha256']
    if exp.get('metadata_correction'):
        original=read('pool-view-at-start.json')
        current=json.loads((release/'pool-counts.json').read_text(encoding='utf-8'))
        assert original['cards']==current['cards']
        assert hashlib.sha256((out/'release-manifest-at-start.json').read_bytes()).hexdigest()==exp['release_manifest_sha256_at_start']
        start=read('release-manifest-at-start.json')
        now=json.loads((release/'manifest.json').read_text(encoding='utf-8'))
        assert all(now['sha256'][name]==value for name,value in start['sha256'].items() if name!='pool-counts.json')
        assert {k:v for k,v in original.items() if k!='status'}=={k:v for k,v in current.items() if k not in ('status','construction_version')}
    cfg=json.loads((release/'probabilities.json').read_text(encoding='utf-8'))
    table=json.loads((release/'damage.json').read_text(encoding='utf-8'))['table']
    assert read('config.json')==cfg and read('selected-table.json')['table']==table
    previous=read('initial-model.json');history=read('training-history.json')
    assert len(history)==exp['args']['cycles']==10
    attempted_updates=accepted_trials=win=loss=draw=0
    for h in history:
        phase=h['phase'];chosen=read(f'phase{phase}-model.json')
        dg=h['benchmark_after']['old_combat']-h['benchmark_before']['old_combat']
        cg=h['fixed_probe']['means']['new']-h['fixed_probe']['means']['old']
        assert h['draft_accepted']==(dg>=.01 and h['after']['spec_by5']>=h['before']['spec_by5']-.05)
        assert h['combat_accepted']==(cg>=.01 and min(h['fixed_probe']['stage_gains'].values())>=-.05)
        if not h['draft_accepted']:
            assert chosen['draft']==previous['draft'] and chosen['prior']==previous['prior']
            assert chosen['draft_strategy_enabled']==previous['draft_strategy_enabled']
        if not h['combat_accepted']:assert chosen['combat']==previous['combat']
        for x in read(f'p{phase}-learning.json')['combat']:
            assert len(x['seed_gains'])==2
            assert x['accepted']==(sum(x['seed_gains'])/2>.005 and min(x['seed_gains'])>=-.03)
            attempted_updates+=1;accepted_trials+=x['accepted']
            win+=x['outcome']=='win';loss+=x['outcome']=='loss';draw+=x['outcome']=='draw'
        previous=chosen
    assert read('selected-model.json')==previous
    selection=read('release-selection.json')
    for name,key in [('selected-model.json','model_sha256'),('selected-table.json','table_sha256')]:assert hashlib.sha256((out/name).read_bytes()).hexdigest()==selection[key]
    rooms=0;reasons=0;mixed=0;train_battles=0;train_ghosts=0
    with gzip.open(out/'episodes.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            ep=json.loads(line);rooms+=1;mixed+=ep['label']=='mixed-final'
            if ep['label'].endswith('-train'):
                train_battles+=ep['battles'];train_ghosts+=sum(b['ghost'] for row in ep['rounds'] for b in row['battles'])
            for row in ep['rounds']:
                assert row['parameters']==table[str(row['round'])]
                for ledger in row['ledger']:
                    for d in ledger.get('decision_reasons',[]):
                        assert d.get('reason') and all(isinstance(x,(int,float)) for x in d.get('contributions',{}).values())
                        reasons+=1
    assert mixed==24
    assert attempted_updates==2*train_battles-train_ghosts
    assert win+loss+draw==attempted_updates
    result=dict(status='passed',rooms=rooms,decision_reasons=reasons,combat_learning_attempts=attempted_updates,
        locally_accepted_trials=accepted_trials,winner_learning=win,loser_learning=loss,draw_learning=draw,
        scope='frozen rules, all ten independent gates, exact rollback, terminal model hash, two shuffle learning, reasons')
    S.save(out/'audit-v1.json',result);print(json.dumps(result))


if __name__=='__main__':main()
