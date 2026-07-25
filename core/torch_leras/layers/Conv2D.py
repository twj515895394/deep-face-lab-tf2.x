"""Conv2D layer - PyTorch implementation"""

import numpy as np
import torch
import torch.nn as nn_torch
import torch.nn.functional as F

from .LayerBase import LayerBase
from .. import nn


class Conv2D(LayerBase):
    """
    PyTorch Conv2D layer mirroring TF version
    
    Features:
    - NCHW format (optimal for PyTorch/GPU)
    - AMP support
    - Equalized learning rate (wscale)
    """
    
    def __init__(self, in_ch, out_ch, kernel_size, strides=1, padding='SAME', 
                 dilations=1, use_bias=True, use_wscale=False,
                 kernel_initializer=None, bias_initializer=None,
                 dtype=None, **kwargs):
        
        super().__init__(**kwargs)
        
        if not isinstance(strides, int):
            raise ValueError("strides must be an int type")
        if not isinstance(dilations, int):
            raise ValueError("dilations must be an int type")
        
        kernel_size = int(kernel_size)
        
        # Handle padding
        if isinstance(padding, str):
            if padding == "SAME":
                self.padding = (kernel_size - 1) * dilations // 2
            elif padding == "VALID":
                self.padding = 0
            else:
                raise ValueError(f"Wrong padding type: {padding}")
        else:
            self.padding = int(padding)
        
        # Set dtype
        self.dtype = dtype or nn.floatx
        
        # Store parameters
        self.in_ch = in_ch
        self.out_ch = out_ch
        self.kernel_size = kernel_size
        self.strides = strides
        self.dilations = dilations
        self.use_bias = use_bias
        self.use_wscale = use_wscale
        
        # Create conv layer
        self.conv = nn_torch.Conv2d(
            in_channels=in_ch,
            out_channels=out_ch,
            kernel_size=kernel_size,
            stride=strides,
            padding=self.padding,
            dilation=dilations,
            bias=use_bias
        )
        
        # Initialize weight scale for equalized LR
        self.wscale = None
        if use_wscale:
            fan_in = kernel_size * kernel_size * in_ch
            gain = 1.0 if kernel_size == 1 else np.sqrt(2)
            he_std = gain / np.sqrt(fan_in)
            self.wscale = he_std
        
        # Custom initialization
        if kernel_initializer is not None:
            # Apply custom initializer to weight
            if hasattr(kernel_initializer, '__call__'):
                with torch.no_grad():
                    kernel_initializer(self.conv.weight)
        
        self._initialize_bias(bias_initializer)
    
    def _initialize_bias(self, bias_initializer):
        """Initialize bias"""
        if self.use_bias and self.conv.bias is not None:
            if bias_initializer is not None:
                if hasattr(bias_initializer, '__call__'):
                    with torch.no_grad():
                        bias_initializer(self.conv.bias)
            else:
                nn_torch.init.zeros_(self.conv.bias)
    
    def get_weights(self):
        """Get trainable weights"""
        weights = [self.conv.weight]
        if self.use_bias:
            weights.append(self.conv.bias)
        return weights
    
    def forward(self, x):
        """Forward pass"""
        weight = self.conv.weight
        
        # Apply weight scaling (equalized learning rate)
        if self.use_wscale and self.wscale is not None:
            weight = weight * self.wscale
        
        # Cast dtype if needed
        original_dtype = x.dtype
        if self.dtype != original_dtype:
            x = x.to(self.dtype)
        
        # Convolution
        x = F.conv2d(x, weight, 
                     self.conv.bias if not self.use_wscale else None,
                     stride=self.strides,
                     padding=self.padding,
                     dilation=self.dilations)
        
        # Add bias separately if using wscale
        if self.use_bias and self.use_wscale and self.conv.bias is not None:
            bias = self.conv.bias.view(1, -1, 1, 1)
            x = x + bias
        
        # Cast back if needed
        if self.dtype != original_dtype:
            x = x.to(original_dtype)
        
        return x
    
    def __repr__(self):
        return f"Conv2D(in_ch={self.in_ch}, out_ch={self.out_ch}, k={self.kernel_size}, s={self.strides})"


nn.Conv2D = Conv2D
