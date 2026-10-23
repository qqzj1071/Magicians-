"""Freeze accepted construction rules; verify obsolete archive before removal."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    release=ROOT/'releases/deckbuilding-v1.0'
    if release.exists():raise FileExistsError(release)
    release.mkdir()
    source=ROOT/'research/shared-draft-v8-stages01'
    cfg=json.loads((source/'config.json').read_text(encoding='utf-8'))
    cfg.update(status='frozen_deckbuilding_v1.0',version='1.0',
        unresolved_policy='Rules accepted 2026-10-23; AI strength and earlier duration targets are not certified.')
    save(release/'probabilities.json',cfg)
    shutil.copyfile(source/'selected-model.json',release/'initial-ai.json')
    shutil.copyfile(source/'selected-table.json',release/'damage.json')
    shutil.copyfile(ROOT/'docs/deckbuilding/shared-pool-counts.json',release/'pool-counts.json')
    economy=dict(version='1.0',implementation_profile='growth-v3',
        income=[dict(rounds=[1,2],points=2),dict(rounds=[3,5],points=3),dict(rounds=[6,None],points=4)],
        carry_cap=2,refresh_cost=1,refresh_limit=1,prices=dict(common=1,rare=2,epic=3,legendary=4),
        route_replacement_cost=2,legendary_capacity=3,specialization_count=3,
        minimum_deck_size=8,starter_cards_consume_pool=False,
        starter=['攻击强化','攻击强化','防御强化','防御强化','护盾','检索附魔','短促','重洗'],
        free_purchase=cfg['free_purchase'],deletions=cfg['deletions'],streak_bonus_every=3,
        deletion_and_replacement_returns='next_round',final_simultaneous_elimination='co_champions')
    save(release/'economy.json',economy)
    # One archive, preserving original paths and byte hashes. No extracted old rules.
    docs=ROOT/'docs/deckbuilding'
    paths=list(docs.glob('*'))
    paths=[p for p in paths if p.is_file()]
    old_roots=sorted((ROOT/'research').glob('shared-draft-*'))
    for d in old_roots:
        assert d.resolve().is_relative_to(ROOT/'research') and d.is_dir()
        paths.extend(p for p in d.rglob('*') if p.is_file())
    paths=sorted(set(paths));manifest=[dict(path=p.relative_to(ROOT).as_posix(),size=p.stat().st_size,sha256=sha(p)) for p in paths]
    archive=ROOT/'archives/obsolete-deckbuilding-pre-v1.0.zip'
    if archive.exists():raise FileExistsError(archive)
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        z.writestr('OBSOLETE-README.txt','OBSOLETE / 已过时。仅供明确要求的历史追溯。不得作为现行规则或AI入口。当前版本：releases/deckbuilding-v1.0/。\n')
        z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        for p in paths:z.write(p,p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for item in manifest:
            data=z.read(item['path']);assert len(data)==item['size'] and hashlib.sha256(data).hexdigest()==item['sha256']
    save(ROOT/'archives/obsolete-deckbuilding-pre-v1.0-verification.json',dict(status='verified',
        files=len(manifest),original_bytes=sum(x['size'] for x in manifest),archive_bytes=archive.stat().st_size,
        archive_sha256=sha(archive),default_access='do_not_extract_or_search',current='releases/deckbuilding-v1.0'))
    for p in paths:
        assert p.resolve().is_relative_to(ROOT) and p.is_file()
        p.unlink()
    for d in old_roots:
        assert d.resolve().is_relative_to(ROOT/'research')
        for sub in sorted((p for p in d.rglob('*') if p.is_dir()),key=lambda p:len(p.parts),reverse=True):sub.rmdir()
        d.rmdir()
    shutil.copyfile(release/'probabilities.json',docs/'construction-probabilities.json')
    shutil.copyfile(release/'pool-counts.json',docs/'shared-pool-counts.json')
    save(docs/'survival-damage-table.json',dict(status='frozen_deckbuilding_v1.0',
        coefficients=json.loads((release/'damage.json').read_text(encoding='utf-8'))['table'],
        tail=dict(from_round=17,m=11,n=6.0,mode='constant'),source='releases/deckbuilding-v1.0/damage.json'))
    print(json.dumps(dict(archive=str(archive),files=len(manifest),release=str(release))))


if __name__=='__main__':main()
