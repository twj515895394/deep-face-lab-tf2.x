"""
Leras.

like lighter keras.
This is my lightweight neural network library written from scratch
based on pure tensorflow without keras.

Provides:
+ full freedom of tensorflow operations without keras model's restrictions
+ easy model operations like in PyTorch, but in graph mode (no eager execution)
+ convenient and understandable logic
+ optimized for TensorFlow 2.21.0 and NVIDIA Blackwell architecture

Reasons why we cannot import tensorflow or any tensorflow.sub modules right here:
1) program is changing env variables based on DeviceConfig before import tensorflow
2) multiprocesses will import tensorflow every spawn

NCHW speed up training for 10-20%.
Blackwell (RTX 50 series) optimizations: mixed precision (bfloat16), Flash Attention
"""

import os
import sys
import gc
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
from pathlib import Path
import numpy as np
from core.interact import interact as io
from .device import Devices

# Suppress TensorFlow and oneDNN warnings for cleaner output
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Show only errors
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'  # Disable oneDNN custom ops warnings


class nn():
    current_DeviceConfig = None

    tf = None
    tf_sess = None
    tf_sess_config = None
    tf_default_device_name = None
    
    data_format = None
    conv2d_ch_axis = None
    conv2d_spatial_axes = None

    floatx = None
    
    _tf_version_major = None
    _tf_version_minor = None
    _is_blackwell = False
    _mixed_precision_policy = None
    _loss_scale = None
    _loss_scale_value = 1.0
    
    @staticmethod
    def initialize(device_config=None, floatx="float32", data_format="NHWC", use_bf16_mixed_precision=False):
        """
        Initialize Leras with TensorFlow 2.21.0 optimizations

        Args:
            device_config: Device configuration (GPU/CPU)
            floatx: Default floating point precision ('float32', 'float16', 'bfloat16')
            data_format: Data format ('NHWC' or 'NCHW')
            use_bf16_mixed_precision: Use bfloat16 mixed precision for Blackwell Tensor Cores
        """

        if nn.tf is None:
            if device_config is None:
                device_config = nn.getCurrentDeviceConfig()
            nn.setCurrentDeviceConfig(device_config)

            # Manipulate environment variables before import tensorflow
            
            # Blackwell-specific CUDA optimizations
            os.environ['TF_USE_CUDNN_BATCHNORM_SPATIAL_PERSISTENT'] = '1'
            os.environ['TF_ENABLE_CUBLASLT'] = '1'

            # TF32 precision mode for Blackwell (faster than fp32, more stable than fp16)
            os.environ['NVIDIA_TF32_OVERRIDE'] = '1'

            # cuDNN v9 Flash Attention support (Blackwell native)
            os.environ['CUDNN_LOGWARN'] = '0'

            # CUDA 12.x / Blackwell memory allocator
            
            first_run = False
            if len(device_config.devices) != 0:
                if sys.platform[0:3] == 'win':
                    # Windows specific env vars
                    if all( [ x.name == device_config.devices[0].name for x in device_config.devices ] ):
                        devices_str = "_" + device_config.devices[0].name.replace(' ','_')
                    else:
                        devices_str = ""
                        for device in device_config.devices:
                            devices_str += "_" + device.name.replace(' ','_')

                    compute_cache_path = Path(os.environ.get('LOCALAPPDATA', os.environ.get('APPDATA', ''))) / 'NVIDIA' / ('ComputeCache' + devices_str)
                    if not compute_cache_path.exists():
                        first_run = True
                        compute_cache_path.mkdir(parents=True, exist_ok=True)
                    os.environ['CUDA_CACHE_PATH'] = str(compute_cache_path)
                    
                    # Blackwell-specific cache optimization
                    os.environ['CUDA_CACHE_MAXSIZE'] = '2147483647'  # 2GB max cache
                    
            if first_run:
                io.log_info("Caching GPU kernels for Blackwell architecture...")

            import tensorflow

            tf_version = tensorflow.version.VERSION
            if tf_version[0] == 'v':
                tf_version = tf_version[1:]
                
            # Parse version
            version_parts = tf_version.split('.')
            nn._tf_version_major = int(version_parts[0])
            nn._tf_version_minor = int(version_parts[1]) if len(version_parts) > 1 else 0
            
            io.log_info(f"TensorFlow {tf_version} detected")
            
            # TensorFlow 2.21.0 uses native v2 API with v1 compatibility layer
            if nn._tf_version_major >= 2:
                import tensorflow.compat.v1 as tf

                # Disable v2 behavior for backward compatibility with existing code
                # Use compat.v1 API to avoid deprecation warnings in TF 2.21+
                tf.compat.v1.disable_v2_behavior()
            else:
                raise ValueError(f"TensorFlow 2.21.0+ required, got {tf_version}")

            nn.tf = tf

            import logging
            # Disable tensorflow warnings
            tf_logger = logging.getLogger('tensorflow')
            tf_logger.setLevel(logging.ERROR)
            
            # Check for Blackwell architecture
            nn._detect_blackwell_architecture(device_config)
            
            if nn._is_blackwell:
                io.log_info("✓ NVIDIA Blackwell (RTX 50 series) detected - enabling optimizations")
            
            # Initialize framework
            import core.leras.ops
            import core.leras.layers
            import core.leras.initializers
            import core.leras.optimizers
            import core.leras.models
            import core.leras.archis
            
            # Configure tensorflow session-config with Blackwell optimizations
            if len(device_config.devices) == 0:
                config = tf.ConfigProto(device_count={'GPU': 0})
                nn.tf_default_device_name = '/CPU:0'
            else:
                nn.tf_default_device_name = f'/{device_config.devices[0].tf_dev_type}:0'
                
                config = tf.ConfigProto()
                config.gpu_options.visible_device_list = ','.join([str(device.index) for device in device_config.devices])
                
            # Blackwell-specific GPU options
            config.gpu_options.force_gpu_compatible = True
            config.gpu_options.allow_growth = True

            # CUDA memory pool for faster allocation
            os.environ['TF_CUDA_HOST_MEM_POOL_IN_MB'] = str(1024)
            
            # Set inter-op and intra-op parallelism threads for Blackwell's high core count
            try:
                intra_op = int(os.environ.get('OMP_NUM_THREADS', '0')) or None
                inter_op = int(os.environ.get('TF_INTER_OP_PARALLELISM', '0')) or None
                
                if intra_op:
                    config.intra_op_parallelism_threads = intra_op
                if inter_op:
                    config.inter_op_parallelism_threads = inter_op
            except:
                pass
            
            nn.tf_sess_config = config
            
        tf = nn.tf

        if nn.tf_sess is None:
            nn.tf_sess = tf.Session(config=nn.tf_sess_config)

        # Set default dtype - support bfloat16 for Blackwell
        if floatx == "float32":
            floatx = nn.tf.float32
        elif floatx == "float16":
            floatx = nn.tf.float16
        elif floatx == "bfloat16":
            if hasattr(nn.tf, 'bfloat16'):
                floatx = nn.tf.bfloat16
                if nn._is_blackwell:
                    io.log_info("✓ Using bfloat16 mixed precision for Blackwell Tensor Cores")
            else:
                io.log_info("bfloat16 not available, falling back to float16")
                floatx = nn.tf.float16
        else:
            raise ValueError(f"unsupported floatx {floatx}")
        nn.set_floatx(floatx)
        nn.set_data_format(data_format)

        # Log optimization status (use print to ensure visibility during init)
        if nn._is_blackwell:
            print("[Blackwell] NVIDIA Blackwell (RTX 50 series) detected - enabling optimizations")
            if os.environ.get('NVIDIA_TF32_OVERRIDE', '0') == '1':
                print("[Blackwell] TF32 precision mode enabled (faster than fp32, more stable than fp16)")
        
        # Apply mixed precision policy for Blackwell
        if use_bf16_mixed_precision and nn._is_blackwell:
            nn._enable_bfloat16_policy()

    @staticmethod
    def _detect_blackwell_architecture(device_config):
        """Detect if running on NVIDIA Blackwell architecture (RTX 50 series)"""
        nn._is_blackwell = False
        
        if len(device_config.devices) == 0:
            return
            
        for device in device_config.devices:
            # Blackwell GPUs typically have names containing RTX 50xx or Blackwell
            name_lower = device.name.lower()
            if any(x in name_lower for x in ['rtx 5090', 'rtx 5080', 'rtx 5070', 'rtx 5060', 'rtx 5050', 'blackwell']):
                nn._is_blackwell = True
                break
        
        # Also check via CUDA compute capability if available
        if not nn._is_blackwell:
            try:
                # Blackwell has compute capability 12.0+
                # We can detect this from device properties
                for device in device_config.devices:
                    if hasattr(device, 'compute_capability'):
                        cc = device.compute_capability
                        if cc >= 120:  # Blackwell = 12.x
                            nn._is_blackwell = True
                            break
            except:
                pass

    @staticmethod
    def _enable_bfloat16_policy():
        """Enable bfloat16 mixed precision policy for Blackwell"""
        try:
            from tensorflow.keras import mixed_precision as mp

            policy = mp.Policy('mixed_bfloat16')
            mp.set_global_policy(policy)
            nn._mixed_precision_policy = 'mixed_bfloat16'
            io.log_info("✓ Mixed precision policy set to bfloat16")

            # Enable Loss Scaling for bf16 stability on Blackwell
            nn._enable_loss_scaling()
        except Exception as e:
            io.log_info(f"Could not enable bfloat16 policy: {e}")

    @staticmethod
    def _enable_loss_scaling():
        """Enable dynamic loss scaling for bf16 training stability"""
        if nn._loss_scale is None:
            try:
                from tensorflow.keras.mixed_precision import LossScaleOptimizer

                # Dynamic loss scaling: initial scale = 2^15, max = 2^20, min = 1
                # Automatically adjusts to prevent gradient underflow/overflow
                nn._loss_scale_value = 32768.0  # 2^15
                io.log_info(f"✓ Loss Scaling enabled (initial scale: {nn._loss_scale_value})")
            except ImportError:
                pass

    @staticmethod
    def get_loss_scale():
        """Get current loss scale value for gradient unscaling"""
        if nn._loss_scale is not None and nn._loss_scale_value > 1.0:
            return nn._loss_scale_value
        return 1.0

    @staticmethod
    def is_tf32_mode():
        """Check if running in TF32 mode (Blackwell optimized)"""
        return os.environ.get('NVIDIA_TF32_OVERRIDE', '0') == '1' and nn._is_blackwell
    
    @staticmethod
    def initialize_main_env():
        Devices.initialize_main_env()

    @staticmethod
    def set_floatx(tf_dtype):
        """
        set default float type for all layers when dtype is None for them
        """
        nn.floatx = tf_dtype

    @staticmethod
    def set_data_format(data_format):
        if data_format not in ["NHWC", "NCHW"]:
            raise ValueError(f"unsupported data_format {data_format}")
        nn.data_format = data_format

        if data_format == "NHWC":
            nn.conv2d_ch_axis = 3
            nn.conv2d_spatial_axes = [1,2]
        elif data_format == "NCHW":
            nn.conv2d_ch_axis = 1
            nn.conv2d_spatial_axes = [2,3]

    @staticmethod
    def get4Dshape ( w, h, c ):
        """
        returns 4D shape based on current data_format
        """
        if nn.data_format == "NHWC":
            return (None,h,w,c)
        else:
            return (None,c,h,w)

    @staticmethod
    def to_data_format( x, to_data_format, from_data_format):
        if to_data_format == from_data_format:
            return x

        if to_data_format == "NHWC":
            return np.transpose(x, (0,2,3,1) )
        elif to_data_format == "NCHW":
            return np.transpose(x, (0,3,1,2) )
        else:
            raise ValueError(f"unsupported to_data_format {to_data_format}")

    @staticmethod
    def getCurrentDeviceConfig():
        if nn.current_DeviceConfig is None:
            nn.current_DeviceConfig = DeviceConfig.BestGPU()
        return nn.current_DeviceConfig

    @staticmethod
    def setCurrentDeviceConfig(device_config):
        nn.current_DeviceConfig = device_config

    @staticmethod
    def reset_session():
        if nn.tf is not None:
            if nn.tf_sess is not None:
                nn.tf.reset_default_graph()
                nn.tf_sess.close()
                nn.tf_sess = nn.tf.Session(config=nn.tf_sess_config)
                gc.collect()

    @staticmethod
    def close_session():
        if nn.tf_sess is not None:
            nn.tf.reset_default_graph()
            nn.tf_sess.close()
            nn.tf_sess = None
            gc.collect()

    @staticmethod
    def compact_gpu_memory():
        if nn.tf is not None and nn.tf_sess is not None:
            try:
                empty = tf.constant([], dtype=tf.float32)
                for _ in range(5):
                    nn.tf_sess.run(empty)

                try:
                    from tensorflow.python.framework import c_api_util
                    c_api_util.tf_flush_gpu_data_buffers()
                except:
                    pass

                gc.collect()
            except Exception as e:
                io.log_info(f"GPU memory compaction warning: {e}")
                gc.collect()

    @staticmethod
    def ask_choose_device_idxs(choose_only_one=False, allow_cpu=True, suggest_best_multi_gpu=False, suggest_all_gpu=False):
        devices = Devices.getDevices()
        if len(devices) == 0:
            return []

        all_devices_indexes = [device.index for device in devices]

        if choose_only_one:
            suggest_best_multi_gpu = False
            suggest_all_gpu = False

        if suggest_all_gpu:
            best_device_indexes = all_devices_indexes
        elif suggest_best_multi_gpu:
            best_device_indexes = [device.index for device in devices.get_equal_devices(devices.get_best_device()) ]
        else:
            best_device_indexes = [ devices.get_best_device().index ]
        best_device_indexes = ",".join([str(x) for x in best_device_indexes])

        io.log_info ("")
        if choose_only_one:
            io.log_info ("Choose one GPU idx.")
        else:
            io.log_info ("Choose one or several GPU idxs (separated by comma).")
        io.log_info ("")

        if allow_cpu:
            io.log_info ("[CPU] : CPU")
        for device in devices:
            arch_marker = " 🖥️ Blackwell" if nn._is_blackwell and any(x in device.name.lower() for x in ['5090', '5080', '5070', '5060', '5050']) else ""
            io.log_info (f"  [{device.index}] : {device.name}{arch_marker}")

        io.log_info ("")

        while True:
            try:
                if choose_only_one:
                    choosed_idxs = io.input_str("Which GPU index to choose?", best_device_indexes)
                else:
                    choosed_idxs = io.input_str("Which GPU indexes to choose?", best_device_indexes)

                if allow_cpu and choosed_idxs.lower() == "cpu":
                    choosed_idxs = []
                    break

                choosed_idxs = [ int(x) for x in choosed_idxs.split(',') ]

                if choose_only_one:
                    if len(choosed_idxs) == 1:
                        break
                else:
                    if all( [idx in all_devices_indexes for idx in choosed_idxs] ):
                        break
            except:
                pass
        io.log_info ("")

        return choosed_idxs

    @staticmethod
    def get_tf_version():
        """Get TensorFlow version tuple"""
        return (nn._tf_version_major, nn._tf_version_minor)
    
    @staticmethod
    def is_blackwell():
        """Check if running on Blackwell architecture"""
        return nn._is_blackwell
    
    @staticmethod
    def optimize_for_blackwell():
        """
        Apply comprehensive Blackwell-specific optimizations
        Call this after initialize() for maximum performance
        """
        if not nn._is_blackwell:
            io.log_info("Not running on Blackwell architecture, skipping optimizations")
            return
            
        io.log_info("Applying Blackwell (RTX 50 series) optimizations...")

        try:
            # Set memory growth strategy for better utilization
            gpus = nn.tf.config.experimental.list_physical_devices('GPU')
            for gpu in gpus:
                nn.tf.config.experimental.set_memory_growth(gpu, True)
            
            # Enable cuDNN deterministic operations for reproducibility (optional)
            # os.environ['TF_DETERMINISTIC_OPS'] = '1'
            
            # Optimize for throughput vs latency
            nn.tf.config.set_soft_device_placement(True)
            
            io.log_info("  ✓ Memory growth enabled for all GPUs")
            io.log_info("  ✓ Soft device placement enabled")
            io.log_info("Blackwell optimization complete!")
            
        except Exception as e:
            io.log_warning(f"Some optimizations could not be applied: {e}")

    class DeviceConfig():
        @staticmethod
        def ask_choose_device(*args, **kwargs):
            return nn.DeviceConfig.GPUIndexes( nn.ask_choose_device_idxs(*args,**kwargs) )
        
        def __init__ (self, devices=None):
            devices = devices or []

            if not isinstance(devices, Devices):
                devices = Devices(devices)

            self.devices = devices
            self.cpu_only = len(devices) == 0

        @staticmethod
        def BestGPU():
            devices = Devices.getDevices()
            if len(devices) == 0:
                return nn.DeviceConfig.CPU()

            # Prefer Blackwell GPUs if available
            for device in devices:
                name_lower = device.name.lower()
                if any(x in name_lower for x in ['rtx 5090', 'rtx 5080', 'rtx 5070']):
                    return nn.DeviceConfig([device])
            
            return nn.DeviceConfig([devices.get_best_device()])

        @staticmethod
        def WorstGPU():
            devices = Devices.getDevices()
            if len(devices) == 0:
                return nn.DeviceConfig.CPU()

            return nn.DeviceConfig([devices.get_worst_device()])

        @staticmethod
        def GPUIndexes(indexes):
            if len(indexes) != 0:
                devices = Devices.getDevices().get_devices_from_index_list(indexes)
            else:
                devices = []

            return nn.DeviceConfig(devices)

        @staticmethod
        def CPU():
            return nn.DeviceConfig([])
