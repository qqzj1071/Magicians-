"""One additional monotone early allocation; select using calibration only."""
import argparse
import gzip
import hashlib
import json
import multiprocessing
import shutil
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
import calibrate_survival_v7 as V
from tournament_inference import load_model
S=V.S;R=V.R


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);args=ap.parse_args();root=S.C.ROOT/'research'/args.run
    out=root/'expanded';out.mkdir();(out/'sources').mkdir();read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    profile=read(root/'expanded-screen.json')['profiles'][0];table=profile['table']
    table['14']=[6,7.0];table['15']=[8,7.5];V.check_bounds(table);V.Q.validate_table(table)
    model=load_model(root/'selected-model.json');cfg=read(root/'config.json');hashes={}
    for path in (root/'sources').iterdir():
        shutil.copyfile(path,out/'sources'/path.name);hashes[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ['calibrate_survival_v7_expanded.py','screen_nine_loss_profiles.py','screen_nine_loss_random.py']:
        src=Path(__file__).parent/name;shutil.copyfile(src,out/'sources'/name);hashes[name]=hashlib.sha256(src.read_bytes()).hexdigest()
    S.save(out/'experiment.json',dict(source_hashes=hashes,card_sha256=hashlib.sha256(S.C.CARD_LIBRARY_PATH.read_bytes()).hexdigest(),
        training_updates=0,targets=dict(strong12=.6,alive14=.5,ended17=.98),method='expanded early allocation; frozen AI; no champion benchmark'))
    S.save(out/'config.json',cfg);shutil.copyfile(root/'selected-model.json',out/'selected-model.json');S.save(out/'selected-table.json',dict(table=table,bounds=V.check_bounds(table)))
    with ProcessPoolExecutor(max_workers=4) as executor,gzip.open(out/'episodes.jsonl.gz','wt',encoding='utf-8') as raw:
        eps,_=R.batch(executor,'calibration-before',24,model,table,cfg,False,root.name+'-calibration',raw,out)
        stats=V.metrics(eps);error=abs(stats['strong12']-.6)*3+abs(stats['alive14']-.5)*3+max(0,.98-stats['ended17'])*10
        S.save(out/'calibration.json',dict(stats=stats,error=error))
        prior=min(read(root/'calibration.json'),key=lambda x:x['error']);use_expanded=error<prior['error']
        folder='expanded' if use_expanded else '.';chosen=out if use_expanded else root
        assert not (chosen/'summary.json').exists(),'Selection must precede selected final results'
        S.save(root/'release-selection.json',dict(chosen_folder=folder,selection_utc=datetime.now(timezone.utc).isoformat(),
            basis='actual calibration only; no selected final results read',expanded_error=error,original_error=prior['error'],
            model_sha256=hashlib.sha256((chosen/'selected-model.json').read_bytes()).hexdigest(),
            table_sha256=hashlib.sha256((chosen/'selected-table.json').read_bytes()).hexdigest()))
        if use_expanded:
            eps,_=R.batch(executor,'sealed-final',200,model,table,cfg,False,root.name+'-expanded-sealed',raw,out)
            S.save(out/'summary.json',dict(final=V.metrics(eps),table=table,bounds=V.check_bounds(table),training_updates=0,
                calibration=dict(stats=stats,error=error),champion_benchmark='not repeated; damage-only calibration'))
        print(json.dumps(dict(use_expanded=use_expanded,calibration=stats)),flush=True)


if __name__=='__main__':multiprocessing.freeze_support();main()
