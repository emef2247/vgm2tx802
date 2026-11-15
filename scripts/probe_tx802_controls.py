#!/usr/bin/env python3
"""Controlled OPLL/DX7II rate-scaling and source-VIB ablation experiment."""
import argparse,csv,hashlib,itertools,json,math,re,struct,subprocess
from pathlib import Path
import numpy as np
import calibrate_tx802_presets as cal
import explore_tx802_presets as explore


def decode_rom_word(word):
    def bit(n):return (word>>n)&1
    patch=[(bit(51)<<7)|(bit(49)<<6)|(bit(47)<<5)|(bit(45)<<4)|((word>>40)&15),
           (bit(50)<<7)|(bit(48)<<6)|(bit(46)<<5)|(bit(44)<<4)|((word>>36)&15),
           (((word>>34)&3)<<6)|((word>>57)&63),
           (((word>>32)&3)<<6)|(bit(56)<<4)|(bit(55)<<3)|((word>>52)&7),
           (((word>>28)&15)<<4)|((word>>20)&15),(((word>>24)&15)<<4)|((word>>16)&15),
           (((word>>12)&15)<<4)|((word>>4)&15),(((word>>8)&15)<<4)|(word&15)]
    return bytes(patch)


def load_rom_patch(path,preset):
    source=path.read_text()
    match=re.search(r"6'h%02X: mem_q <= 63'b([01_]+)"%preset,source,re.IGNORECASE)
    if not match:raise ValueError('No scoped INSTROM_STYLE0 YM2413 entry')
    return decode_rom_word(int(match.group(1).replace('_',''),2))


def custom_reference(case,patch,root,sim,label):
    data=bytearray(Path(case['source']).read_bytes());start=0x34+struct.unpack_from('<I',data,0x34)[0]
    commands=data[start:]
    if commands[:2]!=bytes((0x51,0x30)):raise ValueError('Unexpected authored source setup')
    commands[2]=0
    setup=b''.join(bytes((0x51,i,value)) for i,value in enumerate(patch))
    data=data[:start]+setup+commands;struct.pack_into('<I',data,4,len(data)-4)
    identity=case['id']+'_'+label;vgm=root/(identity+'.vgm');wav=root/(identity+'.wav');vgm.write_bytes(data)
    result=subprocess.run([str(sim),str(vgm),'--output',str(wav),'--sample-rate',str(cal.RATE)],capture_output=True,text=True)
    (root/(identity+'.log')).write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError('Custom reference render failed')
    return dict(case,id=identity,file=str(wav),source=str(vgm))


def temporal_features(path,case):
    data=cal.audio(path,round((case['gate']+.5)*cal.RATE));gate=case['gate']
    # Windows follow source onset/hold/release, never a target-selected loud region.
    windows=[('attack',.1,.1+min(.08,gate/2))]
    if gate>=.2:
        for name,fraction in (('early',.25),('middle',.5),('late',.85)):
            width=min(.08,gate/3);center=.1+gate*fraction
            windows.append((name,center-width/2,center+width/2))
    windows.append(('release',.1+gate,.1+gate+.15))
    rows=[]
    for name,left,right in windows:
        section=data[round(left*cal.RATE):round(right*cal.RATE)]
        size=32768;power=np.abs(np.fft.rfft(section*np.hanning(len(section)),n=size))**2
        hz=np.fft.rfftfreq(size,1/cal.RATE)
        amplitudes=np.array([math.sqrt(float(power[np.abs(hz-case['hz']*.5*n)<max(8,case['hz']*.012)].sum())) for n in range(1,17)])
        rows.append(dict(section=name,start=left,stop=right,rms=float(np.sqrt(np.mean(section**2))),partials=amplitudes/max(amplitudes.sum(),1e-12)))
    return rows


def temporal_distance(target,reference,gain):
    if [r['section'] for r in target]!=[r['section'] for r in reference]:raise ValueError('Different musical windows')
    rows=[]
    for t,s in zip(target,reference):
        ratio=20*math.log10(max(t['rms']*gain,1e-12)/max(s['rms'],1e-12))
        spectrum=16*float(np.mean((t['partials']-s['partials'])**2))
        rows.append(dict(section=s['section'],source_rms=s['rms'],target_rms=t['rms']*gain,level_delta_db=ratio,temporal_spectrum=spectrum,
                         source_partials=' '.join(f'{x:.7f}' for x in s['partials']),target_partials=' '.join(f'{x:.7f}' for x in t['partials'])))
    return rows


