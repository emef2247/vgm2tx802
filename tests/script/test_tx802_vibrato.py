"""Known phase curves validate the optional vibrato fitter."""
import importlib.util,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
HAS_NUMPY=importlib.util.find_spec('numpy') is not None
if HAS_NUMPY:
    import numpy as np
    import fit_tx802_vibrato as fit

@unittest.skipUnless(HAS_NUMPY,'Optional calibration NumPy dependency')
class VibratoTests(unittest.TestCase):
    def test_known_frequency_amplitude_and_phase_invariant_comparison(self):
        time=np.arange(.35,2.45,.01)
        source=fit.descriptor(time,9*np.sin(2*np.pi*6.075*time))
        target=fit.descriptor(time,9*np.sin(2*np.pi*6.075*time+.7))
        self.assertAlmostEqual(source['frequency_hz'],6.075,places=6)
        self.assertAlmostEqual(source['harmonic_amplitudes'][0],9.,places=6)
        self.assertLess(fit.distance(target,source),.01)
        self.assertEqual(fit.distance(source,source),0.)

    def test_missing_vibrato_or_insufficient_data_is_not_a_match(self):
        time=np.arange(.35,2.45,.01);source=fit.descriptor(time,9*np.sin(2*np.pi*6.075*time))
        silent=fit.descriptor(time,np.zeros(len(time)))
        self.assertEqual(fit.distance(silent,source),1e6)
        with self.assertRaises(ValueError):fit.descriptor(time[:10],np.zeros(10))
    def test_ablation_preserves_am_and_invalid_candidates_are_ineligible(self):
        self.assertEqual(fit.without_vibrato(bytes((0xc1,0x61,11,24))),bytes((0x81,0x21,11,24)))
        time=np.arange(.35,2.45,.01);source=fit.descriptor(time,9*np.sin(2*np.pi*6.075*time))
        self.assertIsNone(fit.eligible_score(source,source,1))
        self.assertIsNone(fit.eligible_score(fit.descriptor(time,np.zeros(len(time))),source,0))
        self.assertEqual(fit.eligible_score(source,source,0),0.)
if __name__=='__main__':unittest.main()
