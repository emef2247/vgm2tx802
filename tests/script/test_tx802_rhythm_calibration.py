"""Percussion probes preserve source timing and penalize spectral/decay defects."""
import importlib.util
import struct
import sys
import tempfile
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
HAS_NUMPY = importlib.util.find_spec('numpy') is not None
if HAS_NUMPY:
    import numpy as np
    import calibrate_tx802_rhythm as rhythm


@unittest.skipUnless(HAS_NUMPY, 'NumPy is optional audio calibration tooling')
class RhythmCalibrationTests(unittest.TestCase):
    def test_authored_reference_has_one_trigger_and_exact_integer_waits(self):
        for family, bit in rhythm.BITS.items():
            data = rhythm.reference_bytes(family, gate_samples=3528, pre_samples=4410,
                                          tail_samples=35280, attenuation=4)
            self.assertEqual(struct.unpack_from('<I', data, 0x18)[0], 43218)
            self.assertEqual(struct.unpack_from('<I', data, 4)[0], len(data)-4)
            pos, clock, edges, registers = 0x100, 0, [], {}
            while data[pos] != 0x66:
                if data[pos] == 0x51:
                    reg, value = data[pos+1:pos+3]; registers[reg] = value
                    if reg == 14: edges.append((clock, value))
                    pos += 3
                else:
                    self.assertEqual(data[pos], 0x61)
                    clock += struct.unpack_from('<H', data, pos+1)[0]; pos += 3
            self.assertEqual(edges, [(0, 32), (4410, 32|bit), (7938, 32)])
            self.assertEqual(clock, 43218)
            self.assertEqual(registers[0x37], 0x44)
            self.assertFalse(any(reg < 8 for reg in registers))  # no patch bytes

    def test_reference_rejects_invalid_or_fractional_source_times(self):
        for kw in (dict(gate_samples=0), dict(gate_samples=1.5), dict(gate_samples=-1),
                   dict(gate_samples=True), dict(gate_samples=1, attenuation=16)):
            with self.assertRaises(ValueError): rhythm.reference_bytes('BD', **kw)

    def test_wait_chunks_and_seed_slot_conventions(self):
        data = rhythm.wait(140000)
        self.assertEqual(sum(struct.unpack_from('<H', data, i+1)[0] for i in range(0,len(data),3)), 140000)
        for i, family in enumerate(rhythm.FAMILIES):
            row = rhythm.seed_row(family)
            self.assertEqual(row['voice'], 16+i)
            self.assertLess(abs(row['reference_note']-(69+12*np.log2(row['reference_hz']/440))), .51)
            self.assertEqual(len(rhythm.cal.BANK.tx802_voice_to_packed(row)), 128)

    def write_audio(self, path, hit):
        data = np.r_[np.zeros(4800), hit]
        with wave.open(str(path), 'wb') as f:
            f.setparams((1,2,48000,len(data),'NONE','not compressed'))
            f.writeframes(np.round(data*32767).astype('<i2').tobytes())

    def test_late_metallic_partial_and_amplitude_are_not_hidden_by_normalization(self):
        case = dict(pre=.1, gate=.2, tail=.8)
        t = np.arange(48000)/48000
        reference = .08*np.sin(2*np.pi*250*t)*np.exp(-t*35)
        defect = reference + .015*np.sin(2*np.pi*3700*t)*np.exp(-t*2)
        with tempfile.TemporaryDirectory() as tmp:
            a, b, c = [Path(tmp)/(s+'.wav') for s in ('ref','ring','quiet')]
            self.write_audio(a, reference); self.write_audio(b, defect); self.write_audio(c, reference*.1)
            rf, df, qf = [rhythm.features(p, case) for p in (a,b,c)]
        self.assertAlmostEqual(rhythm.distance(rf,rf,1.)['score'], 0.)
        self.assertGreater(rhythm.distance(df,rf,1.)['spectrum'], .1)
        self.assertGreater(df['tail_rms'], rf['tail_rms'])
        self.assertGreater(rhythm.distance(qf,rf,1.)['amplitude'], 1.)

    def test_silent_reference_or_nonfinite_comparison_rejected(self):
        feature = dict(rms=.1, envelope=np.ones(10), bands=np.ones((5,66)),
                       flatness=np.ones(5), concentration=np.ones(5))
        with self.assertRaises(ValueError): rhythm.distance(feature, dict(feature,rms=0.), 1.)
        with self.assertRaises(ValueError): rhythm.distance(dict(feature,rms=np.nan),feature,1.)
        with self.assertRaises(ValueError): rhythm.distance(dict(feature,envelope=np.ones(9)),feature,1.)

    def test_final_spectral_window_includes_audio_after_420ms(self):
        t = np.arange(48000)/48000
        hit = np.where((t>.45)&(t<.49), .05*np.sin(2*np.pi*3700*t), 0.)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'late.wav'; self.write_audio(p,hit)
            f = rhythm.features(p,dict(pre=.1,gate=.2,tail=.8))
        self.assertEqual(float(f['bands'][:4].sum()),0.)
        self.assertGreater(float(f['bands'][4].sum()),1.)

    def test_fractional_output_frame_has_distinct_source_and_target_contracts(self):
        case = dict(pre=7629/44100, gate=8379/44100, tail=.8,
                    pre_samples=7629, gate_samples=8379, tail_samples=35280)
        source_frames = (7629+8379+35280)*48000//44100
        target_frames = sum(round(case[k]*48000) for k in ('pre','gate','tail'))
        self.assertEqual(target_frames-source_frames, 1)
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp)/'source.wav', Path(tmp)/'target.wav'
            case['file'] = str(source)
            for p, frames in ((source,source_frames), (target,target_frames)):
                with wave.open(str(p),'wb') as f:
                    f.setparams((1,2,48000,frames,'NONE','not compressed'))
                    f.writeframes(np.full(frames,100,dtype='<i2').tobytes())
            sf, tf = rhythm.features(source,case), rhythm.features(target,case)
            self.assertEqual(sf['envelope'].shape,tf['envelope'].shape)
            self.assertEqual(rhythm.distance(tf,sf,1.)['score'],0.)
            source.write_bytes(source.read_bytes()[:-2])
            with self.assertRaises(ValueError): rhythm.features(source,case)


if __name__ == '__main__': unittest.main()
