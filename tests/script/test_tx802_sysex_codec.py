"""Independent documented field vectors for calibration CSV serialization."""
import csv,importlib.util,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];TOOLS=ROOT/'tools/legacy_tx802'
sys.path.insert(0,str(TOOLS))
from tx802_sysex_codec import pack_calibration_voice
spec=importlib.util.spec_from_file_location('single_codec',TOOLS/'convert_tx802csv_to_dx7_single_voice_syx.py')
single=importlib.util.module_from_spec(spec);spec.loader.exec_module(single)
class CalibrationWireTests(unittest.TestCase):
    def test_operator_order_flags_levels_and_globals(self):
        row=dict(name='VECTOR',ALG=4,FB=5,SYNC=1,OP1_R1=11,OP6_R1=91,OP6_L1=82,
                 OP6_BP=39,OP6_LC=2,OP6_RC=1,OP6_RS=3,OP6_DT=9,OP6_AMS=2,
                 OP6_KVS=7,OP6_OL=83,OP6_MODE=1,OP6_COARSE=11,OP6_FINE=19)
        data=pack_calibration_voice(row)
        self.assertEqual(data[0],91);self.assertEqual(data[4],82);self.assertEqual(data[8],39)
        self.assertEqual(list(data[11:17]),[6,75,30,83,23,19])
        self.assertEqual(data[85],11)
        self.assertEqual(list(data[110:112]),[4,13])
        self.assertEqual(data[117],24)
        unpacked=single.build_dx7_single_voice_payload(row,'VECTOR')
        self.assertEqual(list(unpacked[11:21]),[2,1,3,2,7,83,1,11,19,9])
        self.assertEqual(unpacked[105],11)
        self.assertEqual(list(unpacked[134:137]),[4,5,1])
    def test_delivered_fifteen_presets_are_complete_and_legal(self):
        with (ROOT/'data/tx802/OPLL_DX7II_presets.csv').open() as f:rows=list(csv.DictReader(f))
        self.assertEqual([int(r['source_preset']) for r in rows],list(range(1,16)))
        self.assertEqual([int(r['voice']) for r in rows],list(range(1,16)))
        for row in rows:
            packed=pack_calibration_voice(row)
            self.assertEqual(len(packed),128)
            self.assertTrue(any(packed[op*17+14]>0 for op in range(6)))

    def test_vibrato_profile_changes_only_declared_fields_and_packs_lfo(self):
        def read(name):
            with (ROOT/'data/tx802'/name).open() as f:return list(csv.DictReader(f))
        baseline=read('OPLL_DX7II_presets.csv');profile=read('OPLL_DX7II_presets_vibrato.csv')
        self.assertEqual(len(profile),15)
        for index,(before,after) in enumerate(zip(baseline,profile)):
            changed={key for key in before if before[key]!=after[key]}
            self.assertEqual(changed,{'LFO_SPEED','LFO_PMD','LFO_PMS'} if index==9 else set())
            self.assertEqual(len(pack_calibration_voice(after)),128)
        self.assertEqual(list(pack_calibration_voice(profile[9])[112:117]),[38,0,26,0,16])

    def test_invalid_parameter_does_not_wrap(self):
        with self.assertRaises(ValueError): pack_calibration_voice(dict(OP1_R1=100))
if __name__=='__main__':unittest.main()
