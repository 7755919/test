"""
密钥管理器 - 处理许可证验证和加密
"""
import os
import json
import base64
import hashlib
import datetime
import uuid
import socket
import platform
import time
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def load_config(config_path="config.json"):
    """加载配置文件"""
    default_config = {
        "window_title": "Shadowverse",
        "server": "国际服",
        "model": "local",
        "api_url": "",
        "api_key": "",
        "enable_api": False,
        "api_timeout": 5,
        "scan_interval": 2,
        "action_delay": 0.5,
        "card_replacement": {"strategy": "3费档次"},
        "attack_delay": 0.25,
        "extra_drag_delay": 0.05,
        "auto_start_enabled": False,
        "auto_start_hours": 0,
        "auto_start_minutes": 0,
        "auto_start_seconds": 0,
        "scheduled_start_enabled": False,
        "scheduled_start_hour": 8,
        "scheduled_start_minute": 0,
        "repeat_daily": True,
        "repeat_weekdays": False,
        "repeat_weekend": False,
        "close_enabled": False,
        "inactivity_timeout_hours": 0,
        "inactivity_timeout_minutes": 0,
        "inactivity_timeout_seconds": 0,
        "inactivity_timeout": 0,
        "model_path": "",
        "device": "auto",
        "batch_size": 1,
        "cloud_endpoint": "",
        "cloud_version": "v1.0",
        "cloud_timeout": 10,
        "rl_algorithm": "PPO",
        "rl_epochs": 100,
        "rl_learning_rate": 0.0001,
        "rl_gamma": 0.99,
        "rl_models": [],
        "license_key": "",
        "license_valid": False,
        "machine_id": "",
        "ui_opacity": 0.85,
        "settings_opacity": 0.85,
        "license_opacity": 0.90,
        "emulator_port": 16384,
        "background_image": "",
        "settings_background_image": "",
        "scheduled_pause_enabled": False,
        "scheduled_pause_hour": 12,
        "scheduled_pause_minute": 0,
        "scheduled_resume_hour": 13,
        "scheduled_resume_minute": 0,
        "pause_repeat_daily": True,
        "pause_repeat_weekdays": False,
        "pause_repeat_weekend": False
    }
    
    # 如果配置文件不存在，创建默认配置
    if not os.path.exists(config_path):
        print(f"配置文件不存在，创建默认配置: {config_path}")
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            return default_config
        except Exception as e:
            print(f"创建默认配置文件失败: {str(e)}")
            return default_config
    
    # 配置文件存在，尝试加载
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:  # 文件为空
                print("配置文件为空，使用默认配置")
                # 重新写入默认配置
                with open(config_path, 'w', encoding='utf-8') as fw:
                    json.dump(default_config, fw, indent=2, ensure_ascii=False)
                return default_config
            
            user_config = json.loads(content)
            # 合并默认配置和用户配置
            for key, value in user_config.items():
                if key in default_config and isinstance(default_config[key], dict) and isinstance(value, dict):
                    default_config[key].update(value)
                else:
                    default_config[key] = value
            return default_config
    except json.JSONDecodeError as e:
        print(f"配置文件JSON格式错误: {str(e)}，使用默认配置")
        # 备份损坏的配置文件
        backup_path = config_path + ".backup"
        try:
            os.rename(config_path, backup_path)
            print(f"已备份损坏的配置文件到: {backup_path}")
        except:
            pass
        # 创建新的默认配置
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        return default_config
    except Exception as e:
        print(f"加载配置文件失败: {str(e)}，使用默认配置")
        return default_config


class KeyManager:
    """密钥管理器类"""
    
    def __init__(self, config_path="config.json", license_path="license.key"):
        self.config_path = config_path
        self.license_path = license_path
        self.config = self.load_config()
        
        self.crypto_key = self.generate_crypto_key()
        self.license_info = self.load_license()
        
        self.VALIDATION_INTERVAL = 86400
        self.last_validation = 0

    def load_config(self):
        """加载配置文件"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            print(f"保存配置失败: {str(e)}")
            return False

    def generate_crypto_key(self):
        """生成加密密钥"""
        machine_id = self.config.get("machine_id", "default_machine_id")
        salt = machine_id.encode()[:16].ljust(16, b'\0')
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(b"shadowverse_automation"))
        return key

    def encrypt_data(self, data):
        """加密数据"""
        f = Fernet(self.crypto_key)
        return f.encrypt(data.encode()).decode()

    def decrypt_data(self, encrypted_data):
        """解密数据"""
        f = Fernet(self.crypto_key)
        return f.decrypt(encrypted_data.encode()).decode()

    def load_license(self):
        """加载许可证信息"""
        if os.path.exists(self.license_path):
            try:
                with open(self.license_path, 'r', encoding='utf-8') as f:
                    encrypted_data = f.read()
                    decrypted_data = self.decrypt_data(encrypted_data)
                    return json.loads(decrypted_data)
            except Exception as e:
                print(f"加载许可证失败: {str(e)}")
        return {}

    def save_license(self, license_data):
        """保存许可证信息"""
        try:
            data_str = json.dumps(license_data)
            encrypted_data = self.encrypt_data(data_str)
            
            with open(self.license_path, 'w', encoding='utf-8') as f:
                f.write(encrypted_data)
            return True
        except Exception as e:
            print(f"保存许可证失败: {str(e)}")
            return False

    def generate_machine_id(self):
        """生成机器唯一ID"""
        system_info = {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "hostname": socket.gethostname(),
            "mac": ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) 
                            for elements in range(0, 2 * 6, 2)][::-1])
        }
        
        hash_obj = hashlib.sha256()
        hash_obj.update(json.dumps(system_info, sort_keys=True).encode())
        return hash_obj.hexdigest()

    def is_license_valid(self):
        """检查许可证是否有效"""
        if not self.license_info:
            return False
            
        expiration = self.license_info.get("expiration")
        if expiration:
            try:
                exp_date = datetime.datetime.strptime(expiration, "%Y-%m-%d")
                if datetime.datetime.now() > exp_date:
                    return False
            except:
                return False
        
        if self.license_info.get("machine_id") != self.config.get("machine_id", ""):
            return False
            
        current_time = time.time()
        if current_time - self.last_validation > self.VALIDATION_INTERVAL:
            self.last_validation = current_time
            return self.validate_online()
            
        return True

    def validate_online(self):
        """在线验证许可证"""
        if "license_key" not in self.license_info:
            return False
        return True

    def activate_license(self, license_key):
        """激活许可证"""
        if "machine_id" not in self.config:
            self.config["machine_id"] = self.generate_machine_id()
            self.save_config()
        
        self.config["license_key"] = license_key
        
        license_data = {
            "license_key": license_key,
            "machine_id": self.config["machine_id"],
            "activation_date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "expiration": (datetime.datetime.now() + datetime.timedelta(days=365)).strftime("%Y-%m-%d"),
            "product": "Shadowverse Automation",
            "version": "1.0"
        }
        
        if self.save_license(license_data):
            self.license_info = license_data
            self.save_config()
            return True
        return False

    def get_license_info(self):
        """获取许可证信息"""
        return self.license_info.copy()