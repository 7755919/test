# src/config/config_bridge.py
"""
配置桥接器 - 提供统一访问接口，但不强制替换现有代码
"""

class ConfigBridge:
    """配置桥接器，提供统一访问方式，同时保持向后兼容"""
    
    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        
        # 延迟导入，避免循环依赖
        self._coords = None
        self._rois = None
        self._thresholds = None
        self._constants_manager = None
    
    @property
    def coords(self):
        """延迟加载坐标配置"""
        if self._coords is None:
            from src.utils.coordinates import COORDS
            self._coords = COORDS
        return self._coords
    
    @property
    def rois(self):
        """延迟加载ROI配置"""
        if self._rois is None:
            from src.utils.coordinates import ROIS
            self._rois = ROIS
        return self._rois
    
    @property
    def thresholds(self):
        """延迟加载阈值配置"""
        if self._thresholds is None:
            from src.utils.coordinates import THRESHOLDS
            self._thresholds = THRESHOLDS
        return self._thresholds
    
    @property
    def constants_manager(self):
        """延迟加载常量管理器"""
        if self._constants_manager is None and self.config_manager:
            self._constants_manager = self.config_manager.get_constants_manager()
        return self._constants_manager
    
    # 便捷方法 - 可选使用
    def get_battle_ready_coords(self):
        """获取战斗准备坐标"""
        return self.coords.BATTLE_READY_CLICK
    
    def get_main_interface_coords(self):
        """获取主界面坐标"""
        return self.coords.MAIN_INTERFACE_CLICK
    
    def get_enemy_hp_region(self):
        """获取敌方血量区域"""
        if self.constants_manager:
            return self.constants_manager.get_enemy_hp_region()
        # 回退到硬编码
        from src.config.game_constants import ENEMY_HP_REGION
        return ENEMY_HP_REGION
    
    def get_template_threshold(self, template_name):
        """获取模板阈值"""
        return getattr(self.thresholds, template_name, 0.8)

# 创建全局实例
config_bridge = ConfigBridge()