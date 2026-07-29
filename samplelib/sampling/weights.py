import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np


@dataclass
class PoseWeightResult:
    """
    姿态权重计算结果数据结构。

    sample_weights: float32[N]，整组样本经过归一化后的个体采样权重
    bucket_counts: int32[num_buckets]，每个姿态 Bucket 的有效样本数量
    bucket_weights: float32[num_buckets]，每个 Bucket 计算出的目标权重
    expected_distribution: float32[num_buckets]，按权重计算出的理论桶抽样分布概率
    warnings: 警告信息列表
    """
    sample_weights: np.ndarray
    bucket_counts: np.ndarray
    bucket_weights: np.ndarray
    expected_distribution: np.ndarray
    warnings: List[str] = field(default_factory=list)


@dataclass
class QualityWeightResult:
    """
    质量权重计算结果数据结构。

    sample_weights: float32[N]，个体的质量权重
    raw_min: float，原始权重的最小值
    raw_mean: float，原始权重的平均值
    raw_max: float，原始权重的最大值
    clip_low_count: int，低于下限裁剪的样本数
    clip_high_count: int，高于上限裁剪的样本数
    invalid_count: int，质量记录无效或非有限数值的样本数
    warnings: 警告信息列表
    """
    sample_weights: np.ndarray
    raw_min: float
    raw_mean: float
    raw_max: float
    clip_low_count: int = 0
    clip_high_count: int = 0
    invalid_count: int = 0
    warnings: List[str] = field(default_factory=list)


def compute_pose_weights(
    yaw_bucket_ids: np.ndarray,
    pose_valid: np.ndarray,
    balance_strength: float = 0.5,
    unknown_weight: float = 0.75,
    min_bucket_weight: float = 0.5,
    max_bucket_weight: float = 2.0,
    num_buckets: int = 7,
) -> PoseWeightResult:
    """
    根据样本的 Yaw Bucket 分布计算保守、可解释且无 NaN/Inf 的姿态采样权重。

    纯函数：不读取任何图片、配置或全局状态。

    :param yaw_bucket_ids: int 数组 [N]，每个样本的 yaw bucket ID (0 ~ num_buckets-1)，未知为 -1
    :param pose_valid: bool 数组 [N]，每个样本的姿态元数据是否有效
    :param balance_strength: 姿态平衡强度 (0.0=完全不平衡/等权, 1.0=完全反比平衡, 默认 0.5)
    :param unknown_weight: unknown / invalid 姿态样本的基础相对权重 (默认 0.75)
    :param min_bucket_weight: 单 Bucket 最小相对权重剪裁值 (默认 0.5)
    :param max_bucket_weight: 单 Bucket 最大相对权重剪裁值 (默认 2.0)
    :param num_buckets: Yaw Bucket 总数量 (默认 7)
    :return: PoseWeightResult
    """
    warnings: List[str] = []

    # 1. 安全类型转换与形状校验
    yaw_bucket_ids = np.asarray(yaw_bucket_ids)
    pose_valid = np.asarray(pose_valid, dtype=bool)

    if yaw_bucket_ids.ndim != 1 or pose_valid.ndim != 1:
        raise ValueError("yaw_bucket_ids and pose_valid must be 1D numpy arrays.")

    if len(yaw_bucket_ids) != len(pose_valid):
        raise ValueError(
            f"Length mismatch: yaw_bucket_ids ({len(yaw_bucket_ids)}) vs pose_valid ({len(pose_valid)})."
        )

    N = len(yaw_bucket_ids)

    # 边界防御：剪裁与数值有限性检验
    if not math.isfinite(balance_strength):
        warnings.append(f"Non-finite balance_strength {balance_strength}, reset to 0.5")
        balance_strength = 0.5
    balance_strength = max(0.0, float(balance_strength))

    if not math.isfinite(unknown_weight) or unknown_weight <= 0:
        warnings.append(f"Invalid unknown_weight {unknown_weight}, reset to 0.75")
        unknown_weight = 0.75
    unknown_weight = float(unknown_weight)

    if not math.isfinite(min_bucket_weight) or not math.isfinite(max_bucket_weight):
        warnings.append("Non-finite bucket weight limits, reset to [0.5, 2.0]")
        min_bucket_weight, max_bucket_weight = 0.5, 2.0

    if min_bucket_weight > max_bucket_weight:
        min_bucket_weight, max_bucket_weight = max_bucket_weight, min_bucket_weight

    min_bucket_weight = max(1e-4, float(min_bucket_weight))
    max_bucket_weight = max(min_bucket_weight, float(max_bucket_weight))

    # N = 0 极端空数组防御
    if N == 0:
        warnings.append("NO_SAMPLES_PROVIDED")
        return PoseWeightResult(
            sample_weights=np.empty(0, dtype=np.float32),
            bucket_counts=np.zeros(num_buckets, dtype=np.int32),
            bucket_weights=np.ones(num_buckets, dtype=np.float32),
            expected_distribution=np.zeros(num_buckets, dtype=np.float32),
            warnings=warnings,
        )

    # 2. 统计非空有效 Bucket 样本量
    valid_mask = pose_valid & (yaw_bucket_ids >= 0) & (yaw_bucket_ids < num_buckets)
    valid_bucket_ids = yaw_bucket_ids[valid_mask]

    bucket_counts = np.zeros(num_buckets, dtype=np.int32)
    if len(valid_bucket_ids) > 0:
        counts = np.bincount(valid_bucket_ids, minlength=num_buckets)
        bucket_counts[:len(counts)] = counts[:num_buckets]

    # 3. 计算各个 Bucket 的相对权重
    non_empty_mask = bucket_counts > 0
    non_empty_counts = bucket_counts[non_empty_mask]

    bucket_weights = np.ones(num_buckets, dtype=np.float32)

    if len(non_empty_counts) == 0:
        warnings.append("ALL_SAMPLES_UNKNOWN_OR_INVALID")
        sample_weights = np.ones(N, dtype=np.float32)
        expected_distribution = np.zeros(num_buckets, dtype=np.float32)
        return PoseWeightResult(
            sample_weights=sample_weights,
            bucket_counts=bucket_counts,
            bucket_weights=bucket_weights,
            expected_distribution=expected_distribution,
            warnings=warnings,
        )

    reference_count = float(np.median(non_empty_counts))

    if balance_strength > 0.0 and len(non_empty_counts) > 1:
        for b in range(num_buckets):
            if bucket_counts[b] > 0:
                raw_w = (reference_count / float(bucket_counts[b])) ** balance_strength
                bucket_weights[b] = np.clip(raw_w, min_bucket_weight, max_bucket_weight)

    # 4. 映射展开至样本维度 sample_weights
    sample_weights = np.zeros(N, dtype=np.float32)
    sample_weights[valid_mask] = bucket_weights[yaw_bucket_ids[valid_mask]]
    sample_weights[~valid_mask] = unknown_weight

    invalid_w_mask = ~np.isfinite(sample_weights) | (sample_weights <= 0)
    if np.any(invalid_w_mask):
        warnings.append("Detected non-finite or non-positive sample weights, fallback to neutral 1.0")
        sample_weights[invalid_w_mask] = 1.0

    # 5. 均值归一化 (均值恢复为 1.0)
    mean_weight = float(np.mean(sample_weights))
    if mean_weight > 0 and math.isfinite(mean_weight):
        sample_weights = (sample_weights / mean_weight).astype(np.float32)
    else:
        warnings.append("Invalid mean sample weight during normalization, fallback to 1.0")
        sample_weights = np.ones(N, dtype=np.float32)

    # 6. 计算理论期望抽样分布 expected_distribution
    expected_distribution = np.zeros(num_buckets, dtype=np.float32)
    total_weight_sum = float(np.sum(sample_weights))
    if total_weight_sum > 0:
        for b in range(num_buckets):
            mask_b = valid_mask & (yaw_bucket_ids == b)
            expected_distribution[b] = float(np.sum(sample_weights[mask_b])) / total_weight_sum

    return PoseWeightResult(
        sample_weights=sample_weights,
        bucket_counts=bucket_counts,
        bucket_weights=bucket_weights,
        expected_distribution=expected_distribution,
        warnings=warnings,
    )


