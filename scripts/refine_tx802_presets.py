#!/usr/bin/env python3
"""Revisit three failed A5 checks as training, then use a fresh E5 validation."""
import argparse,csv,json,subprocess
from pathlib import Path
import calibrate_tx802_presets as cal

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path)
    p.add_argument('--texed',type=Path,default=cal.ROOT.parent/'texed')
    p.add_argument('--ikaopll',type=Path,default=cal.ROOT.parent/'IKAOPLL-verilator/build/obj_dir/ikaopll_sim')
    a=p.parse_args();run=a.run.resolve();out=run/'refinement';out.mkdir(exist_ok=True)
    packets=out/'packets';packets.mkdir(exist_ok=True);waves=out/'waves';waves.mkdir(exist_ok=True)
    source=out/'source';source.mkdir(exist_ok=True)
    summary=json.loads((run/'summary.json').read_text());gain=summary['gain_anchor']['correction']
    trials={r['trial']:r for r in csv.DictReader((run/'trials.csv').open())}
    old_metrics=list(csv.DictReader((run/'metrics.csv').open()))
    selected=list(csv.DictReader((run/'OPLL_DX7II_presets.csv').open()))
    seeds=list(csv.DictReader((run/'seed_DX7II.csv').open()))
    updates={};all_scores=[]
    def render(label,voices,cases):
        report=out/(label+'.render.json');job=out/(label+'.job.json')
        job.write_text(json.dumps(dict(rate=cal.RATE,gain=.25,voices=voices,cases=cases,output=str(waves),report=str(report)),indent=2)+'\n')
        subprocess.run(['npm','exec','--yes','--package=node@24','--','node',str(a.texed.resolve()/'texed-ts/node_modules/tsx/dist/cli.mjs'),str(cal.ROOT/'tools/texed_calibration_batch.mjs'),str(a.texed.resolve()),str(job)],cwd=a.texed/'texed-ts',check=True)
        return json.loads(report.read_text())['results']
    for preset in (7,10,12):
        case=json.loads((run/f'heldout{preset:02d}.job.json').read_text())['cases'][0]
        reference=cal.features(case['file'],case)
        ids=[identity for identity in trials if identity.startswith(f'p{preset:02d}_')]
        results=render(f'retrain{preset:02d}',[cal.emit_voice(packets,identity,trials[identity]) for identity in ids],[case])
        high={r['voice']:cal.score(cal.features(r['file'],case),reference,gain) for r in results}
        seed=high[f'p{preset:02d}_seed'];scores={}
        for identity in ids:
            earlier=[float(r['score']) for r in old_metrics if r['trial']==identity]
            combined=(sum(earlier)+high[identity])/(len(earlier)+1)
            all_scores.append(dict(preset=preset,trial=identity,earlier_score=sum(earlier)/len(earlier),A5_score=high[identity],combined_score=combined,A5_nonregression=high[identity]<=seed+1e-12))
            if high[identity]<=seed+1e-12:scores[identity]=combined
        best=min(scores,key=scores.get);selected[preset-1]=dict(trials[best])
        updates[preset]=dict(trial=best,score=scores[best],seed_score=next(r['combined_score'] for r in all_scores if r['trial']==f'p{preset:02d}_seed'))
        print(f'retrained preset{preset}: {best}, A5 {seed:.4f}->{high[best]:.4f}',flush=True)
    cal.write_csv(out/'retraining.csv',all_scores,list(all_scores[0]))
    validation=[cal.source_case(source,a.ikaopll.resolve(),i,76,.75) for i in range(1,16)]
    references=[cal.features(case['file'],case) for case in validation]
    voices=[]
    for index,(seed,fit) in enumerate(zip(seeds,selected),1):
        for suffix,row in (('seed',seed),('fit',fit)):
            voices.append(cal.emit_voice(packets,f'p{index:02d}_E5_{suffix}',row))
    probe=dict(validation[0],id='E5_075')
    results=render('fresh_E5',voices,[probe])
    metrics=[]
    for index,(case,reference) in enumerate(zip(validation,references),1):
        values={suffix:cal.score(cal.features(next(r['file'] for r in results if r['voice']==f'p{index:02d}_E5_{suffix}'),case),reference,gain) for suffix in ('seed','fit')}
        training=updates.get(index,summary['selected'][str(index)])
        metrics.append(dict(preset=index,name=selected[index-1]['name'],training_notes='57,69,81' if index in updates else '57,69',
            seed_score=training['seed_score'],calibrated_score=training['score'],validation_note=76,validation_gate=.75,
            validation_seed_score=values['seed'],validation_calibrated_score=values['fit'],validation_improved=values['fit']<values['seed']))
    cal.write_csv(out/'OPLL_DX7II_presets.csv',selected)
    cal.write_csv(out/'OPLL_DX7II_calibration_metrics.csv',metrics,list(metrics[0]))
    result=dict(status='experimental DX7II proxy calibration',refined=updates,fresh_validation=metrics,reference_cases=validation,
                original_A5_checks_now_training_for=[7,10,12],fresh_validation_used_for_selection=False,
                gain_anchor=summary['gain_anchor'],limitations=summary['limitations'])
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f"Fresh E5 validation improved: {sum(r['validation_improved'] for r in metrics)}/15",flush=True)
if __name__=='__main__':main()
