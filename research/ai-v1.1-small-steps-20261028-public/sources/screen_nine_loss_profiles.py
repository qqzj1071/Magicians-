"""Enumerate monotone nine-loss allocations; fixed-fight proposal screen only."""
import gzip
import json
import math
from pathlib import Path
import calibrate_survival_v7 as V
S=V.S


def partitions(total,length,largest=None):
    if length==0:
        if total==0:yield []
        return
    for first in range(min(total,largest if largest is not None else total),-1,-1):
        for tail in partitions(total-first,length-1,first):yield [first]+tail


def candidates():
    for base in range(1,11):
        for deficit in partitions(8,9):
            targets=[12-d for d in deficit]
            if min(targets)<base:continue
            params=[]
            for d in targets:
                possible=[i/10 for i in range(0,31) if V.Q.damage(base,i/10,500)==d]
                if not possible:break
                params.append([base,min(possible)])
            if len(params)!=9:continue
            table=V.make_table(2,1.5,5,3)
            for r in range(1,13):table[str(r)]=params[min(r-1,8)]
            for r in range(13,17):table[str(r)][0]=max(base,table[str(r)][0])
            V.Q.validate_table(table);V.check_bounds(table)
            yield dict(base=base,deficits=deficit,table=table)


def main():
    source=S.C.ROOT/'research/shared-draft-v6-survival01/duration-probe26/episodes.jsonl.gz';eps=[]
    with gzip.open(source,'rt',encoding='utf-8') as f:
        for line in f:
            ep=json.loads(line)
            if ep['label']=='sealed-final':eps.append(ep)
    profiles=[]
    for x in candidates():
        stats=V.fixed_screen(eps,x['table']);x['screen']=stats;profiles.append(x)
    profiles.sort(key=lambda x:(abs(x['screen']['strong12']-.6),abs(x['screen']['alive14']-.5)))
    out=S.C.ROOT/'research/shared-draft-v7-damage01/expanded-screen.json';S.save(out,dict(profiles=profiles))
    print(json.dumps([{k:x[k] for k in ('base','deficits','screen')} for x in profiles[:10]]))


if __name__=='__main__':main()
