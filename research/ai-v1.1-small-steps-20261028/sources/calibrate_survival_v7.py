"""One frozen-AI calibration: nine-loss bound, R12 health, R14 duel, R17 end."""
import argparse
import copy
import gzip
import hashlib
import json
import math
import multiprocessing
import shutil
import statistics as st
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import train_survival as R
from tournament_inference import load_release
S=R.S;Q=R.Q


def make_table(base=2,n=1.5,mid=4.,step=1.5):
    table={}
    for r in range(1,81):
        if r<=8:m,k=base,n
        elif r<=12:m,k=base+1,n
        elif r==13:m,k=5,mid
        elif r==14:m,k=6,mid+step
        elif r==15:m,k=8,max(mid+step,7.5)
        elif r==16:m,k=10,max(mid+step,12.)
        else:m,k=11,max(mid+step,24.)+4*(r-17)
        table[str(r)]=[m,round(k,1)]
    Q.validate_table(table);check_bounds(table);return table


def check_bounds(table):
    windows=[]
    for start in range(1,len(table)-7):
        rows=[table[str(r)] for r in range(start,start+9)]
        base=sum(m for m,n in rows);blowout=sum(Q.damage(m,n,500) for m,n in rows)
        assert base<100 and blowout>=100,(start,base,blowout)
        windows.append(dict(start=start,base=base,damage_at500=blowout))
    return dict(first_nine=windows[0],max_nine_base=max(x['base'] for x in windows),
                min_nine_damage_at500=min(x['damage_at500'] for x in windows))


def hp_at(ep,r):
    hp={i:100 for i in range(4)}
    for row in ep['rounds'][:r]:
        for pid,x in row['settlement'].items():hp[int(pid)]=max(0,x['hp'])
    return hp


def metrics(eps):
    rows=Q.summarize(eps);n=len(eps)
    rows.update(strong12=sum(sum(h>40 for h in hp_at(e,12).values()) for e in eps)/(4*n),
        alive14=sum(sum(h>0 for h in hp_at(e,14).values()) for e in eps)/(4*n),
        ended17=sum(e['end_round']<=17 for e in eps)/n,
        two_alive14=sum(sum(h>0 for h in hp_at(e,14).values())==2 for e in eps)/n)
    entry=[];actual=[]
    for e in eps:
        entry.append(next((row['round'] for row in e['rounds'] if len(row['remaining'])<=2),e['end_round']))
        rounds=[row['round'] for row in e['rounds'] if len(row['players'])==2]
        if rounds:actual.append(rounds[0])
    rows.update(mean_duel_entry=st.mean(entry),median_duel_entry=st.median(entry),
                median_first_duel=st.median(actual) if actual else None,
                skipped_duel=sum(not any(len(row['players'])==2 for row in e['rounds']) for e in eps))
    return rows


