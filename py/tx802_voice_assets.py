"""Inspectably orchestrate the owner's existing TX802-named CSV/SysEx tools.

No six-operator interpretation or SysEx writer is reimplemented here.
"""
import csv
import io
import hashlib
import json
from pathlib import Path
import subprocess
import sys

TOOLS=Path(__file__).resolve().parents[1]/'tools/legacy_tx802'


def check_packet(data, expected_format):
    size={0:155,9:4096}[expected_format]
    if (len(data)!=size+8 or data[:2]!=bytes((0xf0,0x43)) or data[2]>15 or
        data[3]!=expected_format or data[4]*128+data[5]!=size or data[-1]!=0xf7 or
        any(value>127 for value in data[2:-1]) or (sum(data[6:-2])+data[-2])&127):
        raise ValueError('Invalid existing TX802 voice SysEx packet')


def validate_in_texed(folder, texed, audit_assets):
    texed=Path(texed) if texed is not None else TOOLS.parents[2]/'texed'
    runner=texed/'texed-ts/node_modules/tsx/dist/cli.mjs'
    audit_report=(folder/'texed_acceptance.json').resolve()
    audit_job=(folder/'texed_job.json').resolve()
    audit_job.write_text(json.dumps(dict(assets=audit_assets,report=str(audit_report)),indent=2)+'\n')
    command=['npm','exec','--yes','--package=node@24','--','node',str(runner.resolve()),
             str((TOOLS.parent/'check_texed_sysex.mjs').resolve()),str(texed.resolve()),str(audit_job)]
    if not runner.is_file():
        raise ValueError('Texed is required to validate SysEx acceptance; see docs/audio_comparison.md')
    result=subprocess.run(command,cwd=texed/'texed-ts',capture_output=True,text=True)
    (folder/'texed_acceptance.log').write_text(result.stdout+result.stderr,encoding='utf-8')
    if result.returncode:
        raise ValueError('Texed rejected generated voice assets; see diagnostics')
    emulator=json.loads(audit_report.read_text())
    emulator['texed_commit']=subprocess.check_output(['git','-c',f'safe.directory={texed.resolve()}',
        '-C',str(texed.resolve()),'rev-parse','HEAD'],text=True).strip()
    return emulator


def build_voice_assets(text, folder, stem, *, texed=None):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    reader=csv.DictReader(io.StringIO(text));fields=reader.fieldnames
    rows=list(reader)
    if not rows or not fields or 'voice' not in fields:
        raise ValueError('OPLL voice CSV requires voice slot identities')
    by_slot={}
    for row in rows:
        slot=int(row['voice'])
        if not 0<=slot<64 or slot in by_slot:
            raise ValueError('Voice CSV slots must be unique and in 0..63')
        by_slot[slot]=row
    last=max(by_slot)
    slotted=[]
    for slot in range(last+1):
        row=by_slot.get(slot)
        if row is None:
            row={field:'0' for field in fields}
            row.update(voice=str(slot),name=f'EMPTY I{slot+1}')
        slotted.append(row)
    def write_csv(path,columns,values):
        with path.open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader();writer.writerows(values)
    def run(name,*args):
        result=subprocess.run([sys.executable,str(TOOLS/name),*map(str,args)],capture_output=True,text=True)
        (folder/(name+'.'+Path(args[0]).stem+'.log')).write_text(result.stdout+result.stderr,encoding='utf-8')
        if result.returncode:
            raise ValueError(f'{name} failed; see voice-assets diagnostics')
    source=folder/'voice_slots.csv';write_csv(source,fields,slotted)
    run('convert_op2csv_to_op6csv_tx802.py',source)
    op6=source.with_name('voice_slots_tx802_op6.csv')
    with op6.open(encoding='utf-8',newline='') as f:
        reader=csv.DictReader(f);columns=reader.fieldnames;converted=list(reader)
    if len(converted)!=len(slotted):
        raise ValueError('TX802 OP6 conversion changed slot count')
    products={};routing=[];banks=[]
    for start in range(0,len(converted),32):
        number=start//32+1
        chunk=folder/f'voice_bank{number:02d}.csv'
        write_csv(chunk,columns,converted[start:start+32])
        run('convert_tx802csv_to_wmem_bank_syx.py',chunk)
        generated=chunk.with_suffix('.tx802_wmem32.syx')
        data=generated.read_bytes();check_packet(data,9)
        relative=f'voices/{stem}.bank{number:02d}.syx';products[relative]=data
        banks.append(dict(path=relative,first_internal_voice=start+1,last_internal_voice=start+32,
                          padding=32-len(converted[start:start+32])))
        for slot in sorted(by_slot):
            if start<=slot<start+32:
                routing.append(dict(internal_voice=slot+1,bank_path=relative,bank_program=slot-start,
                                    source_name=by_slot[slot]['name']))
    run('convert_tx802csv_to_dx7_single_voice_syx.py',op6)
    for slot in sorted(by_slot):
        if slot<20:
            continue
        generated=folder/f'voice_slots_tx802_op6_I{slot+1}_DX7_single_voice.syx'
        data=generated.read_bytes();check_packet(data,0)
        products[f'voices/{stem}.I{slot+1:02d}.syx']=data
    report=dict(status='packet_validated',formats=[dict(format=9,bytes=4104),dict(format=0,bytes=163)],
                actual_slots=[slot+1 for slot in sorted(by_slot)],
                placeholder_slots=[slot+1 for slot in range(last+1) if slot not in by_slot],
                banks=banks,routing=routing,files=list(products),
                tool_policy='existing TX802-named tools; single155 unpack correction only; no hardware transmission',
                parameter_fidelity='unverified legacy serialization; packet validity is not timbre reproduction')
    packet_dir=folder/'packet_check';packet_dir.mkdir(exist_ok=True)
    audit_assets=[]
    for relative,data in products.items():
        file=(packet_dir/Path(relative).name).resolve();file.write_bytes(data)
        record=dict(relative=relative,file=str(file),format=data[3],sha256=hashlib.sha256(data).hexdigest())
        if data[3]==9:
            record['first_internal_voice']=next(b['first_internal_voice'] for b in banks if b['path']==relative)
        else:
            record['internal_voice']=int(Path(relative).stem.rsplit('.I',1)[1])
        audit_assets.append(record)
    try:
        report['emulator']=validate_in_texed(folder,texed,audit_assets)
        report['status']='emulator_accepted'
        report['asset_hashes']={a['relative']:a['sha256'] for a in audit_assets}
    except Exception as exc:
        report.update(status='emulator_validation_failed',detail=str(exc))
        (folder/'voice_assets.json').write_text(json.dumps(report,indent=2)+'\n')
        raise
    (folder/'voice_assets.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    mapping=io.StringIO(newline='')
    writer=csv.writer(mapping,lineterminator='\n')
    writer.writerow(['bank','voice','syx','library_bank','program'])
    for route in routing:
        writer.writerow(['I',route['internal_voice'],Path(route['bank_path']).name,'internalA',route['bank_program']])
    products[f'voices/{stem}.texed.csv']=mapping.getvalue().encode('utf-8')
    return products,report
