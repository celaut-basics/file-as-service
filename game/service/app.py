import struct
import subprocess
import threading
import time
from http_base import Handler, serve

LOCK=threading.Lock()
FRAME=bytes(2049)
KEYS=0
LAST_INPUT=0
ERROR=None

def run():
    global FRAME, ERROR
    proc=subprocess.Popen(['/usr/local/bin/chip8','/service/payload.ch8'],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    try:
        while True:
            started=time.monotonic()
            with LOCK:
                keys=KEYS if started-LAST_INPUT<1 else 0
            proc.stdin.write(struct.pack('!H',keys));proc.stdin.flush()
            data=bytearray()
            while len(data)<2049:
                chunk=proc.stdout.read(2049-len(data))
                if not chunk:raise RuntimeError('ROM halted: invalid or unsupported instruction')
                data.extend(chunk)
            with LOCK: FRAME=bytes(data)
            time.sleep(max(0,1/60-(time.monotonic()-started)))
    except Exception as e:
        with LOCK: ERROR=str(e)
    finally:
        proc.terminate();proc.wait()

class Game(Handler):
    def route(self,path,args):
        global KEYS,LAST_INPUT
        if path!='/frame':return self.reply({'error':'Not found'},status=404)
        keys=int(args.get('keys',['0'])[0])
        if not 0<=keys<=65535:raise ValueError('Invalid key mask')
        with LOCK:
            KEYS=keys;LAST_INPUT=time.monotonic();frame=FRAME;error=ERROR
        if error:return self.reply({'error':error},status=422)
        return self.reply(frame,'application/octet-stream')
if __name__=='__main__':
    # Emulator inherits the same unprivileged user as the HTTP process.
    import os
    if os.getuid()==0:os.setgroups([]);os.setgid(65534);os.setuid(65534)
    threading.Thread(target=run,daemon=True).start()
    serve(Game)
