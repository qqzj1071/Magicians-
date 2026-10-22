"""Verify and package the frozen v1.0 cards and current handoff documents."""
from pathlib import Path
import json,hashlib,zipfile,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/round_robin'))
from verify_v1 import main as verify
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 release=ROOT/'releases/v1.0';manifest=release/'manifest.json'
 if (ROOT/'releases/Magicians-cards-v1.0.zip').exists():
  verify()
  print('Card release v1.0 is frozen; the existing ZIP was verified and was not rebuilt.')
  return
 # Existing checksums must pass before refreshing the package.
 result=verify()
 (release/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 files=[ROOT/'README.md',ROOT/'AGENTS.md',ROOT/'docs/README.md',ROOT/'docs/CHANGELOG.md',ROOT/'docs/cards/README.md',ROOT/'docs/ai/README.md',ROOT/'docs/deckbuilding/process-draft.md',ROOT/'decks/README.md',ROOT/'decks/decks.json']
 files+=sorted((ROOT/'docs/cards').glob('*.md'))+sorted((ROOT/'docs/combat').glob('*.md'))+sorted(release.glob('*.json'))+[release/'README.md']
 files=sorted(set(p for p in files if p!=manifest))
 metadata=dict(version='1.0',cards=253,files={p.relative_to(ROOT).as_posix():sha(p) for p in files},history_excluded=True)
 manifest.write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 package=ROOT/'releases/Magicians-cards-v1.0.zip'
 with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in files+[manifest]:z.write(p,p.relative_to(ROOT).as_posix())
 with zipfile.ZipFile(package) as z:
  assert z.testzip() is None
  for path,h in metadata['files'].items():assert hashlib.sha256(z.read(path)).hexdigest()==h
 print(json.dumps(dict(package=str(package),package_bytes=package.stat().st_size,package_sha256=sha(package),active_source_bytes=sum(p.stat().st_size for p in files),files=len(files)+1),ensure_ascii=False))
if __name__=='__main__':main()
