"""PyTorch model architectures (mirroring TF versions)"""

import torch
import torch.nn as nn_torch
import torch.nn.functional as F

from .. import nn
from ..layers.LayerBase import ModelBase
from ..layers.Conv2D import Conv2D
from ..layers.Dense import Dense


class DeepFakeArchi(nn.ArchiBase if hasattr(nn, 'ArchiBase') else object):
    """
    DeepFake Architecture for PyTorch
    
    Supports:
    - df: Standard DeepFake architecture
    - liae: LIAE (Low-level Interpolation AutoEncoder) architecture
    - Options:
      - 'u': Increased likeness (pixel norm)
      - 'd': Double resolution at same computation cost
      - 't': Thinner encoder (more downscales)
      - 'c': Cos activation instead of leaky_relu
    """
    
    def __init__(self, resolution, use_fp16=False, mod=None, opts=None):
        super().__init__()
        
        if opts is None:
            opts = ''
        
        self.resolution = resolution
        self.use_fp16 = use_fp16
        self.opts = opts
        
        # Determine activation function
        if 'c' in opts:
            def act(x, alpha=0.1):
                return x * torch.cos(x)
        else:
            def act(x, alpha=0.1):
                return F.leaky_relu(x, alpha)
        
        self.act = act
        
        # Set conv dtype
        self.conv_dtype = torch.float16 if use_fp16 else torch.float32
        
        # Build sub-components
        if mod is None or mod == 'default':
            self._build_default_architecture()
        
        # Register as nn module components
        self._register_components()
    
    def _build_default_architecture(self):
        """Build the default DeepFake/LIAE architecture"""
        opts = self.opts
        resolution = self.resolution
        conv_dtype = self.conv_dtype
        act = self.act
        use_fp16 = self.use_fp16  # Get from instance
        
        # ===== Downscale Block =====
        class Downscale(ModelBase):
            def __init__(self, in_ch, out_ch, kernel_size=5, **kwargs):
                super().__init__(**kwargs)
                self.in_ch = in_ch
                self.out_ch = out_ch
                self.conv1 = Conv2D(in_ch, out_ch, kernel_size=kernel_size,
                                   strides=2, padding='SAME', dtype=conv_dtype)
            
            def forward(self, x):
                x = self.conv1(x)
                x = act(x, 0.1)
                return x
            
            def get_out_ch(self):
                return self.out_ch
        
        class DownscaleBlock(ModelBase):
            def __init__(self, in_ch, ch, n_downscales, kernel_size=5, **kwargs):
                super().__init__(**kwargs)
                self.downs = []
                
                last_ch = in_ch
                for i in range(n_downscales):
                    cur_ch = ch * min(2**i, 8)
                    down = Downscale(last_ch, cur_ch, kernel_size=kernel_size)
                    self.downs.append(down)
                    self.add_module(f'down_{i}', down)
                    last_ch = down.get_out_ch()
            
            def forward(self, inp):
                x = inp
                for down in self.downs:
                    x = down(x)
                return x
        
        class Upscale(ModelBase):
            def __init__(self, in_ch, out_ch, kernel_size=3, **kwargs):
                super().__init__(**kwargs)
                self.conv1 = Conv2D(in_ch, out_ch * 4, kernel_size=kernel_size,
                                   padding='SAME', dtype=conv_dtype)
            
            def forward(self, x):
                x = self.conv1(x)
                x = act(x, 0.1)
                x = nn.depth_to_space(x, 2)
                return x
        
        class ResidualBlock(ModelBase):
            def __init__(self, ch, kernel_size=3, **kwargs):
                super().__init__(**kwargs)
                self.conv1 = Conv2D(ch, ch, kernel_size=kernel_size,
                                   padding='SAME', dtype=conv_dtype)
                self.conv2 = Conv2D(ch, ch, kernel_size=kernel_size,
                                   padding='SAME', dtype=conv_dtype)
            
            def forward(self, inp):
                x = self.conv1(inp)
                x = act(x, 0.2)
                x = self.conv2(x)
                x = act(inp + x, 0.2)
                return x
        
        # Store classes for building models
        self.Downscale = Downscale
        self.DownscaleBlock = DownscaleBlock
        self.Upscale = Upscale
        self.ResidualBlock = ResidualBlock
        
        # ===== Encoder =====
        class Encoder(ModelBase):
            def __init__(self, in_ch, e_ch, **kwargs):
                super().__init__(**kwargs)
                self.in_ch = in_ch
                self.e_ch = e_ch
                self.use_fp16 = use_fp16
                self.opts = opts
                
                if 't' in opts:
                    self.down1 = Downscale(in_ch, e_ch, kernel_size=5)
                    self.res1 = ResidualBlock(e_ch)
                    self.down2 = Downscale(e_ch, e_ch*2, kernel_size=5)
                    self.down3 = Downscale(e_ch*2, e_ch*4, kernel_size=5)
                    self.down4 = Downscale(e_ch*4, e_ch*8, kernel_size=5)
                    self.down5 = Downscale(e_ch*8, e_ch*8, kernel_size=5)
                    self.res5 = ResidualBlock(e_ch*8)
                else:
                    n_downscales = 4 if 't' not in opts else 5
                    self.down1 = DownscaleBlock(in_ch, e_ch, 
                                               n_downscales=n_downscales, 
                                               kernel_size=5)
            
            def forward(self, x):
                if self.use_fp16 and hasattr(self, '_parent'):
                    x = x.to(torch.float16)
                
                if 't' in opts:
                    x = self.down1(x)
                    x = self.res1(x)
                    x = self.down2(x)
                    x = self.down3(x)
                    x = self.down4(x)
                    x = self.down5(x)
                    x = self.res5(x)
                else:
                    x = self.down1(x)
                
                x = nn.flatten(x)
                
                if 'u' in opts:
                    x = nn.pixel_norm(x, axes=-1)
                
                if self.use_fp16:
                    x = x.to(torch.float32)
                
                return x
            
            def get_out_res(self, res):
                n_downs = 4 if 't' not in opts else 5
                return res // (2 ** n_downs)
            
            def get_out_ch(self):
                return self.e_ch * 8
        
        # ===== Inter (Intermediate) =====
        lowest_dense_res = resolution // (32 if 'd' in opts else 16)
        
        class Inter(ModelBase):
            def __init__(self, in_ch, ae_ch, ae_out_ch, **kwargs):
                super().__init__(**kwargs)
                self.in_ch = in_ch
                self.ae_ch = ae_ch
                self.ae_out_ch = ae_out_ch
                self.use_fp16 = use_fp16
                self.opts = opts
                
                self.dense1 = Dense(in_ch, ae_ch)
                self.dense2 = Dense(ae_ch, lowest_dense_res * lowest_dense_res * ae_out_ch)
                
                if 't' not in opts:
                    self.upscale1 = Upscale(ae_out_ch, ae_out_ch)
            
            def forward(self, inp):
                x = inp
                x = self.dense1(x)
                x = self.dense2(x)
                x = nn.reshape_4D(x, lowest_dense_res, lowest_dense_res, self.ae_out_ch)
                
                if self.use_fp16:
                    x = x.to(torch.float16)
                
                if 't' not in opts:
                    x = self.upscale1(x)
                
                return x
            
            def get_out_res(self):
                return lowest_dense_res * 2 if 't' not in opts else lowest_dense_res
            
            def get_out_ch(self):
                return self.ae_out_ch
        
        # ===== Decoder =====
        class Decoder(ModelBase):
            def __init__(self, in_ch, d_ch, d_mask_ch, **kwargs):
                super().__init__(**kwargs)
                self.d_ch = d_ch
                self.use_fp16 = use_fp16
                self.opts = opts
                
                if 't' not in opts:
                    # Image decoder path
                    self.upscale0 = Upscale(in_ch, d_ch*8, kernel_size=3)
                    self.upscale1 = Upscale(d_ch*8, d_ch*4, kernel_size=3)
                    self.upscale2 = Upscale(d_ch*4, d_ch*2, kernel_size=3)
                    
                    self.res0 = ResidualBlock(d_ch*8, kernel_size=3)
                    self.res1 = ResidualBlock(d_ch*4, kernel_size=3)
                    self.res2 = ResidualBlock(d_ch*2, kernel_size=3)
                    
                    # Mask decoder path
                    self.upscalem0 = Upscale(in_ch, d_mask_ch*8, kernel_size=3)
                    self.upscalem1 = Upscale(d_mask_ch*8, d_mask_ch*4, kernel_size=3)
                    self.upscalem2 = Upscale(d_mask_ch*4, d_mask_ch*2, kernel_size=3)
                    
                    self.out_conv = Conv2D(d_ch*2, 3, kernel_size=1,
                                          padding='SAME', dtype=conv_dtype)
                    
                    if 'd' in opts:
                        # Double resolution output
                        self.out_conv1 = Conv2D(d_ch*2, 3, kernel_size=3,
                                               padding='SAME', dtype=conv_dtype)
                        self.out_conv2 = Conv2D(d_ch*2, 3, kernel_size=3,
                                               padding='SAME', dtype=conv_dtype)
                        self.out_conv3 = Conv2D(d_ch*2, 3, kernel_size=3,
                                               padding='SAME', dtype=conv_dtype)
                        self.upscalem3 = Upscale(d_mask_ch*2, d_mask_ch*1, kernel_size=3)
                        self.out_convm = Conv2D(d_mask_ch*1, 1, kernel_size=1,
                                               padding='SAME', dtype=conv_dtype)
                    else:
                        self.out_convm = Conv2D(d_mask_ch*2, 1, kernel_size=1,
                                               padding='SAME', dtype=conv_dtype)
                        
                else:
                    # Thinner version with more upscales
                    self.upscale0 = Upscale(in_ch, d_ch*8, kernel_size=3)
                    self.upscale1 = Upscale(d_ch*8, d_ch*8, kernel_size=3)
                    self.upscale2 = Upscale(d_ch*8, d_ch*4, kernel_size=3)
                    self.upscale3 = Upscale(d_ch*4, d_ch*2, kernel_size=3)
                    
                    self.res0 = ResidualBlock(d_ch*8, kernel_size=3)
                    self.res1 = ResidualBlock(d_ch*8, kernel_size=3)
                    self.res2 = ResidualBlock(d_ch*4, kernel_size=3)
                    self.res3 = ResidualBlock(d_ch*2, kernel_size=3)
                    
                    self.upscalem0 = Upscale(in_ch, d_mask_ch*8, kernel_size=3)
                    self.upscalem1 = Upscale(d_mask_ch*8, d_mask_ch*8, kernel_size=3)
                    self.upscalem2 = Upscale(d_mask_ch*8, d_mask_ch*4, kernel_size=3)
                    self.upscalem3 = Upscale(d_mask_ch*4, d_mask_ch*2, kernel_size=3)
                    
                    self.out_conv = Conv2D(d_ch*2, 3, kernel_size=1,
                                          padding='SAME', dtype=conv_dtype)
                    
                    if 'd' in opts:
                        self.out_conv1 = Conv2D(d_ch*2, 3, kernel_size=3,
                                               padding='SAME', dtype=conv_dtype)
                        self.out_conv2 = Conv2D(d_ch*2, 3, kernel_size=3,
                                               padding='SAME', dtype=conv_dtype)
                        self.out_conv3 = Conv2D(d_ch*2, 3, kernel_size=3,
                                               padding='SAME', dtype=conv_dtype)
                        self.upscalem4 = Upscale(d_mask_ch*2, d_mask_ch*1, kernel_size=3)
                        self.out_convm = Conv2D(d_mask_ch*1, 1, kernel_size=1,
                                               padding='SAME', dtype=conv_dtype)
                    else:
                        self.out_convm = Conv2D(d_mask_ch*2, 1, kernel_size=1,
                                               padding='SAME', dtype=conv_dtype)
            
            def forward(self, z):
                # Image reconstruction path
                x = self.upscale0(z)
                x = self.res0(x)
                x = self.upscale1(x)
                x = self.res1(x)
                x = self.upscale2(x)
                x = self.res2(x)
                
                if 't' in self.opts:
                    x = self.upscale3(x)
                    x = self.res3(x)
                
                # Output image
                if 'd' in self.opts:
                    # Double resolution using depth_to_space
                    cat = torch.cat([self.out_conv(x),
                                    self.out_conv1(x),
                                    self.out_conv2(x),
                                    self.out_conv3(x)], dim=nn.conv2d_ch_axis)
                    x = torch.sigmoid(nn.depth_to_space(cat, 2))
                else:
                    x = torch.sigmoid(self.out_conv(x))
                
                # Mask reconstruction path
                m = self.upscalem0(z)
                m = self.upscalem1(m)
                m = self.upscalem2(m)
                
                if 't' in self.opts:
                    m = self.upscalem3(m)
                    if 'd' in self.opts:
                        m = self.upscalem4(m)
                else:
                    if 'd' in self.opts:
                        m = self.upscalem3(m)
                
                m = torch.sigmoid(self.out_convm(m))
                
                # Cast back to float32 if needed
                if self.use_fp16:
                    x = x.to(torch.float32)
                    m = m.to(torch.float32)
                
                return x, m
        
        # Assign to instance
        self.Encoder = Encoder
        self.Inter = Inter
        self.Decoder = Decoder
    
    def _register_components(self):
        """Register all sub-components as nn.Module attributes"""
        # This is called after architecture is built
        # Components will be registered when instantiated with add_module()
        pass


nn.DeepFakeArchi = DeepFakeArchi

# Create ArchiBase class if it doesn't exist
if not hasattr(nn, 'ArchiBase'):
    class ArchiBase:
        pass
    nn.ArchiBase = ArchiBase
