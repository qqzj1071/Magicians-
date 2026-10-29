from pathlib import Path
import json,sys,shutil
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from tools.sim_v12.catalog import CARDS,export

PANELS={'熔盾烈焰':(11,2),'奔流':(5,6),'层岩结构':(2,8),'风暴':(5,6),'缓释毒素':(8,4)}

def write(rel,text):
 p=ROOT/rel
 if p.exists():
  backup=OUT/'before'/rel;backup.parent.mkdir(parents=True,exist_ok=True)
  if not backup.exists():shutil.copy2(p,backup)
 p.write_text(text,encoding='utf-8')

def main():
 assert not (OUT/'changes.json').exists(),'Already applied'
 export(OUT/'before-catalog')
 records=[]
 for n,(a,d) in PANELS.items():
  c=CARDS[n];assert c.cost==3 and c.rarity=='epic'
  assert 2*a+3*d==28
  records.append(dict(name=n,element=c.element,old_attack=c.attack,old_defense=c.defense,attack=a,defense=d,
   old_value=(2*c.attack+3*c.defense)/(c.cost+1),value=7.))
 for el in ('fire','water','earth','wind','poison'):
  p=ROOT/f'docs/cards-v1.2/{el}.md';lines=p.read_text(encoding='utf-8').splitlines()
  for i,line in enumerate(lines):
   cells=line.split('|')
   if len(cells)==8 and cells[1] in PANELS:
    a,d=PANELS[cells[1]];cells[3]=str(a);cells[4]=str(d);lines[i]='|'.join(cells)
  write(str(p.relative_to(ROOT)),'\n'.join(lines)+'\n')
 p=ROOT/'tools/sim_v12/rules/panel-budgets.json';rules=json.loads(p.read_text(encoding='utf-8'))
 rules['version']='1.2-role-v2-permanent-rare80'
 rules['mechanism_bands']={'three_cost_permanent':dict(reference_rarity='rare',multiplier=.8,cards=list(PANELS),
  reason='User selected the five elemental permanent stackers; water includes only 奔流, not 深渊. Rarity and cost remain epic/3.')}
 write(str(p.relative_to(ROOT)),json.dumps(rules,ensure_ascii=False,indent=2)+'\n')
 write('research/v1.2-permanent-rare80-20261029/changes.json',json.dumps(dict(cards=records,excluded_water='深渊',target_band=[6,7.2]),ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(records,ensure_ascii=False))

if __name__=='__main__':main()
