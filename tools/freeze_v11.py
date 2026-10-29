"""Create an immutable, checksummed v1.1 card/combat release."""
from pathlib import Path
import json,hashlib,zipfile
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 release=ROOT/'releases/v1.1';manifest=release/'freeze-manifest.json';package=ROOT/'releases/Magicians-cards-combat-v1.1.zip'
 if manifest.exists():
  m=json.loads(manifest.read_text(encoding='utf-8'))
  for n,h in m['sha256'].items():assert sha(ROOT/n)==h,n
  assert sha(package)==m['package_sha256'];print('V11_FROZEN_HASHES_OK');return
 cards=json.loads((release/'cards.json').read_text(encoding='utf-8'))
 assert len(cards['cards'])==252 and '守势' not in cards['cards']
 rules={'card_version':'1.1','status':'frozen','date':'2026-10-28','active_cards':252,'initial_life':1000,'initial_attack':100,'initial_defense':40,'base_missile_interval':50,'final_interval_rounding':'floor','deckbuilding_version':'1.0','training_may_change':'AI parameters and decision logic only'}
 (release/'combat-rules.json').write_text(json.dumps(rules,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 files=[release/'cards.json',release/'combat-rules.json',release/'retired-cards.json',ROOT/'tools/round_robin/engine.py',ROOT/'tools/round_robin/shared_draft_combat.py']
 files+=list((ROOT/'Scripts/Core/Combat').glob('*.cs'))+list((ROOT/'docs/cards-v1.1').glob('*.md'))
 files+=[ROOT/'releases/deckbuilding-v1.0'/n for n in ['probabilities.json','pool-counts.json','economy.json','damage.json']]
 hashes={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(files))}
 with zipfile.ZipFile(package,'x',zipfile.ZIP_DEFLATED) as z:
  for n in hashes:z.write(ROOT/n,n)
 with zipfile.ZipFile(package) as z:
  assert z.testzip() is None
  for n,h in hashes.items():assert hashlib.sha256(z.read(n)).hexdigest()==h
 m={**rules,'sha256':hashes,'package':'releases/'+package.name,'package_sha256':sha(package)}
 manifest.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 p=release/'manifest.json';old=json.loads(p.read_text(encoding='utf-8-sig'));old.update(status='frozen',card_count=252,active_card_count=252,cards_sha256=sha(release/'cards.json'),freeze_manifest='freeze-manifest.json');p.write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('V11_FROZEN_PACKAGE_CREATED',sha(package))
if __name__=='__main__':main()
