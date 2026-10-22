"""Restore the lossless historical ZIP from the Git-hosted verified volumes."""
from pathlib import Path
import hashlib,json,os
ROOT=Path(__file__).resolve().parents[1]

def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()

def main():
 folder=ROOT/'archives';manifest=json.loads((folder/'volumes.json').read_text(encoding='utf-8'))
 target=folder/manifest['archive']
 if target.exists():
  if sha(target)!=manifest['sha256']:raise ValueError('Existing archive differs; it was not overwritten.')
  print('Historical archive already exists and its SHA-256 matches.');return
 temporary=target.with_suffix('.zip.restoring')
 created=False
 try:
  with temporary.open('xb') as out:
   created=True
   for part in manifest['parts']:
    p=folder/part['file']
    if p.stat().st_size!=part['bytes'] or sha(p)!=part['sha256']:raise ValueError('Invalid volume: '+part['file'])
    with p.open('rb') as source:
     for block in iter(lambda:source.read(1024*1024),b''):out.write(block)
  if sha(temporary)!=manifest['sha256']:raise ValueError('Reassembled archive checksum mismatch.')
  os.replace(temporary,target)
 except BaseException:
  if created and temporary.exists():temporary.unlink()
  raise
 print('Reassembled and verified: '+str(target))

if __name__=='__main__':main()
