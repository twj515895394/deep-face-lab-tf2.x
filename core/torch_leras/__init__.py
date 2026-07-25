"""
PyTorch Leras - PyTorch version of the lightweight neural network library

This is a PyTorch reimplementation of core.leras (TF-based)
Provides:
- Same interface as TF version but using PyTorch
- Easy model operations with dynamic graph (eager execution)
- Optimized for modern GPUs with AMP support
- NCHW format for optimal GPU performance
"""

import os
import sys
import gc
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

import numpy as np
import torch
import torch.nn as nn_torch
import torch.nn.functional as F

from pathlib import Path


class nn():
    """
    Main neural network class (PyTorch version)
    Mirrors the interface of core.leras.nn (TensorFlow version)
    """
    
    current_DeviceConfig = None
    
    device = None
    data_format = "NCHW"
    floatx = torch.float32
    
    _is_initialized = False
    _use_fp16 = False
    _use_amp = False
    
    @staticmethod
    def initialize(device_config=None, floatx="float32", data_format="NCHW", use_fp16=False, **kwargs):
        """
        Initialize PyTorch Leras
        
        Args:
            device_config: Device configuration object
            floatx: Default floating point precision ('float32', 'float16')
            data_format: Data format ('NCHW' or 'NHWC')
            use_fp16: Use mixed precision training (AMP)
        """
        if not nn._is_initialized:
            if device_config is None:
                from .device import Devices
                device_config = Devices.get_best_device()
            
            nn.current_DeviceConfig = device_config
            
            # Set device
            if hasattr(device_config, 'devices') and len(device_config.devices) > 0:
                nn.device = torch.device(f'cuda:{device_config.devices[0].index}' 
                                        if hasattr(device_config.devices[0], 'index') 
                                        else 'cuda')
            else:
                nn.device = torch.device('cpu')
            
            # Set default dtype
            if floatx == "float32":
                nn.floatx = torch.float32
            elif floatx == "float16":
                nn.floatx = torch.float16
                nn._use_fp16 = True
            else:
                raise ValueError(f"Unsupported floatx: {floatx}")
            
            nn.set_data_format(data_format)
            nn._use_amp = use_fp16
            
            # Initialize submodules in correct order (layers first!)
            import core.torch_leras.layers
            import core.torch_leras.optimizers
            import core.torch_leras.archis
            import core.torch_leras.models  # models depends on layers, so import last
            
            nn._is_initialized = True
            
            print(f"[PyTorch] Initialized on {nn.device}")
            print(f"[PyTorch] Data format: {nn.data_format}, Precision: {floatx}")
            if nn._use_amp:
                print("[PyTorch] AMP (Automatic Mixed Precision) enabled")
    
    @staticmethod
    def set_floatx(dtype):
        """Set default float type"""
        nn.floatx = dtype
    
    @staticmethod
    def set_data_format(data_format):
        """Set data format (NCHW or NHWC)"""
        if data_format not in ["NHWC", "NCHW"]:
            raise ValueError(f"Unsupported data_format: {data_format}")
        nn.data_format = data_format
        
        if data_format == "NHWC":
            nn.conv2d_ch_axis = 3
            nn.conv2d_spatial_axes = [1, 2]
        elif data_format == "NCHW":
            nn.conv2d_ch_axis = 1
            nn.conv2d_spatial_axes = [2, 3]
    
    @staticmethod
    def get4Dshape(w, h, c):
        """Get 4D shape based on current data format"""
        if nn.data_format == "NHWC":
            return (None, h, w, c)
        else:
            return (None, c, h, w)
    
    @staticmethod
    def to_data_format(x, to_data_format, from_data_format):
        """Convert tensor between data formats"""
        if to_data_format == from_data_format:
            return x
        
        if isinstance(x, np.ndarray):
            if to_data_format == "NHWC":
                return np.transpose(x, (0, 2, 3, 1))
            elif to_data_format == "NCHW":
                return np.transpose(x, (0, 3, 1, 2))
        elif isinstance(x, torch.Tensor):
            if to_data_format == "NHWC":
                return x.permute(0, 2, 3, 1)
            elif to_data_format == "NCHW":
                return x.permute(0, 3, 1, 2)
        
        raise ValueError(f"Unsupported to_data_format: {to_data_format}")
    
    @staticmethod
    def concat(tensors, axis=0):
        """Concatenate tensors along axis"""
        return torch.cat(tensors, dim=axis)
    
    @staticmethod
    def flatten(x):
        """Flatten tensor except batch dimension"""
        return x.reshape(x.size(0), -1)
    
    @staticmethod
    def reshape_4D(x, h, w, c):
        """Reshape to 4D tensor"""
        if nn.data_format == "NCHW":
            return x.view(x.size(0), c, h, w)
        else:
            return x.view(x.size(0), h, w, c)
    
    @staticmethod
    def depth_to_space(x, block_size):
        """Pixel shuffle operation (inverse of depth_to_space in TF)"""
        return F.pixel_shuffle(x, block_size)
    
    @staticmethod
    def pixel_norm(x, axes=-1):
        """Pixel normalization"""
        mean = x.mean(dim=axes, keepdim=True)
        std = x.std(dim=axes, keepdim=True) + 1e-8
        return (x - mean) / std
    
    @staticmethod
    def gaussian_blur(x, sigma):
        """Apply Gaussian blur to tensor"""
        from .ops import gaussian_blur as _gaussian_blur
        return _gaussian_blur(x, sigma)
    
    @staticmethod
    def dssim(img1, img2, max_val=1.0, filter_size=11):
        """Compute DSSIM loss"""
        from .ops import dssim as _dssim
        return _dssim(img1, img2, max_val=max_val, filter_size=filter_size)
    
    @staticmethod
    def style_loss(pred, target, gaussian_blur_radius=32, loss_weight=10000):
        """Compute style loss (Gram matrix based)"""
        from .ops import style_loss as _style_loss
        return _style_loss(pred, target, gaussian_blur_radius, loss_weight)
    
    @staticmethod
    def total_variation_mse(x):
        """Total variation regularization"""
        from .ops import total_variation_mse as _tv
        return _tv(x)
    
    @staticmethod
    def random_binomial(shape, p, dtype=torch.float32):
        """Generate random binary mask with probability p"""
        return (torch.empty(shape).uniform_() < p).to(dtype)
    
    @staticmethod
    def gradients(loss, variables):
        """Compute gradients"""
        return torch.autograd.grad(loss, variables, retain_graph=True)
    
    @staticmethod
    def average_gv_list(gv_list):
        """Average multiple gradient lists"""
        if len(gv_list) == 1:
            return gv_list[0]
        
        averaged = []
        for grads_and_vars in zip(*gv_list):
            avg_grad = torch.stack([gv[0] for gv in grads_and_vars]).mean(dim=0)
            var = grads_and_vars[0][1]
            averaged.append((avg_grad, var))
        
        return averaged
    
    class DeviceConfig:
        """Device configuration class"""
        
        def __init__(self, devices=None):
            self.devices = devices or []
            self.cpu_only = len(devices) == 0
        
        @staticmethod
        def BestGPU():
            from .device import Devices
            devices = Devices.getDevices()
            if len(devices) == 0:
                return nn.DeviceConfig.CPU()
            return nn.DeviceConfig([Devices.get_best_device()])
        
        @staticmethod
        def CPU():
            return nn.DeviceConfig([])
        
        @staticmethod
        def GPUIndexes(indexes):
            from .device import Devices
            if len(indexes) != 0:
                devices = Devices.get_devices_from_index_list(indexes)
            else:
                devices = []
            return nn.DeviceConfig(devices)
    
    @staticmethod
    def getCurrentDeviceConfig():
        if nn.current_DeviceConfig is None:
            nn.current_DeviceConfig = nn.DeviceConfig.BestGPU()
        return nn.current_DeviceConfig
    
    @staticmethod
    def setCurrentDeviceConfig(device_config):
        nn.current_DeviceConfig = device_config
    
    @staticmethod
    def reset_session():
        """Reset/clear GPU memory"""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
    
    @staticmethod
    def close_session():
        """Close and cleanup"""
        nn.reset_session()
        nn._is_initialized = False
    
    @staticmethod
    def compact_gpu_memory():
        """Compact GPU memory"""
        nn.reset_session()
