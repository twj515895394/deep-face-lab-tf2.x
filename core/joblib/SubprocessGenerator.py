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
    
    @staticmethod
    def launch_thread(generator): 
        generator._start()
        
    @staticmethod
    def start_in_parallel( generator_list ):
        """
        Start list of generators in parallel
        """
        for generator in generator_list:
            thread = threading.Thread(target=SubprocessGenerator.launch_thread, args=(generator,) )
            thread.daemon = True
            thread.start()

        while not all ([generator._is_started() for generator in generator_list]):
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
        if start_now:
            self._start()

    def _start(self):
        if self.p == None:
            user_param = self.user_param
            self.user_param = None
            p = multiprocessing.Process(target=self.process_func, args=(user_param,) )
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
                    gen_data = next (self.generator_func)
                except StopIteration:
                    self.cs_queue.put (None)
                    return
                if fp16:
                    gen_data = _to_float16(gen_data)
                self.cs_queue.put (gen_data)
                self.prefetch -= 1
            self.sc_queue.get()
            self.prefetch += 1

    def __iter__(self):
        return self

    def __getstate__(self):
        self_dict = self.__dict__.copy()
        del self_dict['p']
        return self_dict

    def __next__(self):
        self._start()
        gen_data = self.cs_queue.get()
        if gen_data is None:
            self.p.terminate()
            self.p.join()
            raise StopIteration()
        if self.enable_fp16_ipc:
            gen_data = _to_float32(gen_data)
        self.sc_queue.put(1)
        return gen_data