def phase_track(path,case):
    data=cal.audio(path,round((case['gate']+.5)*cal.RATE));width=round(.06*cal.RATE)
    centers=np.arange(.35,.1+case['gate']-.05,.01);phase=[]
    for center in centers:
        lo=round(center*cal.RATE)-width//2;section=data[lo:lo+width]
        time=(np.arange(width)+lo)/cal.RATE
        phase.append(np.angle(np.dot(section*np.hanning(width),np.exp(-2j*np.pi*case['hz']*time))))
    delta=np.gradient(np.unwrap(phase),centers)/(2*np.pi)
    cents=1200*np.log2(np.maximum(case['hz']+delta,1e-9)/case['hz'])
    return centers,cents


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--outdir',type=Path,required=True)
    p.add_argument('--presets',type=Path,default=cal.ROOT/'data/tx802/OPLL_DX7II_presets.csv')
    p.add_argument('--texed',type=Path,default=cal.ROOT.parent/'texed')
    p.add_argument('--ikaopll',type=Path,default=cal.ROOT.parent/'IKAOPLL-verilator/build/obj_dir/ikaopll_sim')
    p.add_argument('--rtl-registers',type=Path,default=cal.ROOT.parent/'IKAOPLL-verilator/rtl/IKAOPLL_modules/IKAOPLL_reg.v')
    a=p.parse_args();out=a.outdir.resolve();out.mkdir(parents=True,exist_ok=True)
    source=out/'source';source.mkdir(exist_ok=True);packets=out/'packets';packets.mkdir(exist_ok=True);waves=out/'waves';waves.mkdir(exist_ok=True)
    rows=[explore.numeric(r) for r in csv.DictReader(a.presets.open())];seed=rows[9]
    gain=json.loads((cal.ROOT/'data/tx802/OPLL_DX7II_calibration.json').read_text())['gain_anchor']['correction']
    config=dict(preset=10,input_sha256=hashlib.sha256(a.presets.read_bytes()).hexdigest(),training_notes=[57,69,81],training_gates=[.25,.9],
        reserved_notes=[62,78],reserved_gates=[.18,1.2],selection='old composite mean+0.25*worst; temporal features are diagnostics only',
        topology_fixed=True,modulator_rate_offsets=[-8,-4,0,4],modulator_RS=[0,1,2,3],gain_correction=gain,
        temporal_windows='attack80ms, early/middle/late hold80ms when gate>=200ms, release150ms',
        model='Texed Modern DX7II proxy; not complete TX802',source_time_hz=44100,output_rate=cal.RATE,tail_seconds=.4,
        rtl_source_sha256=hashlib.sha256(a.rtl_registers.read_bytes()).hexdigest())
    (out/'configuration.json').write_text(json.dumps(config,indent=2)+'\n')
    print('Source VIB ablation and exact-custom reference control',flush=True)
    long_case=cal.source_case(source,a.ikaopll.resolve(),10,69,2.4)
    patch=load_rom_patch(a.rtl_registers,10)
    exact=custom_reference(long_case,patch,source,a.ikaopll.resolve(),'custom_exact')
    muted=bytes((v&0x3f) if i<2 else v for i,v in enumerate(patch))
    no_vib=custom_reference(long_case,muted,source,a.ikaopll.resolve(),'custom_no_am_vib')
    original=cal.audio(long_case['file']);custom=cal.audio(exact['file'])
    rms=lambda x:float(np.sqrt(np.mean(x*x)))
    equivalence=rms(original-custom)/max(rms(original),1e-12)
    if equivalence>1e-3:raise ValueError(f'ROM/custom control mismatch: relative RMS {equivalence}')
    phase=[];phase_stats={}
    for role,case in [('original',long_case),('no_am_vib',no_vib)]:
        times,cents=phase_track(case['file'],case);phase_stats[role]=dict(mean_cents=float(cents.mean()),std_cents=float(cents.std()))
        phase.extend(dict(role=role,time_seconds=float(t),baseband_phase_cents=float(c)) for t,c in zip(times,cents))
    cal.write_csv(out/'source_phase.csv',phase,list(phase[0]))
    ablation=dict(exact_custom_relative_waveform_error=equivalence,original_patch=list(patch),ablated_patch=list(muted),AM_originally_enabled=bool((patch[0]|patch[1])&0x80),phase_diagnostics=phase_stats,
                  phase_method='local fundamental complex demodulation; timbre-dependent estimate, not absolute pitch proof')
    (out/'source_ablation.json').write_text(json.dumps(ablation,indent=2)+'\n')
    print(json.dumps(ablation,indent=2),flush=True)
    cases=[cal.source_case(source,a.ikaopll.resolve(),10,n,g) for n in config['training_notes'] for g in config['training_gates']]
    reference={c['id']:cal.features(c['file'],c) for c in cases};temporal_ref={c['id']:temporal_features(c['file'],c) for c in cases}
    candidates={};groups={}
    for rs,offset in itertools.product(config['modulator_RS'],config['modulator_rate_offsets']):
        row=dict(seed)
        for op in (2,4,6):
            row[f'OP{op}_RS']=rs
            for rate in range(1,5):row[f'OP{op}_R{rate}']=max(0,min(99,row[f'OP{op}_R{rate}']+offset))
        identity=f'rs{rs}_offset{offset:+d}';candidates[identity]=row
        groups[identity]='baseline' if rs==0 and offset==0 else 'offset_only' if rs==0 else 'RS_only' if offset==0 else 'combined'
    cal.write_csv(out/'candidate_parameters.csv',[dict(trial=k,group=groups[k],**v) for k,v in candidates.items()],['trial','group']+cal.FIELDS)
    def render(label,voices,probe_cases):
        report=out/(label+'.render.json');job=out/(label+'.job.json')
        job.write_text(json.dumps(dict(rate=cal.RATE,gain=.25,voices=voices,cases=probe_cases,output=str(waves),report=str(report)),indent=2)+'\n')
        subprocess.run(['npm','exec','--yes','--package=node@24','--','node',str(a.texed.resolve()/'texed-ts/node_modules/tsx/dist/cli.mjs'),str(cal.ROOT/'tools/texed_calibration_batch.mjs'),str(a.texed.resolve()),str(job)],cwd=a.texed/'texed-ts',check=True)
        return json.loads(report.read_text())['results']
    def measure(results,probe_cases,ref,tempref,phase):
        metrics=[];temporal=[];aggregates={}
        for identity in dict.fromkeys(r['voice'] for r in results):
            values=[];valid=True
            for case in probe_cases:
                item=next(r for r in results if r['voice']==identity and r['case']==case['id'])
                features=cal.features(item['file'],case);parts=explore.components(features,ref[case['id']],gain)
                contrast=explore.octave_contrast(explore.spectral_signature(item['file'],case),explore.spectral_signature(case['file'],case))
                valid=valid and contrast['ok'] and item['clipped']==0
                data=cal.audio(item['file']);tail=rms(data[-2400:])/max(features['rms'],1e-12)
                metrics.append(dict(phase=phase,trial=identity,group=groups[identity],case=case['id'],**parts,octave_ok=contrast['ok'],clipped=item['clipped'],tail_last50ms_ratio=tail))
                temporal.extend(dict(phase=phase,trial=identity,case=case['id'],**row) for row in temporal_distance(temporal_features(item['file'],case),tempref[case['id']],gain))
                values.append(parts['score'])
            aggregates[identity]=float(np.mean(values)+.25*max(values)) if valid else None
        return metrics,temporal,aggregates
    print('Controlled RS/offset grid:16 candidates x6 cases',flush=True)
    results=render('training',[cal.emit_voice(packets,key,row) for key,row in candidates.items()],cases)
    metrics,temporal,ranking=measure(results,cases,reference,temporal_ref,'training')
    eligible={k:v for k,v in ranking.items() if v is not None};best=min(eligible,key=eligible.get)
    selection=dict(best=best,baseline='rs0_offset+0',training_aggregates=ranking,validation_used_for_selection=False)
    (out/'selection.json').write_text(json.dumps(selection,indent=2)+'\n')
    cal.write_csv(out/'training_metrics.csv',metrics,list(metrics[0]));cal.write_csv(out/'temporal_metrics.csv',temporal,list(temporal[0]))
    print('Selected:',best,ranking[best],flush=True)
    valcases=[cal.source_case(source,a.ikaopll.resolve(),10,n,g) for n in config['reserved_notes'] for g in config['reserved_gates']]
    ref={c['id']:cal.features(c['file'],c) for c in valcases};tempref={c['id']:temporal_features(c['file'],c) for c in valcases}
    ids=list(dict.fromkeys(('rs0_offset+0',best)))
    results=render('reserved',[cal.emit_voice(packets,key,candidates[key]) for key in ids],valcases)
    vm,vt,va=measure(results,valcases,ref,tempref,'validation')
    cal.write_csv(out/'validation_metrics.csv',vm,list(vm[0]));cal.write_csv(out/'temporal_metrics.csv',temporal+vt,list(temporal[0]))
    rows[9]=candidates[best];cal.write_csv(out/'OPLL_DX7II_presets_candidate.csv',rows)
    summary=dict(configuration=config,source_ablation=ablation,selection=selection,reserved_aggregates=va,validation=vm,
                 candidate_changes={k:dict(before=seed[k],after=candidates[best][k]) for k in cal.FIELDS if seed[k]!=candidates[best][k]},
                 conclusion='Controlled model experiment, not sole-cause proof or hardware verification')
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2),flush=True)
if __name__=='__main__':main()
