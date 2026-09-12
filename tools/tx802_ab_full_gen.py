#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# TX802 BANK A/B Domino XML generator (FULL ModuleData version)
# InstrumentList / DrumSetList / ControlChangeMacroList / TemplateList 完全版

from xml.sax.saxutils import escape
import sys

# -------------------------
# TX802 BANK A / B NAMES
# -------------------------

bank_a = [
    "MellowHorn","SilvaBrass","ReverbBras","Tuba","Trombone","HardTrumps","Trumpet A","SilvaTrmpt",
    "Trumpet B","FrenchHorn","Strings","HallOrch","NewOrchest","Analog-Str","LiveStrg","BowedBass",
    "EleCello A","EleCello B","Violins","Bassoon","Clarinet","Oboe","Flute","SongFlute",
    "SpitFlute","PanFluot","Piccolo","Sax","Harmonica","Harp","EbonyIvory","PianoBrite",
    "Piano 1","Piano 2","KnockRoad","RubbaRoad","HardRoads","FullTines","ClaviStuff","Clavi",
    "Clavecin","ClaviPluck","NasalClav","HarpsiBox","HarpsiWire","WireStrg A","WireStrg B","TouchOrgan",
    "ShOrgan","TapOrgan","BriteOrgan","MagicOrgan","SoftOrgan","PipeOrgan","PuffOrgan1","PuffPipes",
    "PuffOrgan2","Harmonium1","Harmonium2","Whisper A","Choir","LadyVox","MaleChoir","Whisper B"
]

bank_b = [
    "SuperBass","StringBass","SkweekBass","SmoothBass","BopBass","OwlBass","JazzBass","HardBass",
    "GuitarBox","PickGuitar","FingaPicka","LeadaPicka","YesBunk","12 Strings","Classipika","Shami",
    "Maribumba","DX Marimba","Nu Marimba","StonePhone","VibraPhone","Celeste","Swissnare","Tom C4",
    "CongaDrum","Tub Bells","Gong","Timpani","Claves","Bells","SteelCans","Handrum",
    "Analog-X","FMilters","Phasers","Ensemble","MalletHorn","FM-Growth","ElectoComb","ClariSolo",
    "PitchaPad","ClaviBrass","WhapSynth","Whasers","Fifths","ElecBrass","ElectroBak","HarmoSynth",
    "PianoBells","St.Elmo’s","MilkyWays","Pluk","TingVoice","Plukatan","OctiLate","LateDown",
    "Glastine","BellWahh","RubberGong","Wallop","Explosion","KoikeCycle","Thunderon","Science"
]

# -------------------------
# GM DRUMSET
# -------------------------

gm_list = [
    ("Acou Bass Drum",35),("Bass Drum 1",36),("Side Stick",37),("Acoustic Snare",38),
    ("Hand clap",39),("Electoric Snare",40),("Low Floor Tom",41),("Closed Hi-Hat",42),
    ("High Floor Tom",43),("Pedal Hi-Hat",44),("Low Tom",45),("Open Hi-Hat",46),
    ("Low Mid Tom",47),("Hi Mid Tom",48),("Crash Cymbal 1",49),("High Tom",50),
    ("Ride Cymbal 1",51),("Chinese Cymbal",52),("Ride Bell",53),("Tambourine",54),
    ("Splash Cymbal",55),("Cowbell",56),("Crash Cymbal 2",57),("Vibraslap",58),
    ("Ride Cymbal 2",59),("Hi Bongo",60),("Low Bongo",61),("Mute Hi Conga",62),
    ("Open Hi Conga",63),("Low Conga",64),("High Timbale",65),("Low Timbale",66),
    ("High Agogo",67),("Low Agogo",68),("Cabassa",69),("Maracas",70),
    ("Short Whistle",71),("Long Whistle",72),("Short Guiro",73),("Long Guiro",74),
    ("Claves",75),("High Wood Block",76),("Low Wood Block",77),("Mute Cuica",78),
    ("Open Cuica",79),("Mute Triangle",80),("Open Triangle",81)
]

# -------------------------
# RX21 DRUMSET
# -------------------------

rx21_list = [
    ("bd",45),("sd",52),("tom",50),("tc",38),("hh",39),("cym",40)
]

