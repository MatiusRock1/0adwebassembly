"""Same-origin, isolated localhost server for the browser fixture."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re

class IsolatedHandler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map,
                      '.wasm': 'application/wasm', '.mjs': 'text/javascript'}
    def send_head(self):
        self._remaining_range = None
        requested = self.headers.get('Range')
        path = Path(self.translate_path(self.path))
        if not requested or not path.is_file():
            return super().send_head()
        size = path.stat().st_size
        match = re.fullmatch(r'bytes=(\d*)-(\d*)', requested)
        start = end = None
        if match and any(match.groups()) and size:
            left, right = match.groups()
            if left:
                start = int(left)
                end = min(int(right), size - 1) if right else size - 1
            elif int(right):
                start, end = max(0, size - int(right)), size - 1
        if start is None or start >= size or end < start:
            self.send_response(416)
            self.send_header('Content-Range', f'bytes */{size}')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return None
        stream = path.open('rb')
        stream.seek(start)
        self._remaining_range = end - start + 1
        self.send_response(206)
        self.send_header('Content-Type', self.guess_type(str(path)))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.send_header('Content-Length', str(self._remaining_range))
        self.end_headers()
        return stream

    def copyfile(self, source, outputfile):
        if self._remaining_range is None:
            return super().copyfile(source, outputfile)
        remaining = self._remaining_range
        while remaining:
            block = source.read(min(64 * 1024, remaining))
            if not block:
                break
            outputfile.write(block)
            remaining -= len(block)

    def end_headers(self):
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
        self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--directory', type=Path, default=Path(__file__).resolve().parents[1] / 'dist/browser')
    args = parser.parse_args()
    if not any((args.directory / name).is_file() for name in ['pyrogenesis-browser.wasm', 'pyrogenesis-map.wasm', 'pyrogenesis-scene.wasm', 'pyrogenesis-application.wasm']):
        parser.error('Missing browser build. Run docker-phase2.ps1 first.')
    with ThreadingHTTPServer(('127.0.0.1', args.port), partial(IsolatedHandler, directory=str(args.directory))) as server:
        print(f'http://localhost:{args.port}/', flush=True)
        server.serve_forever()
