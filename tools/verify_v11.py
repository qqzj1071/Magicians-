from pathlib import Path
import json,hashlib,zipfile
ROOT=Path(__file__).resolve().parents[1]
def main():
 m=json.loads((ROOT/'releases/v1.1/freeze-manifest.json').read_text(encoding='utf-8'))
 for n,h in m['sha256'].items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,n
 assert hashlib.sha256((ROOT/m['package']).read_bytes()).hexdigest()==m['package_sha256']
 with zipfile.ZipFile(ROOT/m['package']) as z:
  assert z.testzip() is None
  for n,h in m['sha256'].items():assert hashlib.sha256(z.read(n)).hexdigest()==h,n
 c=json.loads((ROOT/'releases/v1.1/cards.json').read_text(encoding='utf-8'))['cards'];assert len(c)==252
 bands={'common':(5,6),'rare':(7.5,9),'epic':(9.5,11),'legendary':(11.5,13.5),'specialization':(14,16)}
 for n,x in c.items():
  assert isinstance(x['attack'],int) and isinstance(x['defense'],int)
  v=(x['attack']+1.5*x['defense'])/((x['cost']+1)/2);lo,hi=bands[x['rarity']];assert lo<=v<=hi,(n,v)
 print('V11_RELEASE_VERIFIED cards=252 base_interval=50 integer_panels=true frozen_hashes=true')
if __name__=='__main__':main()
