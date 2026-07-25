import sys
import ctypes
import os
import multiprocessing
import json
import time
from pathlib import Path
from core.interact import interact as io

def _ensure_ld_library_path():
    if 'LD_LIBRARY_PATH' in os.environ and len(os.environ['LD_LIBRARY_PATH']) > 0:
        return
    venv_site = None
    for path in sys.path:
        if 'site-packages' in path and 'nvidia' not in path:
            venv_site = path
            break
    if venv_site is None:
        return
    nvidia_libs = f"{venv_site}/nvidia"
    if not os.path.isdir(nvidia_libs):
        return
    lib_paths = []
    for d in os.listdir(nvidia_libs):
        lib_dir = f"{nvidia_libs}/{d}/lib"
        if os.path.isdir(lib_dir):
            lib_paths.append(lib_dir)
    if lib_paths:
        os.environ['LD_LIBRARY_PATH'] = ':'.join(lib_paths) + ':' + os.environ.get('LD_LIBRARY_PATH', '')

def _get_ld_library_path():
    ld_path = os.environ.get('LD_LIBRARY_PATH', '')
    if ld_path:
        return ld_path
    _ensure_ld_library_path()
    return os.environ.get('LD_LIBRARY_PATH', '')


class Device(object):
    def __init__(self, index, tf_dev_type, name, total_mem, free_mem, compute_capability=None, architecture=None):
        self.index = index
        self.tf_dev_type = tf_dev_type
        self.name = name
        
        self.total_mem = total_mem
        self.total_mem_gb = total_mem / 1024**3
        self.free_mem = free_mem
        self.free_mem_gb = free_mem / 1024**3
        
        # Blackwell-specific attributes
        self.compute_capability = compute_capability  # e.g., (12, 0) for RTX 5090
        self.architecture = architecture  # 'Blackwell', 'Hopper', 'Ampere', etc.
        
        # Detect architecture from name or compute capability
        if self.architecture is None:
            self._detect_architecture()
    
    def _detect_architecture(self):
        """Detect GPU architecture from name or compute capability"""
        name_lower = self.name.lower()
        
        if any(x in name_lower for x in ['rtx 5090', 'rtx 5080', 'rtx 5070', 'rtx 5060', 'rtx 5050', 'blackwell']):
            self.architecture = 'Blackwell'
        elif any(x in name_lower for x in ['rtx 4090', 'rtx 4080', 'rtx 4070', 'rtx 4060', 'rtx 4050', 'ada']):
            self.architecture = 'Ada'
        elif any(x in name_lower for x in ['rtx 3090', 'rtx 3080', 'rtx 3070', 'ampere']):
            self.architecture = 'Ampere'
        elif any(x in name_lower for x in ['rtx 2080', 'rtx 2070', 'turing']):
            self.architecture = 'Turing'
        elif self.compute_capability and self.compute_capability[0] >= 12:
            self.architecture = 'Blackwell'
        elif self.compute_capability and self.compute_capability[0] >= 9:
            self.architecture = 'Hopper' if self.compute_capability[0] == 9 else 'Ada'
        elif self.compute_capability and self.compute_capability[0] == 8:
            self.architecture = 'Ampere'
        else:
            self.architecture = 'Unknown'
    
    @property
    def is_blackwell(self):
        """Check if this is a Blackwell GPU"""
        return self.architecture == 'Blackwell'
    
    @property
    def supports_bfloat16(self):
        """Check if GPU supports native bfloat16 operations (Blackwell+)"""
        return self.is_blackwell or (self.compute_capability and self.compute_capability >= (8, 0))
    
    @property
    def supports_flash_attention(self):
        """Check if GPU supports Flash Attention (Blackwell optimized)"""
        return self.is_blackwell or (self.compute_capability and self.compute_capability >= (8, 0))
    
    @property
    def tensor_core_generation(self):
        """Get Tensor Core generation for optimization hints"""
        if self.is_blackwell:
            return 5  # 5th gen Tensor Cores (highest performance)
        elif self.architecture == 'Ada':
            return 4
        elif self.architecture == 'Ampere':
            return 3
        else:
            return 0  # No Tensor Cores

    def __str__(self):
        arch_str = f" [{self.architecture}]" if self.architecture != 'Unknown' else ""
        cc_str = f" [CC{self.compute_capability[0]}.{self.compute_capability[1]}]" if self.compute_capability else ""
        return f"[{self.index}]:[{self.name}]{arch_str}{cc_str}[{self.free_mem_gb:.1f}/{self.total_mem_gb:.1f} GB]"

