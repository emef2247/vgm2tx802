"""TX802 target lookup tables retained from vgm2tx802 at 8816ed8.

Preset names/program assignments are approximations, not six-operator voice uploads.
No parser, old frame clock, random jitter or MIDI generation is imported here.
"""
from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class Tx802Voice:
    bank: str
    voice: int  # 1..64 within the selected bank

    def to_vnum(self) -> int:
        """Legacy local table index (0..255), not a wire Program Change value."""
        v = self.voice - 1
        b = self.bank.upper()
        if b == "I":
            return 0 + v      # Internal 1–32
        if b == "C":
            return 64 + v     # Internal 33–64 or Cartridge などの想定
        if b == "A":
            return 128 + v    # Preset A
        if b == "B":
            return 192 + v    # Preset B
        return v

TX802_MELODY_OPLL_TO_DEFAULT = {
    1:  Tx802Voice("I", 1), # I1: OPLL Violin
    2:  Tx802Voice("I", 2), # I2: OPLL Guitar
    3:  Tx802Voice("I", 3), # I3: OPLL Piano
    4:  Tx802Voice("I", 5), # I4: OPLL Flute
    5:  Tx802Voice("I", 5), # I5: OPLL Clarinet
    6:  Tx802Voice("I", 6), # I6: OPLL Oboe
    7:  Tx802Voice("I", 7), # I7: OPLL Trumpet
    8:  Tx802Voice("I", 8), # I8: OPLL Organ
    9:  Tx802Voice("I", 9), # I9: OPLL Horn
    10: Tx802Voice("I", 10), # I10: OPLL Synth
    11: Tx802Voice("I", 11), # I11: OPLL Harpsichord
    12: Tx802Voice("I", 12), # I12: OPLL Vibraphone
    13: Tx802Voice("I", 13), # I13: OPLL SynthBass
    14: Tx802Voice("I", 14), # I14: OPLL AcousticBass
    15: Tx802Voice("I", 15), # I15: OPLL ElectricGuitar
}

TX802_MELODY_OPLL_TO_PRESET_A_B = {
    1:  Tx802Voice("A", 11), # A11 Strings
    2:  Tx802Voice("A", 36), # A36 RubbaRoad -
    3:  Tx802Voice("A", 33), # A33 Piano   1
    4:  Tx802Voice("A", 23), # A23 Flute     -
    5:  Tx802Voice("B", 40), # B40 ClariSolo -
    6:  Tx802Voice("A", 20), # A20 Bassoon  -
    7:  Tx802Voice("A", 8),  # A8 SilvaTrmpt -
    8:  Tx802Voice("A", 48), # A48 TouchOrga
    9:  Tx802Voice("A", 10), # A10 FrenchHorn
    10: Tx802Voice("A", 38), # A38 FullTines -
    11: Tx802Voice("A", 41), # A41 Clavecin -
    12: Tx802Voice("B", 21), # B21 VibraPhone -
    13: Tx802Voice("B", 3), # B3 SkweekBass
    14: Tx802Voice("B", 2), # B2 StringBass -
    15: Tx802Voice("B", 11), # ,B11 FingaPicka
}

TX802_MELODY_OPLL_TO_OPLL = {
    1:  Tx802Voice("A", 19), # A19 Violins
    2:  Tx802Voice("B", 10), # B10 PickGuitar
    3:  Tx802Voice("A", 23), # A23 Flute
    4:  Tx802Voice("A", 21), # A21 Clarinet
    5:  Tx802Voice("A", 22), # A22 Oboe
    6:  Tx802Voice("A", 7),  # A07 Trumpet  A
    7:  Tx802Voice("A", 21), # A21 Clarinet
    8:  Tx802Voice("A", 51), # A51 BriteOrgan
    9:  Tx802Voice("A", 10), # A10 FrenchHorn
    10: Tx802Voice("B", 43), # B43 WhapSynth
    11: Tx802Voice("A", 44), # A44 HarpsiBox
    12: Tx802Voice("B", 21), # B21 VibraPhone
    13: Tx802Voice("B", 48), # B48 HarmoSynth
    14: Tx802Voice("A", 16), # A16 BowedBass
    15: Tx802Voice("B", 9),  # B09 GuitarBox
}

TX802_MELODY_OPLL_TO_GM = {
    1:  Tx802Voice("A", 33), # A33 Piano   1
    2:  Tx802Voice("A", 45), # A45 HarpsiWire
    3:  Tx802Voice("B", 21), # B21 VibraPhone
    4:  Tx802Voice("A", 51), # A51 BriteOrgan
    5:  Tx802Voice("B", 9),  # B09 GuitarBox
    6:  Tx802Voice("B", 10), # B10 PickGuitar
    7:  Tx802Voice("B", 3),  # B03 SkweekBass
    8:  Tx802Voice("B", 7),  # B07 JazzBass
    9:  Tx802Voice("A", 19), # A19 Violins
    10: Tx802Voice("A", 7),  # A07 Trumpet  A
    11: Tx802Voice("B", 42), # B42 ClaviBrass
    12: Tx802Voice("A", 22), # A22 Oboe
    13: Tx802Voice("A", 21), # A21 Clarinet
    14: Tx802Voice("A", 23), # A23 Flute
    15: Tx802Voice("B", 12), # B12 LeadaPicka
}


