"""
OCR 处理器模块
"""
import os
import cv2
import numpy as np
from typing import Optional, Tuple, Any

class OCRProcessor:
    """OCR 处理器"""
    
    def __init__(self, tesseract_path: Optional[str] = None):
        self.tesseract_path = tesseract_path
        print("✅ OCRProcessor 初始化")
    
    def set_tesseract_path(self, path: str):
        """设置 Tesseract 路径"""
        self.tesseract_path = path
        print(f"✅ 设置 Tesseract 路径: {path}")
    
    def verify_tesseract(self) -> bool:
        """验证 Tesseract"""
        if self.tesseract_path and os.path.exists(self.tesseract_path):
            print("✅ Tesseract 验证成功")
            return True
        print("❌ Tesseract 验证失败")
        return False

# 全局实例
_global_ocr_processor = None

def get_ocr_processor() -> OCRProcessor:
    """获取全局 OCR 处理器实例"""
    global _global_ocr_processor
    if _global_ocr_processor is None:
        _global_ocr_processor = OCRProcessor()
    return _global_ocr_processor
