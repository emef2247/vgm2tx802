#!/usr/bin/env python3
"""Fit DX7II LFO against paired source-VIB phase tracks, preserving other fields."""
import argparse,csv,hashlib,itertools,json,math,subprocess
from pathlib import Path
import numpy as np
import calibrate_tx802_presets as cal
import explore_tx802_presets as explore
import probe_tx802_controls as probe


def descriptor(times,cents):
    if len(times)<40 or times[-1]-times[0]<.5 or not np.all(np.isfinite(cents)):
        raise ValueError('Need a complete finite phase track of at least0.5s')
    centered=np.asarray(cents)-np.mean(cents);std=float(np.std(centered))
    if std<1e-6:return dict(frequency_hz=0.,std_cents=std,harmonic_amplitudes=[0.]*4,fit_residual=0.)
    trials=[]
    for hz in np.arange(2.,12.001,.025):
        basis=np.column_stack((np.sin(2*np.pi*hz*times),np.cos(2*np.pi*hz*times),np.ones(len(times))))
        coefficients=np.linalg.lstsq(basis,centered,rcond=None)[0]
        trials.append((float(np.mean((basis@coefficients-centered)**2)),float(hz)))
    residual,hz=min(trials);basis=np.column_stack([function(2*np.pi*hz*multiple*times) for multiple in range(1,5) for function in (np.sin,np.cos)]+[np.ones(len(times))])
    coefficients=np.linalg.lstsq(basis,centered,rcond=None)[0]
    amplitudes=[float(np.hypot(coefficients[i*2],coefficients[i*2+1])) for i in range(4)]
    return dict(frequency_hz=hz,std_cents=std,harmonic_amplitudes=amplitudes,fit_residual=residual)


def distance(target,source):
    if target['std_cents']<1e-6:return 1e6
    frequency=((target['frequency_hz']-source['frequency_hz'])/.25)**2
    depth=4*math.log2(target['std_cents']/source['std_cents'])**2
    shape=float(np.mean(((np.array(target['harmonic_amplitudes'])-np.array(source['harmonic_amplitudes']))/source['std_cents'])**2))
    return frequency+depth+shape


def without_vibrato(patch):
    return bytes(v&0xbf if i<2 else v for i,v in enumerate(patch))


