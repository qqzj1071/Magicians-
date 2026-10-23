"""Additional bracketing of midgame damage, frozen AI and matched seeds."""
import argparse
import gzip
import hashlib
import json
import multiprocessing
import shutil
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import train_survival as R
from tournament_inference import load_model
S=R.S


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--base',type=int,required=True)
    ap.add_argument('--rooms',type=int,default=40);ap.add_argument('--final',type=int,default=0);args=ap.parse_args()
    parent=S.C.ROOT/'research'/args.run;out=parent/('duration-probe'+str(args.base))
    if out.exists():raise FileExistsError(out)
    out.mkdir();(out/'sources').mkdir();cfg=json.loads((parent/'config.json').read_text(encoding='utf-8'))
    model=load_model(parent/'selected-model.json');old=R.initial_model();ns=parent.name+'-duration-repair'
    hashes={}
    for src in (parent/'duration-refinement/sources').iterdir():
        shutil.copyfile(src,out/'sources'/src.name);hashes[src.name]=hashlib.sha256(src.read_bytes()).hexdigest()
    for name in ['probe_survival_midgame.py','tournament_inference.py']:
        src=Path(__file__).parent/name;shutil.copyfile(src,out/'sources'/name);hashes[name]=hashlib.sha256(src.read_bytes()).hexdigest()
    table=R.make_table(4,1.6,args.base,1.6,100)
    S.save(out/'experiment.json',dict(args=vars(args),source_hashes=hashes,card_sha256=hashlib.sha256(S.C.CARD_LIBRARY_PATH.read_bytes()).hexdigest(),
        reason='two calibration candidates both below50% alive15, extend bracket downwards; no AI updates'))
    S.save(out/'config.json',cfg);S.save(out/'selected-table.json',dict(table=table));shutil.copyfile(parent/'selected-model.json',out/'selected-model.json')
    with ProcessPoolExecutor(max_workers=4) as executor,gzip.open(out/'episodes.jsonl.gz','wt',encoding='utf-8') as raw:
        eps,stats=R.batch(executor,'calibration-before',args.rooms,model,table,cfg,False,ns+'-calibration',raw,out)
        S.save(out/'calibration.json',dict(base=args.base,stats=stats))
        if args.final:
            eps,stats=R.batch(executor,'sealed-final',args.final,model,table,cfg,False,ns+'-bracket-new-holdout',raw,out)
            matrix=R.benchmark(executor,eps,model,old,ns+'-bracket-champion',out,'champion-matrix',True)
            S.save(out/'summary.json',dict(history=[],final=stats,matrix=matrix,table=table,parent_run=args.run,training_phases=0))
        print('MIDGAME PROBE '+json.dumps(stats),flush=True)


if __name__=='__main__':multiprocessing.freeze_support();main()
