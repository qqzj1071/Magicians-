"""Broader early-curve search on fixed traces; not a simulation claim."""
import gzip
import json
import math
import random
from functools import lru_cache
import calibrate_survival_v7 as V
S=V.S


def main():
    eps=[]
    with gzip.open(S.C.ROOT/'research/shared-draft-v6-survival01/duration-probe26/episodes.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            e=json.loads(line)
            if e['label']=='sealed-final':eps.append(e)
    events=[[None]*(len(eps)*4) for _ in range(12)]
    for i,e in enumerate(eps):
        for row in e['rounds'][:12]:
            r=row['round']
            for b in row['battles']:
                z=b['result'];a,c=b['a'],b['b'];w=z['winner']
                for pid,other in [(a,'ghost' if b['ghost'] else 'survivor-'+str(c))]+([] if b['ghost'] else [(c,'survivor-'+str(a))]):
                    if w!='survivor-'+str(pid):events[r-1][i*4+pid]=-1 if w=='draw' else math.log(max(z['players'][other]['hp'],1))
    @lru_cache(maxsize=30000)
    def costs(r,m,n):return tuple(0 if x is None else m if x<0 else m+math.floor(x*n) for x in events[r-1])
    rng=random.Random(734);rows=[]
    for _ in range(6000):
        a=rng.randint(1,7);b=rng.randint(a+1,8);ms=sorted(rng.randint(1,5) for _ in range(3))
        n1=rng.randint(1,18)/10;n2=rng.randint(round(n1*10),20)/10
        prefix=a*V.Q.damage(ms[0],n1,500)+(b-a)*V.Q.damage(ms[1],n2,500)
        n3=n2
        while prefix+(9-b)*V.Q.damage(ms[2],n3,500)<100:n3=round(n3+.1,1)
        table=V.make_table(2,1.5,max(5,n3),3)
        for r in range(1,13):
            j=0 if r<=a else 1 if r<=b else 2
            table[str(r)]=[ms[j],[n1,n2,n3][j]]
        for r in range(13,17):table[str(r)][0]=max(table[str(r)][0],ms[-1])
        V.Q.validate_table(table);V.check_bounds(table)
        columns=[costs(r,*table[str(r)]) for r in range(1,13)]
        strong=sum(sum(v)<60 for v in zip(*columns))/len(events[0])
        rows.append(dict(cuts=[a,b],m=ms,n=[n1,n2,n3],strong12=strong,table=table))
    rows.sort(key=lambda x:abs(x['strong12']-.6))
    S.save(S.C.ROOT/'research/shared-draft-v7-damage01/random-screen.json',dict(top=rows[:20],tested=len(rows),max_strong=max(x['strong12'] for x in rows)))
    print(json.dumps(dict(max_strong=max(x['strong12'] for x in rows),top=[{k:x[k] for k in ('cuts','m','n','strong12')} for x in rows[:8]])))


if __name__=='__main__':main()