def eligible_score(measured,source,clipped):
    value=distance(measured,source)
    return value if clipped==0 and math.isfinite(value) and value<1e6 else None


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--outdir',type=Path,required=True)
    p.add_argument('--presets',type=Path,default=cal.ROOT/'data/tx802/OPLL_DX7II_presets.csv')
    p.add_argument('--fine-depth',action='store_true',help='Refine training depth before reserved validation')
    p.add_argument('--validation-notes',type=int,nargs=2,default=[67,83])
    p.add_argument('--validation-gates',type=float,nargs=2,default=[.33,.95])
    p.add_argument('--texed',type=Path,default=cal.ROOT.parent/'texed')
    p.add_argument('--ikaopll',type=Path,default=cal.ROOT.parent/'IKAOPLL-verilator/build/obj_dir/ikaopll_sim')
    p.add_argument('--rtl-registers',type=Path,default=cal.ROOT.parent/'IKAOPLL-verilator/rtl/IKAOPLL_modules/IKAOPLL_reg.v')
    a=p.parse_args();out=a.outdir.resolve();out.mkdir(parents=True,exist_ok=True)
    paths={key:out/key for key in ('source','packets','waves')}
    for path in paths.values():path.mkdir(exist_ok=True)
    rows=[explore.numeric(r) for r in csv.DictReader(a.presets.open())];baseline=dict(rows[9]);baseline['LFO_PMD']=0;baseline['LFO_PMS']=0
    gain=json.loads((cal.ROOT/'data/tx802/OPLL_DX7II_calibration.json').read_text())['gain_anchor']['correction']
    config=dict(preset=10,input_sha256=hashlib.sha256(a.presets.read_bytes()).hexdigest(),training_note=69,training_gate=2.4,
        speeds=list(range(36,43)),waves=[0,4],PMS1_depths=[16,20,24,28,32],PMS2_depths=[8,10,12,14,16],
        selection='source-relative isolated VIB descriptor: frequency error/0.25Hz squared +4*log2 depth ratio squared + normalized harmonic error',
        reserved_notes=a.validation_notes,reserved_gates=a.validation_gates,fine_depth=a.fine_depth,gain_correction=gain,phase_alignment='phase-invariant descriptors; no global LFO-phase equivalence claimed',
        changed_fields=['LFO_SPEED','LFO_WAVE','LFO_PMD','LFO_PMS','LFO_DELAY','LFO_SYNC'],other_voice_fields_fixed=True)
    (out/'configuration.json').write_text(json.dumps(config,indent=2)+'\n')
    patch=probe.load_rom_patch(a.rtl_registers,10);no_vib_patch=without_vibrato(patch)
    case=cal.source_case(paths['source'],a.ikaopll.resolve(),10,69,2.4)
    exact=probe.custom_reference(case,patch,paths['source'],a.ikaopll.resolve(),'exact')
    if not np.array_equal(cal.audio(case['file']),cal.audio(exact['file'])):raise ValueError('Exact custom source differs')
    no_vib=probe.custom_reference(case,no_vib_patch,paths['source'],a.ikaopll.resolve(),'no_vib')
    times,on=probe.phase_track(case['file'],case);off_times,off=probe.phase_track(no_vib['file'],case)
    if not np.array_equal(times,off_times):raise ValueError('Source timing differs')
    source_descriptor=descriptor(times,on-off)
    candidates={};metrics=[];ranking={};seen={};all_phase=[]
    def render(label,voices,cases):
        report=out/(label+'.render.json');job=out/(label+'.job.json')
        job.write_text(json.dumps(dict(rate=cal.RATE,gain=.25,voices=voices,cases=cases,output=str(paths['waves']),report=str(report)),indent=2)+'\n')
        subprocess.run(['npm','exec','--yes','--package=node@24','--','node',str(a.texed.resolve()/'texed-ts/node_modules/tsx/dist/cli.mjs'),str(cal.ROOT/'tools/texed_calibration_batch.mjs'),str(a.texed.resolve()),str(job)],cwd=a.texed/'texed-ts',check=True)
        return json.loads(report.read_text())['results']
    base_render=render('baseline',[cal.emit_voice(paths['packets'],'baseline',baseline)],[case])[0]
    _,base_phase=probe.phase_track(base_render['file'],case)
    def evaluate(label,proposals):
        voices=[];ids=[]
        for row in proposals:
            key=json.dumps(row,sort_keys=True)
            if key in seen:continue
            identity=f'{label}_{len(candidates):03d}';seen[key]=identity;candidates[identity]=row;ids.append(identity)
            voices.append(cal.emit_voice(paths['packets'],identity,row))
        print(f'{label}: {len(voices)} candidates',flush=True)
        results=render(label,voices,[case])
        for identity in ids:
            item=next(x for x in results if x['voice']==identity);t,phase=probe.phase_track(item['file'],case)
            measured=descriptor(t,phase-base_phase);score=distance(measured,source_descriptor)
            eligible=eligible_score(measured,source_descriptor,item['clipped'])
            if eligible is not None:ranking[identity]=eligible
            metrics.append(dict(trial=identity,stage=label,score=score,**measured,clipped=item['clipped'],selection_eligible=eligible is not None))
            all_phase.extend(dict(trial=identity,time_seconds=float(x),isolated_cents=float(y)) for x,y in zip(t,phase-base_phase))
        cal.write_csv(out/'trials.csv',[dict(trial=k,**v) for k,v in candidates.items()],['trial']+cal.FIELDS)
        (out/'training_metrics.json').write_text(json.dumps(dict(source=source_descriptor,candidates=metrics),indent=2)+'\n')
        if not ranking:raise ValueError('No valid unclipped vibrato candidates')
        print(f'{label}: best={min(ranking.values()):.6f}',flush=True)
    proposals=[]
    for speed,wave in itertools.product(config['speeds'],config['waves']):
        row=dict(baseline,LFO_SPEED=speed,LFO_WAVE=wave,LFO_PMD=24,LFO_PMS=1,LFO_DELAY=0,LFO_SYNC=0);proposals.append(row)
    evaluate('speed',proposals)
    proposals=[]
    for identity in sorted(ranking,key=ranking.get)[:3]:
        for pms,depths in ((1,config['PMS1_depths']),(2,config['PMS2_depths'])):
            for depth in depths:proposals.append(dict(candidates[identity],LFO_PMS=pms,LFO_PMD=depth))
    evaluate('depth',proposals)
    if a.fine_depth:
        parent=candidates[min(ranking,key=ranking.get)]
        evaluate('fine',[dict(parent,LFO_PMD=depth) for depth in range(max(1,parent['LFO_PMD']-3),min(99,parent['LFO_PMD']+3)+1)])
    best=min(ranking,key=ranking.get);chosen=candidates[best]
    selection=dict(trial=best,score=ranking[best],source=source_descriptor,target=next(x for x in metrics if x['trial']==best),
        changes={k:dict(before=baseline[k],after=chosen[k]) for k in cal.FIELDS if baseline[k]!=chosen[k]},validation_used_for_selection=False)
    (out/'selection.json').write_text(json.dumps(selection,indent=2)+'\n')
    cal.write_csv(out/'training_phase.csv',all_phase,list(all_phase[0]))
    print('Selected',json.dumps(selection,indent=2),flush=True)
    # Selection is frozen before any reserved source render.
    valcases=[cal.source_case(paths['source'],a.ikaopll.resolve(),10,n,g) for n in config['reserved_notes'] for g in config['reserved_gates']]
    ablated={c['id']:probe.custom_reference(c,no_vib_patch,paths['source'],a.ikaopll.resolve(),'no_vib') for c in valcases}
    results=render('reserved',[cal.emit_voice(paths['packets'],'baseline',baseline),cal.emit_voice(paths['packets'],'selected',chosen)],valcases)
    validation=[];temporal=[]
    for c in valcases:
        ref=cal.features(c['file'],c);tempref=probe.temporal_features(c['file'],c)
        base=next(x for x in results if x['voice']=='baseline' and x['case']==c['id'])
        for role in ('baseline','selected'):
            item=next(x for x in results if x['voice']==role and x['case']==c['id'])
            parts=explore.components(cal.features(item['file'],c),ref,gain)
            contrast=explore.octave_contrast(explore.spectral_signature(item['file'],c),explore.spectral_signature(c['file'],c))
            row=dict(case=c['id'],role=role,**parts,clipped=item['clipped'],octave_ok=contrast['ok'])
            if c['gate']>=.8:
                t,source_on=probe.phase_track(c['file'],c);_,source_off=probe.phase_track(ablated[c['id']]['file'],c)
                _,target_on=probe.phase_track(item['file'],c);_,target_off=probe.phase_track(base['file'],c)
                sd=descriptor(t,source_on-source_off);td=descriptor(t,target_on-target_off)
                row.update(source_vibrato=sd,target_vibrato=td,vibrato_distance=distance(td,sd))
            validation.append(row)
            temporal.extend(dict(case=c['id'],role=role,**x) for x in probe.temporal_distance(probe.temporal_features(item['file'],c),tempref,gain))
    cal.write_csv(out/'temporal_validation.csv',temporal,list(temporal[0]));rows[9]=chosen
    cal.write_csv(out/'OPLL_DX7II_vibrato_candidate.csv',rows)
    summary=dict(configuration=config,selection=selection,validation=validation,limitations=['phase-invariant matching does not establish LFO start phase','local phase depends on timbre; paired source/target ablations used','DX7II proxy, no hardware audition','old composite and isolated vibrato distance are different objectives'])
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print('Reserved results',json.dumps(validation,indent=2),flush=True)
if __name__=='__main__':main()
