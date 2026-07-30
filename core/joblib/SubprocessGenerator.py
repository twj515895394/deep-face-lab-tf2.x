import multiprocessing
import queue as Queue
import threading
import time
import numpy as np


def _to_float16(data):
    if isinstance(data, np.ndarray):
        if data.dtype == np.float32:
            return data.astype(np.float16)
        return data
    elif isinstance(data, (list, tuple)):
        return type(data)(_to_float16(x) for x in data)
    elif isinstance(data, dict):
        return {k: _to_float16(v) for k, v in data.items()}
    return data


def _to_float32(data):
    if isinstance(data, np.ndarray):
        if data.dtype == np.float16:
            return data.astype(np.float32)
        return data
    elif isinstance(data, (list, tuple)):
        return type(data)(_to_float32(x) for x in data)
    elif isinstance(data, dict):
        return {k: _to_float32(v) for k, v in data.items()}
    return data


class SubprocessGenerator(object):
    """Prefetching generator that runs batch production in a child process."""

    DEFAULT_JOIN_TIMEOUT_SEC = 3.0
    DEFAULT_KILL_JOIN_TIMEOUT_SEC = 2.0

    @staticmethod
    def launch_thread(generator):
        generator._start()

    @staticmethod
    def start_in_parallel(generator_list):
        """
        Start list of generators in parallel
        """
        for generator in generator_list:
            thread = threading.Thread(target=SubprocessGenerator.launch_thread, args=(generator,))
            thread.daemon = True
            thread.start()

        while not all([generator._is_started() for generator in generator_list]):
            time.sleep(0.005)

    def __init__(self, generator_func, user_param=None, prefetch=4, start_now=True,
                 enable_fp16_ipc=False):
        super().__init__()
        self.prefetch = prefetch
        self.generator_func = generator_func
        self.user_param = user_param
        self.sc_queue = multiprocessing.Queue()
        self.cs_queue = multiprocessing.Queue()
        self.enable_fp16_ipc = enable_fp16_ipc
        self.p = None
        self._closed = False
        if start_now:
            self._start()

    def _start(self):
        if self._closed:
            raise RuntimeError("SubprocessGenerator is closed; cannot start.")
        if self.p is None:
            user_param = self.user_param
            self.user_param = None
            p = multiprocessing.Process(target=self.process_func, args=(user_param,))
            p.daemon = True
            p.start()
            self.p = p

    def _is_started(self):
        return self.p is not None

    def process_func(self, user_param):
        self.generator_func = self.generator_func(user_param)
        fp16 = self.enable_fp16_ipc
        while True:
            while self.prefetch > -1:
                try:
                    gen_data = next(self.generator_func)
                except StopIteration:
                    self.cs_queue.put(None)
                    return
                if fp16:
                    gen_data = _to_float16(gen_data)
                self.cs_queue.put(gen_data)
                self.prefetch -= 1
            self.sc_queue.get()
            self.prefetch += 1

    def __iter__(self):
        return self

    def __getstate__(self):
        self_dict = self.__dict__.copy()
        del self_dict['p']
        return self_dict

    def _close_queues(self):
        """Best-effort Queue + feeder-thread cleanup. Idempotent."""
        for q in (getattr(self, "sc_queue", None), getattr(self, "cs_queue", None)):
            if q is None:
                continue
            try:
                q.close()
            except Exception:
                pass
            # Prefer cancel_join_thread: after terminate, feeder may block on put.
            cancel = getattr(q, "cancel_join_thread", None)
            if callable(cancel):
                try:
                    cancel()
                    continue
                except Exception:
                    pass
            join_thread = getattr(q, "join_thread", None)
            if callable(join_thread):
                try:
                    join_thread()
                except Exception:
                    pass

    def _reap_process(self, join_timeout_sec=None, kill_join_timeout_sec=None):
        """
        Deterministic worker reaping:
        terminate → join → kill (if needed) → join → require exit.
        Process handle is cleared only after the worker is confirmed dead.
        """
        if join_timeout_sec is None:
            join_timeout_sec = self.DEFAULT_JOIN_TIMEOUT_SEC
        if kill_join_timeout_sec is None:
            kill_join_timeout_sec = self.DEFAULT_KILL_JOIN_TIMEOUT_SEC

        p = self.p
        if p is None:
            return

        try:
            if p.is_alive():
                p.terminate()
            p.join(timeout=float(join_timeout_sec))
            if p.is_alive():
                kill = getattr(p, "kill", None)
                if callable(kill):
                    kill()
                p.join(timeout=float(kill_join_timeout_sec))
        except Exception as e:
            # Keep the live handle so callers can still observe/kill the worker.
            if p.is_alive():
                raise RuntimeError(
                    f"SubprocessGenerator failed while reaping worker "
                    f"(pid={getattr(p, 'pid', None)})"
                ) from e
            self.p = None
            return

        if p.is_alive():
            raise RuntimeError(
                f"SubprocessGenerator worker did not exit after terminate/kill "
                f"(pid={getattr(p, 'pid', None)})"
            )

        # Confirmed dead: exitcode is set; safe to drop the handle.
        self.p = None

    def close(self, join_timeout_sec=None, kill_join_timeout_sec=None):
        """
        Explicit lifecycle cleanup for the worker Process and IPC Queues.
        Idempotent. Raises if the worker cannot be reaped.
        """
        if self._closed and self.p is None:
            return
        if self._closed and self.p is not None and self.p.is_alive():
            # Previous close left a live worker; retry reaping.
            self._reap_process(join_timeout_sec, kill_join_timeout_sec)
            self._close_queues()
            return

        reaped_ok = False
        try:
            self._reap_process(join_timeout_sec, kill_join_timeout_sec)
            reaped_ok = True
        finally:
            # Always attempt queue cleanup so feeder threads do not block exit.
            self._close_queues()
            if reaped_ok or self.p is None:
                self._closed = True

        if not reaped_ok and self.p is not None and self.p.is_alive():
            raise RuntimeError(
                f"SubprocessGenerator close left a live worker "
                f"(pid={getattr(self.p, 'pid', None)})"
            )

    def finalize(self, join_timeout_sec=None, kill_join_timeout_sec=None):
        """Alias for close(); matches SampleGeneratorFace.finalize naming."""
        self.close(
            join_timeout_sec=join_timeout_sec,
            kill_join_timeout_sec=kill_join_timeout_sec,
        )

    def __next__(self):
        self._start()
        gen_data = self.cs_queue.get()
        if gen_data is None:
            # Generator exhausted: reap via the shared cleanup path.
            self.close()
            raise StopIteration()
        if self.enable_fp16_ipc:
            gen_data = _to_float32(gen_data)
        self.sc_queue.put(1)
        return gen_data
