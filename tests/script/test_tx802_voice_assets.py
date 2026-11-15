"""Existing TX802 tool orchestration preserves hardware slot identities."""
import csv,io,json,sys,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'py'))
from tx802_voices import voice_csv_text
from tx802_voice_assets import build_voice_assets,check_packet

class VoiceAssetTests(unittest.TestCase):
    def setUp(self):
        self.acceptance=patch('tx802_voice_assets.validate_in_texed',return_value={'status':'accepted','test_double':True})
        self.acceptance.start();self.addCleanup(self.acceptance.stop)

    def test_sparse_second_bank_and_only_actual_single_voices(self):
        text=voice_csv_text({'0102030405060708':dict(bank='I',voice=35)})
        with tempfile.TemporaryDirectory() as tmp:
            files,report=build_voice_assets(text,tmp,'authored')
            self.assertEqual(set(files),{'voices/authored.bank01.syx','voices/authored.bank02.syx','voices/authored.I35.syx','voices/authored.texed.csv'})
            for path,data in files.items():
                if path.endswith('.syx'): check_packet(data,9 if 'bank' in path else 0)
            route=next(r for r in report['routing'] if r['internal_voice']==35)
            self.assertEqual((route['bank_path'],route['bank_program']),('voices/authored.bank02.syx',2))
            self.assertEqual(report['placeholder_slots'],list(range(21,35)))
            self.assertEqual(report['banks'][1]['padding'],29)
            self.assertTrue((Path(tmp)/'voice_slots.csv').exists())
            self.assertTrue((Path(tmp)/'voice_slots_tx802_op6.csv').exists())

    def test_calibration_schema_uses_one_based_slots_and_singles(self):
        text='voice,source_preset,name,OP1_R1,OP5_OL\n1,1,calibrated,99,90\n'
        with tempfile.TemporaryDirectory() as tmp:
            files,report=build_voice_assets(text,tmp,'calibrated')
            self.assertIn('voices/calibrated.I01.syx',files)
            self.assertEqual(report['actual_slots'],[1])
            self.assertEqual(report['routing'][0]['bank_program'],0)

    def test_packet_corruption_is_rejected(self):
        with self.assertRaises(ValueError): check_packet(bytes(4104),9)

if __name__=='__main__': unittest.main()
