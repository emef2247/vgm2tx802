#!/usr/bin/env python3
"""Reproducible synthetic OPLL -> DX7II-proxy preset calibration (not hardware proof)."""
import argparse,csv,copy,hashlib,importlib.util,itertools,json,math,struct,subprocess,sys,wave
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
TOOLS=ROOT/'tools/legacy_tx802';sys.path[:0]=[str(ROOT/'py'),str(TOOLS)]
from tx802_voice_assets import check_packet

def tool(name):
    spec=importlib.util.spec_from_file_location('cal_'+name,TOOLS/(name+'.py'))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
BANK=tool('convert_tx802csv_to_wmem_bank_syx');SINGLE=tool('convert_tx802csv_to_dx7_single_voice_syx')
CLOCK=3579545;RATE=48000
OP_FIELDS=['R1','R2','R3','R4','L1','L2','L3','L4','BP','LD','RD','LC','RC','RS','AMS','KVS','OL','MODE','COARSE','FINE','DT']
GLOBALS=['ALG','FB','SYNC','LFO_SPEED','LFO_DELAY','LFO_PMD','LFO_AMD','LFO_SYNC','LFO_WAVE','LFO_PMS','TRANSPOSE']
FIELDS=['voice','source_preset','name']+GLOBALS+[f'PEG_{k}{i}' for k in ('R','L') for i in range(1,5)]+[f'OP{op}_{f}' for op in range(1,7) for f in OP_FIELDS]+['PB_RANGE','PB_STEP']

def base_row(name):
    row=dict(voice=1,source_preset=0,name=name,ALG=4,FB=0,SYNC=1,LFO_SPEED=0,LFO_DELAY=0,LFO_PMD=0,LFO_AMD=0,LFO_SYNC=0,LFO_WAVE=0,LFO_PMS=0,TRANSPOSE=24,PB_RANGE=12,PB_STEP=0)
    for i in range(1,5):row[f'PEG_R{i}']=99;row[f'PEG_L{i}']=50
    defaults=dict(R1=99,R2=99,R3=0,R4=80,L1=99,L2=99,L3=99,L4=0,BP=39,LD=0,RD=0,LC=0,RC=0,RS=0,AMS=0,KVS=0,OL=0,MODE=0,COARSE=1,FINE=0,DT=7)
    for op in range(1,7):
        for key,value in defaults.items():row[f'OP{op}_{key}']=value
    return row

def seed_row(source,preset):
    row=base_row(source['name']);row.update(voice=preset,source_preset=preset,FB=int(source['FB']))
    half=int(source['OP2_WS'])!=0
    for pair,(car,mod) in enumerate(((5,6),(3,4),(1,2))):
        active=pair==0 or half
        for dest,prefix,is_carrier in ((car,'OP2',True),(mod,'OP1',False)):
            ar,dr,sl,rr=(int(source[f'{prefix}_{f}']) for f in ('AR','DR','SL','RR'))
            level=0 if sl==15 else max(0,99-4*sl)
            values=dict(R1=min(99,24+5*ar),R2=0 if dr==0 else min(99,24+5*dr),R3=0 if int(source[f'{prefix}_EGT']) else min(99,24+5*rr),
                        R4=min(99,24+5*rr),L2=level,L3=level if int(source[f'{prefix}_EGT']) else 0,KVS=7 if is_carrier else 0)
            multiple=int(source[f'{prefix}_MULTI'])
            if is_carrier:
                ratio=(.5 if multiple==0 else multiple)*(1,2,4)[pair]
                values['COARSE']=0 if ratio==.5 else min(31,int(ratio))
                values['OL']=max(0,99-(8 if half else 0)-(0,10,28)[pair]) if active else 0
            else:
                values['COARSE']=multiple
                values['OL']=min(99,max(0,99-int(source['OP1_TL'])+pair*8)) if active else 0
            for key,value in values.items():row[f'OP{dest}_{key}']=value
    return row

def write_csv(path,rows,fields=FIELDS):
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore',lineterminator='\n');w.writeheader();w.writerows(rows)

def emit_voice(root,identity,row):
    packed=BANK.tx802_voice_to_packed(row)
    bank=BANK.build_wmem_bank([packed]*32)
    single=SINGLE.wrap_dx7_single_voice(SINGLE.build_dx7_single_voice_payload(row,row['name']))
    check_packet(bank,9);check_packet(single,0)
    bankpath=root/(identity+'.bank.syx');syxpath=root/(identity+'.syx')
    bankpath.write_bytes(bank);syxpath.write_bytes(single)
    return dict(id=identity,bank=str(bankpath),syx=str(syxpath))