# -------------------------
# ProgramList GENERATOR
# -------------------------
def write_programlist(w):
    w('  <ProgramList>\n')

    # BANK A
    for i, name in enumerate(bank_a):
        number = i + 1 
        gui_pc = i + 1
        pname = f"A{(i+1):02d} {name}"
        w(
            f'    <Program Number="{number}" Name="{escape(pname)}" '
            f'Map="TX802 Internal PresetA" PC="{gui_pc}" />\n'
        )

    # BANK B
    for i, name in enumerate(bank_b):
        number = 64 + i + 1
        gui_pc = 64 + i + 1
        pname = f"B{(i+1):02d} {name}"
        w(
            f'    <Program Number="{number}" Name="{escape(pname)}" '
            f'Map="TX802 Internal PresetB" PC="{gui_pc}" />\n'
        )

    w('  </ProgramList>\n\n')


# -------------------------
# MAIN GENERATOR
# -------------------------

def main(out_path):
    with open(out_path, "w", encoding="shift_jis", newline="\n") as f:
        w = f.write

        # HEADER
        w('<?xml version="1.0" encoding="Shift_JIS"?>\n')
        w('<ModuleData Name="TX802 A/B" Folder="YAMAHA" Priority="10" FileCreator="tx802_ab_gen" FileVersion="1.00">\n\n')

        # -------------------------
        # InstrumentList
        # -------------------------
        w('  <InstrumentList>\n')

        # BANK A
        w('    <Map Name="TX802 Internal PresetA">\n')
        for i, name in enumerate(bank_a, start=1):
            w(f'      <PC Name="{escape(name)}" PC="{i}">\n')
            w('        <Bank Name="A" MSB="1" LSB="0" />\n')
            w('      </PC>\n')
        w('    </Map>\n')

        # BANK B
        w('    <Map Name="TX802 Internal PresetB">\n')
        for i, name in enumerate(bank_b, start=1):
            w(f'      <PC Name="{escape(name)}" PC="{i}">\n')
            w('        <Bank Name="B" MSB="1" LSB="1" />\n')
            w('      </PC>\n')
        w('    </Map>\n')

        w('  </InstrumentList>\n\n')

        # -------------------------
        # DrumSetList
        # -------------------------
        w('  <DrumSetList>\n')

        # GM
        w('    <Map Name="GM">\n')
        w('      <PC Name="Rhythm" PC="1">\n')
        w('        <Bank Name="Rhythm" LSB="0" MSB="0">\n')
        for name, key in gm_list:
            w(f'          <Tone Name="{escape(name)}" Key="{key}" />\n')
        w('        </Bank>\n')
        w('      </PC>\n')
        w('    </Map>\n')

        # RX21
        w('    <Map Name="RX21">\n')
        w('      <PC Name="Rhythm" PC="1">\n')
        w('        <Bank Name="Rhythm" LSB="0" MSB="0">\n')
        for name, key in rx21_list:
            w(f'          <Tone Name="{escape(name)}" Key="{key}" />\n')
        w('        </Bank>\n')
        w('      </PC>\n')
        w('    </Map>\n')

        w('  </DrumSetList>\n\n')

        # -------------------------
        # ProgramList
        # -------------------------
        # write_programlist(w)

        # -------------------------
        # ControlChangeMacroList
        # -------------------------
        w('  <ControlChangeMacroList>\n')
        w('    <Folder Name="Performance">\n')

        w('      <CCM ID="0" Name="Pitch Bend"><Data>@PB #VH #VL</Data></CCM>\n')
        w('      <CCM ID="1" Name="Modulation"><Data>@CC 1 #VL</Data></CCM>\n')
        w('      <CCM ID="7" Name="Volume"><Data>@CC 7 #VL</Data></CCM>\n')
        w('      <CCM ID="10" Name="Pan"><Data>@CC 10 #VL</Data></CCM>\n')
        w('      <CCM ID="11" Name="Expression"><Data>@CC 11 #VL</Data></CCM>\n')
        w('      <CCM ID="32" Name="Bank Select LSB"><Data>@CC 32 #VL</Data></CCM>\n')
        w('      <CCM ID="64" Name="Sustain"><Data>@CC 64 #VL</Data></CCM>\n')
        w('      <CCM ID="65" Name="Portamento"><Data>@CC 65 #VL</Data></CCM>\n')

        w('    </Folder>\n')
        w('  </ControlChangeMacroList>\n\n')


        # -------------------------
        # TemplateList（TX802 専用）
        # -------------------------
        w('  <TemplateList>\n')
        w('    <Template Name="TX802">\n')
        w('      <Map Name="TX802 Internal PresetA" />\n')
        w('      <Map Name="TX802 Internal PresetB" />\n')
        w('    </Template>\n')
        w('  </TemplateList>\n\n')

        # FOOTER
        w('</ModuleData>\n')


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python tx802_ab_full_gen.py TX802_AB.xml")
        sys.exit(1)
    main(sys.argv[1])


