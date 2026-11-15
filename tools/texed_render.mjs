// Offline dry reference host. Texed stays a separate, pinned GPL project.
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
const [texed, jobPath] = process.argv.slice(2);
const job = JSON.parse(fs.readFileSync(jobPath, 'utf8'));
const base = path.join(texed, 'texed-ts/packages');
const load = p => import(pathToFileURL(path.join(base, p)).href);
const { Part, EngineType } = await load('dx7-engine/src/part.ts');
const { initSynthTables, setEngineAccuracy } = await load('dx7-engine/src/synth-unit.ts');
const { initVoice } = await load('dx7-format/src/cartridge.ts');
const { createDefaultAmem } = await load('dx7-format/src/amem.ts');
const { loadSysexFile } = await load('dx7-format/src/sysex-loader.ts');
initSynthTables(job.rate);
setEngineAccuracy('hardware');
const keys = [...new Set(job.events.filter(e => e.kind === 'note_on').map(e => `${e.port}:${e.channel}`))];
const states = new Map();
const libraries = new Map();
const selections = [];
const bankNames = { '0:0': 'I', '0:1': 'C', '1:0': 'A', '1:1': 'B' };
function voiceFor(bank, number) {
  if (job.init_voice) return { vmem: initVoice(), amem: createDefaultAmem() };
  const row = job.voices.find(v => v.bank === bank && v.voice === number);
  if (!row) throw new Error(`Missing explicit voice assignment ${bank}${number}`);
  let result = libraries.get(row.syx);
  if (!result) {
    result = loadSysexFile(new Uint8Array(fs.readFileSync(row.syx)));
    libraries.set(row.syx, result);
  }
  if (result.singleVoice) return { vmem: result.singleVoice, amem: createDefaultAmem() };
  const slot = result.library.resolve({ bank: row.library_bank, program: row.program });
  if (!slot) throw new Error(`Voice slot not loaded: ${row.syx} ${row.library_bank}:${row.program}`);
  return slot;
}
function select(s, frame) {
  const bank = bankNames[`${s.msb}:${s.lsb}`];
  if (!bank) throw new Error(`Unknown converter bank ${s.msb}:${s.lsb}`);
  const voice = voiceFor(bank, s.program + 1);
  const amem = new Uint8Array(voice.amem);
  amem[5] = (amem[5] & 3) | (job.bend_range << 2);
  amem[6] = 0; // continuous, normal bend
  amem[29] = 99; // explicit FC2/CC11 -> volume assignment for this reference setup
  s.part.loadVoiceSlot(voice.vmem, amem);
  selections.push({ frame, port: s.port, channel: s.channel, bank, voice: s.program + 1 });
  s.loaded = true;
}
for (const key of keys) {
  const [port, channel] = key.split(':').map(Number);
  const part = new Part();
  part.setEngineType(EngineType.Modern); // upstream's Mark II / modern FM core
  states.set(key, { part, port, channel, msb: 0, lsb: 0, program: 0, volume: 100, pan: 64, loaded: false });
}
const left = new Float32Array(job.frames);
const right = new Float32Array(job.frames);
let cursor = 0;
function render(to) {
  while (cursor < to) {
    const count = Math.min(1024, to - cursor);
    for (const s of states.values()) {
      const mono = new Float32Array(count);
      s.part.render(mono, count);
      const angle = (s.pan / 127) * Math.PI / 2;
      const gain = job.gain * s.volume / 127;
      for (let i = 0; i < count; i++) {
        left[cursor + i] += mono[i] * gain * Math.cos(angle);
        right[cursor + i] += mono[i] * gain * Math.sin(angle);
      }
    }
    cursor += count;
  }
}
for (const e of job.events) {
  render(e.frame);
  const s = states.get(`${e.port}:${e.channel}`);
  if (!s) continue;
  if (e.kind === 'cc') {
    if (e.a === 0) s.msb = e.b;
    else if (e.a === 32) s.lsb = e.b;
    else if (e.a === 7) s.volume = e.b;
    else if (e.a === 10) s.pan = e.b;
    else s.part.controlChange(e.a, e.b);
  } else if (e.kind === 'program') { s.program = e.a; select(s, e.frame); }
  else if (e.kind === 'note_on') {
    if (!s.loaded) select(s, e.frame);
    s.part.noteOn(e.a, e.b, 1);
  } else if (e.kind === 'note_off') s.part.noteOff(e.a, 1);
  else if (e.kind === 'bend') s.part.pitchBend(e.a | e.b << 7);
  else if (e.kind === 'aftertouch') s.part.aftertouch(e.a);
  else throw new Error(`Unsupported event ${e.kind}`);
}
render(job.frames);
let peak = 0, squares = 0, clipped = 0;
const wav = Buffer.alloc(44 + job.frames * 4);
wav.write('RIFF'); wav.writeUInt32LE(wav.length - 8, 4); wav.write('WAVEfmt ', 8);
wav.writeUInt32LE(16, 16); wav.writeUInt16LE(1, 20); wav.writeUInt16LE(2, 22);
wav.writeUInt32LE(job.rate, 24); wav.writeUInt32LE(job.rate * 4, 28);
wav.writeUInt16LE(4, 32); wav.writeUInt16LE(16, 34); wav.write('data', 36);
wav.writeUInt32LE(job.frames * 4, 40);
for (let i = 0; i < job.frames; i++) {
  for (const [ch, value] of [left[i], right[i]].entries()) {
    peak = Math.max(peak, Math.abs(value)); squares += value * value;
    if (Math.abs(value) > 1) clipped++;
    wav.writeInt16LE(Math.round(Math.max(-1, Math.min(1, value)) * 32767), 44 + i * 4 + ch * 2);
  }
}
fs.writeFileSync(job.output, wav);
fs.writeFileSync(job.output + '.render.json', JSON.stringify({
  engine: 'Texed Modern/Mark-II reference, not hardware proof', accuracy: 'hardware',
  init_voice_plumbing_only: job.init_voice, rate: job.rate, frames: job.frames,
  peak, rms: Math.sqrt(squares / (job.frames * 2)), clipped, gain: job.gain,
  bend_range: job.bend_range, bend_step: 0, cc11_setup: 'FC2 volume range 99',
  dry_part_host: true, internal_engine_block_samples: 64, node: process.version,
  selections, limitations: ['Internal Texed synthesis buffers quantize response within 64 samples',
    'Mid-note voice loads clear Texed voices', 'No RX21/GM drum synthesis',
    'Bank labels resolved by explicit host map, not validation of real TX802 bank MIDI']
}, null, 2) + '\n');
console.log(`${job.output}: peak=${peak.toFixed(6)}, clipped=${clipped}`);