def source_case(root,sim,preset,note,gate=.6,control=False):
    hz=440*2**((note-69)/12)
    block=next(b for b in range(8) if 256<=round(hz*72*2**(19-b)/CLOCK)<=511)
    fnum=round(hz*72*2**(19-block)/CLOCK);actual=CLOCK*fnum*2**(block-19)/72
    identity=f'{"control" if control else "p%02d"%preset}_n{note}_g{gate}'
    source=root/(identity+'.vgm');out=root/(identity+'.wav')
    reg=lambda a,v:bytes((0x51,a,v))
    def wait(n):
        data=b''
        while n:
            k=min(65535,n);data+=bytes((0x61,))+struct.pack('<H',k);n-=k
        return data
    high=(block<<1)|(fnum>>8)
    setup=b''
    if control:setup=b''.join(reg(i,v) for i,v in enumerate([0x21,0x21,63,0,0xf0,0xf0,0,0]))
    commands=setup+reg(0x30,0 if control else preset<<4)+reg(0x10,fnum&255)+reg(0x20,high)+wait(4410)+reg(0x20,high|16)+wait(round(gate*44100))+reg(0x20,high)+wait(17640)+bytes((0x66,))
    data=bytearray(0x100);data[:4]=b'Vgm '
    for offset,value in ((8,0x170),(0x10,CLOCK),(0x18,4410+round(gate*44100)+17640),(0x34,0xcc)):
        struct.pack_into('<I',data,offset,value)
    data+=commands;struct.pack_into('<I',data,4,len(data)-4);source.write_bytes(data)
    result=subprocess.run([str(sim),str(source),'--output',str(out),'--sample-rate',str(RATE)],capture_output=True,text=True)
    (root/(identity+'.render.log')).write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError('IKAOPLL render failed: '+identity)
    return dict(id=identity,note=note,hz=actual,gate=gate,file=str(out),source=str(source),fnum=fnum,block=block)

def audio(path,expected_frames=None):
    with wave.open(str(path),'rb') as f:
        if f.getsampwidth()!=2 or f.getframerate()!=RATE or f.getcomptype()!='NONE':
            raise ValueError('Calibration requires uncompressed 16-bit 48000-Hz WAV')
        frames=f.getnframes();channels=f.getnchannels();raw=f.readframes(frames)
        if channels<1 or len(raw)!=frames*channels*2 or (expected_frames is not None and frames!=expected_frames):
            raise ValueError('Incomplete calibration render or unexpected duration')
        data=np.frombuffer(raw,dtype='<i2').astype(float)/32768
        return data.reshape(-1,channels).mean(axis=1)

def features(path,case):
    start=round(.1*RATE);gate=round(case['gate']*RATE)
    data=audio(path,start+gate+round(.4*RATE))
    if 'analysis_start' not in case:
        bins=[np.sqrt(np.mean(data[i:i+480]**2)) for i in range(start,start+gate-479,480)]
        peak=start+int(np.argmax(bins))*480
        case['analysis_start']=max(start,min(peak-1920,start+gate-5760))
        case['analysis_stop']=case['analysis_start']+5760
    steady=data[case['analysis_start']:case['analysis_stop']]
    rms=float(np.sqrt(np.mean(steady**2)))
    window=np.hanning(len(steady));times=np.arange(len(steady))/RATE
    harmonics=np.array([abs(np.dot(steady*window,np.exp(-2j*np.pi*case['hz']*.5*n*times))) for n in range(1,17)])
    harmonics=harmonics/max(float(harmonics.sum()),1e-12)
    envelope=np.array([np.sqrt(np.mean(data[i:i+480]**2)) for i in range(0,len(data)-479,480)])
    spectrum=np.abs(np.fft.rfft(steady*window));freqs=np.fft.rfftfreq(len(steady),1/RATE)
    indices=np.flatnonzero((freqs>case['hz']*.8)&(freqs<case['hz']*1.2))
    k=int(indices[np.argmax(spectrum[indices])]);adjust=0.
    if 0<k<len(spectrum)-1:
        a,b,c=np.log(spectrum[k-1:k+2]+1e-15);adjust=float(.5*(a-c)/(a-2*b+c))
    measured=(k+adjust)*RATE/len(steady)
    return dict(rms=rms,harmonics=harmonics,envelope=envelope,pitch_cents=1200*math.log2(max(measured,1e-9)/case['hz']))

