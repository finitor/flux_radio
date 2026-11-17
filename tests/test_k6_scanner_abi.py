"""Lock the two existing scanner consumer layouts before shared-engine migration."""
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
K6 = ROOT / 'c/k6'
SOURCE = r'''
#include <stddef.h>
#include <stdio.h>
#include "xscan.h"
int main(void) {
  printf("%zu %zu %zu %zu %zu\n", sizeof(xs_t), offsetof(xs_t, hot),
         offsetof(xs_t, line), offsetof(xs_t, peek_ms), sizeof(((xs_t*)0)->hot));
  return 0;
}
'''

def layout(flags):
    with tempfile.TemporaryDirectory() as d:
        src = pathlib.Path(d) / 'layout.c'
        exe = pathlib.Path(d) / 'layout'
        src.write_text(SOURCE)
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-I', str(K6),
                        *flags, str(src), '-o', str(exe)], check=True)
        return tuple(map(int, subprocess.check_output([str(exe)], text=True).split()))

def test_consumer_layouts_differ_but_prefix_is_identical():
    full = layout([])
    compact = layout(['-DXS_HOT=4', '-DXS_COLS=1'])
    assert full[1] == compact[1]  # same prefix up to hot array
    assert full[4] == 10 * 28
    assert compact[4] == 4 * 28
    assert full[2] - compact[2] == 6 * 28
    assert full[3] - compact[3] == 6 * 28
    assert full[0] - compact[0] == 6 * 28
