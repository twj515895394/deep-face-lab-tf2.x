"""
STCO - Skin Tone Consistency Optimization
基于 FaceFusion 3.x 的肤色一致性算法，针对 DeepFaceLab 优化

核心原理：
1. 精确提取皮肤区域（HSV + 形态学，排除五官）
2. 在目标图皮肤区域采样 → K-means 聚类找主肤色
3. 白化-再着色（Whitening-Recoloring）将源脸肤色对齐到目标
"""

import cv2
import numpy as np


def extract_skin_mask(image, lower=(0, 20, 70), upper=(20, 255, 255),
                     morph_kernel_size=5):
    """
    提取皮肤区域掩码
    
    Args:
        image: BGR 图像 (H, W, 3) uint8 或 float32
        lower: HSV 下界 (H, S, V)
        upper: HSV 上界 (H, S, V)
        morph_kernel_size: 形态学操作核大小
        
    Returns:
        mask: 二值皮肤掩码 (H, W) uint8
    """
    if image.dtype != np.uint8:
        img = (np.clip(image * 255, 0, 255)).astype(np.uint8)
    else:
        img = image.copy()
    
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(lower, dtype=np.uint8), 
                         np.array(upper, dtype=np.uint8))
    
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, 
                                       (morph_kernel_size, morph_kernel_size))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    
    return mask


def get_dominant_skin_color_lab(image, skin_mask=None, n_clusters=3):
    """
    在目标图像的皮肤区域中找到主肤色（Lab 色彩空间）
    
    使用 K-means 聚类找到最大簇的均值作为目标肤色中心
    
    Args:
        image: BGR 图像 (H, W, 3)
        skin_mask: 皮肤掩码 (H, W)，如果为 None 则自动提取
        n_clusters: K-means 聚类数
        
    Returns:
        target_mean: 目标主肤色 Lab 均值 [L_mean, a_mean, b_mean]
        target_std: 目标主肤色 Lab 标准差 [L_std, a_std, b_std]
    """
    if image.dtype == np.float32 or image.dtype == np.float64:
        img_uint8 = (np.clip(image * 255, 0, 255)).astype(np.uint8)
    else:
        img_uint8 = image.copy()
    
    if skin_mask is None:
        skin_mask = extract_skin_mask(img_uint8)
    
    lab = cv2.cvtColor(img_uint8, cv2.COLOR_BGR2LAB).astype(np.float32)
    
    skin_pixels = lab[skin_mask > 0]
    if len(skin_pixels) < 100:
        return np.array([50.0, 0.0, 0.0]), np.array([20.0, 10.0, 10.0])
    
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 
                  20, 1.0)
    labels, centers = cv2.kmeans(skin_pixels, n_clusters, None, criteria, 
                                   attempts=10, flags=cv2.KMEANS_RANDOM_CENTERS)
    
    counts = np.bincount(labels.flatten())
    dominant_idx = np.argmax(counts[:n_clusters])
    target_mean = centers[dominant_idx]
    
    cluster_pixels = skin_pixels[labels.flatten() == dominant_idx]
    if len(cluster_pixels) > 0:
        target_std = np.std(cluster_pixels, axis=0)
    else:
        target_std = np.array([20.0, 12.0, 12.0])
    
    return target_mean, target_std


def whitening_recoloring(src_lab, src_skin_mask, target_mean, target_std,
                          strength=1.0, preserve_luminosity=True):
    """
    白化-再着色 (Whitening-and-Recoloring)
    
    将源脸的肤色分布对齐到目标的肤色分布，
    同时保留纹理细节（通过保留标准差的相对关系）
    
    公式: f_out = σ_t · (f_src - μ_s) / σ_s + μ_t
    
    Args:
        src_lab: 源图像 Lab 空间 (H, W, 3) float32
        src_skin_mask: 源图像皮肤掩码 (H, W)
        target_mean: 目标肤色均值 [L, a, b]
        target_std: 目标肤色标准差 [L, a, b]
        strength: 校正强度 (0.0-1.0)，1.0 = 完全校正
        preserve_luminosity: 是否保持亮度通道不变
        
    Returns:
        corrected_lab: 校正后的 Lab 图像 (H, W, 3) float32
    """
    result = src_lab.copy().astype(np.float32)
    
    mask_3ch = np.stack([src_skin_mask] * 3, axis=-1).astype(np.float32) / 255.0
    
    src_skin_pixels = src_lab[src_skin_mask > 0].astype(np.float32)
    if len(src_skin_pixels) < 10:
        return result
    
    src_mean = np.mean(src_skin_pixels, axis=0)
    src_std = np.std(src_skin_pixels, axis=0) + 1e-6
    
    for c in range(3):
        if c == 0 and preserve_luminosity:
            channel = result[..., c].astype(np.float32)
            adjusted = (channel - src_mean[c]) * (target_std[c] / src_std[c]) * strength
            result[..., c] = channel + adjusted * mask_3ch[..., c]
        else:
            channel = result[..., c].astype(np.float32)
            adjusted = (channel - src_mean[c]) / src_std[c] * target_std[c] + target_mean[c]
            blended = channel * (1 - strength * mask_3ch[..., c]) + adjusted * strength * mask_3ch[..., c]
            result[..., c] = blended
    
    result = np.clip(result, 0, 100 if preserve_luminosity else 255, out=result)
    return result


