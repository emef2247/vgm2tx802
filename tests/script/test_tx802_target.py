"""Synthetic source-to-TX802 event semantics and batch product isolation."""
from dataclasses import asdict, replace
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'py'),str(ROOT/'scripts'),str(ROOT/'tests/script')]
from native_music import NativeDevice, NativePerformance, NativeUnit, NativeVoice, NativePercussion, NativeControl
from tx802_target import project_tx802, TX802ProjectionError
from tx802_voices import velocity, expression, assign_user_patch, load_voice_map
from tx802_midi import decode_smf, meta
from export_tx802 import run_batch
from test_native_imports import vgm


def performance(end=44100):
    device=NativeDevice('opll:0','opll',0,3579545)
    voice=NativeVoice('v1','opll:0','fm',(('instrument',1),('custom_patch',())))
    unit=NativeUnit('u1','opll:0','fm',0,0,end,((0,440.),),((0,0),),((0,'v1'),))
    return NativePerformance((device,),(unit,),(),(voice,),(),(),end,'authored','')


def channel_events(result):
    return [(track,at,data) for track,events in enumerate(decode_smf(result.data)['tracks'])
            for at,data in events if 0x80<=data[0]<=0xef]


class TX802TargetTests(unittest.TestCase):
    def test_native_unchanged_exact_sample_clock_and_binary_matches_plan(self):
        source=performance();before=asdict(source)
        result=project_tx802(source)
        self.assertEqual(asdict(source),before)
        self.assertEqual(result.report['source_clock_hz'],44100)
        self.assertIn((1,12,bytes((0x90,69,98))),channel_events(result))
        actual=channel_events(result)
        expected=[(e.track,e.midi_tick,bytes.fromhex(e.data_hex)) for e in result.events
                  if 0x80<=bytes.fromhex(e.data_hex)[0]<=0xef]
        self.assertEqual(actual,sorted(expected,key=lambda e:(e[0],e[1])))

    def test_velocity_table_and_expression_direction(self):
        self.assertEqual([velocity(i) for i in (0,5,10,15)],[98,52,22,6])
        self.assertGreater(expression(0),expression(15))
        source=performance();unit=replace(source.units[0],volume_curve=((0,10),))
        result=project_tx802(replace(source,units=(unit,)))
        self.assertEqual(next(bytes.fromhex(e.data_hex)[2] for e in result.events if e.kind=='note_on'),22)
        self.assertEqual(next(bytes.fromhex(e.data_hex)[2] for e in result.events if e.kind=='expression'),127)

    def test_curved_volume_uses_peak_velocity_and_relative_expression(self):
        source=performance();unit=replace(source.units[0],volume_curve=((0,10),(22050,0),(33075,15)))
        result=project_tx802(replace(source,units=(unit,)))
        self.assertEqual(sum(e.kind=='note_on' for e in result.events),1)
        self.assertEqual(result.report['gates'][0]['attack_velocity'],98)
        self.assertEqual([bytes.fromhex(e.data_hex)[2] for e in result.events if e.kind=='expression'],[47,127,7])

    def test_held_pitch_uses_bend_without_added_attack(self):
        source=performance();unit=replace(source.units[0],pitch_curve=((0,440.),(22050,880.)))
        result=project_tx802(replace(source,units=(unit,)))
        self.assertEqual(sum(e.kind=='note_on' for e in result.events),1)
        bends=[bytes.fromhex(e.data_hex) for e in result.events if e.kind=='pitch_bend']
        self.assertEqual(bends,[bytes((0xe0,0,64)),bytes((0xe0,127,127))])
        self.assertFalse(any(bytes.fromhex(e.data_hex)[0]==0xf0 for e in result.events))

    def test_bend_overflow_strict_or_reported_force(self):
        source=performance();unit=replace(source.units[0],pitch_curve=((0,440.),(22050,1760.)))
        source=replace(source,units=(unit,))
        with self.assertRaisesRegex(TX802ProjectionError,'bend range'):
            project_tx802(source)
        result=project_tx802(source,force=True)
        self.assertTrue(any(x['kind']=='held_pitch_bend_clipped' for x in result.report['losses']))

    def test_same_pitch_retrigger_off_precedes_on(self):
        source=performance(end=4410);a=replace(source.units[0],end_sample=2205)
        b=replace(a,unit_id='u2',start_sample=2205,end_sample=4410,pitch_curve=((2205,440.),),
                  volume_curve=((2205,0),),voice_curve=((2205,'v1'),))
        result=project_tx802(replace(source,units=(a,b)))
        seam=12+48
        kinds=[e.kind for e in result.events if e.midi_tick==seam]
        self.assertLess(kinds.index('note_off'),kinds.index('note_on'))
        self.assertEqual(sum(e.kind=='note_on' for e in result.events),2)

    def test_three_subtick_gates_remain_distinct_and_nonoverlapping(self):
        source=performance(end=3)
        units=tuple(replace(source.units[0],unit_id=f'u{i}',start_sample=i,end_sample=i+1,
                            pitch_curve=((i,440.),),volume_curve=((i,0),),voice_curve=((i,'v1'),)) for i in range(3))
        result=project_tx802(replace(source,units=units))
        self.assertEqual([g['start_tick'] for g in result.report['gates']],[12,13,14])
        self.assertEqual([g['end_tick'] for g in result.report['gates']],[13,14,15])
        self.assertEqual(result.report['cumulative_gate_delay_ticks'],3)

    def test_bank_only_change_reissues_program_without_retrigger(self):
        source=performance()
        custom=NativeVoice('custom','opll:0','fm',(('instrument',0),('custom_patch',(1,2,3,4,5,6,7,8))))
        unit=replace(source.units[0],voice_curve=((0,'v1'),(22050,'custom')))
        source=replace(source,units=(unit,),voices=source.voices+(custom,))
        result=project_tx802(source,voice_map={'0102030405060708':dict(bank='A',voice=1)})
        programs=[bytes.fromhex(e.data_hex) for e in result.events if e.kind=='program']
        self.assertEqual(programs,[bytes((0xc0,0)),bytes((0xc0,0))])
        self.assertEqual(sum(e.kind=='note_on' for e in result.events),1)
        self.assertTrue(any(x['kind']=='mid_gate_program_change_hardware_dependent' for x in result.report['losses']))

    def test_one_unit_capacity_and_two_port_routing(self):
        source=performance()
        units=tuple(replace(source.units[0],unit_id=f'u{i}',channel=i) for i in range(9))
        source=replace(source,units=units)
        with self.assertRaisesRegex(TX802ProjectionError,'part capacity'):
            project_tx802(source)
        partial=project_tx802(source,force=True)
        self.assertEqual(partial.report['channels'],8)
        self.assertTrue(any(x['kind']=='part_capacity' for x in partial.report['omitted']))
        result=project_tx802(source,tx802_units=2)
        route=result.mappings[8]
        self.assertEqual((route['port'],route['channel'],route['tg']),(1,0,1))
        tracks=decode_smf(result.data)['tracks']
        self.assertIn((0,meta(0x21,b'\x01')),tracks[route['track']])
        self.assertEqual(sum(e.kind=='program' for e in result.events),9)

    def test_all_drum_families_and_shared_lead(self):
        source=performance(end=4410)
        drums=tuple(NativePercussion(f'd{i}','opll:0',str(i),family,0,2205,((0,0),))
                    for i,family in enumerate(('BD','SD','TOM','CYM','HH')))
        result=project_tx802(replace(source,percussion=drums))
        drum_on=[e for e in result.events if e.kind=='drum_on']
        self.assertEqual({bytes.fromhex(e.data_hex)[1] for e in drum_on},{45,52,50,60,57})
        self.assertTrue(all(e.midi_tick==12 and e.channel==9 for e in drum_on))
        self.assertFalse(any(e.kind=='expression' and e.channel==9 for e in result.events))

    def test_fast_repeated_drum_keeps_attack_time(self):
        source=performance(end=44100)
        for observed_stop in (None,22050):
            with self.subTest(stop=observed_stop):
                drums=(NativePercussion('d0','opll:0','4','HH',0,observed_stop,((0,0),)),
                       NativePercussion('d1','opll:0','4','HH',441,None,((441,0),)))
                result=project_tx802(replace(source,units=(),percussion=drums))
                self.assertEqual([e.midi_tick for e in result.events if e.kind=='drum_on'],[12,22])
                self.assertEqual(next(e.midi_tick for e in result.events if e.kind=='drum_off'),22)
                seam=[e.kind for e in result.events if e.midi_tick==22]
                self.assertLess(seam.index('drum_off'),seam.index('drum_on'))
                self.assertTrue(any(x['kind']=='rhythm_gate_shortened_before_repeated_key' for x in result.report['losses']))

    def test_no_init_preserves_source_origin_and_trailing_silence(self):
        source=performance();unit=replace(source.units[0],start_sample=2205,end_sample=4410,
                                        pitch_curve=((2205,440.),),volume_curve=((2205,0),),voice_curve=((2205,'v1'),))
        result=project_tx802(replace(source,units=(unit,)),domino_init=False)
        self.assertEqual(next(e.midi_tick for e in result.events if e.kind=='note_on'),48)
        self.assertEqual(decode_smf(result.data)['tracks'][1][-1][0],961)

    def test_zero_width_setup_voices_do_not_consume_user_slots(self):
        source=performance()
        partial=NativeVoice('partial','opll:0','fm',(('instrument',0),('custom_patch',(1,None,None,None,None,None,None,None))))
        full=NativeVoice('full','opll:0','fm',(('instrument',0),('custom_patch',(1,2,3,4,5,6,7,8))))
        unit=replace(source.units[0],voice_curve=((0,'partial'),(0,'full')))
        result=project_tx802(replace(source,units=(unit,),voices=(partial,full)))
        self.assertEqual(set(result.user_voice_map),{'0102030405060708'})
        self.assertEqual(result.user_voice_map['0102030405060708']['voice'],21)

    def test_custom_patch_identity_and_user_slots(self):
        mapping={}
        self.assertEqual(assign_user_patch(bytes(8),mapping)['bank'],'A')
        self.assertEqual(assign_user_patch(bytes((1,)*8),mapping)['voice'],21)
        self.assertEqual(assign_user_patch(bytes((1,)*8),mapping)['voice'],21)
        occupied={bytes((i,)*8).hex():dict(bank='I',voice=i+20,label='x') for i in range(1,45)}
        with self.assertRaisesRegex(ValueError,'capacity'):
            assign_user_patch(bytes((99,)*8),occupied)

    def test_unsupported_device_report_and_unused_header(self):
        source=performance();extra=NativeDevice('psg:0','psg',0,1789773)
        source=replace(source,devices=source.devices+(extra,))
        self.assertEqual(project_tx802(source).report['omitted'],[])
        source=replace(source,controls=(NativeControl('c','psg:0','tone',0,0,0,'volume',()),))
        with self.assertRaisesRegex(TX802ProjectionError,'OPLL only'):
            project_tx802(source)
        self.assertEqual(project_tx802(source,force=True).report['omitted'][0]['source_chip'],'psg')

    def test_source_loop_is_marker_not_executed_repeat(self):
        source=replace(performance(),song_loop_sample=22050,song_loop_order=0)
        result=project_tx802(source)
        marks=[e for e in result.events if e.kind=='loop_marker']
        self.assertEqual([e.midi_tick for e in marks],[492,972])


