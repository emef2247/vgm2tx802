#!/usr/bin/env python3
"""Batch TX802-oriented MIDI export from the shared source-native musical layer."""
import argparse
import csv
import hashlib
import json
import os
import shutil
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'py'))
from native_source_music import build_native_performance
from native_vgm import write_native_vgm
from native_blueprint import render_native_blueprints
from blueprint_midi import render as render_midi
from tx802_target import project_tx802
from tx802_voices import load_voice_map
from tx802_voice_assets import build_voice_assets


FIELDS = ('source', 'status', 'detail', 'midi', 'reference_vgm', 'blueprint', 'notes', 'channels', 'bytes', 'reference_status', 'blueprint_status', 'voice_map', 'voice_csv', 'voice_assets', 'voice_assets_status')


def parser():
    p = argparse.ArgumentParser(description='Convert VGM/VGZ to TX802 MIDI through NativePerformance')
    p.add_argument('input', type=Path, help='VGM/VGZ file or directory, searched recursively')
    p.add_argument('--outdir', type=Path, help='Output root; default: beside each source file')
    p.add_argument('--ppq', type=int, default=480, help='MIDI ticks per quarter note (default: 480)')
    p.add_argument('--bpm', type=float, default=120, help='SMF tempo; physical source timing is retained (default: 120)')
    p.add_argument('--melody-mode', '--melody_mode', choices=('default','name','gm','opll'), default='default',
                   help='TX802 preset assignment table (default: internal I1..I15)')
    p.add_argument('--rhythm-mode', '--rhythm_mode', choices=('gm','rx21'), default='rx21',
                   help='External drum note map, not TX802 FM voices (default: rx21)')
    p.add_argument('--tx802-units', type=int, choices=(1,2), default=1,
                   help='Eight melodic parts per unit; two units use SMF MIDI ports 0 and 1')
    p.add_argument('--pitch-bend-range', type=int, default=12,
                   help='Must match actual TX802 voice range, 1..12 semitones (default: 12); voice Step must be 0')
    p.add_argument('--texed', type=Path, help='Texed checkout used to verify generated voice SysEx (default: ../texed)')
    p.add_argument('--voice-map', type=Path, help='Optional existing patch-hex -> TX802 bank/voice JSON')
    p.add_argument('--no-domino-init', '--no-tx802-domino-init', dest='domino_init', action='store_false', default=True,
                   help='Disable inherited controller initialization and its common lead-in')
    p.add_argument('--init-lead-ticks', type=int, default=12, help='Common melody/rhythm initialization lead (default: 12 MIDI ticks)')
    p.add_argument('--force', action='store_true', help='Replace owned outputs and permit reported source/part/pitch approximation')
    p.add_argument('--debug', '--dump-passes', dest='debug', action='store_true',
                   help='Print detailed target report; native/target diagnostics are retained')
    p.add_argument('--target', choices=('tx802',), default='tx802', help=argparse.SUPPRESS)
    return p


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _recover_publication(folder):
    journal = folder / '_diagnostics' / 'publication.json'
    if not journal.exists():
        return
    transaction = json.loads(journal.read_text(encoding='utf-8'))
    paths = {key: folder / transaction[key] for key in ('relative', 'stage')}
    if transaction.get('backup'):
        paths['backup'] = folder / transaction['backup']
    if any(not path.resolve().is_relative_to(folder.resolve()) for path in paths.values()):
        raise ValueError('Publication journal contains a path outside its package')
    target = paths['relative']
    manifest_path = folder / 'listening_manifest.json'
    state = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {'files': {}}
    actual = _digest(target) if target.exists() else None
    recorded = state.get('files', {}).get(transaction['relative'], {}).get('sha256')
    if actual == transaction['new_sha256'] and recorded == actual:
        pass  # Both output and ownership were committed; cleanup was interrupted.
    elif actual in (None, transaction['new_sha256'], transaction.get('old_sha256')):
        if 'backup' in paths and paths['backup'].exists():
            os.replace(paths['backup'], target)
        elif transaction.get('old_sha256') is None and target.exists():
            target.unlink()
        elif actual != transaction.get('old_sha256'):
            raise ValueError('Interrupted publication has lost its rollback backup')
    else:
        raise ValueError(f'Interrupted publication target was subsequently edited: {target}')
    for key in ('stage', 'backup'):
        if key in paths and paths[key].exists():
            paths[key].unlink()
    journal.unlink()


