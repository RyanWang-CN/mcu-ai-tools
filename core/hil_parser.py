#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import glob
import time
import json
from elftools.elf.elffile import ELFFile
import yaml  # <--- 新增：用于读取 YAML
# hil_parser.py
SYMBOLS_CACHE_FILE = ".hil_symbols.json"
CONFIG_FILE = "project_config.yaml"  # <--- 增加这行，告诉脚本去哪读型号

def get_whitelist_from_map(map_path):
    """从 .map 文件中提取带有 .hil_expose 标签的安全变量名单"""
    whitelist = set()
    print(f"-> 正在解析 Map 文件: {map_path}")
    
    with open(map_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if '.hil_expose' in line and 'Data' in line:
                parts = line.strip().split()
                if parts:
                    whitelist.add(parts[0]) # 提取变量名
    return whitelist

def get_struct_die(die):
    """递归穿透外壳，直达底层 Struct 定义"""
    current_die = die
    while 'DW_AT_type' in current_die.attributes:
        current_die = current_die.get_DIE_from_attribute('DW_AT_type')
        if current_die.tag == 'DW_TAG_structure_type':
            return current_die
    return None


def parse_struct_layout_recursive(struct_die, base_offset=0):
    """
    递归解析 DWARF 结构体：
    无限向下穿透嵌套结构体，并将相对偏移量累加为绝对偏移量，最终拍平输出。
    """
    layout = {}
    for child in struct_die.iter_children():
        if child.tag == 'DW_TAG_member':
            # 获取成员变量名
            m_name_attr = child.attributes.get('DW_AT_name')
            m_name = m_name_attr.value.decode('utf-8') if m_name_attr else None
            
            # 计算绝对物理偏移：父节点基准偏移 + 当前成员的相对偏移
            loc_attr = child.attributes.get('DW_AT_data_member_location')
            current_abs_offset = base_offset
            if loc_attr:
                rel_offset = loc_attr.value if isinstance(loc_attr.value, int) else loc_attr.value[1]
                current_abs_offset += rel_offset
            
            # 核心机制：检查这个成员是不是另一个嵌套结构体？
            child_struct_die = get_struct_die(child)
            if child_struct_die:
                # 是嵌套结构体！把当前的绝对偏移传进去，递归往下钻
                nested_layout = parse_struct_layout_recursive(child_struct_die, current_abs_offset)
                layout.update(nested_layout) # 把底层的字典拍平合并上来
            else:
                # 是基础数据类型（int, float 等），直接记录
                if m_name:
                    layout[m_name] = current_abs_offset
    return layout



def extract_dwarf_by_whitelist(axf_path, whitelist_names):
    """解析 AXF 文件的 DWARF 信息，提取物理地址与结构体偏移"""
    symbols_dict = {}
    
    with open(axf_path, 'rb') as f:
        elffile = ELFFile(f)
        
        # 1. 提取基础物理地址
        symtab = elffile.get_section_by_name('.symtab')
        if symtab:
            for symbol in symtab.iter_symbols():
                sym_name = symbol.name
                if sym_name in whitelist_names:
                    symbols_dict[sym_name] = {
                        "address": symbol['st_value'],
                        "size": symbol['st_size'],
                        "is_struct": False
                    }
                    
        # 2. 精准解剖结构体布局
        if elffile.has_dwarf_info():
            dwarfinfo = elffile.get_dwarf_info()
            for CU in dwarfinfo.iter_CUs():
                for die in CU.iter_DIEs():
                    if die.tag == 'DW_TAG_variable':
                        name_attr = die.attributes.get('DW_AT_name')
                        if not name_attr: continue
                        
                        var_name = name_attr.value.decode('utf-8')
                        
                        if var_name in whitelist_names and var_name in symbols_dict:
                            struct_die = get_struct_die(die)
                            if struct_die:
                                struct_size = struct_die.attributes.get('DW_AT_byte_size').value if 'DW_AT_byte_size' in struct_die.attributes else 0
                                
                                # 【改造核心】：直接调用递归函数，一键计算并展平所有嵌套偏移！
                                layout = parse_struct_layout_recursive(struct_die, 0)
                                            
                                symbols_dict[var_name]["is_struct"] = True
                                symbols_dict[var_name]["element_size"] = struct_size
                                symbols_dict[var_name]["layout"] = layout
                                print(f"  🧬 成功解析结构体 [{var_name}]，单体大小: {struct_size} 字节")

    return symbols_dict

def generate_symbols_json(project_dir):
    start_time = time.time()
    print("[基建-HIL] 正在启动双核解析引擎 (Map + AXF) ...")
    
    # 1. 直接读取大管家配好的 YAML 获取型号
    device_name = "Cortex-M0+" # 默认兜底
    config_path = os.path.join(project_dir, CONFIG_FILE)
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
                if config_data and "hardware" in config_data and "mcu" in config_data["hardware"]:
                    device_name = config_data["hardware"]["mcu"]
        except Exception:
            pass

    # 2. 搜索物理文件 (被我误删的代码加回来了)
    map_files = glob.glob(os.path.join(project_dir, "**", "*.map"), recursive=True)
    axf_files = glob.glob(os.path.join(project_dir, "**", "*.axf"), recursive=True)
    
    if not map_files or not axf_files:
        print("❌ 找不到 .map 或 .axf 文件！请确保工程已成功编译。")
        return
        
    latest_map = max(map_files, key=os.path.getmtime)
    latest_axf = max(axf_files, key=os.path.getmtime)
    
    # 照妖镜：打印到底抓了哪个文件
    print(f"-> [Debug] 最终锁定的 Map 文件: {latest_map}")
    print(f"-> [Debug] 最终锁定的 AXF 文件: {latest_axf}")

    # 3. 解析与提取
    try:
        whitelist = get_whitelist_from_map(latest_map)
        symbols = {} # 关键1：提前初始化空字典
        
        if not whitelist:
            # 关键2：干掉 return！改成打印警告，让程序继续往下走
            print("⚠️ 警告: 未在 Map 中发现 .hil_expose 变量，字典将仅包含元数据。")
        else:
            print(f"🎯 提取到 {len(whitelist)} 个白名单变量: {', '.join(whitelist)}")
            symbols = extract_dwarf_by_whitelist(latest_axf, whitelist)
        
        # 关键3：无论上面有没有提取到变量，都强行注入 __META__ 节点
        symbols["__META__"] = {
            "device": device_name,
            "map_source": latest_map,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        }
        
        # 关键4：强制执行写入
        cache_path = os.path.join(project_dir, SYMBOLS_CACHE_FILE)
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(symbols, f, indent=4)
            
        print(f"\n✅ HIL 物理隔离字典已生成: {SYMBOLS_CACHE_FILE} (耗时: {(time.time() - start_time) * 1000:.1f} ms)")
    except Exception as e:
        print(f"❌ 解析失败: {e}")

if __name__ == "__main__":
    # 坚决干掉 input()，改用 sys.argv 接收自动化网关传来的路径
    test_workspace = sys.argv[1] if len(sys.argv) > 1 else "."
    generate_symbols_json(test_workspace)