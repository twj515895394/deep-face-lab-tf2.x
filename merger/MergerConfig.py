import numpy as np
import copy

from facelib import FaceType
from core.interact import interact as io


def _opt_label(key, en, zh):
    """交互菜单展示：编号 + 中文 + 英文键名（内部逻辑仍用英文键）。"""
    return f"({key}) {zh} ({en})"


class MergerConfig(object):
    TYPE_NONE = 0
    TYPE_MASKED = 1
    TYPE_FACE_AVATAR = 2
    ####

    TYPE_IMAGE = 3
    TYPE_IMAGE_WITH_LANDMARKS = 4

    def __init__(self, type=0,
                       sharpen_mode=0,
                       blursharpen_amount=0,
                       **kwargs
                       ):
        self.type = type

        # 内部标识保持英文，供滤波逻辑使用；展示用 sharpen_zh_dict
        self.sharpen_dict = {0:"None", 1:'box', 2:'gaussian'}
        self.sharpen_zh_dict = {0:"无", 1:"方框锐化", 2:"高斯锐化"}

        #default changeable params
        self.sharpen_mode = sharpen_mode
        self.blursharpen_amount = blursharpen_amount

    def copy(self):
        return copy.copy(self)

    #overridable
    def ask_settings(self):
        s = "选择锐化模式 (Choose sharpen mode):\n"
        for key in self.sharpen_dict.keys():
            s += _opt_label(key, self.sharpen_dict[key], self.sharpen_zh_dict[key]) + "\n"
        io.log_info(s)
        self.sharpen_mode = io.input_int ("", 0, valid_list=self.sharpen_dict.keys(),
                                          help_message="通过锐化滤镜增强细节 (Enhance details by applying sharpen filter).")

        if self.sharpen_mode != 0:
            self.blursharpen_amount = np.clip (
                io.input_int ("选择模糊/锐化程度 (Choose blur/sharpen amount)", 0, add_info="-100..100"),
                -100, 100 )

    def toggle_sharpen_mode(self):
        a = list( self.sharpen_dict.keys() )
        self.sharpen_mode = a[ (a.index(self.sharpen_mode)+1) % len(a) ]

    def add_blursharpen_amount(self, diff):
        self.blursharpen_amount = np.clip ( self.blursharpen_amount+diff, -100, 100)

    #overridable
    def get_config(self):
        d = self.__dict__.copy()
        d.pop('type')
        return d

    #overridable
    def __eq__(self, other):
        #check equality of changeable params

        if isinstance(other, MergerConfig):
            return self.sharpen_mode == other.sharpen_mode and \
                   self.blursharpen_amount == other.blursharpen_amount

        return False

    #overridable
    def to_string(self, filename):
        r = ""
        zh = self.sharpen_zh_dict.get(self.sharpen_mode, "")
        r += f"锐化模式 sharpen_mode : {zh} ({self.sharpen_dict[self.sharpen_mode]})\n"
        r += f"模糊/锐化程度 blursharpen_amount : {self.blursharpen_amount}\n"
        return r

# 内部 mode 值必须保持英文：MergeMasked / 会话恢复 / 热键逻辑依赖这些字符串
mode_dict = {0:'original',
             1:'overlay',
             2:'hist-match',
             3:'seamless',
             4:'seamless-hist-match',
             5:'raw-rgb',
             6:'raw-predict'}

mode_zh_dict = {0:'原始',
                1:'叠加',
                2:'直方图匹配',
                3:'无缝',
                4:'无缝+直方图匹配',
                5:'原始RGB',
                6:'原始预测'}

mode_str_dict = { mode_dict[key] : key for key in mode_dict.keys() }

mask_mode_dict = {0:'full',
                  1:'dst',
                  2:'learned-prd',
                  3:'learned-dst',
                  4:'learned-prd*learned-dst',
                  5:'learned-prd+learned-dst',
                  6:'XSeg-prd',
                  7:'XSeg-dst',
                  8:'XSeg-prd*XSeg-dst',
                  9:'learned-prd*learned-dst*XSeg-prd*XSeg-dst'
                  }

