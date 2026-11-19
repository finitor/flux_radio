#!/usr/bin/env python3
"""Offline, data-only K6T package codec. No radio writes or executable K6M wrapping."""
import argparse
import struct
import unicodedata
import zlib
from pathlib import Path
from k6_feature_packs import (THEME_EDITOR_PRESETS, validate_theme, theme_layout,
                              theme_meter_bitmap, theme_battery, theme_layers,
                              theme_logo, encode_layer, decode_layer, theme_widgets, validate_widgets)

# Distinct magic deliberately fails old module loaders. Little endian.
HEADER = struct.Struct('<4sHBBI')  # magic/version, payload length, target, reserved, CRC32
MAGIC = b'K6T\x01'
TARGET = 1  # FD6818B 128x64
MAX_BYTES = 8192
LAYER = struct.Struct('<BH')  # encoding (0 blank, 1 sparse, 2 packed), length


def split_mode(source,x,y,flags=0):
    # Default compact row. Optional mutually exclusive CW/repeater hints share
    # an anchor; tone, offset and reverse retain their own independent slots.
    start=15 if source==9 else 22
    positions=[(source,0),(start,13),(start+1,30),(start+2,55),(start+3,60),(start+4,77),(start+5,83),(start+6,83)]
    return bytes(v for sid,dx in positions for v in (sid,x+dx,y,0,flags))

def migrate(theme):
    theme=THEME_EDITOR_PRESETS.get(theme,theme)
    validate_theme(theme)
    old=theme_widgets(theme)
    if old and len(old) in (160,170): return theme
    if old and len(old)==145:
        raw=old+bytes([29,0,0,0,0,30,84,0,0,0,31,99,0,0,0])
        return validate_theme(theme.rsplit('-w',1)[0]+'-w'+raw.hex())
    if old and len(old)==75:
        raw=bytearray()
        for i in range(0,75,5):
            source,x,y,f,flags=old[i:i+5]
            if source in (9,14):
                raw.extend(split_mode(source,x,y,flags))
            else:raw.extend((source,x,y,f,flags))
        return migrate(theme.rsplit('-w',1)[0]+'-w'+raw.hex())
    font,inset,_,_=theme_layout(theme)
    g=old[:15] if old else bytes([0,0,0,0,8,0,0,40,0,0,32,0,109,0,0])
    c=old[15:45] if old and len(old)==50 else bytes([16,0,57,0,109,0,2,0,62,0]+[2,0,12,0,2,8,44,0,2,18]*2)
    raw=bytearray()
    for i in range(15):
        parent=0 if i<3 else 3 if i<5 else 1 if i<10 else 2
        f=0
        if i in (8,13):
            f=font if g[parent*3+2]==0 else g[parent*3+2]-1
        x,y=c[i*2],c[i*2+1]+g[parent*3+1]
        if i in (8,13):
            # Legacy compact was right-aligned inside the 82 pixel slot.
            x=max(0,x+(28 if f else 0)-inset)
        if i in (9,14):raw.extend(split_mode(i,x,y))
        else:raw.extend((i,x,y,f,0))
    validate_widgets(raw)
    parts=theme.split('-')
    if parts[-1].startswith('w'):parts.pop()
    flags=parts[1]
    layers=list(theme_layers(theme) or (bytearray(8192),bytearray(8192),bytearray(8192)))
    for side in (1,2):
        y=g[side*3+1]
        if flags[0]=='1': layers[side][128*y:128*(y+1)]=bytes([1])*128
        if flags[1]=='1':
            for r in range(y+1,y+23):layers[side][128*r]=1
    if parts[-1].startswith('l'):parts.pop()
    if any(any(layer) for layer in layers):parts.append('l'+'.'.join(map(encode_layer,layers)))
    parts.append('w'+raw.hex())
    return migrate('-'.join(parts))


def display_name(name):
    if not name:
        return ""
    ascii_name=unicodedata.normalize("NFKD",str(name)).encode("ascii","ignore").decode("ascii")
    ascii_name="".join(ch for ch in ascii_name if ch.isalnum() or ch in " _-")
    ascii_name=" ".join(ascii_name.split())[:14].strip()
    return ascii_name if any(ch.isalnum() for ch in ascii_name) else ("Theme" if name else "")


