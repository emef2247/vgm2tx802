#!/usr/bin/env python3
"""Broader reproducible ratio/envelope exploration for OPLL presets 7 and 10."""
import argparse,csv,hashlib,itertools,json,math,subprocess
from pathlib import Path
import numpy as np
import calibrate_tx802_presets as cal


def spectral_signature(path,case):
    data=cal.audio(path,round((.5+case['gate'])*cal.RATE))
    section=data[case['analysis_start']:case['analysis_stop']]
    size=32768;power=np.abs(np.fft.rfft(section*np.hanning(len(section)),n=size))**2
    hz=np.fft.rfftfreq(size,1/cal.RATE)
    # Half-base bins retain subharmonic evidence; sum nearby bins for vibrato tolerance.
    return np.array([power[np.abs(hz-case['hz']*.5*n)<max(10,case['hz']*.012)].sum() for n in range(1,65)])


def octave_contrast(target,reference):
    def similarity(left,right):
        a=np.sqrt(left);b=np.sqrt(right)
        return float(np.dot(a,b)/max(1e-15,np.linalg.norm(a)*np.linalg.norm(b)))
    same=similarity(target,reference)
    # Compare within the same source bandwidth; target shifted up/down by one octave.
    lower=similarity(np.ravel(np.column_stack((np.zeros(32),target[:32]))),reference)
    upper=similarity(np.pad(target[1::2],(0,32)),reference)
    return dict(same=same,half=lower,double=upper,ok=same+0.08>=max(lower,upper))


def components(target,reference,gain):
    total=cal.score(target,reference,gain)
    amplitude=.5*math.log2(max(1e-12,target['rms']*gain/reference['rms']))**2
    spectrum=16*float(np.mean((target['harmonics']-reference['harmonics'])**2))
    envelope=float(np.mean((target['envelope']/max(target['rms'],1e-12)-reference['envelope']/reference['rms'])**2))
    return dict(score=total,amplitude=amplitude,spectrum=spectrum,envelope=envelope)


def numeric(row):
    return {k:(v if k=='name' else int(v)) for k,v in row.items()}


def structures(seed):
    for ratio,feedback,mix in itertools.product((1,2,3,4),(0,3,5,7),(0,70,82)):
        row=dict(seed);row['FB']=feedback
        for car,mod,multiple in ((5,6,1),(3,4,2),(1,2,4)):
            row[f'OP{car}_COARSE']=multiple;row[f'OP{car}_FINE']=0;row[f'OP{car}_DT']=7
            row[f'OP{mod}_COARSE']=ratio;row[f'OP{mod}_FINE']=0;row[f'OP{mod}_DT']=7
            if car!=5:row[f'OP{car}_OL']=max(0,mix-(0 if car==3 else 12)) if mix else 0
            row[f'OP{mod}_OL']=seed['OP6_OL']
        yield row
    for ratio in (1,2,3,4):
        for feedback in (0,5):
            row=dict(seed);row['FB']=feedback
            for car,mod,multiple in ((5,6,1),(3,4,3),(1,2,5)):
                row[f'OP{car}_COARSE']=multiple;row[f'OP{mod}_COARSE']=ratio
                if car!=5:row[f'OP{car}_OL']=76 if car==3 else 64
                row[f'OP{mod}_OL']=seed['OP6_OL']
            yield row


def envelopes(parents):
    profiles=((48,35,90,90),(64,60,75,75),(80,80,50,50),(99,99,0,0),(99,40,95,95),(64,70,95,0),(80,40,60,0))
    for parent in parents:
        for attack,decay,sustain,held in profiles:
            row=dict(parent)
            for op in (2,4,6):
                for field,value in dict(R1=attack,R2=decay,L2=sustain,L3=held).items():row[f'OP{op}_{field}']=value
            yield row
        for attack,release in itertools.product((52,76,99),(40,60,80)):
            row=dict(parent)
            for op in (1,3,5):row[f'OP{op}_R1']=attack;row[f'OP{op}_R4']=release
            yield row