def _manifest(folder):
    _recover_publication(folder)
    path = folder / 'listening_manifest.json'
    if not path.exists():
        return dict(schema='tx802-listening-v1', files={})
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema') != 'tx802-listening-v1' or not isinstance(data.get('files'), dict):
        raise ValueError(f'Unrecognized TX802 listening manifest: {path}')
    return data


def _publish(folder, relative, data, manifest, force, source=None):
    target = folder / relative
    if not target.resolve().is_relative_to(folder.resolve()):
        raise ValueError(f'Output escapes its package through a link: {target}')
    old_entry = manifest['files'].get(relative)
    old_sha = None
    if target.exists():
        if not force:
            raise FileExistsError(f'Output exists; use --force: {target}')
        old_sha = _digest(target)
        if source is not None and old_entry is not None and old_entry.get('source') != str(source):
            raise ValueError(f'Output belongs to a different or unknown input source: {target}')
        if old_entry is None or old_sha != old_entry.get('sha256'):
            raise ValueError(f'Output is unowned or edited; preserve it or choose a new outdir: {target}')
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = backup = None
    journal = folder / '_diagnostics' / 'publication.json'
    if journal.exists():
        raise ValueError('Another or interrupted publication is pending; restart the export')
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.tx802_stage_', delete=False) as f:
            stage = Path(f.name)
            f.write(data)
        if target.exists():
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.tx802_backup_', delete=False) as f:
                backup = Path(f.name)
            shutil.copy2(target, backup)
        new_entry = dict(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
        if source is not None:
            new_entry['source'] = str(source)
        transaction = dict(relative=relative, stage=stage.relative_to(folder).as_posix(),
                           backup=backup.relative_to(folder).as_posix() if backup else None,
                           old_sha256=old_sha, new_sha256=new_entry['sha256'])
        journal.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=journal.parent,
                                         prefix='.tx802_journal_', delete=False) as f:
            journal_stage = Path(f.name)
            json.dump(transaction, f)
        os.replace(journal_stage, journal)
        os.replace(stage, target)
        manifest['files'][relative] = new_entry
        _write_manifest(folder, manifest)
        _recover_publication(folder)
        return str(target)
    except Exception:
        if old_entry is None:
            manifest['files'].pop(relative, None)
        else:
            manifest['files'][relative] = old_entry
        _recover_publication(folder)
        raise
    finally:
        # Keep journal-owned recovery material if the rollback could not complete.
        if not journal.exists():
            for path in (stage, backup):
                if path is not None and path.exists():
                    path.unlink()


