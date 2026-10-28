import copy
import threading
from types import SimpleNamespace
from urllib.parse import urlparse,parse_qs
import httpx
from brain_imager_phase3 import web
from brain_imager_phase3.common import save_jsonl,load_jsonl

def test_local_annotation_read_save_and_access_guards(tmp_path,pre_example,monkeypatch):
    row,crop,ann=pre_example;row['coco_image_id']=1000;ann['review_complete']=False
    cfg=SimpleNamespace(work=tmp_path,study=tmp_path/'pilot')
    (tmp_path/'crops').mkdir();(tmp_path/'crops'/crop['filename']).write_bytes(b'SYNTHETIC_TEST_IMAGE_BYTES')
    path=tmp_path/'annotations.jsonl';save_jsonl(path,[ann])
    monkeypatch.setattr(web,'crop_registry',lambda c:{1000:crop})
    monkeypatch.setattr(web,'pilot_rows',lambda c:[row])
    server,url=web.make_server(cfg,'pre',path,0)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}';token=parse_qs(urlparse(url).query)['token'][0]
    try:
        with httpx.Client(trust_env=False) as client:
            assert client.get(base+'/api/state').status_code==403
            assert client.get(url).status_code==200
            state=client.get(base+'/api/state',params={'token':token}).json()
            assert state['records'][0]['caption']==row['caption']
            changed=copy.deepcopy(ann);changed['caption']='wrong'
            assert client.post(base+'/api/save',headers={'X-Session-Token':token},json={'record':changed}).status_code==400
            changed=copy.deepcopy(ann);changed['notes']='Saved synthetic draft'
            assert client.post(base+'/api/save',headers={'X-Session-Token':token},json={'record':changed}).status_code==200
            assert load_jsonl(path)[0]['notes']=='Saved synthetic draft'
            assert client.get(base+'/crop/unrelated.txt',params={'token':token}).status_code==404
            assert client.post(base+'/api/save',headers={'X-Session-Token':token,'Origin':'https://example.invalid'},json={'record':changed}).status_code==403
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)
