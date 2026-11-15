#!/usr/bin/env python3
"""Read-only fixture validation of an explicit DX7II calibration CSV."""
import argparse,csv,json,math,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'py'),str(ROOT/'scripts')]
from native_source_music import build_native_performance
from tx802_target import project_tx802
from tx802_voice_assets import build_voice_assets

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',type=Path,nargs='+');p.add_argument('--presets',type=Path,required=True)
    p.add_argument('--outdir',type=Path,required=True);p.add_argument('--gain',type=float,required=True)
    p.add_argument('--texed',type=Path,default=ROOT.parent/'texed')
    p.add_argument('--ikaopll',type=Path,default=ROOT.parent/'IKAOPLL-verilator/build/obj_dir/ikaopll_sim')
    a=p.parse_args();out=a.outdir.resolve();out.mkdir(parents=True,exist_ok=True)
    text=a.presets.read_text();rows=list(csv.DictReader(text.splitlines()))
    mapping={int(row['source_preset']):dict(bank='I',voice=int(row['voice'])) for row in rows}
    assets,report=build_voice_assets(text,out/'profile_diagnostics','profile',texed=a.texed)
    for relative,data in assets.items():
        file=out/relative;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(data)
    results=[]
    for source in a.input:
        source=source.resolve();folder=out/source.stem;folder.mkdir(parents=True,exist_ok=True)
        print(f'{source.name}: analyzing',flush=True)
        try:
            native=build_native_performance(source,folder/'native',source.stem)
            if native.percussion:raise ValueError('Melody-only calibration excludes active rhythm')
            target=project_tx802(native,stem=source.stem,preset_voice_map=mapping,tx802_units=2,domino_init=False,force=True)
            available={('I',int(row['voice'])) for row in rows}
            if any((value['bank'],value['voice']) not in available for value in target.report['voice_selections'].values()):
                raise ValueError('Input uses custom voices outside the preset calibration')
            target.dump(folder,source.stem);midi=folder/(source.stem+'.mid');midi.write_bytes(target.data)
            subprocess.run([str(a.ikaopll.resolve()),str(source),'--output',str(folder/'opll.wav'),'--sample-rate','48000'],check=True,stdout=(folder/'opll.log').open('w'),stderr=subprocess.STDOUT)
            # Main host pans stereo; keep the measured mono probe scale after downmix.
            center=(math.cos(64/127*math.pi/2)+math.sin(64/127*math.pi/2))/2
            subprocess.run([sys.executable,str(ROOT/'scripts/render_tx802.py'),str(midi),'--out',str(folder/'dx7ii.wav'),
                '--voices',str(out/'voices/profile.texed.csv'),'--texed',str(a.texed.resolve()),'--gain',str(a.gain/center)],check=True)
            render=json.loads((folder/'dx7ii.wav.render.json').read_text())
            results.append(dict(source=str(source),status='rendered',notes=target.report['notes'],omitted=target.report['omitted'],losses=target.report['losses'],peak=render['peak'],clipped=render['clipped']))
            print(f'{source.name}: both WAVs rendered',flush=True)
        except Exception as exc:
            results.append(dict(source=str(source),status='not_rendered',detail=f'{type(exc).__name__}: {exc}'))
            print(f'{source.name}: {exc}',flush=True)
        (out/'validation.json').write_text(json.dumps(results,indent=2)+'\n')
    return 0 if all(r['status']=='rendered' for r in results) else 1
if __name__=='__main__':raise SystemExit(main())
