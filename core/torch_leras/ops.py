"""PyTorch operations (mirroring TF ops)"""

import torch
import torch.nn as nn_torch
import torch.nn.functional as F
import numpy as np
from scipy.ndimage import gaussian_filter


def gaussian_blur(x, sigma):
    """
    Apply Gaussian blur to a batch of images
    
    Args:
        x: Input tensor [B, C, H, W] or [B, H, W, C]
        sigma: Blur radius
    """
    if isinstance(x, torch.Tensor):
        x_np = x.detach().cpu().numpy()
        is_tensor = True
    else:
        x_np = x
        is_tensor = False
    
    # Determine data format
    if x_np.ndim == 4:
        if x_np.shape[1] in [1, 3]:  # NCHW
            nchw = True
        else:  # NHWC
            nchw = False
    else:
        nchw = False
    
    # Apply Gaussian filter to each image in batch
    blurred = np.zeros_like(x_np)
    for i in range(x_np.shape[0]):
        if nchw:
            for c in range(x_np.shape[1]):
                blurred[i, c] = gaussian_filter(x_np[i, c], sigma=sigma)
        else:
            for c in range(x_np.shape[-1]):
                blurred[i, ..., c] = gaussian_filter(x_np[i, ..., c], sigma=sigma)
    
    if is_tensor:
        return torch.from_numpy(blurred).to(x.device).to(x.dtype)
    
    return blurred


def dssim(img1, img2, max_val=1.0, filter_size=11):
    """
    Compute DSSIM (Structural Dissimilarity) loss
    
    Args:
        img1, img2: Input images [B, C, H, W]
        max_val: Maximum value of images
        filter_size: Window size for SSIM computation
    """
    from pytorch_msssim import ssim, ms_ssim
    
    # Convert to [B, H, W, C] format expected by pytorch-msssim
    if img1.dim() == 4 and img1.shape[1] in [1, 3]:
        img1 = img1.permute(0, 2, 3, 1)
        img2 = img2.permute(0, 2, 3, 1)
    
    # Compute SSIM and convert to DSSIM
    ssim_val = ssim(img1, img2, data_range=max_val, size_average=False)
    dssim_val = (1.0 - ssim_val) / 2.0
    
    return dssim_val


def style_loss(pred, target, gaussian_blur_radius=32, loss_weight=10000):
    """
    Compute style loss using Gram matrices
    
    Args:
        pred: Predicted tensor
        target: Target tensor
        gaussian_blur_radius: Radius for Gaussian blur before computing
        loss_weight: Weight for the loss
    """
    def gram_matrix(x):
        b, c, h, w = x.size()
        features = x.view(b, c, h * w)
        gram = torch.bmm(features, features.transpose(1, 2))
        return gram / (c * h * w)
    
    # Apply blur if needed
    if gaussian_blur_radius > 0:
        pred_blur = gaussian_blur(pred, gaussian_blur_radius)
        target_blur = gaussian_blur(target, gaussian_blur_radius)
    else:
        pred_blur = pred
        target_blur = target
    
    # Compute Gram matrices
    pred_gram = gram_matrix(pred_blur)
    target_gram = gram_matrix(target_blur)
    
    # Compute loss
    loss = F.mse_loss(pred_gram, target_gram) * loss_weight
    
    return loss.mean()


def total_variation_mse(x):
    """Total variation regularization"""
    if x.dim() == 4:
        # NCHW format
        tv_h = torch.mean(torch.abs(x[:, :, 1:, :] - x[:, :, :-1, :]))
        tv_w = torch.mean(torch.abs(x[:, :, :, 1:] - x[:, :, :, :-1]))
    else:
        # NHWC format
        tv_h = torch.mean(torch.abs(x[:, 1:, :, :] - x[:, :-1, :, :]))
        tv_w = torch.mean(torch.abs(x[:, :, 1:, :] - x[:, :, :-1, :]))
    
    return tv_h + tv_w


def create_conv2d_weights(in_ch, out_ch, kernel_size, initializer=None):
    """Create Conv2D weights with optional custom initializer"""
    weight = torch.empty(out_ch, in_ch, kernel_size, kernel_size)
    
    if initializer is not None:
        if hasattr(initializer, '__call__'):
            initializer(weight)
    else:
        nn_torch.init.kaiming_normal_(weight, mode='fan_out', nonlinearity='leaky_relu')
    
    return weight


def create_dense_weights(in_ch, out_ch, initializer=None):
    """Create Dense/Linear weights with optional custom initializer"""
    weight = torch.empty(out_ch, in_ch)
    
    if initializer is not None:
        if hasattr(initializer, '__call__'):
            initializer(weight)
    else:
        nn_torch.init.xavier_uniform_(weight)
    
    return weight
