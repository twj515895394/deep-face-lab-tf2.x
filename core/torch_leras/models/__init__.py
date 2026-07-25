"""PyTorch discriminator models"""

import torch
import torch.nn as nn_torch
import torch.nn.functional as F

from .. import nn
from ..layers.LayerBase import ModelBase
from ..layers.Conv2D import Conv2D


class PatchDiscriminator(ModelBase):
    """
    UNet-based Patch Discriminator for GAN training
    
    Discriminates on image patches rather than whole images
    """
    
    def __init__(self, patch_size, in_ch=3, base_ch=16, **kwargs):
        super().__init__(**kwargs)
        
        self.patch_size = patch_size
        self.in_ch = in_ch
        self.base_ch = base_ch
        
        # Encoder path (downsampling)
        self.enc1 = self._conv_block(in_ch, base_ch, kernel_size=4, strides=2)
        self.enc2 = self._conv_block(base_ch, base_ch*2, kernel_size=4, strides=2)
        self.enc3 = self._conv_block(base_ch*2, base_ch*4, kernel_size=4, strides=2)
        self.enc4 = self._conv_block(base_ch*4, base_ch*8, kernel_size=4, strides=2)
        
        # Bottleneck
        self.bottleneck = Conv2D(base_ch*8, base_ch*8, kernel_size=4,
                                 padding='SAME')
        
        # Decoder path (upsampling) - for skip connections
        self.dec4 = self._upconv_block(base_ch*8, base_ch*4)
        self.dec3 = self._upconv_block(base_ch*8, base_ch*2)  # +skip from enc3
        self.dec2 = self._upconv_block(base_ch*4, base_ch)     # +skip from enc2
        self.dec1 = self._upconv_block(base_ch*2, 1)           # +skip from enc1
        
        # Final output (two discriminators: local and global)
        self.out_conv = Conv2D(1, 1, kernel_size=1, padding='SAME')
    
    def _conv_block(self, in_ch, out_ch, kernel_size=4, strides=1):
        """Create conv block with LeakyReLU"""
        return nn_torch.Sequential(
            Conv2D(in_ch, out_ch, kernel_size=kernel_size, 
                  strides=strides, padding='SAME'),
            nn_torch.LeakyReLU(0.2, inplace=True)
        )
    
    def _upconv_block(self, in_ch, out_ch):
        """Create upsampling block with skip connection support"""
        return nn_torch.Sequential(
            nn_torch.Upsample(scale_factor=2, mode='bilinear', align_corners=True),
            Conv2D(in_ch, out_ch, kernel_size=3, padding='SAME'),
            nn_torch.LeakyReLU(0.2, inplace=True)
        )
    
    def forward(self, x):
        # Encoder
        e1 = self.enc1(x)
        e2 = self.enc2(e1)
        e3 = self.enc3(e2)
        e4 = self.enc4(e3)
        
        # Bottleneck
        b = F.leaky_relu(self.bottleneck(e4), 0.2)
        
        # Decoder with skip connections
        d4 = self.dec4(b)
        d4 = torch.cat([d4, e3], dim=nn.conv2d_ch_axis)
        
        d3 = self.dec3(d4)
        d3 = torch.cat([d3, e2], dim=nn.conv2d_ch_axis)
        
        d2 = self.dec2(d3)
        d2 = torch.cat([d2, e1], dim=nn.conv2d_ch_axis)
        
        d1 = self.dec1(d2)
        
        # Output (logits before sigmoid)
        out1 = self.out_conv(d1)
        out2 = F.adaptive_avg_pool2d(out1, 1).view(out1.size(0), -1, 1, 1)
        
        return out1, out2
    
    def get_weights(self):
        return list(self.parameters())


class CodeDiscriminator(ModelBase):
    """
    Discriminator for latent code space (used in 'df' architecture)
    
    Determines if the latent code looks like it comes from src face
    """
    
    def __init__(self, ae_dims, code_res=None, **kwargs):
        super().__init__(**kwargs)
        
        self.ae_dims = ae_dims
        self.code_res = code_res or 1
        
        # Flatten code dimensions
        input_dim = ae_dims * code_res * code_res if code_res > 1 else ae_dims
        
        # Fully connected discriminator
        self.fc1 = nn_torch.Linear(input_dim, ae_dims)
        self.fc2 = nn_torch.Linear(ae_dims, ae_dims // 2)
        self.fc3 = nn_torch.Linear(ae_dims // 2, 1)
        
        # Activation
        self.act = nn_torch.LeakyReLU(0.2, inplace=True)
    
    def forward(self, x):
        # Flatten if needed
        if x.dim() > 2:
            x = x.view(x.size(0), -1)
        
        x = self.act(self.fc1(x))
        x = self.act(self.fc2(x))
        x = self.fc3(x)
        
        # Reshape to spatial format for compatibility
        x = x.view(x.size(0), 1, 1, 1)
        
        return x
    
    def get_weights(self):
        return list(self.parameters())


nn.PatchDiscriminator = PatchDiscriminator
nn.CodeDiscriminator = CodeDiscriminator
