# src/config/config_validator.py
"""
配置验证工具 - 独立运行，不依赖现有代码结构
"""

import logging
from typing import Dict, List

class ConfigValidator:
    """配置验证工具，可以独立运行"""
    
    @staticmethod
    def validate_essential_templates():
        """验证必要的模板是否存在"""
        try:
            from src.global_instances import get_template_manager
            
            template_manager = get_template_manager()
            templates = template_manager.templates
            
            essential_templates = [
                'war', 'decision', 'end_round', 'enemy_round',
                'ResultScreen', 'mainPage', 'LoginPage'
            ]
            
            missing = []
            for template in essential_templates:
                if template not in templates:
                    missing.append(template)
            
            if missing:
                logging.warning(f"缺少必要模板: {missing}")
                return False
            else:
                logging.info("所有必要模板都存在")
                return True
                
        except Exception as e:
            logging.error(f"模板验证失败: {e}")
            return False
    
    @staticmethod
    def validate_coordinates():
        """验证坐标配置"""
        try:
            from src.utils.coordinates import COORDS, ROIS
            
            essential_coords = [
                'BATTLE_READY_CLICK', 'MAIN_INTERFACE_CLICK', 
                'BACK_BUTTON_CLICK', 'SCREEN_CENTER'
            ]
            
            essential_rois = [
                'BATTLE_READY_DETECT', 'MAIN_PAGE_REGION'
            ]
            
            missing_coords = []
            for coord in essential_coords:
                if not hasattr(COORDS, coord):
                    missing_coords.append(coord)
            
            missing_rois = []
            for roi in essential_rois:
                if not hasattr(ROIS, roi):
                    missing_rois.append(roi)
            
            if missing_coords or missing_rois:
                logging.warning(f"缺少坐标: {missing_coords}, 缺少ROI: {missing_rois}")
                return False
            else:
                logging.info("所有坐标配置都存在")
                return True
                
        except Exception as e:
            logging.error(f"坐标验证失败: {e}")
            return False
    
    @staticmethod
    def validate_all():
        """验证所有配置"""
        results = {
            'templates': ConfigValidator.validate_essential_templates(),
            'coordinates': ConfigValidator.validate_coordinates()
        }
        
        all_valid = all(results.values())
        if all_valid:
            logging.info("所有配置验证通过")
        else:
            logging.warning("部分配置验证失败")
        
        return all_valid, results

# 独立运行验证
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    ConfigValidator.validate_all()