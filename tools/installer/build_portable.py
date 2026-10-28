"""Explicit Windows x64 release build. No hooks, background updates or machine paths."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--godot', type=Path, required=True, help='Godot 4.7.2 .NET console editor')
    p.add_argument('--template', type=Path, required=True, help='Matching Windows x64 .NET release template EXE')
    p.add_argument('--python-runtime', type=Path, required=True, help='Complete tested Python 3.12.10 embedded x64 folder')
    p.add_argument('--licenses', type=Path, required=True, help='Godot/.NET redistributable license directory')
    p.add_argument('--output', type=Path, required=True, help='New output folder; existing releases are never overwritten')
    a = p.parse_args()
    out = a.output.resolve()
    if out.exists() or Path(str(out) + '.zip').exists():
        raise SystemExit('Output already exists. Choose a new release directory.')
    for required in [a.godot, a.template, a.python_runtime / 'python.exe', a.licenses,
                     ROOT / 'releases/v1.0/Magicians-v1.0-card-catalogue.docx']:
        if not required.exists():
            raise SystemExit('Missing input: ' + str(required))
    version = subprocess.check_output([str(a.python_runtime / 'python.exe'), '-I', '-c',
                                      'import sys;print(".".join(map(str,sys.version_info[:3])))'], text=True).strip()
    if version != '3.12.10':
        raise SystemExit('Release runtime must be the tested Python 3.12.10, got ' + version)
    out.mkdir(parents=True)
    preset = ROOT / 'export_presets.cfg'
    previous = preset.read_text(encoding='utf-8-sig')
    lines = previous.splitlines()
    lines = [line for line in lines if not line.startswith('custom_template/release=')]
    at = lines.index('[preset.0.options]') + 1
    lines.insert(at, 'custom_template/release=' + json.dumps(a.template.resolve().as_posix(), ensure_ascii=False))
    preset.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    try:
        with (out.parent / (out.name + '.export.log')).open('w', encoding='utf-8') as log:
            subprocess.run([str(a.godot), '--headless', '--editor', '--path', str(ROOT), '--import', '--quit'],
                           stdout=log, stderr=subprocess.STDOUT, check=True)
            subprocess.run([str(a.godot), '--headless', '--path', str(ROOT), '--export-release',
                            'Windows Portable', str(out / 'Magicians.exe'), '--quit'], stdout=log, stderr=subprocess.STDOUT, check=True)
        log = (out.parent / (out.name + '.export.log')).read_text(encoding='utf-8')
        if 'ERROR:' in log or 'completed with warnings' in log:
            raise RuntimeError('Godot reported an export error. See build-export.log; do not distribute this folder.')
    finally:
        preset.write_text(previous, encoding='utf-8')
    data = out / 'runtime-data'
    def copy(relative):
        src, dst = ROOT / relative, data / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        else:
            shutil.copy2(src, dst)
    for relative in ['Data', 'decks', 'releases/v1.0/cards.json', 'releases/deckbuilding-v1.0',
                     'docs/ai/current-tournament.json', 'tools/client_ai/inference_worker.py',
                     'tools/client_ai/runtime.json', 'tools/round_robin']:
        copy(relative)
    pointer = json.loads((ROOT / 'docs/ai/current-tournament.json').read_text(encoding='utf-8-sig'))
    copy(pointer['model'])
    for relative in ['Scripts/Core/AI/AiObservations.cs', 'Scripts/Application/TrainedAiRuntime.cs',
                     'Scripts/Core/Combat/Slice1CombatEngine.cs', 'Scripts/Core/Match/MatchCoordinator.cs',
                     'Scripts/Core/Draft/FrozenDraftRules.cs', 'Scripts/Core/Draft/DraftOfferAllocator.cs']:
        copy(relative)
    shutil.copytree(a.python_runtime, data / 'tools/client_ai/python-runtime')
    shutil.copytree(a.licenses, out / 'licenses')
    player_readme = ROOT / 'docs/client/portable-player-readme.txt'
    if not player_readme.exists():
        player_readme = ROOT / 'docs/client/portable-release.md'
    for src, name in [(ROOT / 'releases/v1.0/Magicians-v1.0-card-catalogue.docx', 'Magicians-v1.0-card-catalogue.docx'),
                      (ROOT / 'tools/installer/Create-Desktop-Shortcut.vbs', 'Create-Desktop-Shortcut.vbs'),
                      (player_readme, 'README.txt')]:
        shutil.copy2(src, out / name)
    # Keep readable creative archives beside the game without exposing flavor in match UI.
    for relative, name in [('docs/lore/fire-all-final.txt', 'FIRE-FLAVOR-TEXTS.txt'),
                           ('docs/lore/fire-card-names.txt', 'FIRE-CARD-NAMES.txt')]:
        source = ROOT / relative
        if source.exists():
            shutil.copy2(source, out / name)
    build_info = dict(version='1.0', source_ref=os.environ.get('MAGICIANS_SOURCE_REF', 'explicit-source-snapshot'),
                      python=version, godot='4.7.2 .NET', architecture='Windows x64',
                      template_sha256=digest(a.template), model_sha256=pointer['model_sha256'],
                      cards_sha256=digest(data / 'releases/v1.0/cards.json'))
    (out / 'BUILD-INFO.json').write_text(json.dumps(build_info, ensure_ascii=False, indent=2), encoding='utf-8')
    hashes = {f.relative_to(out).as_posix(): digest(f) for f in sorted(out.rglob('*')) if f.is_file()}
    (out / 'integrity.json').write_text(json.dumps(hashes, ensure_ascii=False, indent=2), encoding='utf-8')
    hashes['integrity.json'] = digest(out / 'integrity.json')
    (out / 'MANIFEST.sha256').write_text(''.join(f'{h}  {name}\n' for name, h in hashes.items()), encoding='utf-8')
    # Ordinary accidental-edit protection. Not a trust boundary or anti-cheat.
    for f in out.rglob('*'):
        if f.is_file():
            f.chmod(0o444)
    archive = Path(str(out) + '.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(out.rglob('*')):
            if f.is_file():
                z.write(f, out.name + '/' + f.relative_to(out).as_posix())
    archive.with_suffix('.zip.sha256').write_text(digest(archive) + '  ' + archive.name + '\n', encoding='ascii')
    print(json.dumps(dict(zip=str(archive), bytes=archive.stat().st_size, sha256=digest(archive))))

if __name__ == '__main__':
    main()