mask_mode_zh_dict = {0:'全图',
                     1:'目标脸',
                     2:'学习遮罩(预测)',
                     3:'学习遮罩(目标)',
                     4:'学习遮罩(预测*目标)',
                     5:'学习遮罩(预测+目标)',
                     6:'XSeg(预测)',
                     7:'XSeg(目标)',
                     8:'XSeg(预测*目标)',
                     9:'学习遮罩*XSeg 全组合'
                     }

ctm_dict = { 0: "None", 1:"rct", 2:"lct", 3:"mkl", 4:"mkl-m", 5:"idt", 6:"idt-m", 7:"sot-m", 8:"mix-m" }
ctm_zh_dict = { 0: "无", 1:"RCT", 2:"LCT", 3:"MKL", 4:"MKL-M", 5:"IDT", 6:"IDT-M", 7:"SOT-M", 8:"MIX-M" }
ctm_str_dict = {None:0, "rct":1, "lct":2, "mkl":3, "mkl-m":4, "idt":5, "idt-m":6, "sot-m":7, "mix-m":8 }

class MergerConfigMasked(MergerConfig):

    def __init__(self, face_type=FaceType.FULL,
                       default_mode = 'overlay',
                       mode='overlay',
                       masked_hist_match=True,
                       hist_match_threshold = 238,
                       mask_mode = 4,
                       erode_mask_modifier = 0,
                       blur_mask_modifier = 0,
                       motion_blur_power = 0,
                       output_face_scale = 0,
                       super_resolution_power = 0,
                       color_transfer_mode = ctm_str_dict['rct'],
                       image_denoise_power = 0,
                       bicubic_degrade_power = 0,
                       color_degrade_power = 0,
                       **kwargs
                       ):

        super().__init__(type=MergerConfig.TYPE_MASKED, **kwargs)

        self.face_type = face_type
        if self.face_type not in [FaceType.HALF, FaceType.MID_FULL, FaceType.FULL, FaceType.WHOLE_FACE, FaceType.HEAD ]:
            raise ValueError("MergerConfigMasked does not support this type of face.")

        self.default_mode = default_mode

        #default changeable params
        if mode not in mode_str_dict:
            mode = mode_dict[1]

        self.mode = mode
        self.masked_hist_match = masked_hist_match
        self.hist_match_threshold = hist_match_threshold
        self.mask_mode = mask_mode
        self.erode_mask_modifier = erode_mask_modifier
        self.blur_mask_modifier = blur_mask_modifier
        self.motion_blur_power = motion_blur_power
        self.output_face_scale = output_face_scale
        self.super_resolution_power = super_resolution_power
        self.color_transfer_mode = color_transfer_mode
        self.image_denoise_power = image_denoise_power
        self.bicubic_degrade_power = bicubic_degrade_power
        self.color_degrade_power = color_degrade_power

    def copy(self):
        return copy.copy(self)

    def set_mode (self, mode):
        self.mode = mode_dict.get (mode, self.default_mode)

    def toggle_masked_hist_match(self):
        if self.mode == 'hist-match':
            self.masked_hist_match = not self.masked_hist_match

    def add_hist_match_threshold(self, diff):
        if self.mode == 'hist-match' or self.mode == 'seamless-hist-match':
            self.hist_match_threshold = np.clip ( self.hist_match_threshold+diff , 0, 255)

    def toggle_mask_mode(self):
        a = list( mask_mode_dict.keys() )
        self.mask_mode = a[ (a.index(self.mask_mode)+1) % len(a) ]

    def add_erode_mask_modifier(self, diff):
        self.erode_mask_modifier = np.clip ( self.erode_mask_modifier+diff , -400, 400)

    def add_blur_mask_modifier(self, diff):
        self.blur_mask_modifier = np.clip ( self.blur_mask_modifier+diff , 0, 400)

    def add_motion_blur_power(self, diff):
        self.motion_blur_power = np.clip ( self.motion_blur_power+diff, 0, 100)

    def add_output_face_scale(self, diff):
        self.output_face_scale = np.clip ( self.output_face_scale+diff , -50, 50)

    def toggle_color_transfer_mode(self):
        self.color_transfer_mode = (self.color_transfer_mode+1) % ( max(ctm_dict.keys())+1 )

    def add_super_resolution_power(self, diff):
        self.super_resolution_power = np.clip ( self.super_resolution_power+diff , 0, 100)

    def add_color_degrade_power(self, diff):
        self.color_degrade_power = np.clip ( self.color_degrade_power+diff , 0, 100)

    def add_image_denoise_power(self, diff):
        self.image_denoise_power = np.clip ( self.image_denoise_power+diff, 0, 500)

    def add_bicubic_degrade_power(self, diff):
        self.bicubic_degrade_power = np.clip ( self.bicubic_degrade_power+diff, 0, 100)

    def ask_settings(self):
        s = "选择合并模式 (Choose mode):\n"
        for key in mode_dict.keys():
            s += _opt_label(key, mode_dict[key], mode_zh_dict[key]) + "\n"
        io.log_info(s)
        mode = io.input_int ("", mode_str_dict.get(self.default_mode, 1) )

        self.mode = mode_dict.get (mode, self.default_mode )

        if 'raw' not in self.mode:
            if self.mode == 'hist-match':
                self.masked_hist_match = io.input_bool("是否使用遮罩区域直方图匹配？ (Masked hist match?)", True)

            if self.mode == 'hist-match' or self.mode == 'seamless-hist-match':
                self.hist_match_threshold = np.clip (
                    io.input_int("直方图匹配阈值 (Hist match threshold)", 255, add_info="0..255"),
                    0, 255)

        s = "选择遮罩模式 (Choose mask mode):\n"
        for key in mask_mode_dict.keys():
            s += _opt_label(key, mask_mode_dict[key], mask_mode_zh_dict[key]) + "\n"
        io.log_info(s)
        self.mask_mode = io.input_int ("", 1, valid_list=mask_mode_dict.keys() )

        if 'raw' not in self.mode:
            self.erode_mask_modifier = np.clip (
                io.input_int ("选择遮罩边缘侵蚀值 (Choose erode mask modifier)", 0, add_info="-400..400"),
                -400, 400)
            self.blur_mask_modifier =  np.clip (
                io.input_int ("选择遮罩边缘模糊值 (Choose blur mask modifier)", 0, add_info="0..400"),
                0, 400)
            self.motion_blur_power = np.clip (
                io.input_int ("选择运动模糊强度 (Choose motion blur power)", 0, add_info="0..100"),
                0, 100)

        self.output_face_scale = np.clip (
            io.input_int ("选择输出人脸缩放比例 (Choose output face scale modifier)", 0, add_info="-50..50" ),
            -50, 50)

        if 'raw' not in self.mode:
            # 输入仍用英文简写（rct/lct/...），与 ctm_str_dict 及历史会话兼容
            ctm_help = "可选: " + ", ".join(
                f"{k}={ctm_zh_dict[ctm_str_dict[k]]}" for k in list(ctm_str_dict.keys())[1:]
            )
            io.log_info(f"颜色迁移算法说明 (Color transfer): {ctm_help}")
            self.color_transfer_mode = io.input_str (
                "预测脸的颜色迁移方式 (Color transfer to predicted face)",
                None, valid_list=list(ctm_str_dict.keys())[1:] )
            self.color_transfer_mode = ctm_str_dict[self.color_transfer_mode]

        super().ask_settings()

        self.super_resolution_power = np.clip (
            io.input_int ("选择超分辨率增强强度 (Choose super resolution power)", 0, add_info="0..100",
                          help_message="通过超分辨率网络增强细节 (Enhance details by applying superresolution network)."),
            0, 100)

        if 'raw' not in self.mode:
            self.image_denoise_power = np.clip (
                io.input_int ("选择图像降噪退化强度 (Choose image degrade by denoise power)", 0, add_info="0..500"),
                0, 500)
            self.bicubic_degrade_power = np.clip (
                io.input_int ("选择双三次缩放退化强度 (Choose image degrade by bicubic rescale power)", 0, add_info="0..100"),
                0, 100)
            self.color_degrade_power = np.clip (
                io.input_int ("最终图像颜色退化强度 (Degrade color power of final image)", 0, add_info="0..100"),
                0, 100)

        io.log_info ("")

    def __eq__(self, other):
        #check equality of changeable params

        if isinstance(other, MergerConfigMasked):
            return super().__eq__(other) and \
                   self.mode == other.mode and \
                   self.masked_hist_match == other.masked_hist_match and \
                   self.hist_match_threshold == other.hist_match_threshold and \
                   self.mask_mode == other.mask_mode and \
                   self.erode_mask_modifier == other.erode_mask_modifier and \
                   self.blur_mask_modifier == other.blur_mask_modifier and \
                   self.motion_blur_power == other.motion_blur_power and \
                   self.output_face_scale == other.output_face_scale and \
                   self.color_transfer_mode == other.color_transfer_mode and \
                   self.super_resolution_power == other.super_resolution_power and \
                   self.image_denoise_power == other.image_denoise_power and \
                   self.bicubic_degrade_power == other.bicubic_degrade_power and \
                   self.color_degrade_power == other.color_degrade_power

        return False

    def to_string(self, filename):
        mode_key = mode_str_dict.get(self.mode)
        mode_zh = mode_zh_dict.get(mode_key, "") if mode_key is not None else ""
        r = (
            f"合并配置 MergerConfig {filename}:\n"
            f"合并模式 Mode: {mode_zh} ({self.mode})\n"
            )

        if self.mode == 'hist-match':
            r += f"遮罩直方图匹配 masked_hist_match: {self.masked_hist_match}\n"

        if self.mode == 'hist-match' or self.mode == 'seamless-hist-match':
            r += f"直方图匹配阈值 hist_match_threshold: {self.hist_match_threshold}\n"

        r += (f"遮罩模式 mask_mode: {mask_mode_zh_dict.get(self.mask_mode, '')} "
              f"({mask_mode_dict[self.mask_mode]})\n")

        if 'raw' not in self.mode:
            r += (f"遮罩侵蚀 erode_mask_modifier: {self.erode_mask_modifier}\n"
                  f"遮罩模糊 blur_mask_modifier: {self.blur_mask_modifier}\n"
                  f"运动模糊 motion_blur_power: {self.motion_blur_power}\n")

        r += f"输出脸缩放 output_face_scale: {self.output_face_scale}\n"

        if 'raw' not in self.mode:
            r += (f"颜色迁移 color_transfer_mode: "
                  f"{ctm_zh_dict.get(self.color_transfer_mode, '')} ({ctm_dict[self.color_transfer_mode]})\n")
            r += super().to_string(filename)

        r += f"超分辨率强度 super_resolution_power: {self.super_resolution_power}\n"

        if 'raw' not in self.mode:
            r += (f"降噪退化 image_denoise_power: {self.image_denoise_power}\n"
                  f"双三次退化 bicubic_degrade_power: {self.bicubic_degrade_power}\n"
                  f"颜色退化 color_degrade_power: {self.color_degrade_power}\n")

        r += "================"

        return r


class MergerConfigFaceAvatar(MergerConfig):

    def __init__(self, temporal_face_count=0,
                       add_source_image=False):
        super().__init__(type=MergerConfig.TYPE_FACE_AVATAR)
        self.temporal_face_count = temporal_face_count

        #changeable params
        self.add_source_image = add_source_image

    def copy(self):
        return copy.copy(self)

    #override
    def ask_settings(self):
        self.add_source_image = io.input_bool(
            "是否添加源图对比？ (Add source image?)", False,
            help_message="添加源图像以便对比 (Add source image for comparison).")
        super().ask_settings()

    def toggle_add_source_image(self):
        self.add_source_image = not self.add_source_image

    #override
    def __eq__(self, other):
        #check equality of changeable params

        if isinstance(other, MergerConfigFaceAvatar):
            return super().__eq__(other) and \
                   self.add_source_image == other.add_source_image

        return False

    #override
    def to_string(self, filename):
        return (f"合并配置 MergerConfig {filename}:\n"
                f"添加源图对比 add_source_image : {self.add_source_image}\n") + \
                super().to_string(filename) + "================"

