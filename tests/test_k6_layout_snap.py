"""Regression tests for the Layout editor's native-pixel snap geometry."""
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(not shutil.which("node"), reason="Node.js required")
def test_smart_snap():
    editor = Path(__file__).resolve().parents[1] / "tools/k6_store_templates/static/layout-editor.js"
    subprocess.run(["node", "-e", r"""
const assert = require('node:assert/strict');
const {move, absolute} = require(process.argv[1]);
const widget = (id,parent,x,y,w,h) => ({id,parent,x,y,w,h,font:'factory'});
const fixture = () => [
  widget('a',null,0,8,128,24),
  widget('b',null,0,40,128,24),
  widget('vfo-a-marker','a',10,0,7,8),
  widget('vfo-b-marker','b',27,0,7,8)
];
let n=fixture();
// Cross-group left edge overrides a coarse grid. Coordinates stay relative.
let guide=move(n,'vfo-a-marker',26.6,0,8,true,{},2);
assert.equal(absolute(n,'vfo-a-marker').x,27);
assert.equal(guide.x,27);
// Opposite edges meet without overlapping.
n=fixture();
guide=move(n,'vfo-a-marker',19.6,0,8,true,{},2);
assert.equal(absolute(n,'vfo-a-marker').x,20);
assert.equal(guide.x,27);
// Right edge of the LCD, even though its coordinate is not on the grid.
n=fixture();
guide=move(n,'vfo-a-marker',120.3,0,8,true,{},2);
assert.equal(absolute(n,'vfo-a-marker').x,121);
assert.equal(guide.x,128);
// Different-sized center alignment, with a whole-pixel solution.
n=[widget('battery',null,12,20,17,8),widget('vfo-a-marker',null,0,0,7,8)];
guide=move(n,'vfo-a-marker',16.9,0,8,true,{},2);
assert.equal(absolute(n,'vfo-a-marker').x,17);
assert.equal(guide.x,20.5);
// Group move must not magnetize to its own children or ancestor.
n=[widget('group',null,20,20,20,20),widget('vfo-a-marker','group',3,3,7,8)];
guide=move(n,'group',21.6,21.6,1,true,{},2);
assert.deepEqual(absolute(n,'group'),{x:22,y:22});
assert.deepEqual(guide,{});
guide=move(n,'vfo-a-marker',4.6,1.6,1,true,{},2);
assert.deepEqual(absolute(n,'vfo-a-marker'),{x:27,y:24});
assert.deepEqual(guide,{});
// Alt bypass: grid=1, align=false. Both axes remain integer.
n=fixture();
guide=move(n,'vfo-a-marker',25.9,3.3,1,false,{},2);
assert.deepEqual(absolute(n,'vfo-a-marker'),{x:26,y:11});
assert.deepEqual(guide,{});
// When zoomed far in, near-but-not-within the tolerance stays unsnapped.
n=fixture();
guide=move(n,'vfo-a-marker',25.9,3.3,1,true,{},0.5);
assert.equal(absolute(n,'vfo-a-marker').x,26);
assert.equal(guide.x,undefined);
""", str(editor)], check=True)
