"""Decode H.264/AAC to timestamped RGB24 and float32 PCM, never forward the source."""
import os
import queue
import struct
import subprocess
import threading
from http_base import Handler, serve

PAYLOAD = '/service/payload.mp4'
W, H, FPS, RATE = 320, 180, 12, 48000
SESSION = threading.Lock()

def exact(stream, size):
    data = bytearray()
    while len(data) < size:
        chunk = stream.read(size - len(data))
        if not chunk:
            break
        data.extend(chunk)
    return bytes(data)

class Film(Handler):
    def route(self, path, args):
        if path == '/info':
            return self.reply({'width': W, 'height': H, 'fps': FPS, 'rate': RATE,
                               'channels': 2, 'format': 'FAS1 RGB24 + f32le PCM'})
        if path != '/play':
            return self.reply({'error': 'Not found'}, status=404)
        start = float(args.get('start', ['0'])[0])
        if not 0 <= start <= 86400:
            raise ValueError('start must be between 0 and 86400 seconds')
        if not SESSION.acquire(False):
            return self.reply({'error': 'A viewer is already playing'}, status=409)
        proc = None
        readfd, writefd = os.pipe()
        stop = threading.Event()
        packets = queue.Queue(maxsize=8)
        def emit(item):
            while not stop.is_set():
                try:
                    packets.put(item, timeout=.2)
                    return
                except queue.Full:
                    pass
        def pump(stream, size, kind, interval):
            index = 0
            try:
                while not stop.is_set():
                    data = exact(stream, size)
                    if not data:
                        break
                    emit((kind, index * interval, data))
                    index += 1
            finally:
                stream.close()
                emit(None)
        try:
            proc = subprocess.Popen([
                '/usr/local/bin/ffmpeg', '-nostdin', '-v', 'error', '-re', '-ss', str(start),
                '-i', PAYLOAD, '-map', '0:v:0', '-vf',
                f'scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,fps={FPS}',
                '-pix_fmt', 'rgb24', '-c:v', 'rawvideo', '-f', 'rawvideo', 'pipe:1',
                '-map', '0:a:0?', '-ac', '2', '-ar', str(RATE), '-c:a', 'pcm_f32le',
                '-f', 'f32le', f'pipe:{writefd}',
            ], stdout=subprocess.PIPE, pass_fds=(writefd,))
            os.close(writefd)
            writefd = None
            audio = os.fdopen(readfd, 'rb')
            readfd = None
            threads = [threading.Thread(target=pump, args=(proc.stdout, W*H*3, 1, 1/FPS), daemon=True),
                       threading.Thread(target=pump, args=(audio, 4096*8, 2, 4096/RATE), daemon=True)]
            for thread in threads:
                thread.start()
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(b'FAS1')
            ended = 0
            while ended < 2:
                try:
                    item = packets.get(timeout=30)
                except queue.Empty:
                    raise RuntimeError('Decoder stalled')
                if item is None:
                    ended += 1
                    continue
                kind, timestamp, data = item
                self.wfile.write(struct.pack('!BId', kind, len(data), timestamp) + data)
                self.wfile.flush()
        finally:
            stop.set()
            if proc is not None:
                if proc.poll() is None:
                    proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
            for fd in (readfd, writefd):
                if fd is not None:
                    os.close(fd)
            SESSION.release()

if __name__ == '__main__':
    serve(Film)
