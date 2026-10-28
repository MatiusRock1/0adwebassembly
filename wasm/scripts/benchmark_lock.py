"""Serialize GUI benchmarks so focus loss and GPU contention cannot mix runs."""
import atexit
from pathlib import Path
import time

class BenchmarkLock:
    def __init__(self):
        path = Path(__file__).resolve().parents[1] / 'build/phase3-benchmark.lock'
        path.parent.mkdir(parents=True, exist_ok=True)
        self.file = path.open('a+b')
        if self.file.seek(0, 2) == 0:
            self.file.write(b'0'); self.file.flush()
        self.file.seek(0)
        last_message = 0
        while True:
            try:
                if __import__('os').name == 'nt':
                    import msvcrt
                    msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (OSError, BlockingIOError):
                if time.monotonic() - last_message >= 15:
                    print('Waiting for the active GUI benchmark to finish', flush=True)
                    last_message = time.monotonic()
                time.sleep(1)
        atexit.register(self.close)

    def close(self):
        if not self.file.closed:
            self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
