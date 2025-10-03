# debug_singleton.py
import sys
import os
import gc

# 添加项目根目录到 Python 路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
sys.path.insert(0, os.path.join(current_dir, 'src'))

def diagnose_template_manager():
    """诊断 TemplateManager 单例问题"""
    
    print("🔍 TemplateManager 单例诊断")
    print("=" * 50)
    
    try:
        from src.template.template_manager import TemplateManager
        
        # 方法1: 直接实例化
        print("创建实例1...")
        tm1 = TemplateManager()
        print(f"实例1 ID: {id(tm1)}")
        
        # 方法2: 再次实例化
        print("创建实例2...")
        tm2 = TemplateManager()  
        print(f"实例2 ID: {id(tm2)}")
        
        # 检查是否相同
        print(f"实例相同: {tm1 is tm2}")
        
        # 通过GC查找所有实例
        instances = []
        for obj in gc.get_objects():
            if isinstance(obj, TemplateManager):
                instances.append(obj)
        
        print(f"内存中实例数量: {len(instances)}")
        for i, instance in enumerate(instances):
            print(f"  实例 {i}: {id(instance)}")
        
        # 检查初始化状态
        if instances:
            print(f"初始化状态: {getattr(instances[0], '_initialized', '未知')}")
        
        return len(instances)
        
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("当前Python路径:")
        for path in sys.path:
            print(f"  {path}")
        return -1
    except Exception as e:
        print(f"❌ 诊断过程中出错: {e}")
        import traceback
        traceback.print_exc()
        return -1

if __name__ == "__main__":
    count = diagnose_template_manager()
    if count == 1:
        print("✅ 单例模式正常工作")
    elif count > 1:
        print("❌ 单例模式失败: 检测到多个实例")
    else:
        print("❌ 无法诊断 TemplateManager")