def stco_correct(swap_result, target_image, strength=1.0,
                preserve_luminosity=True, smooth_edge=True, edge_blur=15):
    """
    STCO 肤色一致性优化 - 主函数
    
    自动将换脸结果的肤色对齐到目标场景的肤色
    
    Args:
        swap_result: 换脸后的图像 BGR (H, W, 3) float32 [0,1] 或 uint8 [0,255]
        target_image: 原始目标图像 BGR (H, W, 3) 同上格式
        strength: 校正强度 0.0~1.0 (1.0=完全校正)
        preserve_luminosity: 是否保持亮度不变（推荐 True）
        smooth_edge: 是否平滑边缘过渡
        edge_blur: 边缘模糊半径（像素）
        
    Returns:
        corrected: 色彩校正后的图像，与 swap_result 同格式
    """
    is_float = swap_result.dtype in [np.float32, np.float64]
    
    if is_float:
        src = (np.clip(swap_result * 255, 0, 255)).astype(np.uint8)
        tgt = (np.clip(target_image * 255, 0, 255)).astype(np.uint8)
    else:
        src = swap_result.copy()
        tgt = target_image.copy()
    
    h, w = src.shape[:2]
    if tgt.shape[:2] != (h, w):
        tgt = cv2.resize(tgt, (w, h))
    
    src_skin_mask = extract_skin_mask(src)
    tgt_skin_mask = extract_skin_mask(tgt)
    
    combined_mask = np.logical_and(src_skin_mask > 0, tgt_skin_mask > 0).astype(np.uint8)
    
    if smooth_edge:
        combined_mask = cv2.GaussianBlur(combined_mask.astype(np.float32), 
                                           (edge_blur, edge_blur))
        combined_mask = (combined_mask * 255).astype(np.uint8)
    
    target_mean, target_std = get_dominant_skin_color_lab(tgt, tgt_skin_mask)
    
    src_lab = cv2.cvtColor(src, cv2.COLOR_BGR2LAB).astype(np.float32)
    
    corrected_lab = whitening_recoloring(
        src_lab, combined_mask, target_mean, target_std,
        strength=strength, preserve_luminosity=preserve_luminosity
    )
    
    corrected_bgr = cv2.cvtColor(corrected_lab.astype(np.uint8), cv2.COLOR_LAB2BGR)
    
    if is_float:
        corrected_bgr = corrected_bgr.astype(np.float32) / 255.0
    
    alpha = combined_mask.astype(np.float32) / 255.0
    alpha_3ch = np.stack([alpha] * 3, axis=-1)
    
    result = src.astype(np.float32) * (1 - alpha_3ch) + corrected_bgr.astype(np.float32) * alpha_3ch
    
    if not is_float:
        result = (result * 255).clip(0, 255).astype(np.uint8)
    
    return result


def batch_stco_correct(images, target_images, strength=1.0, **kwargs):
    """
    批量 STCO 校正
    
    Args:
        images: 换脸结果列表 [BGR array, ...]
        target_images: 对应的目标图像列表
        strength: 校正强度
        **kwargs: 传递给 stco_correct 的其他参数
        
    Returns:
        corrected_list: 校正后的图像列表
    """
    results = []
    for i in range(len(images)):
        tgt = target_images[i] if i < len(target_images) else target_images[-1]
        results.append(stco_correct(images[i], tgt, strength=strength, **kwargs))
    return results
