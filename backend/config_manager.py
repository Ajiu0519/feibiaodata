"""配置管理模块"""
import json
import os
from datetime import datetime

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'refresh_config.json')

# 所有可用的渠道及 token
ALL_CHANNELS = {
    '星视点': '538FD95F068B9CB986307F81652DD931xqd',
    '江苏数赢': '4AAFBA8646E5A10646070B7626DF87BBSY',
    '中正运动': '154b8c8303e5b569c9990332d2e60b62ZZYD',
    '元创': '1c5f823b699d6597c20c1f192b16d2e0YC',
    '弘景': 'f4b325226ee385f8dc2216744e8013f0HJ',
}

def load_config():
    """加载配置"""
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {
            'enabled_channels': [],
            'schedule_time': '08:00',
            'cron_expression': '0 8 * * *'
        }

def save_config(config):
    """保存配置"""
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def get_enabled_channels():
    """获取已启用的渠道列表"""
    config = load_config()
    return config.get('enabled_channels', [])

def get_enabled_tokens():
    """获取已启用渠道的 token 列表"""
    enabled = get_enabled_channels()
    return [
        {'channel_name': name, 'token': token}
        for name, token in ALL_CHANNELS.items()
        if name in enabled
    ]

def update_config(enabled_channels, schedule_time):
    """更新配置"""
    config = {
        'enabled_channels': enabled_channels,
        'schedule_time': schedule_time,
        'cron_expression': f"0 {schedule_time.split(':')[0]} * * *"
    }
    save_config(config)
    return config
