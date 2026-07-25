"""Dense (Fully Connected) layer - PyTorch implementation"""

import numpy as np
import torch
import torch.nn as nn_torch

from .LayerBase import LayerBase
from .. import nn


class Dense(LayerBase):
    """
    PyTorch Dense/Linear layer mirroring TF version
    
    Features:
    - Weight scaling (equalized learning rate)
    - Maxout support
    """
    
    def __init__(self, in_ch, out_ch, use_bias=True, use_wscale=False,
                 maxout_ch=0, kernel_initializer=None, bias_initializer=None,
                 dtype=None, **kwargs):
        
        super().__init__(**kwargs)
        
        self.in_ch = in_ch
        self.out_ch = out_ch
        self.use_bias = use_bias
        self.use_wscale = use_wscale
        self.maxout_ch = maxout_ch
        self.dtype = dtype or nn.floatx
        
        # Calculate output size considering maxout
        actual_out_ch = out_ch * maxout_ch if maxout_ch > 1 else out_ch
        
        # Create linear layer
        self.linear = nn_torch.Linear(in_ch, actual_out_ch, bias=use_bias)
        
        # Initialize weight scale
        self.wscale = None
        if use_wscale:
            gain = 1.0
            fan_in = in_ch
            he_std = gain / np.sqrt(fan_in)
            self.wscale = he_std
            
            # Use random normal initialization when using wscale
            if kernel_initializer is None:
                nn_torch.init.normal_(self.linear.weight, 0.0, 1.0)
        
        # Apply custom initializer if provided
        if kernel_initializer is not None and not use_wscale:
            if hasattr(kernel_initializer, '__call__'):
                with torch.no_grad():
                    kernel_initializer(self.linear.weight)
        elif kernel_initializer is None and not use_wscale:
            # Default: Glorot uniform (Xavier)
            nn_torch.init.xavier_uniform_(self.linear.weight)
        
        # Initialize bias
        if use_bias and self.linear.bias is not None:
            if bias_initializer is not None:
                if hasattr(bias_initializer, '__call__'):
                    with torch.no_grad():
                        bias_initializer(self.linear.bias)
            else:
                nn_torch.init.zeros_(self.linear.bias)
    
    def get_weights(self):
        """Get trainable weights"""
        weights = [self.linear.weight]
        if self.use_bias:
            weights.append(self.linear.bias)
        return weights
    
    def forward(self, x):
        """Forward pass"""
        weight = self.linear.weight
        
        # Apply weight scaling
        if self.use_wscale and self.wscale is not None:
            weight = weight * self.wscale
        
        # Matrix multiplication
        x = F.linear(x, weight, self.linear.bias if not self.use_wscale else None)
        
        # Apply maxout if enabled
        if self.maxout_ch > 1:
            x = x.view(x.size(0), self.out_ch, self.maxout_ch)
            x = x.max(dim=-1)[0]
        
        # Add bias if using wscale
        if self.use_bias and self.use_wscale and self.linear.bias is not None:
            x = x + self.linear.bias.view(1, -1)
        
        return x
    
    def __repr__(self):
        return f"Dense(in={self.in_ch}, out={self.out_ch})"


# Import F here to avoid circular dependency
import torch.nn.functional as F

nn.Dense = Dense
