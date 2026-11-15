"""Optional calibration exploration retains pitch guard and component accounting."""
import importlib.util
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
HAS_NUMPY=importlib.util.find_spec('numpy') is not None
if HAS_NUMPY:
    import numpy as np
    import explore_tx802_presets as search

@unittest.skipUnless(HAS_NUMPY,'NumPy is optional calibration tooling')
class ExplorationTests(unittest.TestCase):
    def test_octave_sine_vectors(self):
        source=np.zeros(64);source[1]=1
        self.assertTrue(search.octave_contrast(source,source)['ok'])
        for bin_index in (0,3):
            target=np.zeros(64);target[bin_index]=1
            self.assertFalse(search.octave_contrast(target,source)['ok'])

    def test_components_add_to_existing_score(self):
        source=dict(rms=1.,harmonics=np.ones(16)/16,envelope=np.ones(10))
        target=dict(rms=.8,harmonics=np.ones(16)/16,envelope=np.ones(10)*.7)
        parts=search.components(target,source,1.)
        self.assertAlmostEqual(parts['score'],sum(parts[k] for k in ('amplitude','spectrum','envelope')))

    def test_structure_keeps_note_anchor(self):
        seed=search.cal.base_row('TEST');seed['OP5_OL']=90
        candidates=list(search.structures(seed))
        self.assertEqual(len(candidates),56)
        for row in candidates:
            self.assertEqual(row['OP5_COARSE'],1)
            self.assertEqual(row['OP5_FINE'],0)
            self.assertGreater(row['OP5_OL'],0)
            for op in (2,4,6):self.assertIn(row[f'OP{op}_COARSE'],(1,2,3,4))
if __name__=='__main__':unittest.main()