def levels(parents):
    for parent in parents:
        for carrier,modulator in itertools.product((-12,-6,0,6),(-20,-10,0,10,20)):
            row=dict(parent)
            for op in (1,3,5):
                if row[f'OP{op}_OL']:row[f'OP{op}_OL']=max(0,min(99,row[f'OP{op}_OL']+carrier))
            for op in (2,4,6):row[f'OP{op}_OL']=max(0,min(99,row[f'OP{op}_OL']+modulator))
            yield row


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--outdir',type=Path,required=True)
    p.add_argument('--texed',type=Path,default=cal.ROOT.parent/'texed')
    p.add_argument('--ikaopll',type=Path,default=cal.ROOT.parent/'IKAOPLL-verilator/build/obj_dir/ikaopll_sim')
    a=p.parse_args();out=a.outdir.resolve();out.mkdir(parents=True,exist_ok=True)
    dirs={key:out/key for key in ('source','packets','waves')}
    for path in dirs.values():path.mkdir(exist_ok=True)
    preset=cal.ROOT/'data/tx802/OPLL_DX7II_presets.csv';all_rows=[numeric(r) for r in csv.DictReader(preset.open())]
    gain=json.loads((cal.ROOT/'data/tx802/OPLL_DX7II_calibration.json').read_text())['gain_anchor']['correction']
    config=dict(input_sha256=hashlib.sha256(preset.read_bytes()).hexdigest(),presets=[7,10],training_notes=[57,69,81],training_gates=[.25,.9],
        reserved_validation_notes=[60,72],reserved_validation_gates=[.4,.7],gain_correction=gain,
        objective='mean composite + 0.25 * worst case composite',seed_floor=False,beam=3,
        structure='ALG4; main carrier ratio1; secondary ratios2/4 or3/5; integer modulators1/2/3/4; fixed fine0/detune7',
        octave_guard='source-relative spectral contrast; same +0.08 >= best octave-shift similarity; conservative screen, not absolute pitch proof')
    (out/'configuration.json').write_text(json.dumps(config,indent=2)+'\n')
    metrics=[];trials=[];selections={};validation=[]
    def render(label,voices,cases):
        report=out/(label+'.render.json');job=out/(label+'.job.json')
        job.write_text(json.dumps(dict(rate=cal.RATE,gain=.25,voices=voices,cases=cases,output=str(dirs['waves']),report=str(report)),indent=2)+'\n')
        subprocess.run(['npm','exec','--yes','--package=node@24','--','node',str(a.texed.resolve()/'texed-ts/node_modules/tsx/dist/cli.mjs'),str(cal.ROOT/'tools/texed_calibration_batch.mjs'),str(a.texed.resolve()),str(job)],cwd=a.texed/'texed-ts',check=True)
        return json.loads(report.read_text())['results']
    for preset_number in (7,10):
        seed=all_rows[preset_number-1]
        cases=[cal.source_case(dirs['source'],a.ikaopll.resolve(),preset_number,n,g) for n in config['training_notes'] for g in config['training_gates']]
        refs={c['id']:cal.features(c['file'],c) for c in cases}
        signatures={c['id']:spectral_signature(c['file'],c) for c in cases}
        candidates={};ranking={};seen={}
        def evaluate(stage,rows):
            voices=[];ids=[]
            for row in rows:
                key=json.dumps(row,sort_keys=True)
                if key in seen:continue
                identity=f'p{preset_number:02d}_{stage}_{len(candidates):04d}'
                candidates[identity]=dict(row);seen[key]=identity;ids.append(identity)
                voices.append(cal.emit_voice(dirs['packets'],identity,row));trials.append(dict(trial=identity,stage=stage,**row))
            if not voices:return
            print(f'preset{preset_number} {stage}: {len(voices)} new candidates x{len(cases)} cases',flush=True)
            results=render(f'p{preset_number:02d}_{stage}',voices,cases)
            for identity in ids:
                values=[];valid=True
                for case in cases:
                    item=next(x for x in results if x['voice']==identity and x['case']==case['id'])
                    target=cal.features(item['file'],case);parts=components(target,refs[case['id']],gain)
                    contrast=octave_contrast(spectral_signature(item['file'],case),signatures[case['id']])
                    # All candidates keep the primary1:1 carrier; screen severe octave mismatches.
                    valid=valid and contrast['ok'] and item['clipped']==0
                    metrics.append(dict(preset=preset_number,trial=identity,stage=stage,case=case['id'],**parts,
                        octave_same=contrast['same'],octave_half=contrast['half'],octave_double=contrast['double'],octave_ok=contrast['ok'],file=item['file']))
                    values.append(parts['score'])
                aggregate=float(np.mean(values)+.25*max(values));ranking[identity]=(aggregate if valid else float('inf'))
            cal.write_csv(out/'trials.csv',trials,['trial','stage']+cal.FIELDS)
            cal.write_csv(out/'training_metrics.csv',metrics,list(metrics[0]))
            print(f'preset{preset_number} {stage}: best={min(ranking.values()):.6f}',flush=True)
        evaluate('seed',[seed]);seed_id=next(iter(candidates))
        evaluate('structure',structures(seed))
        parents=lambda:[candidates[i] for i in sorted(ranking,key=ranking.get)[:3] if math.isfinite(ranking[i])]
        if not parents():raise ValueError('No octave-consistent structure survived')
        evaluate('envelope',envelopes(parents()))
        evaluate('level',levels(parents()))
        best=min(ranking,key=ranking.get);chosen=candidates[best];all_rows[preset_number-1]=chosen
        baseline_cases=[m for m in metrics if m['trial']==seed_id];best_cases=[m for m in metrics if m['trial']==best]
        changes={k:dict(seed=seed[k],selected=chosen[k]) for k in cal.FIELDS if seed[k]!=chosen[k]}
        selections[preset_number]=dict(trial=best,seed_trial=seed_id,seed_aggregate=ranking[seed_id],selected_aggregate=ranking[best],changes=changes,
            worst_case_delta=max(b['score']-s['score'] for s,b in zip(baseline_cases,best_cases)),candidates=len(candidates))
        print(f'preset{preset_number}: {ranking[seed_id]:.6f} -> {ranking[best]:.6f}, {len(changes)} changed parameters',flush=True)
        # Freeze selection before rendering the reserved validation sources.
        (out/'selection.json').write_text(json.dumps(selections,indent=2,allow_nan=False)+'\n')
        valcases=[cal.source_case(dirs['source'],a.ikaopll.resolve(),preset_number,n,g) for n in config['reserved_validation_notes'] for g in config['reserved_validation_gates']]
        valrefs={c['id']:cal.features(c['file'],c) for c in valcases}
        valsignatures={c['id']:spectral_signature(c['file'],c) for c in valcases}
        results=render(f'p{preset_number:02d}_validation',[cal.emit_voice(dirs['packets'],identity,candidates[identity]) for identity in dict.fromkeys((seed_id,best))],valcases)
        for identity in dict.fromkeys((seed_id,best)):
            for case in valcases:
                item=next(x for x in results if x['voice']==identity and x['case']==case['id'])
                parts=components(cal.features(item['file'],case),valrefs[case['id']],gain)
                contrast=octave_contrast(spectral_signature(item['file'],case),valsignatures[case['id']])
                validation.append(dict(preset=preset_number,trial=identity,role='seed' if identity==seed_id else 'selected',case=case['id'],**parts,
                    octave_ok=contrast['ok'],octave_same=contrast['same'],octave_half=contrast['half'],octave_double=contrast['double'],file=item['file']))
        cal.write_csv(out/'validation_metrics.csv',validation,list(validation[0]))
        cal.write_csv(out/'OPLL_DX7II_presets.csv',all_rows)
    summary=dict(configuration=config,selected=selections,validation_used_for_selection=False,validation=validation)
    (out/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    print(json.dumps(selections,indent=2,allow_nan=False),flush=True)
if __name__=='__main__':main()