def compute_quality_weights(
    quality_scores: np.ndarray,
    quality_valid: np.ndarray,
    quality_strength: float = 0.5,
) -> QualityWeightResult:
    """
    根据静态质量得分计算保守、无 NaN/Inf 的质量采样权重。

    纯函数：不读取文件或全局状态。

    :param quality_scores: float 数组 [N]，范围 [0, 1]
    :param quality_valid: bool 数组 [N]，指示样本质量评分是否有效
    :param quality_strength: 质量调整强度 (默认 0.5，形成 [0.5, 1.5] 相对范围)
    :return: QualityWeightResult
    """
    warnings: List[str] = []

    quality_scores = np.asarray(quality_scores)
    quality_valid = np.asarray(quality_valid, dtype=bool)

    if quality_scores.ndim != 1 or quality_valid.ndim != 1:
        raise ValueError("quality_scores and quality_valid must be 1D numpy arrays.")

    if len(quality_scores) != len(quality_valid):
        raise ValueError(
            f"Length mismatch: quality_scores ({len(quality_scores)}) vs quality_valid ({len(quality_valid)})."
        )

    N = len(quality_scores)

    if not math.isfinite(quality_strength):
        warnings.append(f"Non-finite quality_strength {quality_strength}, reset to 0.5")
        quality_strength = 0.5
    quality_strength = max(0.0, float(quality_strength))

    if N == 0:
        warnings.append("NO_SAMPLES_PROVIDED")
        return QualityWeightResult(
            sample_weights=np.empty(0, dtype=np.float32),
            raw_min=1.0,
            raw_mean=1.0,
            raw_max=1.0,
            warnings=warnings,
        )

    finite_mask = np.isfinite(quality_scores)
    valid_mask = quality_valid & finite_mask
    invalid_count = int(np.sum(~valid_mask))

    if invalid_count > 0:
        warnings.append(f"Detected {invalid_count} invalid or non-finite quality scores; assigned neutral 1.0.")

    sample_weights = np.ones(N, dtype=np.float32)

    if quality_strength > 0.0 and np.any(valid_mask):
        q_valid = np.clip(quality_scores[valid_mask].astype(np.float32), 0.0, 1.0)
        # smoothstep 3 阶 Cubic 曲线: q*q*(3 - 2*q)
        smooth_q = q_valid * q_valid * (3.0 - 2.0 * q_valid)
        valid_weights = 1.0 + quality_strength * (2.0 * smooth_q - 1.0)
        sample_weights[valid_mask] = valid_weights

    raw_min = float(np.min(sample_weights))
    raw_mean = float(np.mean(sample_weights))
    raw_max = float(np.max(sample_weights))

    return QualityWeightResult(
        sample_weights=sample_weights,
        raw_min=raw_min,
        raw_mean=raw_mean,
        raw_max=raw_max,
        invalid_count=invalid_count,
        warnings=warnings,
    )


