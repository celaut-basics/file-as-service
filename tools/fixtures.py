"""Create original, redistributable payloads. Film needs host ffmpeg with libx264."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
# Original CHIP-8 demo: clear, draw a block; held keys 4/6 move it and sound.
ops=[0x6018,0x610e,0xa228,0x00e0,0xd015,0x6204,0xe2a1,0x70ff,
     0x6206,0xe2a1,0x7001,0x6302,0xf315,0xf307,0x3300,0x121a,
     0x1206,0x0000,0x0000,0x0000]
(ROOT/'game/service/payload.ch8').write_bytes(b''.join(x.to_bytes(2,'big') for x in ops)+bytes([0xf0]*5))
# Two-page PDF, authored here; no imported copyrighted document.
objects=[]
objects.append(b'<< /Type /Catalog /Pages 2 0 R >>')
objects.append(b'<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>')
for content in (6,7):objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents {content} 0 R >>'.encode())
objects.append(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
for title in ('File-as-service: page one','Page two: decoded inside the service'):
    text=f'BT /F1 24 Tf 48 700 Td ({title}) Tj ET'.encode();objects.append(b'<< /Length '+str(len(text)).encode()+b' >>\nstream\n'+text+b'\nendstream')
data=bytearray(b'%PDF-1.4\n');offsets=[0]
for i,obj in enumerate(objects,1):offsets.append(len(data));data.extend(f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n')
xref=len(data);data.extend(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
for off in offsets[1:]:data.extend(f'{off:010d} 00000 n \n'.encode())
data.extend(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode());(ROOT/'pdf/service/payload.pdf').write_bytes(data)
subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','testsrc2=size=320x180:rate=12','-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','4','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',str(ROOT/'film/service/payload.mp4')],check=True)