def _write_manifest(folder, manifest):
    target = folder / 'listening_manifest.json'
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=folder,
                                     prefix='.tx802_manifest_', delete=False) as f:
        temporary = Path(f.name)
        json.dump(manifest, f, indent=2)
        f.write('\n')
    try:
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def convert_one(source, folder, *, force=False, debug=False, **options):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    stem = source.stem
    diag = folder / '_diagnostics' / stem
    diag.mkdir(parents=True, exist_ok=True)
    row = dict.fromkeys(FIELDS, '')
    row['source'] = str(source)
    products = []
    try:
        manifest = _manifest(folder)
    except (OSError, ValueError) as exc:
        row.update(status='publication_failed', detail=str(exc))
        return row
    published = set()
    def publish(relative, data):
        path = _publish(folder, relative, data, manifest, force, source=source)
        published.add(relative)
        manifest['files'][relative]['source'] = str(source)
        return path
    def cleanup_stale():
        if not force:
            return
        for relative, entry in list(manifest['files'].items()):
            name = Path(relative).name
            belongs = (relative in (f'voices/{stem}.texed.csv', f'tables/{stem}_voice.csv', f'tracks/{stem}.mid', f'tracks/{stem}.vgm', f'tracks/{stem}.user_voice_tx802.json') or
                       relative.startswith(f'voices/{stem}.') and relative.endswith('.syx') or
                       relative.startswith('blueprint/') and
                       (name in (f'{stem}.mml', f'{stem}.midi') or name.startswith(f'{stem}.part')))
            if entry.get('source') != str(source) or not belongs or relative in published:
                continue
            target = folder / relative
            if not target.resolve().is_relative_to(folder.resolve()):
                products.append(dict(product='stale_artifact', status='preserved', path=relative,
                                     detail='path escapes package'))
                continue
            if target.exists() and _digest(target) != entry.get('sha256'):
                products.append(dict(product='stale_artifact', status='preserved', path=relative,
                                     detail='user-modified artifact'))
                continue
            if target.exists():
                target.unlink()
            del manifest['files'][relative]
            products.append(dict(product='stale_artifact', status='removed', path=relative))
    try:
        performance = build_native_performance(source, diag, stem)
    except Exception as exc:
        row.update(status='conversion_failed', detail=f'{type(exc).__name__}: {exc}')
        cleanup_stale()
        _write_manifest(folder, manifest)
        (diag / f'{stem}.products.json').write_text(json.dumps(products, indent=2) + '\n', encoding='utf-8')
        return row
    # These projections do not depend on TX802 eligibility or compiler success.
    try:
        reference = diag / f'{stem}.reference.vgm'
        write_native_vgm(performance, reference, mapping_path=diag / f'{stem}.reference.mapping.csv')
        row['reference_vgm'] = publish(f'tracks/{stem}.vgm', reference.read_bytes())
        row['reference_status'] = 'success'
        products.append(dict(product='reference_vgm', status='success', path=row['reference_vgm']))
    except Exception as exc:
        row['reference_status'] = f'failed: {type(exc).__name__}: {exc}'
        products.append(dict(product='reference_vgm', status='failed', detail=f'{type(exc).__name__}: {exc}'))
    try:
        results = render_native_blueprints(performance, note_values=True)
        paths = []
        for index, (text, report) in enumerate(results):
            suffix = '' if len(results) == 1 else f'.part{index+1:02d}'
            name = stem + suffix
            # Blueprint remains an editable score; original curves stay in native dumps.
            paths.append(publish(f'blueprint/{name}.mml', text.encode('utf-8')))
            midi_data, midi_report = render_midi(report, stem)
            publish(f'blueprint/{name}.midi', midi_data)
            (diag / f'{name}.blueprint.midi.json').write_text(json.dumps(midi_report, indent=2) + '\n', encoding='utf-8')
            (diag / f'{name}.blueprint.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        row['blueprint'] = ';'.join(paths)
        row['blueprint_status'] = 'success'
        products.append(dict(product='blueprint', status='success', files=len(paths)))
    except Exception as exc:
        row['blueprint_status'] = f'failed: {type(exc).__name__}: {exc}'
        products.append(dict(product='blueprint', status='failed', detail=f'{type(exc).__name__}: {exc}'))
    projection = None
    map_path = options.pop('voice_map', None)
    texed_path = options.pop('texed', None)
    options.pop('target', None)
    template = folder / f'tracks/{stem}.user_voice_tx802.json'
    try:
        if map_path is not None and not Path(map_path).is_file():
            raise FileNotFoundError(f'Voice map does not exist: {map_path}')
        existing_voice_map = load_voice_map(map_path if map_path is not None else template)
        options['voice_map'] = existing_voice_map
        projection = project_tx802(performance, stem=stem, force=force, **options)
        projection.dump(diag, stem)
        if projection.user_voice_map:
            relative = f'tracks/{stem}.user_voice_tx802.json'
            owned = manifest['files'].get(relative, {})
            edited = template.exists() and _digest(template) != owned.get('sha256')
            if edited:
                published.add(relative)
                products.append(dict(product='voice_map', status='preserved_edited', path=str(template),
                                     proposed=str(diag/f'{stem}.user_voice_tx802.proposed.json')))
                row['voice_map'] = str(template)
            else:
                row['voice_map'] = publish(relative, (json.dumps(projection.user_voice_map, indent=2)+'\n').encode('utf-8'))
                products.append(dict(product='voice_map', status='success', path=row['voice_map']))
        row['voice_csv'] = publish(f'tables/{stem}_voice.csv', projection.voice_csv.encode('utf-8'))
        products.append(dict(product='voice_csv', status='success', path=row['voice_csv']))
        try:
            assets, asset_report = build_voice_assets(projection.voice_csv, diag/'voice_assets', stem, texed=texed_path)
            asset_paths=[publish(relative,data) for relative,data in assets.items()]
            row['voice_assets']=';'.join(asset_paths)
            row['voice_assets_status']='success'
            products.append(dict(product='voice_assets',status='success',files=len(asset_paths),
                                 parameter_fidelity=asset_report['parameter_fidelity']))
        except Exception as exc:
            row['voice_assets_status']=f'failed: {type(exc).__name__}: {exc}'
            products.append(dict(product='voice_assets',status='failed',detail=row['voice_assets_status']))
        row['midi'] = publish(f'tracks/{stem}.mid', projection.data)
        row.update(status='success', notes=projection.report['notes'],
                   channels=projection.report['channels'], bytes=len(projection.data))
        products.append(dict(product='tx802', status='success', path=row['midi']))
        if debug:
            print(json.dumps(projection.report, indent=2))
    except Exception as exc:
        row.update(status='publication_failed' if projection is not None else 'conversion_failed', detail=f'{type(exc).__name__}: {exc}')
        products.append(dict(product='tx802', status='failed', detail=row['detail']))
        (diag / f'{stem}.tx802.projection.json').write_text(
            json.dumps(dict(status='failed', detail=row['detail'], source_sha256=performance.source_sha256), indent=2) + '\n', encoding='utf-8')
    cleanup_stale()
    (diag / f'{stem}.products.json').write_text(json.dumps(products, indent=2) + '\n', encoding='utf-8')
    _write_manifest(folder, manifest)
    return row


def run_batch(source, outdir=None, **options):
    source = Path(source).resolve()
    if not source.exists():
        raise FileNotFoundError(f'Input does not exist: {source}')
    if source.is_file():
        if source.suffix.lower() not in ('.vgm', '.vgz'):
            raise ValueError('Input must be VGM or VGZ')
        sources = [source]
    else:
        def is_source(path):
            if not path.is_file() or path.suffix.lower() not in ('.vgm', '.vgz'):
                return False
            relative = path.relative_to(source)
            if '_diagnostics' in relative.parts or '_source_inputs' in relative.parts:
                return False
            for parent in path.parents:
                if parent == source.parent:
                    break
                if parent.name in ('tracks', 'blueprint', 'vgm-variants') and (parent.parent / 'listening_manifest.json').exists():
                    return False
            return True
        sources = sorted(p for p in source.rglob('*') if is_source(p))
        if outdir:
            output = Path(outdir).resolve()
            if output != source and output.is_relative_to(source):
                sources = [p for p in sources if not p.is_relative_to(output)]
    rows, packages = [], {}
    # Reject same-stem case collisions before publishing either source.
    destinations = set()
    jobs = []
    for path in sources:
        relative = path.parent.relative_to(source) if source.is_dir() else Path()
        folder = Path(outdir).resolve() / relative if outdir else path.parent
        key = str(folder).casefold(), path.stem.casefold()
        if key in destinations:
            raise ValueError(f'Multiple inputs would overwrite the same output stem: {path}')
        destinations.add(key)
        jobs.append((path, folder))
    for path, folder in jobs:
        row = convert_one(path, folder, **options)
        rows.append(row)
        packages.setdefault(folder, []).append(row)
        detail = ': ' + row['detail'] if row['detail'] else ''
        warnings = [row[k] for k in ('reference_status', 'blueprint_status', 'voice_map', 'voice_csv', 'voice_assets', 'voice_assets_status') if row[k].startswith('failed:')]
        if warnings:
            detail += '; source products: ' + '; '.join(warnings)
        print(f"{path.name}: {row['status']}{detail}", flush=True)
    for folder, group in packages.items():
        diag = folder / '_diagnostics'
        diag.mkdir(parents=True, exist_ok=True)
        with (diag / 'results.csv').open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(group)
    return rows


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    options = vars(args).copy()
    source, output = options.pop('input'), options.pop('outdir')
    try:
        rows = run_batch(source, output, **options)
    except (ValueError, OSError) as exc:
        p.error(str(exc))
    success = sum(row['status'] == 'success' for row in rows)
    print(f'{success}/{len(rows)} exported')
    return 0 if rows and success == len(rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())