def combine_sampling_weights(
    pose_weights: np.ndarray,
    quality_weights: np.ndarray,
    min_weight: float = 0.5,
    max_weight: float = 2.0,
) -> np.ndarray:
    """
    将 Pose 权重与 Quality 权重相乘组合，并进行剪裁与二次均值归一化。
    """
    pose_weights = np.asarray(pose_weights, dtype=np.float32)
    quality_weights = np.asarray(quality_weights, dtype=np.float32)

    if pose_weights.ndim != 1 or quality_weights.ndim != 1:
        raise ValueError("pose_weights and quality_weights must be 1D numpy arrays.")

    if len(pose_weights) != len(quality_weights):
        raise ValueError(
            f"Length mismatch: pose_weights ({len(pose_weights)}) vs quality_weights ({len(quality_weights)})."
        )

    N = len(pose_weights)
    if N == 0:
        return np.empty(0, dtype=np.float32)

    if not math.isfinite(min_weight) or not math.isfinite(max_weight):
        min_weight, max_weight = 0.5, 2.0
    if min_weight > max_weight:
        min_weight, max_weight = max_weight, min_weight
    min_weight = max(0.01, float(min_weight))
    max_weight = max(min_weight, float(max_weight))

    # 1. 乘积组合
    combined = pose_weights * quality_weights

    invalid_mask = ~np.isfinite(combined) | (combined <= 0)
    if np.any(invalid_mask):
        combined[invalid_mask] = 1.0

    # 2. 剪裁 -> 均值归一化 -> 再剪裁 -> 再均值归一化
    combined = np.clip(combined, min_weight, max_weight)
    mean_w1 = float(np.mean(combined))
    if mean_w1 > 0 and math.isfinite(mean_w1):
        combined = combined / mean_w1
    else:
        combined = np.ones(N, dtype=np.float32)

    combined = np.clip(combined, min_weight, max_weight)
    mean_w2 = float(np.mean(combined))
    if mean_w2 > 0 and math.isfinite(mean_w2):
        combined = (combined / mean_w2).astype(np.float32)
    else:
        combined = np.ones(N, dtype=np.float32)

    return combined


def weights_to_probabilities(
    weights: np.ndarray,
    uniform_mix: float = 0.10,
) -> np.ndarray:
    """
    将样本权重转化为真正的概率分布，混合 uniform 探索项。
    p_final = (1 - mix) * p_weighted + mix * (1 / N)
    """
    weights = np.asarray(weights, dtype=np.float32)
    if weights.ndim != 1:
        raise ValueError("weights must be a 1D numpy array.")

    N = len(weights)
    if N == 0:
        return np.empty(0, dtype=np.float32)

    if not math.isfinite(uniform_mix):
        uniform_mix = 0.10
    uniform_mix = float(np.clip(uniform_mix, 0.0, 1.0))

    invalid_mask = ~np.isfinite(weights) | (weights <= 0)
    if np.any(invalid_mask):
        weights = weights.copy()
        weights[invalid_mask] = 1.0

    total_weight = float(np.sum(weights))
    if total_weight <= 0 or not math.isfinite(total_weight):
        p_weighted = np.full(N, 1.0 / float(N), dtype=np.float32)
    else:
        p_weighted = (weights / total_weight).astype(np.float32)

    p_uniform = 1.0 / float(N)
    p_final = (1.0 - uniform_mix) * p_weighted + uniform_mix * p_uniform

    p_final = (p_final / np.sum(p_final)).astype(np.float32)
    return p_final
