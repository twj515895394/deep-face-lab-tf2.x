import copy
import multiprocessing
import operator
import os
import traceback
from functools import partial
import time

import numpy as np

from core import mathlib
from core.interact import interact as io
from core.leras import nn
from facelib import FaceType
from models import ModelBase
from samplelib import *

try:
    from core.enhancements import normalize_enhancement_config
    ENHANCEMENTS_AVAILABLE = True
except ImportError:
    normalize_enhancement_config = None
    ENHANCEMENTS_AVAILABLE = False

try:
    from core.leras.optimizations import (
        MixedPrecisionManager,
        set_mixed_precision
    )
    OPTIMIZATIONS_AVAILABLE = True
except ImportError:
    OPTIMIZATIONS_AVAILABLE = False

try:
    from core.leras.precision_contract import (
        resolve_precision_contract,
        summarize_precision_contract,
    )
    PRECISION_CONTRACT_AVAILABLE = True
except ImportError:
    resolve_precision_contract = None
    summarize_precision_contract = None
    PRECISION_CONTRACT_AVAILABLE = False

# 这些 helper 故意保持纯 NumPy：macOS 无 GPU 时也能验证样本协议，
# 避免再次把 priority loss 配置错误静默伪装成正常训练。
def _sample_shapes(samples):
    return [getattr(sample, 'shape', None) for sample in samples]

def _validate_eyes_mouth_mask(eyes_mouth_mask, full_mask, domain):
    if eyes_mouth_mask is None:
        raise ValueError(f"{domain} eyes/mouth mask is required when eyes_mouth_prio is enabled.")
    if getattr(eyes_mouth_mask, 'shape', None) != getattr(full_mask, 'shape', None):
        raise ValueError(
            f"{domain} eyes/mouth mask shape must match full mask shape: "
            f"eyes_mouth={getattr(eyes_mouth_mask, 'shape', None)}, "
            f"full={getattr(full_mask, 'shape', None)}"
        )
    mask_dtype = getattr(eyes_mouth_mask, 'dtype', None)
    full_mask_dtype = getattr(full_mask, 'dtype', None)
    if mask_dtype is not None and full_mask_dtype is not None:
        if not np.can_cast(mask_dtype, full_mask_dtype, casting='same_kind'):
            raise ValueError(
                f"{domain} eyes/mouth mask dtype {mask_dtype} cannot be safely "
                f"converted to full mask dtype {full_mask_dtype}."
            )
    if not np.all(np.isfinite(eyes_mouth_mask)):
        raise ValueError(f"{domain} eyes/mouth mask contains inf or nan values.")
    return eyes_mouth_mask

def _unpack_training_samples(samples, has_eyes_mouth, domain):
    expected = 4 if has_eyes_mouth else 3
    if len(samples) != expected:
        raise ValueError(
            f"{domain} training samples expected {expected} outputs, got {len(samples)}. "
            f"shapes={_sample_shapes(samples)}"
        )

    warped, target, full_mask = samples[:3]
    eyes_mouth_mask = None
    if has_eyes_mouth:
        eyes_mouth_mask = _validate_eyes_mouth_mask(samples[3], full_mask, domain)
    return warped, target, full_mask, eyes_mouth_mask

def _add_eyes_mouth_masks_to_feed(feed_dict,
                                  src_placeholder, dst_placeholder,
                                  target_srcm, target_dstm,
                                  target_srcm_em, target_dstm_em,
                                  has_eyes_mouth):
    if not has_eyes_mouth:
        return feed_dict

    feed_dict[src_placeholder] = _validate_eyes_mouth_mask(
        target_srcm_em, target_srcm, 'src'
    )
    feed_dict[dst_placeholder] = _validate_eyes_mouth_mask(
        target_dstm_em, target_dstm, 'dst'
    )
    return feed_dict

def _as_training_bool(value, default=True):
    if value is None:
        return default
    try:
        return bool(np.all(value))
    except Exception:
        return default

def _unpack_unified_train_result(result):
    src_loss, dst_loss = result[0], result[1]
    gradients_finite = _as_training_bool(result[2], default=True) if len(result) > 2 else True
    step_applied = _as_training_bool(result[3], default=gradients_finite) if len(result) > 3 else gradients_finite
    return src_loss, dst_loss, gradients_finite, step_applied

def _update_loss_scale_state(model, gradients_finite):
    if model.loss_scale_var is None:
        return
    log_info = getattr(io, 'log_info', None)
    if not gradients_finite:
        current_scale = nn.tf_sess.run(model.loss_scale_var)
        new_scale = max(current_scale / 2.0, 1.0)
        nn.tf_sess.run(model.loss_scale_var.assign(new_scale))
        if log_info is not None:
            log_info(f"⚠️ Loss scale reduced: {current_scale:.0f} → {new_scale:.0f} (non-finite gradient detected)")
        model._loss_scale_consecutive_normal_steps = 0
        model._loss_scale_steps_since_last_adjustment = 0
        return

    model._loss_scale_consecutive_normal_steps += 1
    model._loss_scale_steps_since_last_adjustment += 1

    if model._loss_scale_consecutive_normal_steps >= model._LOSS_SCALE_RECOVERY_INTERVAL:
        current_scale = nn.tf_sess.run(model.loss_scale_var)
        if current_scale < model._LOSS_SCALE_MAX:
            new_scale = min(current_scale * 2.0, model._LOSS_SCALE_MAX)
            nn.tf_sess.run(model.loss_scale_var.assign(new_scale))
            if log_info is not None:
                log_info(
                    f"✓ Loss scale increased: {current_scale:.0f} → "
                    f"{new_scale:.0f} (stable for "
                    f"{model._loss_scale_consecutive_normal_steps} steps)"
                )
        model._loss_scale_consecutive_normal_steps = 0

def _get_training_batch_size(model):
    get_batch_size = getattr(model, 'get_batch_size', None)
    if get_batch_size is None:
        return getattr(model, 'batch_size', None)
    try:
        return get_batch_size()
    except Exception:
        return '<unavailable>'

def _get_training_iter(model):
    get_iter = getattr(model, 'get_iter', None)
    if get_iter is None:
        return getattr(model, 'iter', None)
    try:
        return get_iter()
    except Exception:
        return '<unavailable>'

def _get_training_precision(model):
    contract = getattr(model, 'precision_contract', None)
    if isinstance(contract, dict) and contract.get('effective_precision'):
        return contract.get('effective_precision')
    options = getattr(model, 'options', None)
    if isinstance(options, dict):
        return options.get('precision')
    return getattr(model, 'precision', None)

def _training_exception_context(model, src_samples=None, dst_samples=None):
    return {
        'iter': _get_training_iter(model),
        'batch_size': _get_training_batch_size(model),
        'resolution': getattr(model, 'resolution', None),
        'precision': _get_training_precision(model),
        'has_eyes_mouth': getattr(model, '_has_eyes_mouth', None),
        'src_shapes': _sample_shapes(src_samples) if src_samples is not None else None,
        'dst_shapes': _sample_shapes(dst_samples) if dst_samples is not None else None,
    }

def _is_oom_exception(error):
    if isinstance(error, MemoryError):
        return True
    error_text = ' '.join(str(arg) for arg in getattr(error, 'args', ()) if arg)
    error_text = f"{type(error).__name__} {error_text}".lower()
    oom_markers = (
        'out of memory',
        'resource exhausted',
        'resourceexhausted',
        'cuda_error_out_of_memory',
        'cublas_status_alloc_failed',
        'cudnn_status_alloc_failed',
        'ran out of memory',
    )
    if any(marker in error_text for marker in oom_markers):
        return True
    if 'non-oom' in error_text or 'non oom' in error_text:
        return False
    error_tokens = error_text.replace('_', ' ').replace('-', ' ').split()
    return 'oom' in error_tokens

def _format_training_exception_message(error, context, is_oom):
    failure_kind = 'OOM' if is_oom else 'non-OOM'
    traceback_text = ''.join(
        traceback.format_exception(type(error), error, error.__traceback__)
    )
    return (
        f"SAEHD training iteration failed ({failure_kind}). "
        f"Context: iter={context.get('iter')}, "
        f"batch_size={context.get('batch_size')}, "
        f"resolution={context.get('resolution')}, "
        f"precision={context.get('precision')}, "
        f"has_eyes_mouth={context.get('has_eyes_mouth')}, "
        f"src_shapes={context.get('src_shapes')}, "
        f"dst_shapes={context.get('dst_shapes')}\n"
        f"{traceback_text}"
    )

def _log_training_exception(error, model, src_samples=None, dst_samples=None):
    is_oom = _is_oom_exception(error)
    context = _training_exception_context(model, src_samples, dst_samples)
    message = _format_training_exception_message(error, context, is_oom)
    io.log_err(message)
    return message