class Devices(object):
    all_devices = None

    def __init__(self, devices):
        self.devices = devices

    def __len__(self):
        return len(self.devices)

    def __getitem__(self, key):
        result = self.devices[key]
        if isinstance(key, slice):
            return Devices(result)
        return result

    def __iter__(self):
        for device in self.devices:
            yield device

    def get_best_device(self):
        result = None
        idx_mem = 0
        for device in self.devices:
            mem = device.total_mem
            # Prefer Blackwell GPUs when memory is similar (within 10%)
            if result is not None:
                mem_diff_ratio = abs(mem - result.total_mem) / max(result.total_mem, 1)
                if device.is_blackwell and not result.is_blackwell and mem_diff_ratio < 0.1:
                    result = device
                    idx_mem = mem
                    continue
            
            if mem > idx_mem:
                result = device
                idx_mem = mem
        return result

    def get_worst_device(self):
        result = None
        idx_mem = sys.maxsize
        for device in self.devices:
            mem = device.total_mem
            if mem < idx_mem:
                result = device
                idx_mem = mem
        return result

    def get_device_by_index(self, idx):
        for device in self.devices:
            if device.index == idx:
                return device
        return None

    def get_devices_from_index_list(self, idx_list):
        result = []
        for device in self.devices:
            if device.index in idx_list:
                result += [device]
        return Devices(result)

    def get_equal_devices(self, device):
        device_name = device.name
        result = []
        for device in self.devices:
            if device.name == device_name:
                result.append (device)
        return Devices(result)

    def get_devices_at_least_mem(self, totalmemsize_gb):
        result = []
        for device in self.devices:
            if device.total_mem >= totalmemsize_gb*(1024**3):
                result.append (device)
        return Devices(result)
    
    def get_blackwell_devices(self):
        """Get all Blackwell architecture devices"""
        return Devices([d for d in self.devices if d.is_blackwell])
    
    def has_blackwell(self):
        """Check if any Blackwell device is present"""
        return any(d.is_blackwell for d in self.devices)
    
    def get_preferred_data_format(self):
        """
        Get recommended data format based on available hardware
        Blackwell: NCHW for best performance (Tensor Core optimized)
        Others: NHWC for compatibility
        """
        if self.has_blackwell():
            return "NCHW"
        return "NHWC"

    @staticmethod
    def _get_tf_devices_proc(q : multiprocessing.Queue, ld_library_path=''):

        if sys.platform[0:3] == 'win':
            cache_base = os.environ.get('LOCALAPPDATA', os.environ.get('APPDATA', ''))
            compute_cache_path = Path(cache_base) / 'NVIDIA' / ('ComputeCache_ALL')
            os.environ['CUDA_CACHE_PATH'] = str(compute_cache_path)
            if not compute_cache_path.exists():
                io.log_info("Caching GPU kernels...")
                compute_cache_path.mkdir(parents=True, exist_ok=True)

        if ld_library_path:
            os.environ['LD_LIBRARY_PATH'] = ld_library_path
        else:
            _ensure_ld_library_path()
        
        import tensorflow
        
        tf_version = tensorflow.version.VERSION
        if tf_version[0] == 'v':
            tf_version = tf_version[1:]
            
        # TensorFlow 2.21.0+ required
        version_parts = tf_version.split('.')
        major = int(version_parts[0])
        
        if major >= 2:
            tf = tensorflow.compat.v1
        else:
            raise ValueError(f"TensorFlow 2.21.0+ required, got {tf_version}")
        
        import logging
        tf_logger = logging.getLogger('tensorflow')
        tf_logger.setLevel(logging.ERROR)

        from tensorflow.python.client import device_lib

        devices = {}
        
        physical_devices = device_lib.list_local_devices()
        for dev in physical_devices:
            dev_type = dev.device_type
            dev_tf_name = dev.name
            dev_tf_name = dev_tf_name[ dev_tf_name.index(dev_type) : ]
            
            dev_idx = int(dev_tf_name.split(':')[-1])
            
            if dev_type in ['GPU','DML']:
                dev_name = dev_tf_name
                compute_capability = None
                
                dev_desc = dev.physical_device_desc
                if len(dev_desc) != 0:
                    if dev_desc[0] == '{':
                        try:
                            dev_desc_json = json.loads(dev_desc)
                            dev_name = dev_desc_json.get('name', dev_name)
                            cc_major = dev_desc_json.get('compute_capability_major')
                            cc_minor = dev_desc_json.get('compute_capability_minor')
                            if cc_major is not None and cc_minor is not None:
                                compute_capability = (int(cc_major), int(cc_minor))
                        except json.JSONDecodeError:
                            pass
                    else:
                        for param, value in ( v.split(':') for v in dev_desc.split(',') ):
                            param = param.strip()
                            value = value.strip()
                            if param == 'name':
                                dev_name = value
                                break
                
                # Try to get compute capability from CUDA if not available from TF
                if compute_capability is None:
                    compute_capability = Devices._get_compute_capability_cuda(dev_idx)
                
                devices[dev_idx] = {
                    'dev_type': dev_type,
                    'name': dev_name,
                    'total_mem': dev.memory_limit
                }
                
                if compute_capability:
                    devices[dev_idx]['compute_capability'] = compute_capability
                        
        q.put(devices)
        time.sleep(0.1)

    @staticmethod
    def _detect_tf_devices_inprocess():
        devices = {}
        try:
            import tensorflow as tf

            gpus = tf.config.list_physical_devices('GPU')
            if not gpus:
                io.log_info("tf.config.list_physical_devices('GPU') returned empty")
                ld_path = os.environ.get('LD_LIBRARY_PATH', '')
                io.log_info(f"LD_LIBRARY_PATH={'(set)' if ld_path else '(NOT SET)'} [{len(ld_path)} chars]")
                if ld_path:
                    io.log_info(f"LD_LIBRARY_PATH first 200 chars: {ld_path[:200]}")

                from tensorflow.python.client import device_lib
                all_devs = device_lib.list_local_devices()
                io.log_info(f"device_lib.list_local_devices() returned {len(all_devs)} total devices")
                for d in all_devs:
                    io.log_info(f"  device: {d.name} type={d.device_type}")
                return devices

            for idx, gpu in enumerate(gpus):
                dev_name = gpu.name
                dev_type = gpu.device_type
                compute_capability = Devices._get_compute_capability_cuda(idx)

                memory_limit = 0
                try:
                    try:
                        gpu_details = tf.config.experimental.get_memory_info(gpu)
                        if gpu_details:
                            memory_limit = gpu_details.get('current', 0) + gpu_details.get('peak', 0)
                    except Exception:
                        pass
                    if memory_limit == 0:
                        import subprocess
                        result = subprocess.run(
                            ['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'],
                            capture_output=True, text=True, timeout=5
                        )
                        if result.returncode == 0 and idx < len(result.stdout.strip().split('\n')):
                            memory_limit = int(result.stdout.strip().split('\n')[idx].strip()) * 1024 * 1024
                except Exception:
                    pass

                if memory_limit == 0:
                    memory_limit = 16 * 1024 * 1024 * 1024

                devices[idx] = {
                    'dev_type': dev_type,
                    'name': dev_name,
                    'total_mem': memory_limit
                }
                if compute_capability:
                    devices[idx]['compute_capability'] = compute_capability

            io.log_info(f"In-process GPU detection found {len(devices)} device(s): {[d['name'] for d in devices.values()]}")
        except Exception as e:
            io.log_info(f"In-process GPU detection failed: {e}")
            import traceback
            traceback.print_exc()
        return devices
    
    @staticmethod
    def _get_compute_capability_cuda(device_idx=0):
        """Get compute capability using CUDA driver API"""
        try:
            libnames = ('nvcuda.dll',) if sys.platform[0:3] == 'win' else ('libcuda.so', 'libcuda.dylib')
            
            for libname in libnames:
                try:
                    cuda = ctypes.CDLL(libname)
                except OSError:
                    continue
                else:
                    break
            else:
                return None
            
            cuInit = cuda.cuInit
            cuInit.argtypes = [ctypes.c_uint]
            cuInit.restype = ctypes.c_int
            
            cuDeviceGet = cuda.cuDeviceGet
            cuDeviceGet.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_int]
            cuDeviceGet.restype = ctypes.c_int
            
            cuDeviceComputeCapability = cuda.cuDeviceComputeCapability
            cuDeviceComputeCapability.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.c_int]
            cuDeviceComputeCapability.restype = ctypes.c_int
            
            if cuInit(0) != 0:
                return None
            
            device = ctypes.c_int()
            if cuDeviceGet(ctypes.byref(device), device_idx) != 0:
                return None
            
            cc_major = ctypes.c_int()
            cc_minor = ctypes.c_int()
            if cuDeviceComputeCapability(ctypes.byref(cc_major), ctypes.byref(cc_minor), device) != 0:
                return None
            
            return (cc_major.value, cc_minor.value)
            
        except Exception as e:
            return None

    @staticmethod
    def initialize_main_env():
        if int(os.environ.get("NN_DEVICES_INITIALIZED", 0)) != 0:
            return
            
        if 'CUDA_VISIBLE_DEVICES' in os.environ.keys():
            os.environ.pop('CUDA_VISIBLE_DEVICES')
        
        # Blackwell-specific optimizations
        os.environ['TF_DIRECTML_KERNEL_CACHE_SIZE'] = '2500'
        os.environ['CUDA_CACHE_MAXSIZE'] = '2147483647'  # 2GB cache for faster compilation
        os.environ['TF_MIN_GPU_MULTIPROCESSOR_COUNT'] = '2'
        os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Log errors only
        
        # CUDA 12.x / Blackwell optimizations
        os.environ['TF_USE_CUDNN_BATCHNORM_SPATIAL_PERSISTENT'] = '1'  # Faster BatchNorm
        os.environ['TF_ENABLE_CUBLASLT'] = '1'  # Enable cuBLASlt for Blackwell
        
        # Memory allocator optimizations for Blackwell's high bandwidth memory
        os.environ['TF_GPU_ALLOCATOR'] = 'cuda_malloc_async'  # Async allocator for better utilization

        io.log_info("Detecting GPU devices (in-process)...")
        visible_devices = Devices._detect_tf_devices_inprocess()

        os.environ['NN_DEVICES_INITIALIZED'] = '1'
        os.environ['NN_DEVICES_COUNT'] = str(len(visible_devices))
        
        for i in sorted(visible_devices.keys()):
            dev_info = visible_devices[i]
            
            os.environ[f'NN_DEVICE_{i}_TF_DEV_TYPE'] = dev_info['dev_type']
            os.environ[f'NN_DEVICE_{i}_NAME'] = dev_info['name']
            os.environ[f'NN_DEVICE_{i}_TOTAL_MEM'] = str(dev_info['total_mem'])
            os.environ[f'NN_DEVICE_{i}_FREE_MEM'] = str(dev_info['total_mem'])  # Assume all free at start
            
            if 'compute_capability' in dev_info:
                cc = dev_info['compute_capability']
                os.environ[f'NN_DEVICE_{i}_CC_MAJOR'] = str(cc[0])
                os.environ[f'NN_DEVICE_{i}_CC_MINOR'] = str(cc[1])

    @staticmethod
    def getDevices():
        if Devices.all_devices is None:
            if int(os.environ.get("NN_DEVICES_INITIALIZED", 0)) != 1:
                raise Exception("nn devices are not initialized. Run initialize_main_env() in main process.")
            devices = []
            for i in range ( int(os.environ['NN_DEVICES_COUNT']) ):
                # Get compute capability if available
                cc = None
                cc_major = os.environ.get(f'NN_DEVICE_{i}_CC_MAJOR')
                cc_minor = os.environ.get(f'NN_DEVICE_{i}_CC_MINOR')
                if cc_major and cc_minor:
                    cc = (int(cc_major), int(cc_minor))
                
                devices.append ( Device(index=i,
                                        tf_dev_type=os.environ[f'NN_DEVICE_{i}_TF_DEV_TYPE'],
                                        name=os.environ[f'NN_DEVICE_{i}_NAME'],
                                        total_mem=int(os.environ[f'NN_DEVICE_{i}_TOTAL_MEM']),
                                        free_mem=int(os.environ[f'NN_DEVICE_{i}_FREE_MEM']),
                                        compute_capability=cc)
                                )
            Devices.all_devices = Devices(devices)

        return Devices.all_devices
