#!/usr/bin/env python3
"""Export an experimental rhythm-only FM audition with verified voice assets."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'py'))
from native_source_music import build_native_performance
from opll_rhythm_context import dump_opll_rhythm_context
from tx802_rhythm_target import load_rhythm_profile, project_rhythm
from tx802_voice_assets import build_voice_assets


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',type=Path)
    p.add_argument('--outdir',type=Path,required=True,help='New or empty output folder')
    p.add_argument('--presets',type=Path,default=ROOT/'data/tx802/OPLL_DX7II_rhythm.csv')
    p.add_argument('--texed',type=Path,default=ROOT.parent/'texed')
    a=p.parse_args()
    if not a.input.is_file():p.error('input must be one VGM/VGZ file')
    if a.outdir.exists() and any(a.outdir.iterdir()):p.error('Use a new or empty --outdir to preserve existing experiments')
    profiles=load_rhythm_profile(a.presets)
    out=a.outdir.resolve();out.mkdir(parents=True,exist_ok=True);stem=a.input.stem
    native=build_native_performance(a.input.resolve(),out/'native',stem)
    dump_opll_rhythm_context(native,out/(stem+'.rhythm.context.csv'),tail_samples=35280)
    projected=project_rhythm(native,profiles);projected.dump(out,stem)
    print(f'{stem}: {projected.report["notes"]} FM rhythm notes; melodic events remain in native analysis')
    try:
        products,report=build_voice_assets(a.presets.read_text(encoding='utf-8'),out/'voice_diagnostics',stem,texed=a.texed.resolve())
        for relative,data in products.items():
            target=out/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    except Exception as exc:
        (out/'voice_assets_status.json').write_text(json.dumps(dict(status='failed',detail=str(exc)),indent=2)+'\n',encoding='utf-8')
        print(f'Voice asset validation failed; MIDI/native evidence retained: {exc}',file=sys.stderr)
        return 1
    (out/'voice_assets_status.json').write_text(json.dumps(dict(status=report['status'],actual_slots=report['actual_slots']),indent=2)+'\n',encoding='utf-8')
    print(f'Voice assets: {report["status"]}')
    return 0


if __name__=='__main__':raise SystemExit(main())