def fixed_screen(eps,table):
    strong=alive=0
    for ep in eps:
        hp={i:100 for i in range(4)}
        for row in ep['rounds']:
            r=row['round']
            if r>14:break
            m,n=table[str(r)]
            for battle in row['battles']:
                res=battle['result'];a,b=battle['a'],battle['b'];win=res['winner']
                # No invented rematching: this is only a proposal screen.
                for pid,other in [(a,'ghost' if battle['ghost'] else 'survivor-'+str(b))]+([] if battle['ghost'] else [(b,'survivor-'+str(a))]):
                    if hp[pid]>0 and win!='survivor-'+str(pid):
                        hp[pid]-=Q.damage(m,n,res['players'][other]['hp'],win=='draw')
            if r==12:strong+=sum(v>40 for v in hp.values())/4
        alive+=sum(v>0 for v in hp.values())/4
    return dict(strong12=strong/len(eps),alive14=alive/len(eps))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--calibrate',type=int,default=24)
    ap.add_argument('--final',type=int,default=200);args=ap.parse_args();out=S.C.ROOT/'research'/args.run
    if out.exists():raise FileExistsError(out)
    out.mkdir();(out/'sources').mkdir();parent=S.C.ROOT/'research/shared-draft-v6-survival01'
    model,old_table,cfg=load_release(parent)
    source=parent/'duration-probe26/episodes.jsonl.gz';old=[]
    with gzip.open(source,'rt',encoding='utf-8') as f:
        for line in f:
            ep=json.loads(line)
            if ep['label']=='sealed-final':old.append(ep)
    proposals=[]
    for base,n in [(1,1.7),(2,1.5),(3,1.3)]:
        for mid in (2.5,3.,3.5,4.,4.5,5.):
            for step in (1.,2.,3.):
                table=make_table(base,n,mid,step);stats=fixed_screen(old,table)
                proposals.append(dict(base=base,n=n,mid=mid,step=step,table=table,screen=stats,
                    error=abs(stats['strong12']-.6)*3+abs(stats['alive14']-.5)*3))
    # Different early profiles, plus the next best midgame curve.
    selected=[]
    for base in (1,2,3):selected.append(min((x for x in proposals if x['base']==base),key=lambda x:x['error']))
    extra=min((x for x in proposals if all((x['base'],x['mid'],x['step'])!=(s['base'],s['mid'],s['step']) for s in selected)),key=lambda x:x['error'])
    selected.append(extra);S.save(out/'screened-proposals.json',dict(selected=selected,all=proposals,
        limitation='fixed fights only; real shared inventory, elimination and ghost feedback require validation'))
    hashes={}
    names=['calibrate_survival_v7.py','survival_tournament.py','tournament_draft.py','tournament_inference.py','train_survival.py',
        'public_baseline_inference.py','route_feasible_draft.py','train_joint_draft.py','joint_draft_combat.py',
        'dice_draft_agent.py','simulate_shared_draft.py','shared_draft_pool.py','shared_draft_combat.py','draft_economy.py',
        'construction_templates.py','engine.py','planner.py','cards.py','policies.json']
    for name in names:
        path=Path(__file__).parent/name;shutil.copyfile(path,out/'sources'/name);hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    S.save(out/'experiment.json',dict(args=vars(args),source_hashes=hashes,card_sha256=hashlib.sha256(S.C.CARD_LIBRARY_PATH.read_bytes()).hexdigest(),
        targets=dict(strong12=.6,alive14=.5,ended17=.98),training_updates=0,
        unchanged='cards, six bucket copies, rarity odds, 8/10/12 first-face3 legends, economy, frozen v6 AI',
        model_sha256=hashlib.sha256((parent/'duration-probe26/selected-model.json').read_bytes()).hexdigest()))
    shutil.copyfile(parent/'duration-probe26/selected-model.json',out/'selected-model.json');S.save(out/'config.json',cfg)
    history=[]
    with ProcessPoolExecutor(max_workers=4) as executor,gzip.open(out/'episodes.jsonl.gz','wt',encoding='utf-8') as raw:
        for i,proposal in enumerate(selected):
            # Identical construction/battle named seeds; labels before/after
            # normalize to the same calibration identifier in simulator.
            label='calibration-before' if i%2==0 else 'calibration-after'
            eps,_=R.batch(executor,label,args.calibrate,model,proposal['table'],cfg,False,out.name+'-calibration',raw,out)
            stats=metrics(eps);error=abs(stats['strong12']-.6)*3+abs(stats['alive14']-.5)*3+max(0,.98-stats['ended17'])*10
            history.append(dict(index=i,proposal=proposal,stats=stats,error=error))
            S.save(out/'calibration.json',history);print('CALIBRATION '+json.dumps(history[-1]),flush=True)
        chosen=min(history,key=lambda x:(x['error'],abs(x['stats']['median_duel_entry']-14)))
        table=chosen['proposal']['table'];S.save(out/'selected-table.json',dict(table=table,bounds=check_bounds(table)))
        S.save(out/'selection.json',dict(chosen=chosen['index'],basis='calibration only; final seeds not read',proposal=chosen['proposal']))
        eps,_=R.batch(executor,'sealed-final',args.final,model,table,cfg,False,out.name+'-sealed',raw,out)
        summary=metrics(eps);S.save(out/'summary.json',dict(final=summary,table=table,calibration=history,bounds=check_bounds(table),
            training_updates=0,champion_benchmark='not repeated: this experiment changes damage only'))
        print('FINAL '+json.dumps(summary),flush=True)


if __name__=='__main__':multiprocessing.freeze_support();main()
