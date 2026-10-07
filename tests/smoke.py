"""Real interpreter/HTTP checks against running containers; no mocked decoders."""
import hashlib,json,struct,time,urllib.request,urllib.error

def get(port,path):
    return urllib.request.urlopen(f'http://127.0.0.1:{port}{path}',timeout=30).read()

def reject(port,path,code):
    try:get(port,path)
    except urllib.error.HTTPError as e:assert e.code==code,(path,e.code);return
    raise AssertionError('Expected rejection: '+path)

for port in (18081,18082,18083):
    assert json.loads(get(port,'/health'))['ok']
    reject(port,'/payload.mp4',404)
p1,p2=get(18083,'/page?n=1'),get(18083,'/page?n=2')
assert p1.startswith(b'\x89PNG\r\n\x1a\n') and p1!=p2
reject(18083,'/page?n=0',400)
reject(18083,'/page?n=not-a-page',400)
a=get(18082,'/frame?keys=0');assert len(a)==2049 and any(a[:2048])
for _ in range(6):get(18082,'/frame?keys=64');time.sleep(.03)
b=get(18082,'/frame?keys=0');assert a[:2048]!=b[:2048],'Game input did not change pixels'
reject(18082,'/frame?keys=65536',400)
data=get(18081,'/play');assert data[:4]==b'FAS1';offset=4;frames=[];audio=bytearray()
while offset<len(data):
    kind,size,t=struct.unpack('!BId',data[offset:offset+13]);offset+=13
    payload=data[offset:offset+size];assert len(payload)==size;offset+=size
    if kind==1:assert size==320*180*3;frames.append(hashlib.sha256(payload).hexdigest())
    elif kind==2:assert size%8==0;audio.extend(payload)
    else:raise AssertionError(kind)
assert len(frames)>=40 and len(set(frames))>20
assert len(audio)>48000*8*3 and any(audio)
reject(18081,'/play?start=-1',400)
print(json.dumps({'film_frames':len(frames),'pcm_bytes':len(audio),'pdf_page_bytes':[len(p1),len(p2)],'game_input_changes_pixels':True},indent=2))
