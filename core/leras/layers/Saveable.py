import pickle
import time
import traceback
from pathlib import Path
from core import pathex
import numpy as np

from core.leras import nn
from core.interact import interact as io

tf = nn.tf


def _fmt_size(n):
    if n >= 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024 * 1024):.2f} GiB"
    elif n >= 1024 * 1024:
        return f"{n / (1024 * 1024):.2f} MiB"
    elif n >= 1024:
        return f"{n / 1024:.2f} KiB"
    return f"{n} B"


def _fmt_duration(seconds):
    if seconds >= 60:
        return f"{seconds:.1f}s ({seconds/60:.1f}m)"
    elif seconds >= 1:
        return f"{seconds:.2f}s"
    else:
        return f"{seconds*1000:.0f}ms"


def _get_rss():
    try:
        with open('/proc/self/status') as f:
            for line in f:
                if line.startswith('VmRSS:'):
                    kb = int(line.split()[1])
                    if kb >= 1024 * 1024:
                        return f"{kb / (1024 * 1024):.2f} GiB"
                    elif kb >= 1024:
                        return f"{kb / 1024:.2f} MiB"
                    return f"{kb} KiB"
    except Exception:
        return "N/A"
    return "N/A"

class Saveable():
    def __init__(self, name=None):
        self.name = name

    #override
    def get_weights(self):
        #return tf tensors that should be initialized/loaded/saved
        return []

    #override
    def get_weights_np(self):
        weights = self.get_weights()
        if len(weights) == 0:
            return []
        return nn.tf_sess.run (weights)

    def set_weights(self, new_weights):
        weights = self.get_weights()
        if len(weights) != len(new_weights):
            raise ValueError ('len of lists mismatch')

        tuples = []
        for w, new_w in zip(weights, new_weights):

            if len(w.shape) != new_w.shape:
                new_w = new_w.reshape(w.shape)

            tuples.append ( (w, new_w) )

        nn.batch_set_value (tuples)

    def save_weights(self, filename, force_dtype=None):
        d = {}
        weights = self.get_weights()

        if self.name is None:
            raise Exception("name must be defined.")

        name = self.name

        for w in weights:
            w_val = nn.tf_sess.run (w).copy()
            w_name_split = w.name.split('/', 1)
            if name != w_name_split[0]:
                raise Exception("weight first name != Saveable.name")

            if force_dtype is not None:
                w_val = w_val.astype(force_dtype)

            d[ w_name_split[1] ] = w_val

        d_dumped = pickle.dumps (d, 4)
        pathex.write_bytes_safe ( Path(filename), d_dumped )

    def load_weights(self, filename):
        """
        returns True if file exists
        """
        filepath = Path(filename)
        if not filepath.exists():
            return False

        file_size = filepath.stat().st_size
        io.log_info(f"  File size: {_fmt_size(file_size)}")
        io.log_info(f"  RSS before load: {_get_rss()}")

        t0 = time.monotonic()

        d_dumped = filepath.read_bytes()
        t1 = time.monotonic()
        io.log_info(f"  [1/4] Reading file... {_fmt_duration(t1 - t0)}")

        d = pickle.loads(d_dumped)
        t2 = time.monotonic()
        _n_entries = len(d)
        _data_bytes = sum(v.nbytes for v in d.values() if hasattr(v, 'nbytes'))
        io.log_info(
            f"  [2/4] Deserializing pickle... {_fmt_duration(t2 - t1)}"
        )
        io.log_info(f"    Entries: {_n_entries}")
        io.log_info(f"    Tensor data: {_fmt_size(_data_bytes)}")
        io.log_info(f"  RSS after deserialize: {_get_rss()}")

        weights = self.get_weights()

        if self.name is None:
            raise Exception("name must be defined.")

        try:
            tuples = []
            missing = []
            for w in weights:
                w_name_split = w.name.split('/')
                if self.name != w_name_split[0]:
                    raise Exception("weight first name != Saveable.name")

                sub_w_name = "/".join(w_name_split[1:])
                w_val = d.get(sub_w_name, None)

                if w_val is None:
                    missing.append(sub_w_name)
                    tuples.append((w, w.initializer))
                else:
                    w_val = np.reshape(w_val, w.shape.as_list())
                    tuples.append((w, w_val))

            t3 = time.monotonic()
            _assign_bytes = sum(
                v.nbytes for _, v in tuples if hasattr(v, 'nbytes')
            )
            io.log_info(
                f"  [3/4] Preparing assignments... {_fmt_duration(t3 - t2)}"
            )
            io.log_info(f"    Variables: {len(tuples)}")
            io.log_info(f"    Assignment bytes: {_fmt_size(_assign_bytes)}")
            if missing:
                io.log_info(
                    f"    Missing entries (will init): {len(missing)}"
                )
                for m in missing[:5]:
                    io.log_info(f"      - {m}")
                if len(missing) > 5:
                    io.log_info(f"      ... and {len(missing) - 5} more")

            nn.batch_set_value(
                tuples,
                log_label=f"  [4/4] Running TensorFlow assignments",
            )
            t4 = time.monotonic()

            io.log_info(
                f"  Completed in {_fmt_duration(t4 - t0)}"
            )
        except Exception:
            io.log_err(
                f"Failed loading weights from {filename}:\n"
                f"{traceback.format_exc()}"
            )
            return False

        return True

    def init_weights(self):
        nn.init_weights(self.get_weights())

nn.Saveable = Saveable
