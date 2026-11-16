// Controlled DX7II-proxy probes; no MIDI or hardware convenience mapping here.
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
const [texed, jobFile] = process.argv.slice(2);
const job = JSON.parse(fs.readFileSync(jobFile,'utf8'));
const base=path.join(texed,'texed-ts/packages');
const load=p=>import(pathToFileURL(path.join(base,p)).href);
const {Part,EngineType}=await load('dx7-engine/src/part.ts');
const {initSynthTables,setEngineAccuracy}=await load('dx7-engine/src/synth-unit.ts');
const {loadSysexFile}=await load('dx7-format/src/sysex-loader.ts');
const {createDefaultAmem}=await load('dx7-format/src/amem.ts');
const {identifySysex}=await load('dx7-format/src/sysex.ts');
initSynthTables(job.rate);setEngineAccuracy('hardware');
const results=[];
for (let vi=0;vi<job.voices.length;vi++) {
  const voice=job.voices[vi];
  const singleBytes=new Uint8Array(fs.readFileSync(voice.syx));
  const bankBytes=new Uint8Array(fs.readFileSync(voice.bank));
  if (![singleBytes,bankBytes].every(b=>identifySysex(b).length===1&&identifySysex(b)[0].checksumOk))
    throw new Error(`Unaccepted packet ${voice.id}`);
  const single=loadSysexFile(singleBytes).singleVoice;
  const bank=loadSysexFile(bankBytes).library.resolve({bank:'internalA',program:0});
  if (!single||!bank||JSON.stringify(Array.from(single.slice(0,145)))!==JSON.stringify(Array.from(bank.vmem.slice(0,145))))
    throw new Error(`Voice roundtrip differs ${voice.id}`);
  for (const c of job.cases) {
    const part=new Part();part.setEngineType(EngineType.Modern);
    const supplement=createDefaultAmem();supplement[5]=12<<2;supplement[6]=0;supplement[29]=99;
    part.loadVoiceSlot(single,supplement);part.controlChange(11,127);
    const delta=12*Math.log2(c.hz/440)+69-c.note;
    part.pitchBend(Math.max(0,Math.min(16383,Math.round(8192+8192*delta/12))));
    const pre=Math.round((c.pre??.1)*job.rate),gate=Math.round(c.gate*job.rate),tail=Math.round((c.tail??.4)*job.rate);
    const velocity=c.velocity??98;
    if (![pre,gate,tail].every(n=>Number.isSafeInteger(n)&&n>=0)||!Number.isInteger(velocity)||velocity<1||velocity>127)
      throw new Error(`Invalid probe timing/velocity ${c.id}`);
    const frames=pre+gate+tail;const output=new Float32Array(frames);let at=0;
    const render=n=>{while(n>0){const count=Math.min(1024,n),buf=new Float32Array(count);part.render(buf,count);output.set(buf,at);at+=count;n-=count;}};
    render(pre);part.noteOn(c.note,velocity);render(gate);part.noteOff(c.note);render(tail);
    const wav=Buffer.alloc(44+frames*2);wav.write('RIFF');wav.writeUInt32LE(wav.length-8,4);wav.write('WAVEfmt ',8);
    wav.writeUInt32LE(16,16);wav.writeUInt16LE(1,20);wav.writeUInt16LE(1,22);wav.writeUInt32LE(job.rate,24);
    wav.writeUInt32LE(job.rate*2,28);wav.writeUInt16LE(2,32);wav.writeUInt16LE(16,34);wav.write('data',36);wav.writeUInt32LE(frames*2,40);
    let peak=0,clipped=0;
    for(let i=0;i<frames;i++){const value=output[i]*job.gain*100/127;peak=Math.max(peak,Math.abs(value));if(Math.abs(value)>1)clipped++;
      wav.writeInt16LE(Math.round(Math.max(-1,Math.min(1,value))*32767),44+i*2);}
    const file=path.join(job.output,`${voice.id}__${c.id}.wav`);fs.writeFileSync(file,wav);
    results.push({voice:voice.id,case:c.id,file,peak,clipped,accepted:true,velocity,
      pre_frames:pre,gate_frames:gate,tail_frames:tail});
  }
  if((vi+1)%10===0)console.log(`rendered ${vi+1}/${job.voices.length} parameter sets`);
}
fs.writeFileSync(job.report,JSON.stringify({engine:'Texed Modern / DX7II proxy',accuracy:'hardware',node:process.version,
  rate:job.rate,gain:job.gain,volume_cc7:100,velocity:job.cases.every(c=>(c.velocity??98)===98)?98:'case-specific',expression:127,bend_range:12,bend_step:0,
  dry:true,internal_block_samples:64,results},null,2)+'\n');
