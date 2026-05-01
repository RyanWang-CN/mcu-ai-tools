#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HIL 自动化框架 - 模块 1：Keil 工程解析器
职责：解析 .uvprojx 文件，提取并缓存 .map 文件的绝对路径 及 单片机型号。
"""

import os
import glob
import json
import xml.etree.ElementTree as ET
#name:keil_parser.py
CACHE_FILE_NAME = ".hil_cache.json"

def find_map_file_path(project_dir):
    """
    解析 Keil 工程 XML，寻找 .map 文件的预期生成路径和单片机型号
    """
    project_dir = os.path.abspath(project_dir)
    
    # 1. 查找 .uvprojx 文件 (防呆检查)
    proj_files = glob.glob(os.path.join(project_dir, "*.uvprojx"))
    if not proj_files:
        raise FileNotFoundError(f"[错误] 在目录 {project_dir} 下未找到 .uvprojx 工程文件！")
    if len(proj_files) > 1:
        print(f"[警告] 找到多个工程文件，默认使用第一个: {os.path.basename(proj_files[0])}")
    
    proj_file = proj_files[0]
    
    # 2. 解析 XML
    try:
        tree = ET.parse(proj_file)
        root = tree.getroot()
    except ET.ParseError as e:
        raise ValueError(f"[错误] Keil 工程文件 XML 格式损坏: {e}")

    # 3. 提取 OutputName, ListingPath 和 Device
    output_name = None
    listing_path = None
    device_name = "Cortex-M0+" # 【新增】默认兜底型号

    for elem in root.iter('OutputName'):
        if elem.text:
            output_name = elem.text.strip()
            break # 找到第一个 Target 的名字即退出
            
    for elem in root.iter('ListingPath'):
        if elem.text:
            listing_path = elem.text.strip()
            break

    # 【新增】提取单片机具体型号
    for elem in root.iter('Device'):
        if elem.text:
            device_name = elem.text.strip()
            break

    # 4. 逻辑校验
    if not output_name:
        raise ValueError("[错误] XML 解析失败：未找到 <OutputName> 标签！")
    if not listing_path:
        # Keil 默认如果没有指定 ListingPath，通常在工程根目录
        listing_path = ".\\" 

    # 5. 拼接绝对路径 (处理相对路径中的 .\ 或 ..\)
    full_listing_dir = os.path.normpath(os.path.join(project_dir, listing_path))
    map_file_path = os.path.join(full_listing_dir, f"{output_name}.map")

    # 【修改】同时返回 map 路径和型号
    return map_file_path, device_name

def get_or_update_map_path(project_dir, force_update=False):
    """
    带有缓存机制的路径获取函数（对外接口）
    """
    cache_path = os.path.join(project_dir, CACHE_FILE_NAME)
    
    # 如果不强制更新，且缓存存在，直接秒读缓存
    if not force_update and os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                if "map_file_path" in cache_data:
                    return cache_data["map_file_path"]
        except Exception:
            pass # 缓存读取失败则忽略，重新解析

    # 解析 XML 获取路径和型号
    print("[基建] 正在扫描并解析 Keil 工程文件...")
    # 【修改】接收两个返回值
    map_path, device_name = find_map_file_path(project_dir)
    
    # 写入缓存文件 (隐藏文件)
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            # 【修改】将路径和单片机型号一起存入 JSON
            json.dump({
                "map_file_path": map_path,
                "device": device_name
            }, f, indent=4)
        print(f"[基建] Map 路径与芯片型号({device_name}) 已缓存至: {CACHE_FILE_NAME}")
    except Exception as e:
        print(f"[警告] 缓存文件写入失败，但不影响本次运行: {e}")

    return map_path

# ================= 测试入口 =================
if __name__ == "__main__":
    test_workspace = input("请输入你的 Keil 工程根目录 (直接回车默认当前目录): ").strip()
    if not test_workspace:
        test_workspace = os.getcwd()
        
    try:
        result_path = get_or_update_map_path(test_workspace, force_update=True)
        print(f"\n✅ 成功计算出 Map 文件预期路径:\n-> {result_path}")
        
        # 验证缓存文件内容
        cache_file = os.path.join(test_workspace, CACHE_FILE_NAME)
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"✅ 成功提取到单片机型号: {data.get('device')}")
        
        if os.path.exists(result_path):
            print(f"📦 状态: 文件已存在，大小: {os.path.getsize(result_path)/1024:.1f} KB")
        else:
            print(f"⚠️ 状态: 文件暂不存在 (可能需要先在 Keil 中编译一次 build_project)")
            
    except Exception as err:
        print(f"\n❌ 解析失败: {err}")