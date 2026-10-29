"""Separate held-out balanced-affinity diagnostic; same frozen learned weights."""
import argparse
import copy
import gzip
import json
import random
import statistics
import time
import simulate_shared_draft as S


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True)
    ap.add_argument('--weights',default='learned-weights.json');args=ap.parse_args()
    out=S.C.ROOT/'research'/args.run
    weights=json.loads((out/args.weights).read_text(encoding='utf-8'))
    S.IDS=list(S.IDS);random.Random('balanced-affinity-curriculum-v1').shuffle(S.IDS)
    model=S.Learner();model.w=weights['learned']
    path=out/'balanced-affinity.jsonl.gz'
    if path.exists():raise FileExistsError(path)
    summary={};t=time.time()
    with gzip.open(path,'wt',encoding='utf-8') as f:
        for label,noncompetitive in [('shared',False),('noncompetitive',True)]:
            episodes=[]
            for index in range(15):
                ep=S.simulate_episode('balanced-evaluation',index,copy.deepcopy(model),False,False,noncompetitive,
                                      namespace=args.run+'-balanced')
                ep['condition']=label;episodes.append(ep);f.write(json.dumps(ep,ensure_ascii=False)+'\n');f.flush()
                print(f'balanced {label} {index+1}/15 {time.time()-t:.1f}s',flush=True)
            summary[label]=S.aggregate(episodes)
    S.save(out/'balanced-affinity-summary.json',dict(affinity_order=S.IDS,results=summary,
           caveat='Different preference cohort from primary test; frozen parameters, new seeds, no retraining.'))


if __name__=='__main__':main()
