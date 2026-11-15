"""Reject incomplete or incompatible audio before optional calibration scoring."""
import importlib.util
import sys
import tempfile
import unittest
import wave
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
HAS_NUMPY=importlib.util.find_spec('numpy') is not None
if HAS_NUMPY:
    import numpy as np
    import calibrate_tx802_presets as cal

@unittest.skipUnless(HAS_NUMPY,'NumPy is optional calibration tooling')
class CalibrationAudioTests(unittest.TestCase):
    def wav(self,path,rate=48000,width=2,frames=48):
        with wave.open(str(path),'wb') as f:
            f.setparams((1,width,rate,frames,'NONE','not compressed'))
            f.writeframes(bytes(frames*width))

    def test_valid_pcm_and_format_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'probe.wav'
            self.wav(path)
            self.assertEqual(len(cal.audio(path,48)),48)
            for rate,width in ((44100,2),(48000,1)):
                self.wav(path,rate,width)
                with self.assertRaises(ValueError):cal.audio(path)

    def test_declared_or_expected_truncation_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'probe.wav';self.wav(path)
            with self.assertRaises(ValueError):cal.audio(path,49)
            path.write_bytes(path.read_bytes()[:-2])
            with self.assertRaises(ValueError):cal.audio(path)

    def test_nonfinite_or_short_features_fail(self):
        reference=dict(rms=1.,harmonics=np.ones(16),envelope=np.ones(10))
        self.assertEqual(cal.score(reference,reference,1.),0.)
        for key,value in (('rms',float('nan')),('envelope',np.ones(9)),('harmonics',np.full(16,np.inf))):
            target=dict(reference);target[key]=value
            with self.assertRaises(ValueError):cal.score(target,reference,1.)

if __name__=='__main__':unittest.main()
