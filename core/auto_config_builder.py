#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import glob
import json
import yaml
import winreg

# 【极简修改】：因为是通过 -m 从根目录运行，Python 直接认识 core 文件夹
from core import keil_parser

CONFIG_FILE = "project_config.yaml"
SYMBOLS_FILE = ".hil_symbols.json"

def auto_sniff_environment():
    """嗅探工程环境，自动提取关键配置（强依赖 keil_parser 作为唯一事实源）"""
    print("[装配引擎] 正在自动嗅探工程环境...")
    config = {
        "paths": {},
        "hardware": {"interface": "swd", "jlink_speed": 4000}, # 默认项
        "verify": {"default_timeout": 10}
    }

    # 1. 强依赖 keil_parser 解析工程，提取单一事实来源的 MCU 型号和 Map 预期路径
    try:
        # 调用底层基建，获取路径和型号 (传 "." 代表当前调用命令的业务工程目录)
        map_path, device_name = keil_parser.find_map_file_path(".")
        config["hardware"]["mcu"] = device_name
        config["paths"]["map_file_expected"] = map_path # 存入预期路径，供下游进行防御性双重校验
        print(f"✅ 从 Keil 工程提取到 MCU 型号: {config['hardware']['mcu']}")
        
        # 顺便记录工程文件路径，供编译脚本使用
        proj_files = glob.glob("*.uvprojx")
        if proj_files:
            config["paths"]["keil_project"] = f"./{proj_files[0]}"
    except Exception as e:
        print(f"⚠️ keil_parser 解析底座异常，请检查工程结构: {e}")

    # 2. 自动寻找 Hex 文件 (防御性寻址：优先找 EIDE 的 build 目录，其次找 Keil 的 Objects)
    # 铁律：只相信物理磁盘上生成的最新文件
    hex_files = glob.glob("build/**/*.hex", recursive=True) + glob.glob("Objects/*.hex")
    if hex_files:
        # 取最新生成的 Hex
        latest_hex = max(hex_files, key=os.path.getmtime)
        config["paths"]["hex_output"] = f"./{os.path.normpath(latest_hex).replace(os.sep, '/')}"
        print(f"✅ 探测到最新 Hex (时间戳校验): {config['paths']['hex_output']}")
    else:
        print("⚠️ 未找到任何 Hex 文件，请确认是否已成功编译。")

    # 3. 从符号字典中自动提取 RTT 地址！
    if os.path.exists(SYMBOLS_FILE):
        try:
            with open(SYMBOLS_FILE, 'r', encoding='utf-8') as f:
                symbols = json.load(f)
                if "_SEGGER_RTT" in symbols:
                    rtt_info = symbols["_SEGGER_RTT"]
                    # 将十进制地址转回漂亮的 0x 格式
                    config["verify"]["rtt_address"] = hex(rtt_info["address"])
                    config["verify"]["rtt_size"] = hex(rtt_info["size"])
                    print(f"✅ 探测到 RTT 控制块 -> 地址: {config['verify']['rtt_address']}, 大小: {config['verify']['rtt_size']}")
                else:
                    print("⚠️ 在符号字典中未找到 _SEGGER_RTT (确认 C 代码中是否包含了 RTT 组件)")
        except Exception as e:
            print(f"⚠️ 读取符号字典失败: {e}")
    else:
        print("⚠️ 未找到 .hil_symbols.json，RTT 交互参数将留空 (若需交互，请先运行 hil_parser.py)")

    return config

def update_yaml(new_config):
    """合并并更新 YAML 文件"""
    # 如果已有配置文件，读取并保留手动设置的项（比如 keil_exe 路径）
    existing_config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                existing_config = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"⚠️ 读取已有 YAML 失败，将重新生成: {e}")

    # 递归合并字典 (用嗅探到的新配置覆盖老配置)
    for section, values in new_config.items():
        if section not in existing_config:
            existing_config[section] = {}
        for k, v in values.items():
            existing_config[section][k] = v

    # 确保 paths 节点存在，防止下方调用报错
    if "paths" not in existing_config:
        existing_config["paths"] = {}

    # 【核心修改】：终极 Keil 路径探测器（注册表 + 穷举兜底）
    if "keil_exe" not in existing_config["paths"]:
        found_path = None
        
        # 1. 终极大招：直接查 Windows 注册表 (精准打击，无论装在哪个盘都能找到)
        try:
            # Keil 通常是 32 位软件，在 64 位系统下会登记在 WOW6432Node 下
            reg_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Keil\Products\MDK")
            install_dir, _ = winreg.QueryValueEx(reg_key, "Path")
            winreg.CloseKey(reg_key)
            
            # 拼装出 UV4.exe 的绝对路径
            test_path = os.path.join(install_dir, "UV4", "UV4.exe").replace("\\", "/")
            if os.path.exists(test_path):
                found_path = test_path
                print(f"✅ [终极定位] 从 Windows 注册表精准捕获 Keil: {found_path}")
        except Exception:
            # 如果注册表没查到（比如用了绿色免安装版），静默进入下一步
            pass

        # 2. 备用兜底：如果没查到注册表，再用常见路径清单盲狙
        if not found_path:
            user_appdata = os.environ.get('LOCALAPPDATA', 'C:/Users/Default/AppData/Local').replace('\\', '/')
            common_paths = [
                f"{user_appdata}/Keil_v5/UV4/UV4.exe",  # 兼容你的安装习惯
                "C:/Keil_v5/UV4/UV4.exe",               # 官方默认习惯
                "D:/Keil_v5/UV4/UV4.exe",               # 常见 D 盘习惯
                "C:/Keil/UV4/UV4.exe"                   # 老版本习惯
            ]
            for cp in common_paths:
                if os.path.exists(cp):
                    found_path = cp
                    print(f"✅ [盲狙定位] 扫描常见目录找到 Keil: {found_path}")
                    break
        
        # 3. 最终写入：如果连盲狙都失败了，给个默认值听天由命
        existing_config["paths"]["keil_exe"] = found_path or "C:/Keil_v5/UV4/UV4.exe"

    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(existing_config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        print(f"\n🎉 project_config.yaml 装配完成！")
    except Exception as e:
        print(f"\n❌ 写入 YAML 失败: {e}")

if __name__ == "__main__":
    sniffed_data = auto_sniff_environment()
    update_yaml(sniffed_data)