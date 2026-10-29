import subprocess,json,os,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
profiles=json.loads((root/'Data/AI/single-player-styles.json').read_text(encoding='utf-8'))['profiles']
for profile in profiles:
 env=dict(os.environ,MAGICIANS_AI_STYLE=profile['id'],PYTHONIOENCODING='utf-8')
 public=[dict(id=x,spec='',route='',life=100,ghost=False) for x in ['human','ai-1','ai-2','ai-3']]
 draft=dict(player='ai-1',round=1,points=2,freeUsed=False,refreshes=0,removals=0,winStreak=0,lossStreak=0,spec='',route='',deck=[dict(id='own',name='护盾')],offers=[],publicPlayers=public,nextOpponent='human',legalActions=[dict(kind='finish',cost=0)],lossEstimate=0)
 combat=dict(player='ai-1',round=1,actionValue=0,self=dict(Life=1000,Attack=100,Defense=40,Energy=3,NextFire=50),opponent=dict(Life=1000,Attack=100,Defense=40,NextFire=50),hand=[],ownDeck=['护盾'],ownDiscard=[],ownPlayed=[],ownSpec='',ownRoute='',opponentSpec='',opponentRoute='')
 requests=[dict(kind='draft',actor='ai-1',view=draft),dict(kind='combat',actor='ai-1',view=combat),dict(kind='combat',actor='ai-2',view={**combat,'player':'ai-2'})]
 result=subprocess.run([sys.executable,str(root/'tools/client_ai/inference_worker.py')],input=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in requests),text=True,encoding='utf-8',capture_output=True,env=env,timeout=30)
 rows=[json.loads(x) for x in result.stdout.splitlines()]
 assert len(rows)==3 and rows[0]['ok'] and rows[1]['ok'] and not rows[2]['ok'],(profile['id'],result.stdout,result.stderr)
 print(profile['id'],rows[0]['result']['target'],'draft/combat OK; actor isolation OK')
