// Validate the exact generated packets against the pinned external emulator.
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
const [texed, jobFile] = process.argv.slice(2);
const job = JSON.parse(fs.readFileSync(jobFile, 'utf8'));
const base = path.join(texed, 'texed-ts/packages/dx7-format/src');
const { loadSysexFile } = await import(pathToFileURL(path.join(base, 'sysex-loader.ts')).href);
const { identifySysex } = await import(pathToFileURL(path.join(base, 'sysex.ts')).href);
const { VoiceLibrary } = await import(pathToFileURL(path.join(base, 'voice-library.ts')).href);
const combined = new VoiceLibrary();
const decoded = new Map();
const singles = new Map();
const results = [];
for (const item of job.assets) {
  const bytes = new Uint8Array(fs.readFileSync(item.file));
  const frames = identifySysex(bytes);
  if (frames.length !== 1 || frames[0].checksumOk !== true || !['voice','cartridge'].includes(frames[0].kind))
    throw new Error(`Emulator did not accept the expected packet: ${item.relative}`);
  const result = loadSysexFile(bytes);
  if (item.format === 9) {
    if (!result.loaded) throw new Error(`Bank not loaded: ${item.relative}`);
    for (let i = 0; i < 32; i++) {
      const slot = result.library.resolve({ bank:'internalA', program:i });
      if (!slot) throw new Error(`Missing bank slot ${i}`);
      const number = item.first_internal_voice + i;
      const ref = { bank: number<=32 ? 'internalA':'internalB', program:i };
      combined.storeVoice(ref,slot.vmem,slot.amem);
      decoded.set(number,Array.from(slot.vmem.slice(0,145)));
    }
    results.push({ path:item.relative, accepted:true, populated_slots:32 });
  } else {
    if (!result.singleVoice) throw new Error(`Single voice not loaded: ${item.relative}`);
    singles.set(item.internal_voice,Array.from(result.singleVoice.slice(0,145)));
    results.push({ path:item.relative, accepted:true, internal_voice:item.internal_voice });
  }
}
for (const [number, values] of decoded) {
  const ref={bank:number<=32?'internalA':'internalB',program:(number-1)%32};
  if (JSON.stringify(Array.from(combined.resolve(ref).vmem.slice(0,145)))!==JSON.stringify(values))
    throw new Error(`Combined bank placement overwrote I${number}`);
}
for (const [number, values] of singles) {
  if (JSON.stringify(values)!==JSON.stringify(decoded.get(number)))
    throw new Error(`Single/bank parameters differ for I${number}`);
}
fs.writeFileSync(job.report,JSON.stringify({status:'accepted',node:process.version,assets:results,
  single_bank_parameters_equal:true,combined_bank_placement_verified:true,
  compared_parameters:'first145 decoded VCED bytes; names excluded',
  playback:'not certified by packet acceptance'},null,2)+'\n');
