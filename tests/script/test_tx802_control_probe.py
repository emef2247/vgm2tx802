"""Independent field/window checks for optional control attribution tooling."""
import importlib.util,sys,tempfile,unittest,wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
HAS_NUMPY=importlib.util.find_spec('numpy') is not None
if HAS_NUMPY:
    import numpy as np
    import probe_tx802_controls as probe

@unittest.skipUnless(HAS_NUMPY,'Optional calibration NumPy dependency')
class ControlProbeTests(unittest.TestCase):
    def test_rom_fields_map_to_custom_patch_registers(self):
        word=(1<<51)|(1<<48)|(1<<47)|(1<<44)|(3<<40)|(5<<36)|(2<<34)|(1<<32)|(17<<57)|(1<<56)|(6<<52)
        word|=(9<<28)|(8<<24)|(7<<20)|(6<<16)|(5<<12)|(4<<8)|(3<<4)|2
        self.assertEqual(list(probe.decode_rom_word(word)),[0xa3,0x55,0x91,0x56,0x97,0x86,0x53,0x42])

    def test_short_gate_has_no_invented_hold_and_raw_level_is_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'probe.wav';frames=round(.68*48000)
            time=np.arange(frames)/48000;data=(np.sin(2*np.pi*440*time)*2000).astype('<i2')
            with wave.open(str(path),'wb') as f:
                f.setparams((1,2,48000,frames,'NONE','not compressed'));f.writeframes(data.tobytes())
            case=dict(gate=.18,hz=440)
            features=probe.temporal_features(path,case)
            self.assertEqual([x['section'] for x in features],['attack','release'])
            same=probe.temporal_distance(features,features,1.)
            self.assertTrue(all(abs(x['level_delta_db'])<1e-12 for x in same))
            louder=probe.temporal_distance(features,features,2.)
            self.assertAlmostEqual(louder[0]['level_delta_db'],6.020599913,places=7)
if __name__=='__main__':unittest.main()