def pack(theme, name=None):
    theme = migrate(theme)
    parts = theme.split('-')
    flags = int(parts[1][0]) | (int(parts[1][1]) << 1)
    layout = theme_layout(theme)
    meter = theme_meter_bitmap(theme)
    battery = theme_battery(theme)
    logo = theme_logo(theme)
    name=display_name(name)
    body = bytearray([flags, *layout, int(battery is not None)])
    body.extend(bytes.fromhex(parts[2]))
    if meter:
        body.extend(bytes(meter[0] + meter[1]))
    if battery:
        body.extend(battery)
    if logo:
        body.extend(logo)
    if name or len(theme_widgets(theme))==170:
        encoded_name=name.encode("ascii")
        body.append(len(encoded_name))
        body.extend(encoded_name)
    for pixels in theme_layers(theme) or (bytearray(8192),)*3:
        token = encode_layer(pixels)
        data = bytes.fromhex(token[1:]) if token != '0' else b''
        body.extend(LAYER.pack({'0':0,'s':1,'p':2}[token[0]],len(data)))
        body.extend(data)
    widgets=theme_widgets(theme)
    font=next((bytes.fromhex(p[1:]) for p in parts[3:] if p.startswith('f')),None)
    body.append(int(font is not None))
    if font:body.extend(font)
    body.extend(widgets)
    version=9 if len(widgets)==170 else 8 if name else 7 if logo else 6
    return HEADER.pack(f"K6T{chr(version)}".encode("latin1"),len(body),TARGET,0,zlib.crc32(body))+body


def unpack(blob, include_name=False):
    if not HEADER.size <= len(blob) <= MAX_BYTES:
        raise ValueError('invalid package size')
    magic,n,target,reserved,crc = HEADER.unpack_from(blob)
    body = blob[HEADER.size:]
    if magic not in (MAGIC,b"K6T\x02",b"K6T\x03",b"K6T\x04",b"K6T\x05",b"K6T\x06",b"K6T\x07",b"K6T\x08",b"K6T\x09") or (target,reserved,n,crc)!=(TARGET,0,len(body),zlib.crc32(body)):
        raise ValueError('invalid package header or checksum')
    if len(body)<14:
        raise ValueError('truncated theme metadata')
    flags,font,inset,meter,splash,battery=body[:6]
    if flags>3 or battery>1 or font>1 or inset>3 or meter>3 or splash>(3 if magic in (b"K6T\x07",b"K6T\x08",b"K6T\x09") else 2):
        raise ValueError('invalid metadata')
    token=f'custom-{flags&1}{flags>>1}-{body[6:14].hex()}'
    at=14
    def take(n):
        nonlocal at
        if at+n>len(body): raise ValueError('truncated package')
        data=body[at:at+n]; at+=n; return data
    if any((font,inset,meter,splash)):
        token+=f'-{font}{inset}{meter}{splash}'
    if meter==3: token+='-m'+take(14).hex()
    if battery: token+='-b'+take(120).hex()
    if magic in (b"K6T\x07",b"K6T\x08",b"K6T\x09") and splash==3: token+='-g'+take(32).hex()
    name=""
    if magic in (b"K6T\x08",b"K6T\x09"):
        n_name=take(1)[0]
        if not (0 if magic==b"K6T\x09" else 1)<=n_name<=14:raise ValueError('invalid theme display name length')
        raw_name=take(n_name)
        try:name=raw_name.decode('ascii')
        except UnicodeDecodeError as exc:raise ValueError('theme display name must be ASCII') from exc
        if any(not (ch.isalnum() or ch in " _-") for ch in name) or (n_name and not name.strip()):
            raise ValueError('invalid theme display name')
    layers=[]
    for _ in range(3):
        kind,n=LAYER.unpack(take(LAYER.size))
        if kind>2 or (kind==0 and n) or (kind==1 and not 0<n<=2048) or (kind==2 and n!=2048):
            raise ValueError('invalid layer descriptor')
        raw=take(n)
        part='0' if kind==0 else ('s' if kind==1 else 'p')+raw.hex()
        layers.append(encode_layer(decode_layer(part)))
    font_data=None
    if magic in (b'K6T\x06',b'K6T\x07',b'K6T\x08',b'K6T\x09'):
        present=take(1)[0]
        if present>1:raise ValueError('invalid font flag')
        if present:font_data=take(132)
    widgets=validate_widgets(take(170 if magic==b"K6T\x09" else 160 if magic in (b'K6T\x06',b'K6T\x07',b'K6T\x08') else 145 if magic==b'K6T\x05' else 75 if magic==b'K6T\x04' else 50 if magic==b'K6T\x03' else 15)) if magic!=MAGIC else None
    if at!=len(body): raise ValueError('unexpected trailing data')
    if any(x!='0' for x in layers): token+='-l'+'.'.join(layers)
    if font_data:token += "-f"+font_data.hex()
    if widgets: token += "-w"+widgets.hex()
    token=validate_theme(token)
    return (token,name) if include_name else token


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='action',required=True)
    e=sub.add_parser('export');e.add_argument('theme');e.add_argument('output', type=Path)
    i=sub.add_parser('inspect');i.add_argument('input',type=Path)
    a=p.parse_args()
    try:
        if a.action=='export':
            blob=pack(a.theme);unpack(blob);a.output.write_bytes(blob);print(f'{len(blob)} bytes')
        else: print(unpack(a.input.read_bytes()))
    except (ValueError,OSError) as exc: p.error(str(exc))

if __name__=='__main__': main()
