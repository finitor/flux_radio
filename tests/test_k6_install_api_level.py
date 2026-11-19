"""Install preflight for level-23 and later modules."""
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import k6_install as ki

class Cable:
    def __init__(self,level):
        self.level=level
        self.calls=0
    def capabilities(self):
        self.calls+=1
        if self.level is None:
            raise ki.InstallError("unsupported capability query")
        return {"module_api_max":self.level}
def entries(level):
    return [{"kind":"module","level":level}]
def test_new_module_rejected_on_old_firmware():
    c=Cable(22)
    with pytest.raises(ki.InstallError,match="requires API level 23, but radio supports level 22"):
        ki.check_module_api(c,entries(23))
    assert c.calls==1
def test_new_module_accepted_on_new_firmware():
    c=Cable(23)
    ki.check_module_api(c,entries(23))
    assert c.calls==1
def test_old_module_still_works_without_capability_query():
    c=Cable(None)
    ki.check_module_api(c,entries(22))
    assert c.calls==0
def test_new_module_fails_closed_without_capability_query():
    c=Cable(None)
    with pytest.raises(ki.InstallError,match="cannot verify compatible"):
        ki.check_module_api(c,entries(23))
