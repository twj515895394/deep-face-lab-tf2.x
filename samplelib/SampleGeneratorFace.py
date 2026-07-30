import multiprocessing
import time
import traceback

import cv2
import numpy as np

from core import mplib
from core.interact import interact as io
from core.joblib import SubprocessGenerator, ThisThreadGenerator
from facelib import LandmarksProcessor
from samplelib import (SampleGeneratorBase, SampleLoader, SampleProcessor,
                       SampleType)


'''
arg
output_sample_types = [
                        [SampleProcessor.TypeFlags, size, (optional) {} opts ] ,
                        ...
                      ]
'''
class SampleGeneratorFace(SampleGeneratorBase):
    def __init__ (self, samples_path, debug=False, batch_size=1,
                        random_ct_samples_path=None,
                        sample_process_options=SampleProcessor.Options(),
                        output_sample_types=[],
                        uniform_yaw_distribution=False,
                        generators_count=4,
                        raise_on_no_data=True,
                        sampling_policy=None,
                        sampling_role=None,
                        **kwargs):

        super().__init__(debug, batch_size)
        self.initialized = False
        self.sample_process_options = sample_process_options
        self.output_sample_types = output_sample_types
        self.sampling_policy = sampling_policy
        self.sampling_role = sampling_role
        self._finalized = False
        
        if self.debug:
            self.generators_count = 1
        else:
            self.generators_count = max(1, generators_count)

        samples = SampleLoader.load (SampleType.FACE, samples_path)
        self.samples_len = len(samples)
        # Keep host ownership on the generator so finalize/close can stop IPC cleanly.
        self.index_host = None
        self.ct_index_host = None
        self.generators = []
        
        if self.samples_len == 0:
            if raise_on_no_data:
                raise ValueError('No training data provided.')
            else:
                return
                
        if self.sampling_policy is not None:
            index_host = self.sampling_policy.build_index_host(samples, role=sampling_role)
        elif uniform_yaw_distribution:
            samples_pyr = [ ( idx, sample.get_pitch_yaw_roll() ) for idx, sample in enumerate(samples) ]
            
            grads = 128
            #instead of math.pi / 2, using -1.2,+1.2 because actually maximum yaw for 2DFAN landmarks are -1.2+1.2
            grads_space = np.linspace (-1.2, 1.2,grads)

            yaws_sample_list = [None]*grads
            for g in io.progress_bar_generator ( range(grads), "Sort by yaw"):
                yaw = grads_space[g]
                next_yaw = grads_space[g+1] if g < grads-1 else yaw

                yaw_samples = []
                for idx, pyr in samples_pyr:
                    s_yaw = -pyr[1]
                    if (g == 0          and s_yaw < next_yaw) or \
                    (g < grads-1     and s_yaw >= yaw and s_yaw < next_yaw) or \
                    (g == grads-1    and s_yaw >= yaw):
                        yaw_samples += [ idx ]
                if len(yaw_samples) > 0:
                    yaws_sample_list[g] = yaw_samples
            
            yaws_sample_list = [ y for y in yaws_sample_list if y is not None ]
            
            index_host = mplib.Index2DHost( yaws_sample_list )
        else:
            index_host = mplib.IndexHost(self.samples_len)

        if random_ct_samples_path is not None:
            ct_samples = SampleLoader.load (SampleType.FACE, random_ct_samples_path)
            ct_index_host = mplib.IndexHost( len(ct_samples) )
        else:
            ct_samples = None
            ct_index_host = None

        # Persist hosts for explicit finalize; do not rely on __del__.
        self.index_host = index_host
        self.ct_index_host = ct_index_host

        if self.debug:
            self.generators = [ThisThreadGenerator ( self.batch_func, (samples, index_host.create_cli(), ct_samples, ct_index_host.create_cli() if ct_index_host is not None else None) )]
        else:
            _res = 128
            for _ost in self.output_sample_types:
                if isinstance(_ost, dict) and 'resolution' in _ost:
                    _res = _ost['resolution']
                    break
            _use_fp16_ipc = (_res >= 192)
            if _use_fp16_ipc:
                io.log_info(f"FP16 IPC enabled for resolution={_res} (halves data transfer size)")
            # create_cli() must happen in the main process before worker start.
            self.generators = [SubprocessGenerator ( self.batch_func, (samples, index_host.create_cli(), ct_samples, ct_index_host.create_cli() if ct_index_host is not None else None), prefetch=8, start_now=False, enable_fp16_ipc=_use_fp16_ipc ) \
                               for i in range(self.generators_count) ]
                               
            SubprocessGenerator.start_in_parallel( self.generators )

        self.generator_counter = -1
        
        self.initialized = True
        
    #overridable
    def is_initialized(self):
        return self.initialized

    def finalize(self):
        """
        Explicit lifecycle cleanup:
        1) stop generator worker processes (deterministic terminate/kill/join)
        2) close IPC queues via SubprocessGenerator.close()
        3) close index hosts (WeightedIndexHost / mplib hosts with close)
        Does not rely on Python __del__ as the primary path.

        Cleanup failures are collected and re-raised after best-effort work so
        callers are never told finalize succeeded while workers remain alive.
        Idempotent once all resources are confirmed released.
        """
        if getattr(self, "_finalized", False):
            # Allow retry if a previous attempt left live workers / host threads.
            live_workers = False
            for g in getattr(self, "generators", None) or []:
                p = getattr(g, "p", None)
                if p is not None and getattr(p, "is_alive", lambda: False)():
                    live_workers = True
                    break
            host_live = False
            for host_attr in ("index_host", "ct_index_host"):
                host = getattr(self, host_attr, None)
                thread = getattr(host, "thread", None) if host is not None else None
                if thread is not None and thread.is_alive():
                    host_live = True
                    break
            if not live_workers and not host_live:
                return

        errors = []
        generators = getattr(self, "generators", None) or []
        for g in generators:
            if g is None:
                continue
            if hasattr(g, "close") and callable(getattr(g, "close")):
                try:
                    g.close()
                except Exception as e:
                    errors.append(e)
                continue
            if hasattr(g, "finalize") and callable(getattr(g, "finalize")):
                try:
                    g.finalize()
                except Exception as e:
                    errors.append(e)
                continue
            # Legacy fallback for generators without explicit close/finalize.
            p = getattr(g, "p", None)
            if p is None:
                continue
            try:
                if p.is_alive():
                    p.terminate()
                p.join(timeout=3)
                if p.is_alive():
                    kill = getattr(p, "kill", None)
                    if callable(kill):
                        kill()
                    p.join(timeout=2)
                if p.is_alive():
                    raise RuntimeError(
                        f"SampleGeneratorFace worker did not exit "
                        f"(pid={getattr(p, 'pid', None)})"
                    )
                try:
                    g.p = None
                except Exception:
                    pass
            except Exception as e:
                errors.append(e)

        for host_attr in ("index_host", "ct_index_host"):
            host = getattr(self, host_attr, None)
            if host is not None and hasattr(host, "close"):
                try:
                    host.close()
                except Exception as e:
                    errors.append(e)
            # Only drop host ref when its thread is gone (or has no thread).
            thread = getattr(host, "thread", None) if host is not None else None
            if host is None or thread is None or not thread.is_alive():
                try:
                    setattr(self, host_attr, None)
                except Exception:
                    pass

        if errors:
            # Do not mark fully finalized if anything failed; allow retry.
            raise RuntimeError(
                f"SampleGeneratorFace.finalize failed with {len(errors)} error(s): "
                f"{errors[0]}"
            ) from errors[0]

        self._finalized = True

    def __del__(self):
        # Safety net for tests/tools that forget finalize(); training uses ModelBase.finalize.
        try:
            self.finalize()
        except Exception:
            pass
        
    def __iter__(self):
        return self

    def __next__(self):
        if not self.initialized:
            return []
            
        self.generator_counter += 1
        generator = self.generators[self.generator_counter % len(self.generators) ]
        return next(generator)

    def batch_func(self, param ):
        samples, index_host, ct_samples, ct_index_host = param

        bs = self.batch_size
        while True:
            batches = None

            indexes = index_host.multi_get(bs)
            ct_indexes = ct_index_host.multi_get(bs) if ct_samples is not None else None

            t = time.time()
            preloaded_samples = []
            for n_batch in range(bs):
                sample_idx = indexes[n_batch]
                sample = samples[sample_idx]

                ct_sample = None
                if ct_samples is not None:
                    ct_sample = ct_samples[ct_indexes[n_batch]]

                try:
                    sample_bgr = sample.load_bgr()
                    ct_sample_bgr = ct_sample.load_bgr() if ct_sample is not None else None
                except Exception as e:
                    raise Exception ("Exception occured in loading sample %s. Error: %s" % (sample.filename, traceback.format_exc() ) )

                preloaded_samples.append( (sample, ct_sample, sample_bgr, ct_sample_bgr) )

            for n_batch in range(bs):
                sample, ct_sample, sample_bgr, ct_sample_bgr = preloaded_samples[n_batch]

                try:
                    x, = SampleProcessor.process ([sample], self.sample_process_options, self.output_sample_types, self.debug, ct_sample=ct_sample,
                                                    cached_bgr=sample_bgr, cached_ct_bgr=ct_sample_bgr)
                except:
                    raise Exception ("Exception occured in sample %s. Error: %s" % (sample.filename, traceback.format_exc() ) )

                if batches is None:
                    batches = [ [] for _ in range(len(x)) ]

                for i in range(len(x)):
                    batches[i].append ( x[i] )

            yield [ np.array(batch) for batch in batches ]
