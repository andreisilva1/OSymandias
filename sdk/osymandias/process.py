"""
Manages child subprocesses started by `osy serve`.
Handles clean shutdown on Ctrl+C / SIGTERM.
"""
import os
import signal
import subprocess
import sys
import threading
import time
from typing import Optional


class ManagedProcess:
    def __init__(self, name: str, proc: subprocess.Popen):
        self.name = name
        self.proc = proc
        self._thread: Optional[threading.Thread] = None

    def stream_output(self) -> None:
        prefix = f"[{self.name}]"
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            print(f"{prefix} {line}", end="", flush=True)

    def start_streaming(self) -> None:
        self._thread = threading.Thread(target=self.stream_output, daemon=True)
        self._thread.start()

    def terminate(self, timeout: int = 5) -> None:
        if self.proc.poll() is not None:
            return
        if sys.platform == "win32":
            self.proc.terminate()
        else:
            self.proc.send_signal(signal.SIGTERM)
        try:
            self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.proc.kill()


class ProcessManager:
    def __init__(self):
        self._procs: list[ManagedProcess] = []
        self._register_signals()

    def _register_signals(self) -> None:
        if sys.platform == "win32":
            signal.signal(signal.SIGINT, self._handle_signal)
            signal.signal(signal.SIGTERM, self._handle_signal)
        else:
            signal.signal(signal.SIGINT, self._handle_signal)
            signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, sig, frame) -> None:
        print("\n[osy] Shutting down...", flush=True)
        self.stop_all()
        sys.exit(0)

    def start(self, name: str, cmd: list[str], env: Optional[dict] = None) -> ManagedProcess:
        merged_env = {**os.environ, **(env or {})}
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=merged_env,
        )
        mp = ManagedProcess(name, proc)
        mp.start_streaming()
        self._procs.append(mp)
        return mp

    def stop_all(self) -> None:
        for mp in reversed(self._procs):
            mp.terminate()
        self._procs.clear()

    def wait_all(self) -> None:
        try:
            while True:
                time.sleep(1)
                dead = [mp for mp in self._procs if mp.proc.poll() is not None]
                for mp in dead:
                    print(f"[osy] {mp.name} exited unexpectedly", flush=True)
                    self.stop_all()
                    sys.exit(1)
        except KeyboardInterrupt:
            pass
