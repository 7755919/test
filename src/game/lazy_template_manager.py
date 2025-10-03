# lazy_template_manager.py
import os
import cv2
import logging
from typing import Dict, Optional
import threading

logger = logging.getLogger("LazyTemplateManager")

class LazyTemplateManager:
    """懒加载模板管理器 - 只在需要时加载模板"""
    
    _instance = None
    _lock = threading.Lock()
    
    def load_templates(self, template_config=None):
        """加载模板方法 - 兼容原有接口"""
        if not self.templates_loaded:
            # 调用实际的模板加载逻辑
            if hasattr(self, '_load_all_templates'):
                self._load_all_templates()
            elif hasattr(self, 'load_all_templates'):
                self.load_all_templates()
            else:
                # 如果都没有，至少设置标志位
                self.templates_loaded = True
        return self.templates

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(LazyTemplateManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        self.templates_loaded = False
        self.templates = {}
        self.template_config = None
        self.loading = False
        
        if self._initialized:
            return
            
        self.templates_dir = 'templates'
        self.task_templates_dir = 'templates_task'
        self.templates = {}  # 对战模板缓存
        self.task_templates = {}  # 任务模板缓存
        self.ui_templates = {}  # UI模板缓存
        self.template_paths = {}  # 模板路径映射
        
        # 扫描模板文件但不立即加载
        self._scan_template_files()
        
        self._initialized = True
        logger.info("🔄 懒加载模板管理器初始化完成")
    
    def _scan_template_files(self):
        """扫描模板文件路径，但不加载图片"""
        logger.info("📁 扫描模板文件...")
        
        # 扫描对战模板
        if os.path.exists(self.templates_dir):
            for file in os.listdir(self.templates_dir):
                if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    name = os.path.splitext(file)[0]
                    self.template_paths[name] = os.path.join(self.templates_dir, file)
        
        # 扫描任务模板
        if os.path.exists(self.task_templates_dir):
            for file in os.listdir(self.task_templates_dir):
                if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    name = os.path.splitext(file)[0]
                    self.template_paths[name] = os.path.join(self.task_templates_dir, file)
        
        logger.info(f"📊 发现 {len(self.template_paths)} 个模板文件")
    
    def get_template(self, template_name: str) -> Optional:
        """获取模板（懒加载）"""
        if template_name in self.templates:
            return self.templates[template_name]
        
        if template_name in self.template_paths:
            try:
                logger.debug(f"🔄 懒加载模板: {template_name}")
                template = cv2.imread(self.template_paths[template_name], cv2.IMREAD_UNCHANGED)
                if template is not None:
                    self.templates[template_name] = template
                    return template
                else:
                    logger.warning(f"❌ 无法加载模板: {template_name}")
            except Exception as e:
                logger.error(f"❌ 加载模板 {template_name} 时出错: {e}")
        
        logger.warning(f"⚠️  模板不存在: {template_name}")
        return None
    
    def preload_essential_templates(self):
        """预加载必要的核心模板"""
        essential_templates = [
            'mainPage', 'LoginPage', 'war', 'decision', 
            'end_round', 'enemy_round', 'ResultScreen'
        ]
        
        logger.info("🚀 预加载核心模板...")
        loaded_count = 0
        
        for template_name in essential_templates:
            if self.get_template(template_name) is not None:
                loaded_count += 1
        
        logger.info(f"✅ 预加载 {loaded_count}/{len(essential_templates)} 个核心模板")
    
    def get_loaded_count(self):
        """获取已加载的模板数量"""
        return len(self.templates)
    
    def get_total_count(self):
        """获取总模板数量"""
        return len(self.template_paths)