def score(target,reference,gain):
    if not math.isfinite(gain) or gain<=0:
        raise ValueError('Calibration gain must be finite and positive')
    for value in (target,reference):
        if not all(np.all(np.isfinite(value[key])) for key in ('rms','harmonics','envelope')):
            raise ValueError('Nonfinite calibration feature')
    if any(target[key].shape!=reference[key].shape or not target[key].size for key in ('harmonics','envelope')):
        raise ValueError('Calibration feature lengths differ or are empty')
    if reference['rms']<1e-7:raise ValueError('Silent calibration reference')
    if target['rms']<1e-7:return 1e6
    amplitude=math.log2(max(1e-12,target['rms']*gain/reference['rms']))**2
    harmonic=float(np.mean((target['harmonics']-reference['harmonics'])**2))
    env=float(np.mean((target['envelope']/target['rms']-reference['envelope']/reference['rms'])**2))
    return .5*amplitude+16*harmonic+env

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--outdir',type=Path,required=True)
    p.add_argument('--texed',type=Path,default=ROOT.parent/'texed');p.add_argument('--ikaopll',type=Path,default=ROOT.parent/'IKAOPLL-verilator/build/obj_dir/ikaopll_sim')
    args=p.parse_args();out=args.outdir.resolve();out.mkdir(parents=True,exist_ok=True)
    src=out/'source';src.mkdir(exist_ok=True);packets=out/'packets';packets.mkdir(exist_ok=True);waves=out/'waves';waves.mkdir(exist_ok=True)
    originals=list(csv.DictReader((ROOT/'data/opll/presets/OPLL_OP2_MB14.csv').open()))[:15]
    seeds=[seed_row(row,i+1) for i,row in enumerate(originals)]
    write_csv(out/'seed_DX7II.csv',seeds)
    controls=[source_case(src,args.ikaopll.resolve(),0,69,control=True)]
    cases={i+1:[source_case(src,args.ikaopll.resolve(),i+1,note) for note in (57,69)] for i in range(15)}
    references={case['id']:features(case['file'],case) for pair in cases.values() for case in pair}
    def render(label,voices,probe_cases):
        report=out/(label+'.render.json');job=out/(label+'.job.json')
        job.write_text(json.dumps(dict(rate=RATE,gain=.25,voices=voices,cases=probe_cases,output=str(waves),report=str(report)),indent=2)+'\n')
        subprocess.run(['npm','exec','--yes','--package=node@24','--','node',str(args.texed.resolve()/'texed-ts/node_modules/tsx/dist/cli.mjs'),str(ROOT/'tools/texed_calibration_batch.mjs'),str(args.texed.resolve()),str(job)],cwd=args.texed/'texed-ts',check=True)
        return json.loads(report.read_text())['results']
    control=base_row('LEVEL PROBE');control['OP5_OL']=99;control['OP5_KVS']=7
    levels=[]
    for level in (50,60,70,80,90,95,99):
        row=dict(control);row['OP5_OL']=level
        levels.append((level,row,emit_voice(packets,f'level{level}',row)))
    level_results=render('level_probe',[x[2] for x in levels],controls)
    ref_control=features(controls[0]['file'],controls[0])
    level_rms={int(r['voice'][5:]):features(r['file'],controls[0])['rms'] for r in level_results}
    gain=ref_control['rms']/level_rms[99]
    all_rows={};metrics=[];best={};baseline={}
    def evaluate(preset,identities,results):
        local={}
        for identity in identities:
            matches=[r for r in results if r['voice']==identity]
            values=[]
            for case in cases[preset]:
                item=next(r for r in matches if r['case']==case['id']);f=features(item['file'],case)
                value=score(f,references[case['id']],gain);values.append(value)
                metrics.append(dict(preset=preset,trial=identity,case=case['id'],score=value,rms_raw=f['rms'],rms_reference=references[case['id']]['rms'],base_band_peak_cents=f['pitch_cents'],file=item['file']))
            local[identity]=sum(values)/len(values)
        candidate=min(local,key=local.get)
        if preset not in best or local[candidate]<best[preset][1]:best[preset]=(candidate,local[candidate])
        return local
    for preset,seed in enumerate(seeds,1):
        variants=[];identities=[]
        initial=f'p{preset:02d}_seed';all_rows[initial]=dict(seed);identities.append(initial);variants.append(emit_voice(packets,initial,seed))
        for index,(change,feedback) in enumerate(itertools.product((-10,0,10),sorted({max(0,int(seed['FB'])-2),int(seed['FB']),min(7,int(seed['FB'])+2)}))):
            row=dict(seed);row['FB']=feedback
            for op in (2,4,6):
                if row[f'OP{op}_OL']>0:row[f'OP{op}_OL']=min(99,max(0,row[f'OP{op}_OL']+change))
            identity=f'p{preset:02d}_body{index:02d}';all_rows[identity]=row;identities.append(identity);variants.append(emit_voice(packets,identity,row))
        values=evaluate(preset,identities,render(f'body{preset:02d}',variants,cases[preset]));baseline[preset]=values[initial]
        print(f'preset {preset}: body seed={baseline[preset]:.4f} best={best[preset][1]:.4f}',flush=True)
        current=dict(all_rows[best[preset][0]]);variants=[];identities=[]
        for index,(attack,release) in enumerate(itertools.product((-12,0,12),(-12,0,12))):
            row=dict(current)
            for op in (1,3,5):
                if row[f'OP{op}_OL']>0:
                    row[f'OP{op}_R1']=min(99,max(0,row[f'OP{op}_R1']+attack));row[f'OP{op}_R4']=min(99,max(0,row[f'OP{op}_R4']+release))
            identity=f'p{preset:02d}_env{index:02d}';all_rows[identity]=row;identities.append(identity);variants.append(emit_voice(packets,identity,row))
        evaluate(preset,identities,render(f'env{preset:02d}',variants,cases[preset]))
        current=dict(all_rows[best[preset][0]]);ratios=[]
        for case in cases[preset]:
            item=next(m for m in metrics if m['trial']==best[preset][0] and m['case']==case['id'])
            ratios.append(math.log(references[case['id']]['rms']/(item['rms_raw']*gain)))
        delta=sum(ratios)/len(ratios);probe_levels=sorted(level_rms);probe_logs=[math.log(max(level_rms[x],1e-12)) for x in probe_levels]
        old=int(current['OP5_OL']);desired=float(np.interp(old,probe_levels,probe_logs))+delta
        fitted=int(round(np.interp(desired,probe_logs,probe_levels)));variants=[];identities=[]
        for index,level in enumerate(sorted({max(0,fitted-2),fitted,min(99,fitted+2)})):
            row=dict(current)
            for op in (1,3,5):
                if row[f'OP{op}_OL']>0:row[f'OP{op}_OL']=min(99,max(0,row[f'OP{op}_OL']+level-old))
            identity=f'p{preset:02d}_level{index:02d}';all_rows[identity]=row;identities.append(identity);variants.append(emit_voice(packets,identity,row))
        evaluate(preset,identities,render(f'level{preset:02d}',variants,cases[preset]))
        print(f'preset {preset}: final score={best[preset][1]:.4f}',flush=True)
    selected=[dict(all_rows[best[i][0]]) for i in range(1,16)]
    heldout=[]
    for preset,row in enumerate(selected,1):
        case=source_case(src,args.ikaopll.resolve(),preset,81,.9)
        reference=features(case['file'],case)
        ids=[f'p{preset:02d}_seed',best[preset][0]]
        results=render(f'heldout{preset:02d}',[emit_voice(packets,identity,all_rows[identity]) for identity in dict.fromkeys(ids)],[case])
        scores={item['voice']:score(features(item['file'],case),reference,gain) for item in results}
        heldout.append(dict(preset=preset,seed_score=scores[ids[0]],selected_score=scores[ids[1]],case=case['id']))
    write_csv(out/'OPLL_DX7II_presets.csv',selected)
    write_csv(out/'trials.csv',[dict(trial=identity,**row) for identity,row in all_rows.items()],['trial']+FIELDS)
    write_csv(out/'metrics.csv',metrics,list(metrics[0]))
    write_csv(out/'heldout.csv',heldout,list(heldout[0]))
    summary=dict(status='DX7II_proxy_calibration',source_clock_hz=CLOCK,rate=RATE,training_notes=[57,69],training_gate=.6,heldout_note=81,heldout_gate=.9,
        source_time_unit='integer 44100-Hz VGM samples',source='IKAOPLL RTL preset1..15',initial_parameter_seed='legacy OPLL_OP2_MB14.csv, explicit experimental rate/level/half-wave mappings',
        gain_anchor=dict(raw_target_gain=.25,correction=gain,source_control_rms=ref_control['rms'],target_control_rms=level_rms[99],per_voice_normalization=False),
        output_level_probe=level_rms,objective='0.5*log2(RMS ratio)^2 +16*mean(normalized partials1..16 on half-base-frequency grid difference^2)+mean(normalized10ms RMS-envelope error^2)',
        texed_commit=subprocess.check_output(['git','-c',f'safe.directory={args.texed.resolve()}','-C',str(args.texed.resolve()),'rev-parse','HEAD'],text=True).strip(),
        ikaopll_executable_sha256=hashlib.sha256(args.ikaopll.read_bytes()).hexdigest(),
        reference_cases=cases,control_case=controls[0],
        selected={i:dict(trial=best[i][0],seed_score=baseline[i],score=best[i][1]) for i in range(1,16)},heldout=heldout,
        limitations=['DX7II proxy, not TX802 hardware verification','per-operator OPLL AM/vibrato not fitted','half-wave carrier approximated with three FM pairs','preset ROM/source CSV differences retained in measured reference','existing production defaults unchanged'])
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(dict(csv=str(out/'OPLL_DX7II_presets.csv'),training_improved=sum(best[i][1]<baseline[i] for i in best),heldout_improved=sum(r['selected_score']<r['seed_score'] for r in heldout)),indent=2),flush=True)

if __name__=='__main__':main()
