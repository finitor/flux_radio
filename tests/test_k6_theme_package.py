"""Cross-language K6T reader validation against the host codec."""
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from k6_feature_packs import encode_layer, theme_layers, validate_theme
from k6_theme_package import pack, unpack, migrate

@pytest.fixture(scope='module')
def reader(tmp_path_factory):
    if not shutil.which('rustc'):
        pytest.skip('rustc required for device reader test')
    temp = tmp_path_factory.mktemp('k6t')
    path = temp / 'main.rs'
    source = ROOT / 'firmware/k6-aura/theme-reader.rs'
    path.write_text(f'#[path = "{source}"] mod theme_reader;\n' + '''
fn main() {
    let blob = std::fs::read(std::env::args().nth(1).unwrap()).unwrap();
    let mut read = |off: u16, dst: &mut [u8]| {
        if dst.len() > 48 { panic!("oversized read"); }
        let start = usize::from(off);
        if let Some(src) = blob.get(start..start+dst.len()) {
            dst.copy_from_slice(src); true
        } else { false }
    };
    let Some(theme) = theme_reader::open(&mut read) else { std::process::exit(2); };
    for layer in theme.layers {
        let mut pixels = [0u8;8192];
        assert!(theme_reader::spans(&mut read, layer, |pos,n,ink| {
            pixels[usize::from(pos)..usize::from(pos)+usize::from(n)].fill(if ink {1} else {2});
        }));
        use std::io::Write;
        std::io::stdout().write_all(&pixels).unwrap();
    }
}
''')
    out = temp/'reader'
    subprocess.run(['rustc','--edition=2021','-O',str(path),'-o',str(out)],check=True)
    return out

def check(reader,tmp_path,blob):
    path=tmp_path/'test.k6t'
    path.write_bytes(blob)
    return subprocess.run([reader,path],capture_output=True)

def custom():
    a=bytearray(8192); b=bytearray(8192); c=bytearray(8192)
    a[128:256]=bytes([1])*128
    b[1024:1030]=bytes([1,2,1,2,1,2])
    c[:]=bytes(i%3 for i in range(8192))
    return ('custom-11-0000000000000000-1231-mf8f8f8f8f8f8f8f88888888888f8-b'
            + '800000'*40 + '-l'+'.'.join(map(encode_layer,(a,b,c))))

@pytest.mark.parametrize('token',['flux','classic','minimal',custom()])
def test_device_reader(reader,tmp_path,token):
    blob=pack(token)
    canonical=unpack(blob)
    assert pack(canonical)==blob
    result=check(reader,tmp_path,blob)
    assert result.returncode==0, result.stderr
    assert result.stdout==b''.join(theme_layers(canonical) or (bytes(8192),)*3)

def test_corruption(reader,tmp_path):
    blob=pack(custom())
    for i in (0,3,4,6,7,8,12,27,len(blob)-1):
        broken=bytearray(blob); broken[i]^=1
        with pytest.raises(ValueError): unpack(bytes(broken))
        assert check(reader,tmp_path,broken).returncode==2
    for end in (0,11,12,30,len(blob)-1):
        assert check(reader,tmp_path,blob[:end]).returncode==2

def test_valid_crc_invalid_structure(reader,tmp_path):
    blob=bytearray(pack('flux'))
    for offset, value in [(12,4),(13,2),(18,1),(26,3),(27,1)]:
        broken=bytearray(blob); broken[offset]=value
        struct.pack_into('<I',broken,8,zlib.crc32(broken[12:]))
        with pytest.raises(ValueError): unpack(bytes(broken))
        assert check(reader,tmp_path,broken).returncode==2


@pytest.mark.parametrize('token',[
 'custom-11-0000000000000000-w'+bytes([0,0,0,0,40,1,0,8,2,0,32,0,109,0,0]).hex(),
 'custom-11-0000000000000000-w'+(bytes([0,0,0,0,8,1,0,40,2,0,32,0,109,0,0])+bytes([16,0,57,0,72,0,2,0,62,0]+[2,0,12,0,2,8,44,0,2,18]*2)+bytes(5)).hex(),
])
def test_legacy_migration(reader,tmp_path,token):
    blob=pack(token)
    assert blob[:4]==b'K6T\x06'
    assert unpack(blob)==migrate(token)
    assert check(reader,tmp_path,blob).returncode==0
    old=bytearray(blob);old[3]=3
    assert check(reader,tmp_path,old).returncode==2

def test_flat_v6(reader,tmp_path):
    token=migrate('flux')
    blob=pack(token)
    assert blob[:4]==b'K6T\x06'
    assert unpack(blob)==token
    for index,value in [(0,32),(1,127),(3,3),(4,2),(5,0)]:
        bad=bytearray(blob);bad[-160+index]=value
        struct.pack_into('<I',bad,8,zlib.crc32(bad[12:]))
        with pytest.raises(ValueError):unpack(bad)
        assert check(reader,tmp_path,bad).returncode==2

def test_custom_font(reader,tmp_path):
    token=migrate('flux')
    head,raw=token.rsplit('-w',1)
    raw=bytearray.fromhex(raw)
    for i in range(0,len(raw),5):
        if raw[i]==8:raw[i+3]=2
    with pytest.raises(ValueError):pack(head+'-w'+raw.hex())
    token=head+'-f'+(bytes([0x7e])*132).hex()+'-w'+raw.hex()
    blob=pack(token)
    assert unpack(blob)==token
    assert check(reader,tmp_path,blob).returncode==0
    bad=bytearray(blob);bad[-292:-280]=bytes(12)
    struct.pack_into('<I',bad,8,zlib.crc32(bad[12:]))
    with pytest.raises(ValueError):unpack(bad)
    assert check(reader,tmp_path,bad).returncode==2
