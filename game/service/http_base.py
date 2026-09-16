"""Small, dependency-free slot server. No source-file/download endpoint."""
import json
import os
import signal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parent

class Handler(BaseHTTPRequestHandler):
    def reply(self, data, content_type='application/json', status=200):
        if not isinstance(data, bytes):
            data = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        try:
            url = urlsplit(self.path)
            if url.path == '/':
                return self.reply((ROOT / 'index.html').read_bytes(), 'text/html; charset=utf-8')
            if url.path == '/health':
                return self.reply({'ok': True})
            return self.route(url.path, parse_qs(url.query))
        except (BrokenPipeError, ConnectionResetError):
            pass
        except (ValueError, KeyError) as e:
            self.reply({'error': str(e)}, status=400)
        except Exception as e:
            self.log_error('%s', e)
            self.reply({'error': 'Interpreter failed; inspect service logs.'}, status=500)

    def log_message(self, fmt, *args):
        print(fmt % args, flush=True)


def serve(handler):
    # Drop privilege even when launched directly as PID 1 by nodo.
    if os.getuid() == 0:
        os.setgroups([])
        os.setgid(65534)
        os.setuid(65534)
    signal.signal(signal.SIGTERM, lambda *_: os._exit(0))
    server = ThreadingHTTPServer(('0.0.0.0', 8080), handler)
    server.daemon_threads = True
    server.serve_forever()
