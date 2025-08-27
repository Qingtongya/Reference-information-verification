import json
import os
from typing import Dict, Any


class ConfigManager:
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.config = self.load_config()

    def load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        default_config = {
            "api_key": "",
            "last_index_path": "",
            "use_proxy": False,
            "proxy_url": "",
            "recent_files": [],
            "index_status": {
                "document_count": 0,
                "file_count": 0,
                "dimension": 0,
                "status": "未初始化"
            }
        }

        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 确保所有必要的键都存在
                    for key in default_config:
                        if key not in config:
                            config[key] = default_config[key]
                    return config
            else:
                return default_config
        except Exception as e:
            print(f"加载配置文件失败: {str(e)}")
            return default_config

    def save_config(self) -> bool:
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存配置文件失败: {str(e)}")
            return False

    def get(self, key: str, default=None) -> Any:
        """获取配置值"""
        return self.config.get(key, default)

    def set(self, key: str, value: Any) -> bool:
        """设置配置值并保存"""
        self.config[key] = value
        return self.save_config()

    def add_recent_file(self, file_path: str) -> bool:
        """添加最近使用的文件"""
        if file_path in self.config["recent_files"]:
            self.config["recent_files"].remove(file_path)

        self.config["recent_files"].insert(0, file_path)

        # 限制最近文件列表的长度
        if len(self.config["recent_files"]) > 10:
            self.config["recent_files"] = self.config["recent_files"][:10]

        return self.save_config()

    def update_index_status(self, status: Dict) -> bool:
        """更新索引状态"""
        self.config["index_status"] = status
        return self.save_config()