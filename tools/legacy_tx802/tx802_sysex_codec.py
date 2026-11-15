"""Explicit DX7II parameter CSV -> the existing Format09 packed voice payload.

Calibration-only schema. The legacy CSV branch is retained in the calling tools.
"""
def pack_calibration_voice(row):
    def number(name,default,maximum):
        value=int(row.get(name,default))
        if not 0<=value<=maximum:
            raise ValueError(f'{name} outside 0..{maximum}')
        return value
    packed=bytearray()
    for op in range(6,0,-1):
        def n(field,default=0,maximum=99):return number(f'OP{op}_{field}',default,maximum)
        packed.extend(n(f'R{i}',99) for i in range(1,5))
        packed.extend(n(f'L{i}',99 if i<4 else 0) for i in range(1,5))
        packed.extend((n('BP'),n('LD'),n('RD'),n('LC',0,3)|(n('RC',0,3)<<2),
                       n('RS',0,7)|(n('DT',7,14)<<3),n('AMS',0,3)|(n('KVS',0,7)<<2),
                       n('OL'),n('MODE',0,1)|(n('COARSE',1,31)<<1),n('FINE')))
    packed.extend(number(f'PEG_R{i}',99,99) for i in range(1,5))
    packed.extend(number(f'PEG_L{i}',50,99) for i in range(1,5))
    packed.extend((number('ALG',4,31),number('FB',0,7)|(number('SYNC',1,1)<<3),
                   number('LFO_SPEED',0,99),number('LFO_DELAY',0,99),number('LFO_PMD',0,99),number('LFO_AMD',0,99),
                   number('LFO_SYNC',0,1)|(number('LFO_WAVE',0,5)<<1)|(number('LFO_PMS',0,7)<<4),
                   number('TRANSPOSE',24,48)))
    packed.extend(row.get('name','CALIBRATE')[:10].ljust(10).encode('ascii'))
    assert len(packed)==128
    return bytes(packed)