class SAEHDModel(ModelBase):

    #override
    def on_initialize_options(self):
        device_config = nn.getCurrentDeviceConfig()

        lowest_vram = 2
        if len(device_config.devices) != 0:
            lowest_vram = device_config.devices.get_worst_device().total_mem_gb

        if lowest_vram >= 4:
            suggest_batch_size = 8
        else:
            suggest_batch_size = 4

        yn_str = {True:'y',False:'n'}
        min_res = 64
        max_res = 640

        #default_usefp16            = self.options['use_fp16']           = self.load_or_def_option('use_fp16', False)
        default_resolution         = self.options['resolution']         = self.load_or_def_option('resolution', 128)
        default_face_type          = self.options['face_type']          = self.load_or_def_option('face_type', 'f')
        default_models_opt_on_gpu  = self.options['models_opt_on_gpu']  = self.load_or_def_option('models_opt_on_gpu', True)

        default_archi              = self.options['archi']              = self.load_or_def_option('archi', 'liae-ud')

        default_ae_dims            = self.options['ae_dims']            = self.load_or_def_option('ae_dims', 256)
        default_e_dims             = self.options['e_dims']             = self.load_or_def_option('e_dims', 64)
        default_d_dims             = self.options['d_dims']             = self.options.get('d_dims', None)
        default_d_mask_dims        = self.options['d_mask_dims']        = self.options.get('d_mask_dims', None)
        default_masked_training    = self.options['masked_training']    = self.load_or_def_option('masked_training', True)
        default_eyes_mouth_prio    = self.options['eyes_mouth_prio']    = self.load_or_def_option('eyes_mouth_prio', False)
        default_uniform_yaw        = self.options['uniform_yaw']        = self.load_or_def_option('uniform_yaw', False)
        default_blur_out_mask      = self.options['blur_out_mask']      = self.load_or_def_option('blur_out_mask', False)

        default_optimizer         = self.options['optimizer']          = self.load_or_def_option('optimizer', 'adabelief')

        lr_dropout = self.load_or_def_option('lr_dropout', 'n')
        lr_dropout = {True:'y', False:'n'}.get(lr_dropout, lr_dropout) #backward comp
        default_lr_dropout         = self.options['lr_dropout'] = lr_dropout

        default_random_warp        = self.options['random_warp']        = self.load_or_def_option('random_warp', True)
        default_random_hsv_power   = self.options['random_hsv_power']   = self.load_or_def_option('random_hsv_power', 0.0)
        default_true_face_power    = self.options['true_face_power']    = self.load_or_def_option('true_face_power', 0.0)
        default_face_style_power   = self.options['face_style_power']   = self.load_or_def_option('face_style_power', 0.0)
        default_bg_style_power     = self.options['bg_style_power']     = self.load_or_def_option('bg_style_power', 0.0)
        default_ct_mode            = self.options['ct_mode']            = self.load_or_def_option('ct_mode', 'none')
        default_clipgrad           = self.options['clipgrad']           = self.load_or_def_option('clipgrad', False)
        default_pretrain           = self.options['pretrain']           = self.load_or_def_option('pretrain', False)
        default_precision          = self.options['precision']         = self.load_or_def_option('precision', 'fp32')

        if ENHANCEMENTS_AVAILABLE:
            # 新增强配置必须 legacy-safe：旧模型无字段时只构造运行时对象，不强制改写 data.dat。
            raw_enhancements = self.options.get('enhancements', None)
            self.enhancements = normalize_enhancement_config(raw_enhancements)
            if self.is_first_run() or raw_enhancements is not None:
                self.options['enhancements'] = self.enhancements.to_dict()

        ask_override = self.ask_override()
        if self.is_first_run() or ask_override:
            self.ask_autobackup_hour()
            self.ask_write_preview_history()
            self.ask_target_iter()
            self.ask_random_src_flip()
            self.ask_random_dst_flip()
            self.ask_batch_size(suggest_batch_size)

            precision_choices = ['fp32', 'fp16', 'bf16']
            default_precision = io.input_str ("Precision", default_precision, precision_choices,
                help_message="fp32: Most stable, slowest. fp16: Faster, less stable, may crash. bf16: Best balance for RTX 50 series, fast + stable.").lower()
            if default_precision not in precision_choices:
                default_precision = 'fp32'
            self.options['precision'] = default_precision

        if self.is_first_run():
            resolution = io.input_int("Resolution", default_resolution, add_info="64-640", help_message="More resolution requires more VRAM and time to train. Value will be adjusted to multiple of 16 and 32 for -d archi.")
            resolution = np.clip ( (resolution // 16) * 16, min_res, max_res)
            self.options['resolution'] = resolution



            self.options['face_type'] = io.input_str ("Face type", default_face_type, ['h','mf','f','wf','head'], help_message="Half / mid face / full face / whole face / head. Half face has better resolution, but covers less area of cheeks. Mid face is 30% wider than half face. 'Whole face' covers full area of face include forehead. 'head' covers full head, but requires XSeg for src and dst faceset.").lower()

            while True:
                archi = io.input_str ("AE architecture", default_archi, help_message=\
"""
'df' keeps more identity-preserved face.
'liae' can fix overly different face shapes.
'-u' increased likeness of the face.
'-d' (experimental) doubling the resolution using the same computation cost.
Examples: df, liae, df-d, df-ud, liae-ud, ...
""").lower()

                archi_split = archi.split('-')

                if len(archi_split) == 2:
                    archi_type, archi_opts = archi_split
                elif len(archi_split) == 1:
                    archi_type, archi_opts = archi_split[0], None
                else:
                    continue

                if archi_type not in ['df', 'liae']:
                    continue

                if archi_opts is not None:
                    if len(archi_opts) == 0:
                        continue
                    if len([ 1 for opt in archi_opts if opt not in ['u','d','t','c'] ]) != 0:
                        continue

                    if 'd' in archi_opts:
                        self.options['resolution'] = np.clip ( (self.options['resolution'] // 32) * 32, min_res, max_res)

                break
            self.options['archi'] = archi

        default_d_dims             = self.options['d_dims']             = self.load_or_def_option('d_dims', 64)

        default_d_mask_dims        = default_d_dims // 3
        default_d_mask_dims        += default_d_mask_dims % 2
        default_d_mask_dims        = self.options['d_mask_dims']        = self.load_or_def_option('d_mask_dims', default_d_mask_dims)

        if self.is_first_run():
            self.options['ae_dims'] = np.clip ( io.input_int("AutoEncoder dimensions", default_ae_dims, add_info="32-1024", help_message="All face information will packed to AE dims. If amount of AE dims are not enough, then for example closed eyes will not be recognized. More dims are better, but require more VRAM. You can fine-tune model size to fit your GPU." ), 32, 1024 )

            e_dims = np.clip ( io.input_int("Encoder dimensions", default_e_dims, add_info="16-256", help_message="More dims help to recognize more facial features and achieve sharper result, but require more VRAM. You can fine-tune model size to fit your GPU." ), 16, 256 )
            self.options['e_dims'] = e_dims + e_dims % 2

            d_dims = np.clip ( io.input_int("Decoder dimensions", default_d_dims, add_info="16-256", help_message="More dims help to recognize more facial features and achieve sharper result, but require more VRAM. You can fine-tune model size to fit your GPU." ), 16, 256 )
            self.options['d_dims'] = d_dims + d_dims % 2

            d_mask_dims = np.clip ( io.input_int("Decoder mask dimensions", default_d_mask_dims, add_info="16-256", help_message="Typical mask dimensions = decoder dimensions / 3. If you manually cut out obstacles from the dst mask, you can increase this parameter to achieve better quality." ), 16, 256 )
            self.options['d_mask_dims'] = d_mask_dims + d_mask_dims % 2

        if self.is_first_run() or ask_override:
            if self.options['face_type'] == 'wf' or self.options['face_type'] == 'head':
                self.options['masked_training']  = io.input_bool ("Masked training", default_masked_training, help_message="This option is available only for 'whole_face' or 'head' type. Masked training clips training area to full_face mask or XSeg mask, thus network will train the faces properly.")

            self.options['eyes_mouth_prio'] = io.input_bool ("Eyes and mouth priority", default_eyes_mouth_prio, help_message='Helps to fix eye problems during training like "alien eyes" and wrong eyes direction. Also makes the detail of the teeth higher.')
            self.options['uniform_yaw'] = io.input_bool ("Uniform yaw distribution of samples", default_uniform_yaw, help_message='Helps to fix blurry side faces due to small amount of them in the faceset.')

            if ENHANCEMENTS_AVAILABLE and self.enhancements is not None:
                from core.enhancements import apply_interactive_sampling_base_update

                current_meta_sampling = self.enhancements.is_enabled("training.metadata_sampling")
                enable_meta_sampling = io.input_bool ("Enable metadata sampling?", current_meta_sampling, help_message="Use faceset_metadata.v1.json to enable pose-balanced or quality-aware sampling.")

                # R1-03: only edit base mode / gates; never drop sampling.src / sampling.dst.
                chosen_mode = None
                if enable_meta_sampling:
                    current_mode = self.enhancements.sampling_config.mode.value
                    if current_mode == "legacy":
                        current_mode = "quality_pose_balanced"
                    mode_choices = ["legacy", "pose_balanced", "quality_pose_balanced"]
                    chosen_mode = io.input_str ("Sampling mode", current_mode, mode_choices, help_message="legacy: standard random/uniform_yaw. pose_balanced: weight rare head poses. quality_pose_balanced: weight pose + image quality.").lower()
                    if chosen_mode not in mode_choices:
                        chosen_mode = current_mode

                updated_dict = apply_interactive_sampling_base_update(
                    self.enhancements.to_dict(),
                    enable_meta_sampling=enable_meta_sampling,
                    chosen_base_mode=chosen_mode if enable_meta_sampling else None,
                )

                self.enhancements = normalize_enhancement_config(updated_dict)
                self.options["enhancements"] = self.enhancements.to_dict()

            self.options['blur_out_mask'] = io.input_bool ("Blur out mask", default_blur_out_mask, help_message='Blurs nearby area outside of applied face mask of training samples. The result is the background near the face is smoothed and less noticeable on swapped face. The exact xseg mask in src and dst faceset is required.')

        default_gan_power          = self.options['gan_power']          = self.load_or_def_option('gan_power', 0.0)
        default_gan_patch_size     = self.options['gan_patch_size']     = self.load_or_def_option('gan_patch_size', self.options['resolution'] // 8)
        default_gan_dims           = self.options['gan_dims']           = self.load_or_def_option('gan_dims', 16)

        if self.is_first_run() or ask_override:
            self.options['models_opt_on_gpu'] = io.input_bool ("Place models and optimizer on GPU", default_models_opt_on_gpu, help_message="When you train on one GPU, by default model and optimizer weights are placed on GPU to accelerate the process. You can place they on CPU to free up extra VRAM, thus set bigger dimensions.")

            self.options['opt_states_on_gpu'] = io.input_bool ("Place optimizer states on GPU", self.load_or_def_option('opt_states_on_gpu', True),
                help_message="Optimizer states (momentum/variance for AdaBelief, momentum for Lion) take significant VRAM: AdaB ~320MB, Lion ~160MB. They are ONLY used during weight update step (~5% of iteration time). Keeping them on CPU saves this VRAM with minimal speed cost (~3-5% slower per iter). Recommended: No for AdaB, Yes for Lion.")

            optimizer_choices = ['adabelief', 'lion', 'rmsprop']
            self.options['optimizer'] = io.input_str ("Optimizer", default_optimizer, optimizer_choices,
                help_message="adabelief: Stable, good generalization (default). lion: Google 2023, -15% VRAM, better for GANs, sign-based. rmsprop: Classic, lowest VRAM usage.").lower()
            if self.options['optimizer'] not in optimizer_choices:
                self.options['optimizer'] = 'adabelief'

            self.options['lr_dropout']  = io.input_str (f"Use learning rate dropout", default_lr_dropout, ['n','y','cpu'], help_message="When the face is trained enough, you can enable this option to get extra sharpness and reduce subpixel shake for less amount of iterations. Enabled it before `disable random warp` and before GAN. \nn - disabled.\ny - enabled\ncpu - enabled on CPU. This allows not to use extra VRAM, sacrificing 20% time of iteration.")

            self.options['random_warp'] = io.input_bool ("Enable random warp of samples", default_random_warp, help_message="Random warp is required to generalize facial expressions of both faces. When the face is trained enough, you can disable it to get extra sharpness and reduce subpixel shake for less amount of iterations.")

            self.options['random_hsv_power'] = np.clip ( io.input_number ("Random hue/saturation/light intensity", default_random_hsv_power, add_info="0.0 .. 0.3", help_message="Random hue/saturation/light intensity applied to the src face set only at the input of the neural network. Stabilizes color perturbations during face swapping. Reduces the quality of the color transfer by selecting the closest one in the src faceset. Thus the src faceset must be diverse enough. Typical fine value is 0.05"), 0.0, 0.3 )

            self.options['gan_power'] = np.clip ( io.input_number ("GAN power", default_gan_power, add_info="0.0 .. 5.0", help_message="Forces the neural network to learn small details of the face. Enable it only when the face is trained enough with lr_dropout(on) and random_warp(off), and don't disable. The higher the value, the higher the chances of artifacts. Typical fine value is 0.1"), 0.0, 5.0 )

            if self.options['gan_power'] != 0.0:
                gan_patch_size = np.clip ( io.input_int("GAN patch size", default_gan_patch_size, add_info="3-640", help_message="The higher patch size, the higher the quality, the more VRAM is required. You can get sharper edges even at the lowest setting. Typical fine value is resolution / 8." ), 3, 640 )
                self.options['gan_patch_size'] = gan_patch_size

                gan_dims = np.clip ( io.input_int("GAN dimensions", default_gan_dims, add_info="4-512", help_message="The dimensions of the GAN network. The higher dimensions, the more VRAM is required. You can get sharper edges even at the lowest setting. Typical fine value is 16." ), 4, 512 )
                self.options['gan_dims'] = gan_dims

            if 'df' in self.options['archi']:
                self.options['true_face_power'] = np.clip ( io.input_number ("'True face' power.", default_true_face_power, add_info="0.0000 .. 1.0", help_message="Experimental option. Discriminates result face to be more like src face. Higher value - stronger discrimination. Typical value is 0.01 . Comparison - https://i.imgur.com/czScS9q.png"), 0.0, 1.0 )
            else:
                self.options['true_face_power'] = 0.0

            self.options['face_style_power'] = np.clip ( io.input_number("Face style power", default_face_style_power, add_info="0.0..100.0", help_message="Learn the color of the predicted face to be the same as dst inside mask. If you want to use this option with 'whole_face' you have to use XSeg trained mask. Warning: Enable it only after 10k iters, when predicted face is clear enough to start learn style. Start from 0.001 value and check history changes. Enabling this option increases the chance of model collapse."), 0.0, 100.0 )
            self.options['bg_style_power'] = np.clip ( io.input_number("Background style power", default_bg_style_power, add_info="0.0..100.0", help_message="Learn the area outside mask of the predicted face to be the same as dst. If you want to use this option with 'whole_face' you have to use XSeg trained mask. For whole_face you have to use XSeg trained mask. This can make face more like dst. Enabling this option increases the chance of model collapse. Typical value is 2.0"), 0.0, 100.0 )

            self.options['ct_mode'] = io.input_str (f"Color transfer for src faceset", default_ct_mode, ['none','rct','lct','mkl','idt','sot'], help_message="Change color distribution of src samples close to dst samples. Try all modes to find the best.")
            self.options['clipgrad'] = io.input_bool ("Enable gradient clipping", default_clipgrad, help_message="Gradient clipping reduces chance of model collapse, sacrificing speed of training.")

            self.options['pretrain'] = io.input_bool ("Enable pretraining mode", default_pretrain, help_message="Pretrain the model with large amount of various faces. After that, model can be used to train the fakes more quickly. Forces random_warp=N, random_flips=Y, gan_power=0.0, lr_dropout=N, styles=0.0, uniform_yaw=Y")

        if self.options['pretrain'] and self.get_pretraining_data_path() is None:
            raise Exception("pretraining_data_path is not defined")

        self.gan_model_changed = (default_gan_patch_size != self.options['gan_patch_size']) or (default_gan_dims != self.options['gan_dims'])

        self.pretrain_just_disabled = (default_pretrain == True and self.options['pretrain'] == False)

    #override
    def on_initialize(self):
        device_config = nn.getCurrentDeviceConfig()
        devices = device_config.devices
        self.model_data_format = "NCHW" if len(devices) != 0 and not self.is_debug() else "NHWC"
        nn.initialize(data_format=self.model_data_format)
        tf = nn.tf

        self.resolution = resolution = self.options['resolution']
        self.face_type = {'h'  : FaceType.HALF,
                          'mf' : FaceType.MID_FULL,
                          'f'  : FaceType.FULL,
                          'wf' : FaceType.WHOLE_FACE,
                          'head' : FaceType.HEAD}[ self.options['face_type'] ]

        if 'eyes_prio' in self.options:
            self.options.pop('eyes_prio')

        eyes_mouth_prio = self.options['eyes_mouth_prio']
        self._has_eyes_mouth = bool(eyes_mouth_prio)

        archi_split = self.options['archi'].split('-')

        if len(archi_split) == 2:
            archi_type, archi_opts = archi_split
        elif len(archi_split) == 1:
            archi_type, archi_opts = archi_split[0], None

        self.archi_type = archi_type

        ae_dims = self.options['ae_dims']
        e_dims = self.options['e_dims']
        d_dims = self.options['d_dims']
        d_mask_dims = self.options['d_mask_dims']
        self.pretrain = self.options['pretrain']
        if self.pretrain_just_disabled:
            self.set_iter(0)

        optimizer_name = self.options['optimizer']
        opt_info = {
            'adabelief': 'AdaBelief (stable, good generalization)',
            'lion': 'Lion (Google 2023, -15% VRAM, sign-based)',
            'rmsprop': 'RMSprop (classic, lowest VRAM)',
        }
        io.log_info(f"Optimizer: {opt_info.get(optimizer_name, optimizer_name)}")

        opt_on_gpu = self.options.get('opt_states_on_gpu', True)
        if not opt_on_gpu:
            io.log_info("Optimizer states: CPU (saves ~320MB AdaB / ~160MB Lion VRAM)")
        else:
            io.log_info("Optimizer states: GPU (fastest updates)")

        requested_precision = self.options.get('precision', 'fp32')
        precision = requested_precision
        self.precision_contract = None
        use_fp16 = False
        self.loss_scale_var = None

        if PRECISION_CONTRACT_AVAILABLE:
            try:
                # 这里不做真实 runtime 探测，避免初始化阶段因缺少可选依赖影响旧模型。
                # BF16/FP16 是否能建图仍由下面 legacy 分支实际尝试后决定。
                self.precision_contract = resolve_precision_contract(
                    requested_precision,
                    runtime_capabilities={
                        'tensorflow_available': True,
                        'float16_dtype_available': True,
                        'bfloat16_dtype_available': True,
                    },
                )
                precision = self.precision_contract.get('effective_precision', 'fp32')
                io.log_info(summarize_precision_contract(self.precision_contract))
                if self.precision_contract.get('status') == 'experimental':
                    io.log_info(f"  Precision status=experimental: {self.precision_contract.get('risk_notes')}")
                if self.precision_contract.get('fallback_reason'):
                    io.log_info(f"  Precision fallback: {self.precision_contract.get('fallback_reason')}")
            except Exception as e:
                io.log_info(f"Precision contract unavailable, falling back to fp32: {e}")
                precision = 'fp32'

        if precision == 'fp16':
            use_fp16 = True
            io.log_info("Precision effective: fp16 (experimental; may be unstable)")
        elif precision == 'bf16':
            try:
                from tensorflow.keras import mixed_precision as mp
                mp.set_global_policy(mp.Policy('mixed_bfloat16'))
                current_policy = mp.global_policy()
                io.log_info("Precision effective: bf16 (experimental)")
                io.log_info(f"  Current mixed precision policy: {current_policy.name}")
                io.log_info(f"  Variable dtype: {current_policy.variable_dtype}")
                io.log_info(f"  Compute dtype: {current_policy.compute_dtype}")
                with tf.device('/CPU:0'):
                    self.loss_scale_var = tf.Variable(32768.0, dtype=tf.float32, name='loss_scale', trainable=False)
                    nn.tf_sess.run(self.loss_scale_var.initializer)
                io.log_info("  Loss Scaling: legacy static initial=32768 (still experimental)")
            except Exception as e:
                io.log_info(f"bf16 not available, falling back to fp32: {e}")
                precision = 'fp32'
                use_fp16 = False
                if PRECISION_CONTRACT_AVAILABLE:
                    try:
                        self.precision_contract = resolve_precision_contract(
                            requested_precision,
                            runtime_capabilities={
                                'tensorflow_available': True,
                                'float16_dtype_available': True,
                                'bfloat16_dtype_available': False,
                            },
                        )
                        self.precision_contract['fallback_reason'] = f"bf16_init_failed:{e}"
                        io.log_info(summarize_precision_contract(self.precision_contract))
                    except Exception:
                        pass
        else:
            precision = 'fp32'
            io.log_info("Precision effective: fp32 (validated baseline)")
            try:
                from tensorflow.keras import mixed_precision as mp
                current_policy = mp.global_policy()
                io.log_info(f"  Current mixed precision policy: {current_policy.name}")
                io.log_info(f"  Variable dtype: {current_policy.variable_dtype}")
                io.log_info(f"  Compute dtype: {current_policy.compute_dtype}")
            except Exception as e:
                pass

        self.options['precision'] = precision
        self.precision = precision

        # Loss Scale management state (for bf16 training stability)
        self._loss_scale_steps_since_last_adjustment = 0
        self._loss_scale_consecutive_normal_steps = 0
        self._LOSS_SCALE_RECOVERY_INTERVAL = 500  # steps before attempting to increase
        self._LOSS_SCALE_MAX = 65536  # maximum loss scale (2^16)

        if OPTIMIZATIONS_AVAILABLE and self.is_training:
            # Enhanced Mixed Precision via new manager
            try:
                mp_manager = MixedPrecisionManager()
                optimal_prec = mp_manager.get_optimal_precision_for_gpu()
                if optimal_prec != precision and precision == 'auto':
                    set_mixed_precision(optimal_prec)
                    io.log_info(f"✓ Auto-detected optimal precision: {optimal_prec}")
            except Exception as e:
                pass

        if self.is_exporting:
            use_fp16 = io.input_bool ("Export quantized?", False, help_message="Makes the exported model faster. If you have problems, disable this option.")

        self.gan_power = gan_power = 0.0 if self.pretrain else self.options['gan_power']
        random_warp = False if self.pretrain else self.options['random_warp']
        random_src_flip = self.random_src_flip if not self.pretrain else True
        random_dst_flip = self.random_dst_flip if not self.pretrain else True
        random_hsv_power = self.options['random_hsv_power'] if not self.pretrain else 0.0
        blur_out_mask = self.options['blur_out_mask']

        if self.pretrain:
            self.options_show_override['lr_dropout'] = 'n'
            self.options_show_override['random_warp'] = False
            self.options_show_override['gan_power'] = 0.0
            self.options_show_override['random_hsv_power'] = 0.0
            self.options_show_override['face_style_power'] = 0.0
            self.options_show_override['bg_style_power'] = 0.0
            self.options_show_override['uniform_yaw'] = True

        masked_training = self.options['masked_training']
        ct_mode = self.options['ct_mode']
        if ct_mode == 'none':
            ct_mode = None


        models_opt_on_gpu = False if len(devices) == 0 else self.options['models_opt_on_gpu']
        models_opt_device = nn.tf_default_device_name if models_opt_on_gpu and self.is_training else '/CPU:0'
        _opt_states_on_gpu = self.options.get('opt_states_on_gpu', None)
        if _opt_states_on_gpu is None:
            optimizer_vars_on_cpu = models_opt_device == '/CPU:0'
        else:
            optimizer_vars_on_cpu = not _opt_states_on_gpu

        input_ch=3
        bgr_shape = self.bgr_shape = nn.get4Dshape(resolution,resolution,input_ch)
        mask_shape = nn.get4Dshape(resolution,resolution,1)
        self.model_filename_list = []

        with tf.device ('/CPU:0'):
            #Place holders on CPU
            self.warped_src = tf.placeholder (nn.floatx, bgr_shape, name='warped_src')
            self.warped_dst = tf.placeholder (nn.floatx, bgr_shape, name='warped_dst')

            self.target_src = tf.placeholder (nn.floatx, bgr_shape, name='target_src')
            self.target_dst = tf.placeholder (nn.floatx, bgr_shape, name='target_dst')

            self.target_srcm    = tf.placeholder (nn.floatx, mask_shape, name='target_srcm')
            self.target_srcm_em = tf.placeholder (nn.floatx, mask_shape, name='target_srcm_em')
            self.target_dstm    = tf.placeholder (nn.floatx, mask_shape, name='target_dstm')
            self.target_dstm_em = tf.placeholder (nn.floatx, mask_shape, name='target_dstm_em')

        # Initializing model classes
        model_archi = nn.DeepFakeArchi(resolution, use_fp16=use_fp16, use_bf16=(precision == 'bf16'), opts=archi_opts)

        with tf.device (models_opt_device):
            if 'df' in archi_type:
                self.encoder = model_archi.Encoder(in_ch=input_ch, e_ch=e_dims, name='encoder')
                encoder_out_ch = self.encoder.get_out_ch()*self.encoder.get_out_res(resolution)**2

                self.inter = model_archi.Inter (in_ch=encoder_out_ch, ae_ch=ae_dims, ae_out_ch=ae_dims, name='inter')
                inter_out_ch = self.inter.get_out_ch()

                self.decoder_src = model_archi.Decoder(in_ch=inter_out_ch, d_ch=d_dims, d_mask_ch=d_mask_dims, name='decoder_src')
                self.decoder_dst = model_archi.Decoder(in_ch=inter_out_ch, d_ch=d_dims, d_mask_ch=d_mask_dims, name='decoder_dst')

                self.model_filename_list += [ [self.encoder,     'encoder.npy'    ],
                                              [self.inter,       'inter.npy'      ],
                                              [self.decoder_src, 'decoder_src.npy'],
                                              [self.decoder_dst, 'decoder_dst.npy']  ]

                if self.is_training:
                    if self.options['true_face_power'] != 0:
                        # 为CodeDiscriminator设置正确的dtype
                        discriminator_dtype = tf.bfloat16 if precision == 'bf16' else (tf.float16 if use_fp16 else tf.float32)
                        self.code_discriminator = nn.CodeDiscriminator(ae_dims, code_res=self.inter.get_out_res(), name='dis', dtype=discriminator_dtype )
                        self.model_filename_list += [ [self.code_discriminator, 'code_discriminator.npy'] ]

            elif 'liae' in archi_type:
                self.encoder = model_archi.Encoder(in_ch=input_ch, e_ch=e_dims, name='encoder')
                encoder_out_ch = self.encoder.get_out_ch()*self.encoder.get_out_res(resolution)**2

                self.inter_AB = model_archi.Inter(in_ch=encoder_out_ch, ae_ch=ae_dims, ae_out_ch=ae_dims*2, name='inter_AB')
                self.inter_B  = model_archi.Inter(in_ch=encoder_out_ch, ae_ch=ae_dims, ae_out_ch=ae_dims*2, name='inter_B')

                inter_out_ch = self.inter_AB.get_out_ch()
                inters_out_ch = inter_out_ch*2
                self.decoder = model_archi.Decoder(in_ch=inters_out_ch, d_ch=d_dims, d_mask_ch=d_mask_dims, name='decoder')

                self.model_filename_list += [ [self.encoder,  'encoder.npy'],
                                              [self.inter_AB, 'inter_AB.npy'],
                                              [self.inter_B , 'inter_B.npy'],
                                              [self.decoder , 'decoder.npy'] ]

            if self.is_training:
                if gan_power != 0:
                    # 为UNetPatchDiscriminator设置正确的精度
                    self.D_src = nn.UNetPatchDiscriminator(patch_size=self.options['gan_patch_size'], in_ch=input_ch, base_ch=self.options['gan_dims'], name="D_src", use_fp16=use_fp16, use_bf16=(precision == 'bf16'))
                    self.model_filename_list += [ [self.D_src, 'GAN.npy'] ]

                # Initialize optimizers
                lr=5e-5
                if self.options['lr_dropout'] in ['y','cpu'] and not self.pretrain:
                    lr_cos = 500
                    lr_dropout = 0.3
                else:
                    lr_cos = 0
                    lr_dropout = 1.0
                OptimizerClass = {
                    'adabelief': nn.AdaBelief,
                    'lion': nn.Lion,
                    'rmsprop': nn.RMSprop,
                }.get(optimizer_name, nn.AdaBelief)
                clipnorm = 1.0 if self.options['clipgrad'] else 0.0

                if 'df' in archi_type:
                    self.src_dst_saveable_weights = self.encoder.get_weights() + self.inter.get_weights() + self.decoder_src.get_weights() + self.decoder_dst.get_weights()
                    self.src_dst_trainable_weights = self.src_dst_saveable_weights
                elif 'liae' in archi_type:
                    self.src_dst_saveable_weights = self.encoder.get_weights() + self.inter_AB.get_weights() + self.inter_B.get_weights() + self.decoder.get_weights()
                    if random_warp:
                        self.src_dst_trainable_weights = self.src_dst_saveable_weights
                    else:
                        self.src_dst_trainable_weights = self.encoder.get_weights() + self.inter_B.get_weights() + self.decoder.get_weights()

                self.src_dst_opt = OptimizerClass(lr=lr, lr_dropout=lr_dropout, lr_cos=lr_cos, clipnorm=clipnorm, name='src_dst_opt')
                self.src_dst_opt.initialize_variables (self.src_dst_saveable_weights, vars_on_cpu=optimizer_vars_on_cpu, lr_dropout_on_cpu=self.options['lr_dropout']=='cpu')
                self.model_filename_list += [ (self.src_dst_opt, 'src_dst_opt.npy') ]

                if self.options['true_face_power'] != 0:
                    self.D_code_opt = OptimizerClass(lr=lr, lr_dropout=lr_dropout, lr_cos=lr_cos, clipnorm=clipnorm, name='D_code_opt')
                    self.D_code_opt.initialize_variables ( self.code_discriminator.get_weights(), vars_on_cpu=optimizer_vars_on_cpu, lr_dropout_on_cpu=self.options['lr_dropout']=='cpu')
                    self.model_filename_list += [ (self.D_code_opt, 'D_code_opt.npy') ]

                if gan_power != 0:
                    self.D_src_dst_opt = OptimizerClass(lr=lr, lr_dropout=lr_dropout, lr_cos=lr_cos, clipnorm=clipnorm, name='GAN_opt')
                    self.D_src_dst_opt.initialize_variables ( self.D_src.get_weights(), vars_on_cpu=optimizer_vars_on_cpu, lr_dropout_on_cpu=self.options['lr_dropout']=='cpu')#+self.D_src_x2.get_weights()
                    self.model_filename_list += [ (self.D_src_dst_opt, 'GAN_opt.npy') ]

        if self.is_training:
            # Adjust batch size for multiple GPU
            gpu_count = max(1, len(devices) )
            bs_per_gpu = max(1, self.get_batch_size() // gpu_count)
            self.set_batch_size( gpu_count*bs_per_gpu)

            # Compute losses per GPU
            gpu_pred_src_src_list = []
            gpu_pred_dst_dst_list = []
            gpu_pred_src_dst_list = []
            gpu_pred_src_srcm_list = []
            gpu_pred_dst_dstm_list = []
            gpu_pred_src_dstm_list = []

            gpu_src_losses = []
            gpu_dst_losses = []
            gpu_G_loss_gvs = []
            gpu_D_code_loss_gvs = []
            gpu_D_src_dst_loss_gvs = []

            # 辅助函数：在 bf16 模式下确保损失类型匹配
            def cast_loss_to_target(loss_tensor, target_dtype):
                if precision == 'bf16':
                    return tf.cast(loss_tensor, target_dtype)
                return loss_tensor

            for gpu_id in range(gpu_count):
                with tf.device( f'/{devices[gpu_id].tf_dev_type}:{gpu_id}' if len(devices) != 0 else f'/CPU:0' ):
                    with tf.device(f'/CPU:0'):
                        # slice on CPU, otherwise all batch data will be transfered to GPU first
                        batch_slice = slice( gpu_id*bs_per_gpu, (gpu_id+1)*bs_per_gpu )
                        gpu_warped_src      = self.warped_src [batch_slice,:,:,:]
                        gpu_warped_dst      = self.warped_dst [batch_slice,:,:,:]
                        gpu_target_src      = self.target_src [batch_slice,:,:,:]
                        gpu_target_dst      = self.target_dst [batch_slice,:,:,:]
                        gpu_target_srcm     = self.target_srcm[batch_slice,:,:,:]
                        gpu_target_srcm_em  = self.target_srcm_em[batch_slice,:,:,:]
                        gpu_target_dstm     = self.target_dstm[batch_slice,:,:,:]
                        gpu_target_dstm_em  = self.target_dstm_em[batch_slice,:,:,:]

                    gpu_target_srcm_anti = 1-gpu_target_srcm
                    gpu_target_dstm_anti = 1-gpu_target_dstm

                    if blur_out_mask:
                        sigma = resolution / 128

                        x = nn.gaussian_blur(gpu_target_src*gpu_target_srcm_anti, sigma)
                        y = 1-nn.gaussian_blur(gpu_target_srcm, sigma)
                        y = tf.where(tf.equal(y, 0), tf.ones_like(y), y)
                        gpu_target_src = gpu_target_src*gpu_target_srcm + (x/y)*gpu_target_srcm_anti

                        x = nn.gaussian_blur(gpu_target_dst*gpu_target_dstm_anti, sigma)
                        y = 1-nn.gaussian_blur(gpu_target_dstm, sigma)
                        y = tf.where(tf.equal(y, 0), tf.ones_like(y), y)
                        gpu_target_dst = gpu_target_dst*gpu_target_dstm + (x/y)*gpu_target_dstm_anti


                    # process model tensors
                    if 'df' in archi_type:
                        gpu_encoder_out = self.encoder(gpu_warped_src)
                        gpu_src_code = self.inter(gpu_encoder_out)
                        gpu_pred_src_src, gpu_pred_src_srcm = self.decoder_src(gpu_src_code)

                        gpu_dst_code     = self.inter(self.encoder(gpu_warped_dst))
                        gpu_pred_dst_dst, gpu_pred_dst_dstm = self.decoder_dst(gpu_dst_code)
                        gpu_pred_src_dst, gpu_pred_src_dstm = self.decoder_src(gpu_dst_code)
                        gpu_pred_src_dst_no_code_grad = tf.stop_gradient(gpu_pred_src_dst)

                    elif 'liae' in archi_type:
                        gpu_src_code = self.encoder (gpu_warped_src)

                        gpu_src_inter_AB_code = self.inter_AB (gpu_src_code)

                        gpu_src_code = tf.concat([gpu_src_inter_AB_code,gpu_src_inter_AB_code], nn.conv2d_ch_axis  )

                        gpu_dst_code = self.encoder (gpu_warped_dst)
                        gpu_dst_inter_B_code = self.inter_B (gpu_dst_code)
                        gpu_dst_inter_AB_code = self.inter_AB (gpu_dst_code)
                        gpu_dst_code = tf.concat([gpu_dst_inter_B_code,gpu_dst_inter_AB_code], nn.conv2d_ch_axis  )
                        gpu_src_dst_code = tf.concat([gpu_dst_inter_AB_code,gpu_dst_inter_AB_code], nn.conv2d_ch_axis  )

                        gpu_pred_src_src, gpu_pred_src_srcm = self.decoder(gpu_src_code)

                        gpu_pred_dst_dst, gpu_pred_dst_dstm = self.decoder(gpu_dst_code)
                        gpu_pred_src_dst, gpu_pred_src_dstm = self.decoder(gpu_src_dst_code)
                        gpu_pred_src_dst_no_code_grad = tf.stop_gradient(gpu_pred_src_dst)

                    gpu_pred_src_src_list.append(gpu_pred_src_src)
                    gpu_pred_dst_dst_list.append(gpu_pred_dst_dst)
                    gpu_pred_src_dst_list.append(gpu_pred_src_dst)

                    gpu_pred_src_srcm_list.append(gpu_pred_src_srcm)
                    gpu_pred_dst_dstm_list.append(gpu_pred_dst_dstm)
                    gpu_pred_src_dstm_list.append(gpu_pred_src_dstm)

                    # 确保目标张量类型与模型输出匹配（bf16 模式下统一转换）
                    if precision == 'bf16':
                        gpu_target_src = tf.cast(gpu_target_src, tf.bfloat16)
                        gpu_target_srcm = tf.cast(gpu_target_srcm, tf.bfloat16)
                        gpu_target_dst = tf.cast(gpu_target_dst, tf.bfloat16)
                        gpu_target_dstm = tf.cast(gpu_target_dstm, tf.bfloat16)
                        if self._has_eyes_mouth:
                            gpu_target_srcm_em = tf.cast(gpu_target_srcm_em, tf.bfloat16)
                            gpu_target_dstm_em = tf.cast(gpu_target_dstm_em, tf.bfloat16)

                    # 计算 mask blur（在 bf16 模式下输入已为正确类型）
                    gpu_target_srcm_blur = nn.gaussian_blur(gpu_target_srcm,  max(1, resolution // 32) )
                    gpu_target_srcm_blur = tf.clip_by_value(gpu_target_srcm_blur, 0, 0.5) * 2
                    gpu_target_srcm_anti_blur = 1.0-gpu_target_srcm_blur

                    gpu_target_dstm_blur = nn.gaussian_blur(gpu_target_dstm,  max(1, resolution // 32) )
                    gpu_target_dstm_blur = tf.clip_by_value(gpu_target_dstm_blur, 0, 0.5) * 2

                    gpu_style_mask_blur = nn.gaussian_blur(gpu_pred_src_dstm*gpu_pred_dst_dstm,  max(1, resolution // 32) )
                    gpu_style_mask_blur = tf.stop_gradient(tf.clip_by_value(gpu_style_mask_blur, 0.0, 1.0))
                    gpu_style_mask_anti_blur = 1.0 - gpu_style_mask_blur

                    # 统一处理 blur 结果的类型（避免重复 cast）
                    if precision == 'bf16':
                        gpu_target_srcm_blur = tf.cast(gpu_target_srcm_blur, tf.bfloat16)
                        gpu_target_srcm_anti_blur = tf.cast(gpu_target_srcm_anti_blur, tf.bfloat16)
                        gpu_target_dstm_blur = tf.cast(gpu_target_dstm_blur, tf.bfloat16)
                        gpu_style_mask_blur = tf.cast(gpu_style_mask_blur, tf.bfloat16)
                        gpu_style_mask_anti_blur = tf.cast(gpu_style_mask_anti_blur, tf.bfloat16)

                    gpu_target_dst_masked = gpu_target_dst*gpu_target_dstm_blur

                    gpu_target_src_anti_masked = gpu_target_src*gpu_target_srcm_anti_blur
                    gpu_pred_src_src_anti_masked = gpu_pred_src_src*gpu_target_srcm_anti_blur

                    # 确保类型匹配
                    gpu_target_src_masked_opt  = gpu_target_src*gpu_target_srcm_blur if masked_training else gpu_target_src
                    gpu_target_dst_masked_opt  = gpu_target_dst_masked if masked_training else gpu_target_dst
                    gpu_pred_src_src_masked_opt = gpu_pred_src_src*gpu_target_srcm_blur if masked_training else gpu_pred_src_src
                    gpu_pred_dst_dst_masked_opt = gpu_pred_dst_dst*gpu_target_dstm_blur if masked_training else gpu_pred_dst_dst

                    if resolution < 256:
                        gpu_src_loss =  tf.reduce_mean ( 10*nn.dssim(gpu_target_src_masked_opt, gpu_pred_src_src_masked_opt, max_val=1.0, filter_size=int(resolution/11.6)), axis=[1])
                    else:
                        gpu_src_loss =  tf.reduce_mean ( 5*nn.dssim(gpu_target_src_masked_opt, gpu_pred_src_src_masked_opt, max_val=1.0, filter_size=int(resolution/11.6)), axis=[1])
                        gpu_src_loss += tf.reduce_mean ( 5*nn.dssim(gpu_target_src_masked_opt, gpu_pred_src_src_masked_opt, max_val=1.0, filter_size=int(resolution/23.2)), axis=[1])
                    
                    # 确保类型匹配
                    square_loss = tf.reduce_mean ( 10*tf.square ( gpu_target_src_masked_opt - gpu_pred_src_src_masked_opt ), axis=[1,2,3])
                    gpu_src_loss += cast_loss_to_target(square_loss, gpu_src_loss.dtype)

                    if eyes_mouth_prio and self._has_eyes_mouth:
                        # 确保类型匹配
                        eyes_mouth_loss = tf.reduce_mean ( 300*tf.abs ( gpu_target_src*gpu_target_srcm_em - gpu_pred_src_src*gpu_target_srcm_em ), axis=[1,2,3])
                        gpu_src_loss += cast_loss_to_target(eyes_mouth_loss, gpu_src_loss.dtype)

                    # 确保类型匹配
                    mask_loss = tf.reduce_mean ( 10*tf.square( gpu_target_srcm - gpu_pred_src_srcm ),axis=[1,2,3] )
                    gpu_src_loss += cast_loss_to_target(mask_loss, gpu_src_loss.dtype)

                    face_style_power = self.options['face_style_power'] / 100.0
                    if face_style_power != 0 and not self.pretrain:
                        # 确保类型匹配
                        style_loss = nn.style_loss(gpu_pred_src_dst_no_code_grad*tf.stop_gradient(gpu_pred_src_dstm), tf.stop_gradient(gpu_pred_dst_dst*gpu_pred_dst_dstm), gaussian_blur_radius=resolution//8, loss_weight=10000*face_style_power)
                        gpu_src_loss += cast_loss_to_target(style_loss, gpu_src_loss.dtype)

                    bg_style_power = self.options['bg_style_power'] / 100.0
                    if bg_style_power != 0 and not self.pretrain:
                        gpu_target_dst_style_anti_masked = gpu_target_dst*gpu_style_mask_anti_blur
                        gpu_psd_style_anti_masked = gpu_pred_src_dst*gpu_style_mask_anti_blur

                        # 确保类型匹配
                        bg_dssim_loss = tf.reduce_mean( (10*bg_style_power)*nn.dssim( gpu_psd_style_anti_masked,  gpu_target_dst_style_anti_masked, max_val=1.0, filter_size=int(resolution/11.6)), axis=[1])
                        gpu_src_loss += cast_loss_to_target(bg_dssim_loss, gpu_src_loss.dtype)

                        bg_square_loss = tf.reduce_mean( (10*bg_style_power)*tf.square(gpu_psd_style_anti_masked - gpu_target_dst_style_anti_masked), axis=[1,2,3] )
                        gpu_src_loss += cast_loss_to_target(bg_square_loss, gpu_src_loss.dtype)

                    if resolution < 256:
                        gpu_dst_loss =  tf.reduce_mean ( 10*nn.dssim(gpu_target_dst_masked_opt, gpu_pred_dst_dst_masked_opt, max_val=1.0, filter_size=int(resolution/11.6)), axis=[1])
                    else:
                        gpu_dst_loss =  tf.reduce_mean ( 5*nn.dssim(gpu_target_dst_masked_opt, gpu_pred_dst_dst_masked_opt, max_val=1.0, filter_size=int(resolution/11.6)), axis=[1])
                        gpu_dst_loss += tf.reduce_mean ( 5*nn.dssim(gpu_target_dst_masked_opt, gpu_pred_dst_dst_masked_opt, max_val=1.0, filter_size=int(resolution/23.2)), axis=[1])
                    
                    # 确保类型匹配
                    square_loss = tf.reduce_mean ( 10*tf.square ( gpu_target_dst_masked_opt - gpu_pred_dst_dst_masked_opt ), axis=[1,2,3])
                    gpu_dst_loss += cast_loss_to_target(square_loss, gpu_dst_loss.dtype)

                    if eyes_mouth_prio and self._has_eyes_mouth:
                        # 确保类型匹配
                        eyes_mouth_dst_loss = tf.reduce_mean ( 300*tf.abs ( gpu_target_dst*gpu_target_dstm_em - gpu_pred_dst_dst*gpu_target_dstm_em ), axis=[1,2,3])
                        gpu_dst_loss += cast_loss_to_target(eyes_mouth_dst_loss, gpu_dst_loss.dtype)

                    # 确保类型匹配
                    mask_loss = tf.reduce_mean ( 10*tf.square( gpu_target_dstm - gpu_pred_dst_dstm ),axis=[1,2,3] )
                    gpu_dst_loss += cast_loss_to_target(mask_loss, gpu_dst_loss.dtype)

                    gpu_src_losses += [gpu_src_loss]
                    gpu_dst_losses += [gpu_dst_loss]

                    # 确保类型匹配
                    gpu_G_loss = tf.cast(gpu_src_loss, tf.float32) + tf.cast(gpu_dst_loss, tf.float32)
                    if self.loss_scale_var is not None:
                        gpu_G_loss = gpu_G_loss * tf.cast(self.loss_scale_var, gpu_G_loss.dtype)

                    def DLoss(labels,logits):
                        return tf.reduce_mean( tf.nn.sigmoid_cross_entropy_with_logits(labels=labels, logits=logits), axis=[1,2,3])

                    if self.options['true_face_power'] != 0:
                        gpu_src_code_d = self.code_discriminator( gpu_src_code )
                        gpu_src_code_d_ones  = tf.ones_like (gpu_src_code_d)
                        gpu_src_code_d_zeros = tf.zeros_like(gpu_src_code_d)
                        gpu_dst_code_d = self.code_discriminator( gpu_dst_code )
                        gpu_dst_code_d_ones = tf.ones_like(gpu_dst_code_d)

                        # 确保类型匹配
                        dloss_result = self.options['true_face_power']*DLoss(gpu_src_code_d_ones, gpu_src_code_d)
                        gpu_G_loss += tf.cast(dloss_result, gpu_G_loss.dtype)

                        gpu_D_code_loss = (DLoss(gpu_dst_code_d_ones , gpu_dst_code_d) + \
                                           DLoss(gpu_src_code_d_zeros, gpu_src_code_d) ) * 0.5

                        if self.loss_scale_var is not None:
                            gpu_D_code_loss = gpu_D_code_loss * tf.cast(self.loss_scale_var, gpu_D_code_loss.dtype)

                        gpu_D_code_loss_gvs += [ nn.gradients (gpu_D_code_loss, self.code_discriminator.get_weights() ) ]

                    if gan_power != 0:
                        gpu_pred_src_src_d, \
                        gpu_pred_src_src_d2           = self.D_src(gpu_pred_src_src_masked_opt)

                        gpu_pred_src_src_d_ones  = tf.ones_like (gpu_pred_src_src_d)
                        gpu_pred_src_src_d_zeros = tf.zeros_like(gpu_pred_src_src_d)

                        gpu_pred_src_src_d2_ones  = tf.ones_like (gpu_pred_src_src_d2)
                        gpu_pred_src_src_d2_zeros = tf.zeros_like(gpu_pred_src_src_d2)

                        gpu_target_src_d, \
                        gpu_target_src_d2            = self.D_src(gpu_target_src_masked_opt)

                        gpu_target_src_d_ones    = tf.ones_like(gpu_target_src_d)
                        gpu_target_src_d2_ones    = tf.ones_like(gpu_target_src_d2)

                        gpu_D_src_dst_loss = (DLoss(gpu_target_src_d_ones      , gpu_target_src_d) + \
                                              DLoss(gpu_pred_src_src_d_zeros   , gpu_pred_src_src_d) ) * 0.5 + \
                                             (DLoss(gpu_target_src_d2_ones      , gpu_target_src_d2) + \
                                              DLoss(gpu_pred_src_src_d2_zeros   , gpu_pred_src_src_d2) ) * 0.5

                        if self.loss_scale_var is not None:
                            gpu_D_src_dst_loss = gpu_D_src_dst_loss * tf.cast(self.loss_scale_var, gpu_D_src_dst_loss.dtype)

                        gpu_D_src_dst_loss_gvs += [ nn.gradients (gpu_D_src_dst_loss, self.D_src.get_weights() ) ]#+self.D_src_x2.get_weights()

                        # 确保类型匹配
                        gan_loss = gan_power*(DLoss(gpu_pred_src_src_d_ones, gpu_pred_src_src_d)  + \
                                            DLoss(gpu_pred_src_src_d2_ones, gpu_pred_src_src_d2))
                        gpu_G_loss += tf.cast(gan_loss, gpu_G_loss.dtype)

                        if masked_training:
                            # Minimal src-src-bg rec with total_variation_mse to suppress random bright dots from gan
                            # 确保类型匹配
                            tv_loss = 0.000001*nn.total_variation_mse(gpu_pred_src_src)
                            gpu_G_loss += cast_loss_to_target(tv_loss, gpu_G_loss.dtype)
                            # 确保类型匹配
                            bg_rec_loss = 0.02*tf.reduce_mean(tf.square(gpu_pred_src_src_anti_masked-gpu_target_src_anti_masked),axis=[1,2,3] )
                            gpu_G_loss += cast_loss_to_target(bg_rec_loss, gpu_G_loss.dtype)

                    gpu_G_loss_gvs += [ nn.gradients ( gpu_G_loss, self.src_dst_trainable_weights )]




            # Average losses and gradients, and create optimizer update ops
            with tf.device(f'/CPU:0'):
                pred_src_src  = nn.concat(gpu_pred_src_src_list, 0)
                pred_dst_dst  = nn.concat(gpu_pred_dst_dst_list, 0)
                pred_src_dst  = nn.concat(gpu_pred_src_dst_list, 0)
                pred_src_srcm = nn.concat(gpu_pred_src_srcm_list, 0)
                pred_dst_dstm = nn.concat(gpu_pred_dst_dstm_list, 0)
                pred_src_dstm = nn.concat(gpu_pred_src_dstm_list, 0)

            with tf.device (models_opt_device):
                src_loss = tf.concat(gpu_src_losses, 0)
                dst_loss = tf.concat(gpu_dst_losses, 0)

                def _prepare_gv_for_finite_gate(gv_list):
                    if self.loss_scale_var is None:
                        unscaled_gv = gv_list
                    else:
                        unscaled_gv = [
                            (g / tf.cast(self.loss_scale_var, g.dtype), v)
                            for g, v in gv_list
                        ]
                    is_finite = getattr(tf, 'is_finite', None)
                    if is_finite is None:
                        is_finite = tf.math.is_finite
                    finite_checks = [
                        tf.reduce_all(is_finite(g))
                        for g, v in unscaled_gv
                    ]
                    return unscaled_gv, tf.reduce_all(tf.stack(finite_checks))

                def _get_gated_update_op(optimizer, gv_list, all_gradients_finite):
                    # 先在图里判断所有 unscaled gradients，避免坏 step 先污染参数再被 Python 端发现。
                    def _apply_update():
                        update_op = optimizer.get_update_op(gv_list)
                        with tf.control_dependencies([update_op]):
                            return tf.constant(True, dtype=tf.bool, name=optimizer.name + '_step_applied')

                    def _skip_update():
                        return tf.constant(False, dtype=tf.bool, name=optimizer.name + '_skip_nonfinite_gradients')

                    return tf.cond(all_gradients_finite, _apply_update, _skip_update)

                src_dst_gv, src_dst_gradients_finite = _prepare_gv_for_finite_gate(
                    nn.average_gv_list(gpu_G_loss_gvs)
                )
                finite_flags = [src_dst_gradients_finite]
                optimizer_update_specs = [(self.src_dst_opt, src_dst_gv)]

                if self.options['true_face_power'] != 0:
                    D_code_gv, D_code_gradients_finite = _prepare_gv_for_finite_gate(
                        nn.average_gv_list(gpu_D_code_loss_gvs)
                    )
                    finite_flags.append(D_code_gradients_finite)
                    optimizer_update_specs.append((self.D_code_opt, D_code_gv))

                if gan_power != 0:
                    D_src_dst_gv, D_src_dst_gradients_finite = _prepare_gv_for_finite_gate(
                        nn.average_gv_list(gpu_D_src_dst_loss_gvs)
                    )
                    finite_flags.append(D_src_dst_gradients_finite)
                    optimizer_update_specs.append((self.D_src_dst_opt, D_src_dst_gv))

                all_gradients_finite = tf.reduce_all(tf.stack(finite_flags))
                optimizer_update_ops = [
                    _get_gated_update_op(optimizer, gv_list, all_gradients_finite)
                    for optimizer, gv_list in optimizer_update_specs
                ]
                step_applied = tf.reduce_all(tf.stack(optimizer_update_ops))

            # Unified training function (only one used)
            _unified_ops = [src_loss, dst_loss, all_gradients_finite, step_applied]

            def unified_train(warped_src, target_src, target_srcm,
                               warped_dst, target_dst, target_dstm,
                               target_srcm_em=None, target_dstm_em=None):
                fd = {self.warped_src: warped_src, self.target_src: target_src,
                     self.target_srcm: target_srcm,
                     self.warped_dst: warped_dst, self.target_dst: target_dst,
                     self.target_dstm: target_dstm}
                _add_eyes_mouth_masks_to_feed(
                    fd,
                    self.target_srcm_em, self.target_dstm_em,
                    target_srcm, target_dstm,
                    target_srcm_em, target_dstm_em,
                    self._has_eyes_mouth,
                )
                results = nn.tf_sess.run(_unified_ops, feed_dict=fd)
                return results[0], results[1], results[2], results[3]
            self.unified_train = unified_train


            def AE_view(warped_src, warped_dst):
                return nn.tf_sess.run ( [pred_src_src, pred_dst_dst, pred_dst_dstm, pred_src_dst, pred_src_dstm],
                                            feed_dict={self.warped_src:warped_src,
                                                    self.warped_dst:warped_dst})
            self.AE_view = AE_view
        else:
            # Initializing merge function
            with tf.device( nn.tf_default_device_name if len(devices) != 0 else f'/CPU:0'):
                if 'df' in archi_type:
                    gpu_dst_code     = self.inter(self.encoder(self.warped_dst))
                    gpu_pred_src_dst, gpu_pred_src_dstm = self.decoder_src(gpu_dst_code)
                    _, gpu_pred_dst_dstm = self.decoder_dst(gpu_dst_code)

                elif 'liae' in archi_type:
                    gpu_dst_code = self.encoder (self.warped_dst)
                    gpu_dst_inter_B_code = self.inter_B (gpu_dst_code)
                    gpu_dst_inter_AB_code = self.inter_AB (gpu_dst_code)
                    gpu_dst_code = tf.concat([gpu_dst_inter_B_code,gpu_dst_inter_AB_code], nn.conv2d_ch_axis)
                    gpu_src_dst_code = tf.concat([gpu_dst_inter_AB_code,gpu_dst_inter_AB_code], nn.conv2d_ch_axis)

                    gpu_pred_src_dst, gpu_pred_src_dstm = self.decoder(gpu_src_dst_code)
                    _, gpu_pred_dst_dstm = self.decoder(gpu_dst_code)


            def AE_merge( warped_dst):
                return nn.tf_sess.run ( [gpu_pred_src_dst, gpu_pred_dst_dstm, gpu_pred_src_dstm], feed_dict={self.warped_dst:warped_dst})

            self.AE_merge = AE_merge

        # Loading/initializing all models/optimizers weights
        for model, filename in io.progress_bar_generator(self.model_filename_list, "Initializing models"):
            if self.pretrain_just_disabled:
                do_init = False
                if 'df' in archi_type:
                    if model == self.inter:
                        do_init = True
                elif 'liae' in archi_type:
                    if model == self.inter_AB or model == self.inter_B:
                        do_init = True
            else:
                do_init = self.is_first_run()
                if self.is_training and gan_power != 0 and model == self.D_src:
                    if self.gan_model_changed:
                        do_init = True

            if not do_init:
                do_init = not model.load_weights( self.get_strpath_storage_for_file(filename) )

            if do_init:
                model.init_weights()


        ###############

        # initializing sample generators
        if self.is_training:
            training_data_src_path = self.training_data_src_path if not self.pretrain else self.get_pretraining_data_path()
            training_data_dst_path = self.training_data_dst_path if not self.pretrain else self.get_pretraining_data_path()

            random_ct_samples_path=training_data_dst_path if ct_mode is not None and not self.pretrain else None

            cpu_count = multiprocessing.cpu_count()
            if resolution >= 192:
                src_generators_count = max(4, cpu_count * 3 // 4)
                dst_generators_count = max(4, cpu_count * 3 // 4)
            else:
                src_generators_count = cpu_count // 2
                dst_generators_count = cpu_count // 2
            if ct_mode is not None:
                src_generators_count = int(src_generators_count * 1.5)

            _base_src_types = [
                                {'sample_type': SampleProcessor.SampleType.FACE_IMAGE,'warp':random_warp, 'transform':True, 'channel_type' : SampleProcessor.ChannelType.BGR, 'ct_mode': ct_mode,   'random_hsv_shift_amount' : random_hsv_power,                                        'face_type':self.face_type, 'data_format':nn.data_format, 'resolution': resolution},
                                {'sample_type': SampleProcessor.SampleType.FACE_IMAGE,'warp':False                      , 'transform':True, 'channel_type' : SampleProcessor.ChannelType.BGR, 'ct_mode': ct_mode,                           'face_type':self.face_type, 'data_format':nn.data_format, 'resolution': resolution},
                                {'sample_type': SampleProcessor.SampleType.FACE_MASK, 'warp':False                      , 'transform':True, 'channel_type' : SampleProcessor.ChannelType.G,   'face_mask_type' : SampleProcessor.FaceMaskType.FULL_FACE, 'face_type':self.face_type, 'data_format':nn.data_format, 'resolution': resolution},
                              ]
            if self._has_eyes_mouth:
                _base_src_types.append( {'sample_type': SampleProcessor.SampleType.FACE_MASK, 'warp':False                      , 'transform':True, 'channel_type' : SampleProcessor.ChannelType.G,   'face_mask_type' : SampleProcessor.FaceMaskType.EYES_MOUTH, 'face_type':self.face_type, 'data_format':nn.data_format, 'resolution': resolution})

            _base_dst_types = [
                                {'sample_type': SampleProcessor.SampleType.FACE_IMAGE,'warp':random_warp, 'transform':True, 'channel_type' : SampleProcessor.ChannelType.BGR,                                                                'face_type':self.face_type, 'data_format':nn.data_format, 'resolution': resolution},
                                {'sample_type': SampleProcessor.SampleType.FACE_IMAGE,'warp':False                      , 'transform':True, 'channel_type' : SampleProcessor.ChannelType.BGR,                                                'face_type':self.face_type, 'data_format':nn.data_format, 'resolution': resolution},
                                {'sample_type': SampleProcessor.SampleType.FACE_MASK, 'warp':False                      , 'transform':True, 'channel_type' : SampleProcessor.ChannelType.G,   'face_mask_type' : SampleProcessor.FaceMaskType.FULL_FACE, 'face_type':self.face_type, 'data_format':nn.data_format, 'resolution': resolution},
                              ]
            if self._has_eyes_mouth:
                _base_dst_types.append( {'sample_type': SampleProcessor.SampleType.FACE_MASK, 'warp':False                      , 'transform':True, 'channel_type' : SampleProcessor.ChannelType.G,   'face_mask_type' : SampleProcessor.FaceMaskType.EYES_MOUTH, 'face_type':self.face_type, 'data_format':nn.data_format, 'resolution': resolution})

            if not self._has_eyes_mouth:
                io.log_info('EYES_MOUTH mask output disabled (saves IPC bandwidth)')

            from samplelib.sampling.runtime import build_sampling_runtime

            enh_cfg = (
                self.enhancements
                if ENHANCEMENTS_AVAILABLE and self.enhancements is not None
                else normalize_enhancement_config(None)
            )
            # One authority: resolve side configs here and pass explicitly so SRC/DST
            # never silently share a single flat SamplingConfig by accident.
            # Also pass sampling_config_source so startup logs keep base/side provenance (R1-02).
            src_sampling_cfg = enh_cfg.sampling_config_for("src")
            src_config_source = enh_cfg.sampling_config_source("src")
            dst_sampling_cfg = enh_cfg.sampling_config_for("dst")
            dst_config_source = enh_cfg.sampling_config_source("dst")
            model_seed = self.options.get("seed", 42)

            src_runtime = build_sampling_runtime(
                role="src",
                samples_path=training_data_src_path,
                enhancement_config=enh_cfg,
                sampling_config=src_sampling_cfg,
                sampling_config_source=src_config_source,
                legacy_uniform_yaw=self.options['uniform_yaw'] or self.pretrain,
                base_seed=model_seed,
            )

            dst_runtime = build_sampling_runtime(
                role="dst",
                samples_path=training_data_dst_path,
                enhancement_config=enh_cfg,
                sampling_config=dst_sampling_cfg,
                sampling_config_source=dst_config_source,
                legacy_uniform_yaw=self.options['uniform_yaw'] or self.pretrain,
                base_seed=model_seed,
            )

            self.src_sampling_runtime = src_runtime
            self.dst_sampling_runtime = dst_runtime

            self.set_training_data_generators ([
                    SampleGeneratorFace(training_data_src_path, random_ct_samples_path=random_ct_samples_path, debug=self.is_debug(), batch_size=self.get_batch_size(),
                        sample_process_options=SampleProcessor.Options(scale_range=[-0.15, 0.15], random_flip=random_src_flip),
                        output_sample_types = _base_src_types,
                        uniform_yaw_distribution=self.options['uniform_yaw'] or self.pretrain,
                        generators_count=src_generators_count,
                        sampling_policy=src_runtime.policy,
                        sampling_role="src" ),

                    SampleGeneratorFace(training_data_dst_path, debug=self.is_debug(), batch_size=self.get_batch_size(),
                        sample_process_options=SampleProcessor.Options(scale_range=[-0.15, 0.15], random_flip=random_dst_flip),
                        output_sample_types = _base_dst_types,
                        uniform_yaw_distribution=self.options['uniform_yaw'] or self.pretrain,
                        generators_count=dst_generators_count,
                        sampling_policy=dst_runtime.policy,
                        sampling_role="dst" )
                             ])

            if self.pretrain_just_disabled:
                self.update_sample_for_preview(force_new=True)

    def export_dfm (self):
        output_path=self.get_strpath_storage_for_file('model.dfm')

        io.log_info(f'Dumping .dfm to {output_path}')

        tf = nn.tf
        nn.set_data_format('NCHW')

        with tf.device (nn.tf_default_device_name):
            warped_dst = tf.placeholder (nn.floatx, (None, self.resolution, self.resolution, 3), name='in_face')
            warped_dst = tf.transpose(warped_dst, (0,3,1,2))


            if 'df' in self.archi_type:
                gpu_dst_code     = self.inter(self.encoder(warped_dst))
                gpu_pred_src_dst, gpu_pred_src_dstm = self.decoder_src(gpu_dst_code)
                _, gpu_pred_dst_dstm = self.decoder_dst(gpu_dst_code)

            elif 'liae' in self.archi_type:
                gpu_dst_code = self.encoder (warped_dst)
                gpu_dst_inter_B_code = self.inter_B (gpu_dst_code)
                gpu_dst_inter_AB_code = self.inter_AB (gpu_dst_code)
                gpu_dst_code = tf.concat([gpu_dst_inter_B_code,gpu_dst_inter_AB_code], nn.conv2d_ch_axis)
                gpu_src_dst_code = tf.concat([gpu_dst_inter_AB_code,gpu_dst_inter_AB_code], nn.conv2d_ch_axis)

                gpu_pred_src_dst, gpu_pred_src_dstm = self.decoder(gpu_src_dst_code)
                _, gpu_pred_dst_dstm = self.decoder(gpu_dst_code)

            gpu_pred_src_dst = tf.transpose(gpu_pred_src_dst, (0,2,3,1))
            gpu_pred_dst_dstm = tf.transpose(gpu_pred_dst_dstm, (0,2,3,1))
            gpu_pred_src_dstm = tf.transpose(gpu_pred_src_dstm, (0,2,3,1))

        tf.identity(gpu_pred_dst_dstm, name='out_face_mask')
        tf.identity(gpu_pred_src_dst, name='out_celeb_face')
        tf.identity(gpu_pred_src_dstm, name='out_celeb_face_mask')

        output_graph_def = tf.graph_util.convert_variables_to_constants(
            nn.tf_sess,
            tf.get_default_graph().as_graph_def(),
            ['out_face_mask','out_celeb_face','out_celeb_face_mask']
        )

        try:
            import tf2onnx
            with tf.device("/CPU:0"):
                model_proto, _ = tf2onnx.convert._convert_common(
                    output_graph_def,
                    name='SAEHD',
                    input_names=['in_face:0'],
                    output_names=['out_face_mask:0','out_celeb_face:0','out_celeb_face_mask:0'],
                    opset=12,
                    output_path=output_path)
        except ImportError as e:
            io.log_err(f"Failed to export DFM: {e}. Please ensure 'tf2onnx' and 'tensorflow' are installed in python environment.")
            return

    #override
    def get_model_filename_list(self):
        return self.model_filename_list

    #override
    def onSave(self):
        for model, filename in io.progress_bar_generator(self.get_model_filename_list(), "Saving", leave=False):
            model.save_weights ( self.get_strpath_storage_for_file(filename), force_dtype=np.float32 )

    #override
    def should_save_preview_history(self):
        return (not io.is_colab() and self.iter % ( 10*(max(1,self.resolution // 64)) ) == 0) or \
               (io.is_colab() and self.iter % 100 == 0)

    #override
    def onTrainOneIter(self):
        if self.get_iter() == 0 and not self.pretrain and not self.pretrain_just_disabled:
            io.log_info('You are training the model from scratch. It is strongly recommended to use a pretrained model to speed up the training and improve the quality.\n')

        # Start profiler if available
        iter_start_time = time.time()
        src_samples = None
        dst_samples = None

        try:
            src_samples, dst_samples = self.generate_next_samples()
            warped_src, target_src, target_srcm, target_srcm_em = _unpack_training_samples(
                src_samples, self._has_eyes_mouth, 'src'
            )
            warped_dst, target_dst, target_dstm, target_dstm_em = _unpack_training_samples(
                dst_samples, self._has_eyes_mouth, 'dst'
            )

            train_result = self.unified_train(warped_src, target_src, target_srcm,
                                              warped_dst, target_dst, target_dstm,
                                              target_srcm_em=target_srcm_em,
                                              target_dstm_em=target_dstm_em)
            src_loss, dst_loss, gradients_finite, step_applied = _unpack_unified_train_result(train_result)

            iter_time_ms = (time.time() - iter_start_time) * 1000

            _update_loss_scale_state(self, gradients_finite)
            if not step_applied:
                if self.loss_scale_var is None:
                    io.log_info("⚠️ Optimizer step skipped: non-finite gradient detected")
                return (('src_loss', 0.0), ('dst_loss', 0.0))

        except Exception as e:
            # 训练异常必须保留原始失败语义，避免后续返回路径掩盖根因。
            _log_training_exception(e, self, src_samples, dst_samples)
            raise

        return ( ('src_loss', np.mean(src_loss) ), ('dst_loss', np.mean(dst_loss) ), )

    #override
    def onGetPreview(self, samples, for_history=False):
        src_samples, dst_samples = samples
        warped_src, target_src, target_srcm = src_samples[0], src_samples[1], src_samples[2]
        warped_dst, target_dst, target_dstm = dst_samples[0], dst_samples[1], dst_samples[2]

        S, D, SS, DD, DDM, SD, SDM = [ np.clip( nn.to_data_format(x,"NHWC", self.model_data_format), 0.0, 1.0) for x in ([target_src,target_dst] + self.AE_view (target_src, target_dst) ) ]
        DDM, SDM = [ np.repeat (x, (3,), -1) for x in [DDM, SDM] ]

        target_srcm, target_dstm = [ nn.to_data_format(x,"NHWC", self.model_data_format) for x in ([target_srcm, target_dstm] )]

        n_samples = min(4, self.get_batch_size(), 800 // self.resolution )

        if self.resolution <= 400:
            result = []

            st = []
            for i in range(n_samples):
                ar = S[i], SS[i], D[i], DD[i], SD[i]
                st.append ( np.concatenate ( ar, axis=1) )
            result += [ ('SAEHD', np.concatenate (st, axis=0 )), ]


            st_m = []
            for i in range(n_samples):
                SD_mask = DDM[i]*SDM[i] if self.face_type < FaceType.HEAD else SDM[i]

                ar = S[i]*target_srcm[i], SS[i], D[i]*target_dstm[i], DD[i]*DDM[i], SD[i]*SD_mask
                st_m.append ( np.concatenate ( ar, axis=1) )

            result += [ ('SAEHD masked', np.concatenate (st_m, axis=0 )), ]
        else:
            result = []

            st = []
            for i in range(n_samples):
                ar = S[i], SS[i]
                st.append ( np.concatenate ( ar, axis=1) )
            result += [ ('SAEHD src-src', np.concatenate (st, axis=0 )), ]

            st = []
            for i in range(n_samples):
                ar = D[i], DD[i]
                st.append ( np.concatenate ( ar, axis=1) )
            result += [ ('SAEHD dst-dst', np.concatenate (st, axis=0 )), ]

            st = []
            for i in range(n_samples):
                ar = D[i], SD[i]
                st.append ( np.concatenate ( ar, axis=1) )
            result += [ ('SAEHD pred', np.concatenate (st, axis=0 )), ]


            st_m = []
            for i in range(n_samples):
                ar = S[i]*target_srcm[i], SS[i]
                st_m.append ( np.concatenate ( ar, axis=1) )
            result += [ ('SAEHD masked src-src', np.concatenate (st_m, axis=0 )), ]

            st_m = []
            for i in range(n_samples):
                ar = D[i]*target_dstm[i], DD[i]*DDM[i]
                st_m.append ( np.concatenate ( ar, axis=1) )
            result += [ ('SAEHD masked dst-dst', np.concatenate (st_m, axis=0 )), ]

            st_m = []
            for i in range(n_samples):
                SD_mask = DDM[i]*SDM[i] if self.face_type < FaceType.HEAD else SDM[i]
                ar = D[i]*target_dstm[i], SD[i]*SD_mask
                st_m.append ( np.concatenate ( ar, axis=1) )
            result += [ ('SAEHD masked pred', np.concatenate (st_m, axis=0 )), ]

        return result

    def predictor_func (self, face=None):
        face = nn.to_data_format(face[None,...], self.model_data_format, "NHWC")

        bgr, mask_dst_dstm, mask_src_dstm = [ nn.to_data_format(x,"NHWC", self.model_data_format).astype(np.float32) for x in self.AE_merge (face) ]

        return bgr[0], mask_src_dstm[0][...,0], mask_dst_dstm[0][...,0]

    def switch_to_merge_mode(self):
        import gc
        from core.leras import nn as leras_nn
        from core.leras import device as leras_device

        io.log_info("Switching to merge mode: releasing all training GPU memory...")

        saved_state = {
            'options': dict(self.options),
            'model_name': self.model_name,
            'model_class_name': self.model_class_name,
            'resolution': self.resolution,
            'face_type_name': getattr(self, 'face_type_name', None),
            'archi_type': self.options.get('archi', 'df'),
            'saved_models_path': self.saved_models_path,
        }

        io.log_info("Saving model weights before session reset...")
        try:
            self.onSave()
        except Exception as e:
            io.log_info(f"Save warning: {e}")

        for attr in ['encoder', 'decoder', 'decoder_src', 'decoder_dst',
                     'inter', 'inter_AB', 'inter_B',
                     'D_src', 'code_discriminator',
                     'src_dst_opt', 'D_src_dst_opt', 'D_code_opt',
                     'warped_src', 'warped_dst',
                     'target_src', 'target_dst',
                     'target_srcm', 'target_dstm',
                     'target_srcm_em', 'target_dstm_em',
                     'src_dst_saveable_weights', 'src_dst_trainable_weights',
                     'model_filename_list',
                     'AE_view', 'AE_merge',
                     'sample_generators']:
            if hasattr(self, attr):
                delattr(self, attr)

        gc.collect()

        leras_nn.close_session()
        leras_nn.compact_gpu_memory()
        gc.collect()

        leras_nn.initialize (leras_nn.DeviceConfig.GPUIndexes( [device.index for device in leras_device.Devices.getDevices()] ) )
        tf = leras_nn.tf

        devices = leras_device.Devices.getDevices()
        models_opt_device = '/CPU:0'
        input_ch = 3
        resolution = saved_state['resolution']
        bgr_shape = leras_nn.get4Dshape(resolution, resolution, input_ch)
        mask_shape = leras_nn.get4Dshape(resolution, resolution, 1)

        with tf.device('/CPU:0'):
            self.warped_dst = tf.placeholder(leras_nn.floatx, bgr_shape, name='warped_dst')

        with tf.device(models_opt_device):
            archi_type_split = saved_state['archi_type'].split('-')
            if len(archi_type_split) == 2:
                _, archi_opts = archi_type_split
            else:
                archi_opts = ''
            model_archi = leras_nn.DeepFakeArchi(resolution, use_fp16=False, opts=archi_opts)

            if 'df' in saved_state['archi_type']:
                e_dims = self.options.get('e_dims', 128)
                d_dims = self.options.get('d_dims', 64)
                ae_dims = self.options.get('ae_dims', 192)
                d_mask_dims = self.options.get('d_mask_dims', 16)

                self.encoder = model_archi.Encoder(in_ch=input_ch, e_ch=e_dims, name='encoder')
                inter_out_ch = self.encoder.get_out_ch() * self.encoder.get_out_res(resolution) ** 2
                self.inter = model_archi.Inter(in_ch=inter_out_ch, ae_ch=ae_dims, ae_out_ch=ae_dims, name='inter')
                inter_out_ch = self.inter.get_out_ch()
                self.decoder_src = model_archi.Decoder(in_ch=inter_out_ch, d_ch=d_dims, d_mask_ch=d_mask_dims, name='decoder_src')
                self.decoder_dst = model_archi.Decoder(in_ch=inter_out_ch, d_ch=d_dims, d_mask_ch=d_mask_dims, name='decoder_dst')

                gpu_dst_code = self.inter(self.encoder(self.warped_dst))
                gpu_pred_src_dst, gpu_pred_src_dstm = self.decoder_src(gpu_dst_code)
                _, gpu_pred_dst_dstm = self.decoder_dst(gpu_dst_code)

            elif 'liae' in saved_state['archi_type']:
                e_dims = self.options.get('e_dims', 128)
                d_dims = self.options.get('d_dims', 64)
                ae_dims = self.options.get('ae_dims', 192)
                d_mask_dims = self.options.get('d_mask_dims', 16)

                self.encoder = model_archi.Encoder(in_ch=input_ch, e_ch=e_dims, name='encoder')
                encoder_out_ch = self.encoder.get_out_ch() * self.encoder.get_out_res(resolution) ** 2
                self.inter_AB = model_archi.Inter(in_ch=encoder_out_ch, ae_ch=ae_dims, ae_out_ch=ae_dims * 2, name='inter_AB')
                self.inter_B = model_archi.Inter(in_ch=encoder_out_ch, ae_ch=ae_dims, ae_out_ch=ae_dims * 2, name='inter_B')
                inter_out_ch = self.inter_AB.get_out_ch()
                inters_out_ch = inter_out_ch * 2
                self.decoder = model_archi.Decoder(in_ch=inters_out_ch, d_ch=d_dims, d_mask_ch=d_mask_dims, name='decoder')

                gpu_dst_code = self.encoder(self.warped_dst)
                gpu_dst_inter_B_code = self.inter_B(gpu_dst_code)
                gpu_dst_inter_AB_code = self.inter_AB(gpu_dst_code)
                gpu_dst_code = tf.concat([gpu_dst_inter_B_code, gpu_dst_inter_AB_code], leras_nn.conv2d_ch_axis)
                gpu_src_dst_code = tf.concat([gpu_dst_inter_AB_code, gpu_dst_inter_AB_code], leras_nn.conv2d_ch_axis)

                gpu_pred_src_dst, gpu_pred_src_dstm = self.decoder(gpu_src_dst_code)
                _, gpu_pred_dst_dstm = self.decoder(gpu_dst_code)

        def AE_merge(warped_dst):
            return leras_nn.tf_sess.run([gpu_pred_src_dst, gpu_pred_dst_dstm, gpu_pred_src_dstm],
                                         feed_dict={self.warped_dst: warped_dst})

        self.AE_merge = AE_merge

        merge_weights = []
        if 'df' in saved_state['archi_type']:
            merge_weights = [
                [self.encoder, 'encoder.npy'],
                [self.inter, 'inter.npy'],
                [self.decoder_src, 'decoder_src.npy'],
                [self.decoder_dst, 'decoder_dst.npy'],
            ]
        elif 'liae' in saved_state['archi_type']:
            merge_weights = [
                [self.encoder, 'encoder.npy'],
                [self.inter_AB, 'inter_AB.npy'],
                [self.inter_B, 'inter_B.npy'],
                [self.decoder, 'decoder.npy'],
            ]

        leras_nn.tf_sess.run(tf.global_variables_initializer())

        for model, filename in merge_weights:
            path = self.get_strpath_storage_for_file(filename)
            if os.path.exists(path):
                model.load_weights(path)

        self.is_training = False
        self.model_data_format = 'NHWC'
        gc.collect()

        io.log_info("Merge mode ready. Training components fully released from GPU memory.")
        io.log_info("Only inference weights loaded (encoder + inter + decoder).")

    def release_training_resources(self):
        released = []
        release_names = {
            'D_src': 'GAN Discriminator (~32MB)',
            'code_discriminator': 'Code Discriminator (~8MB)',
            'D_src_dst_opt': 'GAN Optimizer state (~64MB)',
            'D_code_opt': 'Code Optimizer state (~16MB)',
            'src_dst_opt': 'Main Optimizer state (AdaB:~320MB / Lion:~160MB)',
        }
        for attr_name, desc in release_names.items():
            if hasattr(self, attr_name):
                obj = getattr(self, attr_name)
                if obj is not None:
                    if hasattr(obj, 'c_dict'):
                        for key in list(obj.c_dict.keys()):
                            try:
                                del obj.c_dict[key]
                            except:
                                pass
                        obj.c_dict.clear()
                    if hasattr(obj, 'vs_dict'):
                        for key in list(obj.vs_dict.keys()):
                            try:
                                del obj.vs_dict[key]
                            except:
                                pass
                        obj.vs_dict.clear()
                    if hasattr(obj, 'ms_dict'):
                        for key in list(obj.ms_dict.keys()):
                            try:
                                del obj.ms_dict[key]
                            except:
                                pass
                        obj.ms_dict.clear()
                    if hasattr(obj, 'lr_rnds_dict'):
                        for key in list(obj.lr_rnds_dict.keys()):
                            try:
                                del obj.lr_rnds_dict[key]
                            except:
                                pass
                        obj.lr_rnds_dict.clear()
                    setattr(self, attr_name, None)
                    released.append(f"  ✓ {attr_name}: {desc}")

        for list_attr in ['src_dst_saveable_weights', 'src_dst_trainable_weights',
                          'gpu_G_loss_gvs', 'gpu_D_code_loss_gvs', 'gpu_D_src_dst_loss_gvs']:
            if hasattr(self, list_attr):
                setattr(self, list_attr, [])
                released.append(f"  ✓ {list_attr}: gradient lists cleared")

        if released:
            import gc
            from core.leras import nn as leras_nn

            try:
                leras_nn.reset_session()
            except Exception as e:
                io.log_info(f"Session reset warning: {e}")

            gc.collect()
            leras_nn.compact_gpu_memory()
            gc.collect()
            io.log_info("Released training resources:\n" + "\n".join(released))
        return len(released)

    #override
    def get_MergerConfig(self):
        import merger
        return self.predictor_func, (self.options['resolution'], self.options['resolution'], 3), merger.MergerConfigMasked(face_type=self.face_type, default_mode = 'overlay')

Model = SAEHDModel