VELOCITIES = (98,86,76,68,60,52,44,38,32,26,22,18,14,12,10,6)


def velocity(attenuation):
    if not isinstance(attenuation, int) or not 0 <= attenuation <= 15:
        raise ValueError('OPLL attenuation must be an integer in 0..15')
    return VELOCITIES[attenuation]


def expression(attenuation):
    # Native OPLL volume is attenuation. The old unused helper had this direction;
    # old compute_cc11() accidentally made VOL=0 silent.
    return max(0, min(127, 127 - 8*attenuation))


def validate_voice(entry):
    if not isinstance(entry, dict):
        raise ValueError('TX802 voice assignment must be an object')
    bank = entry.get('bank', '').upper()
    number = entry.get('voice')
    if bank not in ('I','C','A','B') or isinstance(number, bool) or not isinstance(number, int) or not 1 <= number <= 64:
        raise ValueError('TX802 assignment requires bank I/C/A/B and voice 1..64')
    return dict(bank=bank, voice=number, label=str(entry.get('label', f'{bank}{number}')))


def load_voice_map(path):
    if path is None or not Path(path).exists():
        return {}
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(raw, dict):
        raise ValueError('TX802 voice map must be a JSON object')
    result = {}
    for key, entry in raw.items():
        if key.startswith('_'):
            continue
        try:
            patch = bytes.fromhex(key)
        except (ValueError, TypeError) as exc:
            raise ValueError('Invalid OPLL patch key in voice map') from exc
        if len(patch) != 8:
            raise ValueError('A user-voice key must contain eight OPLL bytes')
        result[patch.hex()] = validate_voice(entry)
    return result


def assign_user_patch(patch, mapping):
    key = patch.hex()
    if key in mapping:
        return validate_voice(mapping[key])
    if patch == bytes(8):
        entry = dict(bank='A', voice=11, label='Unused (all-zero)')
    else:
        used = {e['voice'] for e in mapping.values() if e['bank']=='I'}
        number = next((n for n in range(21,65) if n not in used), None)
        if number is None:
            raise ValueError('TX802 internal user-voice assignment capacity exceeded: I21..I64')
        entry = dict(bank='I', voice=number, label=f'I{number}')
    mapping[key] = entry
    return entry


def preset_voice(number, mode='default'):
    tables = {'default':TX802_MELODY_OPLL_TO_DEFAULT, 'name':TX802_MELODY_OPLL_TO_PRESET_A_B,
              'gm':TX802_MELODY_OPLL_TO_GM, 'opll':TX802_MELODY_OPLL_TO_OPLL}
    if mode not in tables or number not in tables[mode]:
        raise ValueError('Unknown TX802 preset/melody mode')
    voice = tables[mode][number]
    return dict(bank=voice.bank, voice=voice.voice, label=f'{voice.bank}{voice.voice}')


def bank_select(entry):
    entry = validate_voice(entry)
    banks = {'I':(0,0),'C':(0,1),'A':(1,0),'B':(1,1)}
    return (*banks[entry['bank']], entry['voice']-1)


def voice_csv_text(selected_patches):
    """Legacy OPLL OP2 interchange CSV: presets plus emitted I21+ patches.

    Rows retain the zero-based voice column, not a packed six-operator format.
    Unused gaps are identified by that column rather than filled with dummy voices.
    """
    import csv
    import io
    from opll import _ym2413_patch_to_mgsdrv
    source = Path(__file__).resolve().parents[1]/'data/opll/presets/OPLL_OP2_MB14.csv'
    with source.open(encoding='utf-8',newline='') as f:
        reader=csv.DictReader(f)
        fields=list(reader.fieldnames)
        rows=list(reader)
    pending=[]
    for key, entry in selected_patches.items():
        entry=validate_voice(entry)
        if entry['bank']!='I' or entry['voice']<21:
            continue
        patch=bytes.fromhex(key)
        if len(patch)!=8:
            raise ValueError('OPLL CSV requires complete eight-byte patches')
        d=_ym2413_patch_to_mgsdrv(patch)
        row=dict(voice=str(entry['voice']-1),name=f"I{entry['voice']} User patch {key}",ALG='0',FB=str(d['fb']))
        for prefix,op in (('OP1',d['mod']),('OP2',d['car'])):
            for field,index in (('AR',0),('DR',1),('SL',2),('RR',3),('KSL',4),('MULTI',5),('AM',6),('VIB',7),('EGT',8),('KSR',9)):
                row[f'{prefix}_{field}']=str(op[index])
            row[f'{prefix}_TL']=str(d['tl'] if prefix=='OP1' else 0)
            row[f'{prefix}_WS']='0' # retained legacy interchange convention
        pending.append((entry['voice'],key,row))
    occupied={}
    for number,key,row in sorted(pending):
        if number in occupied and occupied[number]!=key:
            raise ValueError(f'Two different source patches require the same CSV slot I{number}')
        occupied[number]=key
        rows.append({field:row.get(field,'') for field in fields})
    out=io.StringIO(newline='')
    writer=csv.DictWriter(out,fieldnames=fields,lineterminator='\n')
    writer.writeheader();writer.writerows(rows)
    return out.getvalue()
