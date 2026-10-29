"""Small staged damage calibration; frozen AI, untouched draft rules."""
import gzip
import hashlib
import json
import multiprocessing
import shutil
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import calibrate_survival_v7 as V
from tournament_inference import load_release
R=V.R;S=V.S


def make_table(early):
    stages=early+[(9,3.2),(10,4.5),(11,6.0)]
    table={str(r):list(stages[0 if r<=4 else 1 if r<=8 else 2 if r<=12 else 3 if r<=14 else 4 if r<=16 else 5]) for r in range(1,81)}
    V.Q.validate_table(table);V.check_bounds(table)
    assert all(.8<=n<=6 for m,n in table.values())
    return table


def main():
    out=S.C.ROOT/'research/shared-draft-v8-stages01'
    if out.exists():raise FileExistsError(out)
    (out/'sources').mkdir(parents=True)
    parent=S.C.ROOT/'research/shared-draft-v7-damage01'
    model,_,cfg=load_release(parent)
    shutil.copyfile(parent/'selected-model.json',out/'selected-model.json')
    hashes={}
    for path in Path(__file__).parent.iterdir():
        if path.suffix=='.py' or path.name=='policies.json':
            shutil.copyfile(path,out/'sources'/path.name)
            hashes[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    S.save(out/'config.json',cfg)
    S.save(out/'experiment.json',dict(training_updates=0,targets=dict(strong12=.6,alive14=.5,ended17=.98),
        source_hashes=hashes,card_sha256=hashlib.sha256(S.C.CARD_LIBRARY_PATH.read_bytes()).hexdigest(),
        calibration_rooms_per_candidate=8,final_rooms=40,unchanged='frozen v6 AI, cards, pool, odds, guarantees, economy',
        tail='R17+ stays m11 n6, table extends to round80'))
    candidates=[[(2,.8),(4,1.8),(7,2.)],[(3,.8),(5,1.4),(7,2.1)],[(2,.8),(5,1.5),(8,2.)]]
    history=[]
    with ProcessPoolExecutor(max_workers=4) as executor,gzip.open(out/'episodes.jsonl.gz','wt',encoding='utf-8') as raw:
        for i,early in enumerate(candidates):
            table=make_table(early)
            eps,_=R.batch(executor,'calibration-before',8,model,table,cfg,False,out.name+'-calibration',raw,out)
            stats=V.metrics(eps)
            error=3*abs(stats['strong12']-.6)+3*abs(stats['alive14']-.5)+10*max(0,.98-stats['ended17'])
            history.append(dict(index=i,table=table,stats=stats,error=error))
            S.save(out/'calibration.json',history)
            print('CANDIDATE',i,json.dumps(stats),flush=True)
        chosen=min(history,key=lambda x:x['error']);table=chosen['table']
        S.save(out/'selection.json',dict(chosen=chosen['index'],basis='8 calibration rooms per candidate only; independent final seeds not read'))
        S.save(out/'selected-table.json',dict(table=table,bounds=V.check_bounds(table)))
        eps,_=R.batch(executor,'sealed-final',40,model,table,cfg,False,out.name+'-sealed',raw,out)
        stats=V.metrics(eps)
        S.save(out/'summary.json',dict(final=stats,table=table,bounds=V.check_bounds(table),training_updates=0))
        print('FINAL',json.dumps(stats),flush=True)


if __name__=='__main__':multiprocessing.freeze_support();main()
