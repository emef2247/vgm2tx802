"""Experimental rhythm output uses five synth voices, preserving native evidence."""
from dataclasses import asdict,replace
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'py'))
from native_music import NativeDevice, NativePerformance, NativePercussion
from tx802_rhythm_target import FAMILIES,load_rhythm_profile,project_rhythm
from tx802_midi import decode_smf
from tx802_voices import velocity


class RhythmExportTests(unittest.TestCase):
    def setUp(self):
        self.profiles=load_rhythm_profile(ROOT/'data/tx802/OPLL_DX7II_rhythm.csv')

    def performance(self,hits):
        device=NativeDevice('opll:0','opll',0,3579545)
        return NativePerformance((device,),(),(),(),tuple(hits),(),44100,'authored','')

    def hit(self,family='BD',start=4410,stop=8820,volume=0,identity='hit'):
        return NativePercussion(identity,'opll:0','0',family,start,stop,((start,volume),))

    def messages(self,data):
        return [(t,at,event) for t,events in enumerate(decode_smf(data)['tracks'])
                for at,event in events if 0x80<=event[0]<0xf0]

    def test_five_fm_parts_and_bank_slots_match_profile_not_gm_channel10(self):
        source=self.performance([self.hit(f,identity=f) for f in FAMILIES]);before=asdict(source)
        result=project_rhythm(source,self.profiles);events=self.messages(result.data)
        self.assertEqual(asdict(source),before)
        self.assertEqual({e[2][0]&15 for e in events if e[2][0]&240==0x90},set(range(5)))
        self.assertEqual([e[2][1] for e in events if e[2][0]&240==0xc0],list(range(15,20)))
        self.assertTrue(all(h['start_tick']==96 and h['stop_tick']==192 for h in result.hits))
        self.assertEqual(result.report['notes'],5)

    def test_fixed_calibrated_pitch_and_onset_velocity_ignore_source_pitch_curve(self):
        event=replace(self.hit(volume=4),pitch_curve=((4410,880.),),volume_curve=((4410,4),(5000,8)))
        result=project_rhythm(self.performance([event]),self.profiles)
        self.assertEqual(result.hits[0]['velocity'],velocity(4))
        self.assertEqual(result.hits[0]['note'],self.profiles['BD']['note'])
        self.assertTrue(result.report['source_rhythm_pitch_context_not_projected'])
        self.assertIn('internal_volume_curve_retained_only_in_native',[x['kind'] for x in result.report['losses']])

    def test_repeat_noteoff_precedes_next_on_and_zero_tick_hits_are_reported(self):
        events=[self.hit(start=10,stop=8000,identity='first'),self.hit(start=10,stop=9000,identity='second')]
        result=project_rhythm(self.performance(events),self.profiles)
        self.assertEqual([(h['start_tick'],h['stop_tick']) for h in result.hits],[(0,1),(1,196)])
        at1=[e[2][0]&240 for e in self.messages(result.data) if e[0]==1 and e[1]==1]
        self.assertEqual(at1,[0x80,0x90])
        self.assertIn('subtick_hit_displaced',[x['kind'] for x in result.report['losses']])

    def test_missing_stop_and_unknown_volume_are_explicit(self):
        source=self.performance([self.hit(stop=None)])
        result=project_rhythm(source,self.profiles)
        self.assertIsNone(result.hits[0]['observed_stop_sample'])
        self.assertIn('unobserved_stop_uses_target_gate',[x['kind'] for x in result.report['losses']])
        with self.assertRaises(ValueError):project_rhythm(self.performance([self.hit(volume=None)]),self.profiles)
        with self.assertRaises(ValueError):project_rhythm(self.performance([]),self.profiles)

    def test_dump_retains_source_stop_and_target_time_separately(self):
        result=project_rhythm(self.performance([self.hit()]),self.profiles)
        with tempfile.TemporaryDirectory() as tmp:
            result.dump(tmp,'probe')
            self.assertTrue((Path(tmp)/'probe.mid').is_file())
            text=(Path(tmp)/'probe.rhythm.hits.csv').read_text()
            self.assertIn('observed_stop_sample',text);self.assertIn('stop_tick',text)


if __name__=='__main__':unittest.main()
