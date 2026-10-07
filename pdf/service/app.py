"""MuPDF rasterizes the fixed document; the host receives only PNG pages."""
import subprocess
import threading
from http_base import Handler, serve
LOCK = threading.Lock()
class PDF(Handler):
    def route(self, path, args):
        if path != '/page':
            return self.reply({'error': 'Not found'}, status=404)
        page = int(args.get('n', ['1'])[0])
        if not 1 <= page <= 100000:
            raise ValueError('Page out of range')
        if not LOCK.acquire(False):
            return self.reply({'error': 'Renderer busy'}, status=429)
        try:
            result = subprocess.run(['mutool', 'draw', '-q', '-F', 'png', '-r', '96',
                                     '-w', '1280', '-h', '1600', '-o', '-',
                                     '/service/payload.pdf', str(page)],
                                    capture_output=True, timeout=20)
            if result.returncode or not result.stdout.startswith(b'\x89PNG'):
                return self.reply({'error': 'Page unavailable'}, status=404)
            return self.reply(result.stdout, 'image/png')
        finally:
            LOCK.release()
if __name__ == '__main__':
    serve(PDF)