class TX802BatchTests(unittest.TestCase):
    def make_source(self,path,custom=False,foreign=False):
        commands=bytes.fromhex('51 30 10 51 10 a0 51 20 18 62 62 51 20 08 62')
        if custom:
            commands=b''.join(bytes((0x51,i,i+1)) for i in range(8))+commands.replace(bytes.fromhex('51 30 10'),bytes.fromhex('51 30 00'))
        if foreign:
            commands+=bytes.fromhex('a0 00 80 a0 01 01 a0 07 3e a0 08 0f 62')
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(vgm(commands,{0x10:3579545,0x74:1789773} if foreign else {0x10:3579545}))

    def test_recursive_layout_and_safe_forced_rerun(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.make_source(root/'in/provider/album/authored.vgm')
            output=root/'out';rows=run_batch(root/'in',output)
            self.assertEqual(rows[0]['status'],'success',rows)
            package=output/'provider/album'
            for relative in ('tracks/authored.mid','tracks/authored.vgm','blueprint/authored.mml','blueprint/authored.midi'):
                self.assertTrue((package/relative).exists(),relative)
            self.assertEqual(run_batch(root/'in',output,force=True)[0]['status'],'success')

    def test_beside_source_does_not_reimport_generated_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.make_source(root/'album/authored.vgm')
            self.assertEqual(len(run_batch(root)),1)
            self.assertEqual(len(run_batch(root,force=True)),1)

    def test_source_products_survive_target_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.make_source(root/'authored.vgm',foreign=True)
            row=run_batch(root/'authored.vgm',root/'out')[0]
            self.assertEqual(row['status'],'conversion_failed')
            self.assertTrue(row['reference_vgm']);self.assertTrue(row['blueprint'])
            self.assertFalse((root/'out/tracks/authored.mid').exists())

    def test_edited_voice_map_is_consumed_and_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'authored.vgm';self.make_source(source,custom=True)
            output=root/'out';rows=run_batch(source,output)
            self.assertEqual(rows[0]['status'],'success',rows)
            path=output/'tracks/authored.user_voice_tx802.json'
            mapping=json.loads(path.read_text());key=next(iter(mapping))
            mapping[key]=dict(bank='B',voice=4,label='my arrangement')
            text=json.dumps(mapping,indent=4);path.write_text(text)
            row=run_batch(source,output,force=True)[0]
            self.assertEqual(row['status'],'success',row)
            self.assertEqual(path.read_text(),text)
            report=json.loads((output/'_diagnostics/authored/authored.tx802.projection.json').read_text())
            self.assertTrue(any(e['bank']=='B' and e['voice']==4 for e in report['voice_selections'].values()))

    def test_broken_explicit_map_does_not_fallback_silently(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'authored.vgm';self.make_source(source,custom=True)
            path=root/'map.json';path.write_text('{broken')
            row=run_batch(source,root/'out',voice_map=path)[0]
            self.assertEqual(row['status'],'conversion_failed')
            self.assertTrue(row['reference_vgm'])


if __name__=='__main__':
    unittest.main()
