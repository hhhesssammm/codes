import hashlib
import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('release_verifier',Path(__file__).resolve().parents[1]/'verify_release.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

@pytest.mark.parametrize('state',['valid','changed','missing'])
def test_release_verifier_detects_byte_changes(tmp_path,state):
    expected=hashlib.sha256(b'original').hexdigest()
    (tmp_path/'CHECKSUMS.sha256').write_text(expected+'  example.txt\n')
    if state!='missing':(tmp_path/'example.txt').write_bytes(b'original' if state=='valid' else b'changed')
    count,failures=module.verify(tmp_path)
    assert count==1 and bool(failures)==(state!='valid')

def test_release_verifier_rejects_path_traversal(tmp_path):
    (tmp_path/'CHECKSUMS.sha256').write_text('0'*64+'  ../outside.txt\n')
    with pytest.raises(ValueError,match='Unsafe'):module.verify(tmp_path)
