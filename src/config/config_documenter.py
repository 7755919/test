# src/config/config_documenter.py
"""
配置文档生成器 - 帮助理解现有配置结构
"""

class ConfigDocumenter:
    """生成配置文档，帮助理解现有配置"""
    
    @staticmethod
    def generate_coordinates_doc():
        """生成坐标配置文档"""
        try:
            from src.utils.coordinates import COORDS, ROIS, THRESHOLDS
            
            doc = "# 坐标配置文档\n\n"
            
            doc += "## 坐标点\n"
            for attr in dir(COORDS):
                if not attr.startswith('_'):
                    value = getattr(COORDS, attr)
                    doc += f"- {attr}: {value}\n"
            
            doc += "\n## ROI区域\n"
            for attr in dir(ROIS):
                if not attr.startswith('_'):
                    value = getattr(ROIS, attr)
                    doc += f"- {attr}: {value}\n"
            
            doc += "\n## 阈值配置\n"
            for attr in dir(THRESHOLDS):
                if not attr.startswith('_'):
                    value = getattr(THRESHOLDS, attr)
                    doc += f"- {attr}: {value}\n"
            
            return doc
        except Exception as e:
            return f"生成文档失败: {e}"
    
    @staticmethod
    def save_documentation():
        """保存配置文档"""
        doc = ConfigDocumenter.generate_coordinates_doc()
        with open("config_documentation.md", "w", encoding="utf-8") as f:
            f.write(doc)
        print("配置文档已保存到 config_documentation.md")