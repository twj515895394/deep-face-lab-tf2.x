import os
import sys
import traceback
import queue
import threading
import time
import numpy as np
import itertools
from pathlib import Path
from core import pathex
from core import imagelib
import cv2
import models
from core.interact import interact as io


def main(model_class_name, saved_models_path):
    # 确保 saved_models_path 是有效的 Path 对象
    from pathlib import Path
    if saved_models_path is None:
        raise ValueError("saved_models_path cannot be None")
    
    # 转换为 Path 对象（如果还不是）
    if not isinstance(saved_models_path, Path):
        saved_models_path = Path(saved_models_path)
    
    # 确保路径存在
    if not saved_models_path.exists():
        raise ValueError(f"Model directory does not exist: {saved_models_path}")
    
    # 对于 SAEHD 模型，使用 Model_DFM.py 进行导出
    if model_class_name == 'SAEHD':
        from models.Model_SAEHD.Model_DFM import SAEHDModel as ModelClass
        model = ModelClass(
            is_exporting=True,
            saved_models_path=saved_models_path,
            cpu_only=True
        )
    else:
        # 对于其他模型，使用默认的导入方式
        model = models.import_model(model_class_name)(
                            is_exporting=True,
                            saved_models_path=saved_models_path,
                            cpu_only=True)
    
    model.export_dfm ()