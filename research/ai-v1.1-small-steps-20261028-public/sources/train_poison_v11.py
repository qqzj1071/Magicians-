"""Two-round poison-only retraining for the v1.1 temporary-attack experiment."""
from dataclasses import replace
from pathlib import Path
import json, hashlib, statistics
import engine as E
from planner import initial
import cards
ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/'research/ai-v1.1-poison'; OUT.mkdir(parents=True,exist_ok=True)
POISON=tuple(x for x in cards.DECKS if x.startswith('poison-')); ALL=('fire-01','water-03','earth-02','wind-02','poison-02')
def evaluate(policies,games,seed_base):
 rows=[]
 for own in POISON:
  for opp in ALL:
   pa=policies[own]; pb=policies.get(opp,initial(opp,own)); wins=0;times=[]
   for k in range(games):
    r=E.simulate(own,opp,seed_base+k,winner_policy(pa),winner_policy(pb),validate=False);wins+=r['winner']==own;times.append(r['time'])
   rows.append({'own':own,'opponent':opp,'games':games,'wins':wins,'win_rate':wins/games,'mean_time':statistics.mean(times)})
 return rows

def winner_policy(p): return p

def score(rows):
 by={a:[] for a in POISON}
 for r in rows:by[r['own']].append(r['win_rate'])
 return statistics.mean(statistics.mean(v) for v in by.values()),{k:statistics.mean(v) for k,v in by.items()}
def main():
 card_sha=hashlib.sha256((ROOT/'releases/v1.1/cards.json').read_bytes()).hexdigest(); policies={a:initial(a,'fire-01') for a in POISON}; history=[]
 ladders=[[(35,1.3,1.3),(50,1.3,1.6),(65,1.2,1.8)],[(50,1.3,1.6),(60,1.5,1.8),(75,1.5,2.2)]]
 for rnd,candidates in enumerate(ladders,1):
  before=evaluate(policies,10,100000+rnd*10000);chosen={};candidate_scores={}
  for own in POISON:
   trials=[]
   for j,(layer,burst,tempo) in enumerate(candidates):
    candidate=replace(policies[own],operation_layer=layer,finish_burst=burst,tempo_value=tempo,damage=1.3,sustain_value=1.5);trial=dict(policies);trial[own]=candidate
    rows=evaluate(trial,2,200000+rnd*10000+j*1000+int(own[-1])*100);s,detail=score(rows)
    trials.append({'candidate':j,'operation_layer':layer,'finish_burst':burst,'tempo_value':tempo,'score':s,'route_scores':detail})
   best=max(trials,key=lambda x:(x['score'],x['route_scores'][own]));layer,burst,tempo=candidates[best['candidate']];policies[own]=replace(policies[own],operation_layer=layer,finish_burst=burst,tempo_value=tempo,damage=1.3,sustain_value=1.5);chosen[own]=best;candidate_scores[own]=trials
  after=evaluate(policies,10,300000+rnd*10000);sb,detailb=score(before);sa,detaila=score(after);rec={'round':rnd,'games_per_matchup':10,'before_score':sb,'after_score':sa,'before_routes':detailb,'after_routes':detaila,'chosen':chosen,'candidates':candidate_scores,'after_rows':after};history.append(rec);(OUT/f'round_{rnd:02d}.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 payload={'version':'1.1-poison-ai','card_library':'../../releases/v1.1/cards.json','card_sha256':card_sha,'rounds':history,'poison_policies':{k:vars(v) for k,v in policies.items()},'method':'two rounds; candidate ladder; 10 held-out games per poison-initiated matchup; operation score rewards poison-element commons and temporary-attack stacking'};(OUT/'policies-v1.1-poison.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'card_sha256':card_sha,'rounds':2,'final_score':history[-1]['after_score'],'final_routes':history[-1]['after_routes']},ensure_ascii=False))
if __name__=='__main__':main()


