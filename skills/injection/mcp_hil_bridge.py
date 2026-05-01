#!/usr/bin/env python3

# -*- coding: utf-8 -*-

import sys
import os
import json
import time

# 【动态寻址终极修复】：脚本在 skills/injection 下，需要向上退两级回到 MCU_AI_Tools 根目录
TOOL_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if TOOL_ROOT not in sys.path:
    sys.path.insert(0, TOOL_ROOT)

# 从根目录下的 core 文件夹引入注入引擎
from core.mcu_mem_ctrl import MCUInjector



def run_mcp_verification(payload_json_str):

    """

    MCP 标准化注入桥梁：

    1. 固化协议原语，动态匹配多结构体指纹

    2. 【防倒灌】：执行先克隆(Clone)后差分(Delta)的 Ping-Pong 注入策略

    3. 【防死机】：M0+ 内核硬件对齐安全写机制

    """

    result = {"status": "success", "injected": {}, "verified": True, "error_msg": ""}



    try:

        params_to_inject = json.loads(payload_json_str)

        if not isinstance(params_to_inject, dict):

            raise ValueError("入参必须是 JSON 字典格式。")

        

        param_keys = set(params_to_inject.keys())

        if not param_keys:

            raise ValueError("注入参数为空，无法推导目标结构体！")

            

    except Exception as e:

        print(json.dumps({"status": "error", "error_msg": f"JSON解析失败: {e}"}, ensure_ascii=False))

        return



    injector = MCUInjector(project_dir=".") 

    

    try:

        injector.connect()



        # =================【1. 协议预检与指纹锁定】=================

        if "g_config_version" not in injector.symbols or "g_active_idx" not in injector.symbols:

            raise ValueError("未找到协议信号灯 (g_config_version / g_active_idx)！")

            

        ver_addr = injector.symbols["g_config_version"]["address"]

        idx_addr = injector.symbols["g_active_idx"]["address"]



        struct_candidates = {

            name: info for name, info in injector.symbols.items() 

            if isinstance(info, dict) and info.get("is_struct") and "layout" in info

        }



        matched_structs = [

            name for name, info in struct_candidates.items()

            if param_keys.issubset(set(info["layout"].keys()))

        ]



        if len(matched_structs) == 0:

            raise ValueError(f"寻址失败：参数 {list(param_keys)} 不属于任何已暴露的结构体！")

        elif len(matched_structs) > 1:

            raise ValueError(f"寻址歧义：参数同时匹配多个结构体 {matched_structs}！")



        target_struct_name = matched_structs[0]

        struct_info = injector.symbols[target_struct_name]

        base_addr = struct_info["address"]

        elem_size = struct_info["element_size"]

        layout = struct_info["layout"]



        # =================【2. 核心防御：数据全量克隆 (Clone)】=================

        # 读取真实的活动索引与版本号

        real_active_idx = injector.jlink.memory_read8(idx_addr, 1)[0] & 0xFF

        current_ver = injector.jlink.memory_read8(ver_addr, 1)[0] & 0xFF

        

        next_ver = (current_ver + 1) & 0xFF

        target_idx = next_ver & 0x01



        # 如果元素大小一致，执行全量拷贝，防止局部更新导致历史废弃数据倒灌

        if elem_size > 0:

            active_struct_addr = base_addr + (real_active_idx * elem_size)

            target_struct_addr = base_addr + (target_idx * elem_size)

            

            try:

                # 以字节为单位全量读取当前运行的健康数据

                active_data = injector.jlink.memory_read8(active_struct_addr, elem_size)

                # 全量覆盖写入目标 Buffer，将其洗净

                injector.jlink.memory_write8(target_struct_addr, active_data)

                time.sleep(0.005) # 物理内存屏障

            except Exception as e:

                raise ValueError(f"数据克隆失败 (Addr: {hex(active_struct_addr)}): {e}")



        # =================【3. 精准注入：差分写入 (Delta)】=================

        sorted_offsets = sorted(layout.items(), key=lambda x: x[1])

        

        for param_name, target_val in params_to_inject.items():

            target_phys_addr = base_addr + (target_idx * elem_size) + layout[param_name]

            

            curr_pos = [n for n, o in sorted_offsets].index(param_name)

            if curr_pos < len(sorted_offsets) - 1:

                byte_size = sorted_offsets[curr_pos+1][1] - layout[param_name]

            else:

                byte_size = elem_size - layout[param_name]



            bits = byte_size * 8

            mask = (1 << bits) - 1

            val_to_write = int(target_val) & mask



            # 【防死机 & 防截断】：M0+ 内核严禁非对齐访问！

            is_4byte_aligned = (target_phys_addr % 4) == 0

            is_2byte_aligned = (target_phys_addr % 2) == 0



            if byte_size == 4 and is_4byte_aligned:

                injector.jlink.memory_write32(target_phys_addr, [val_to_write])

                read_back = injector.jlink.memory_read32(target_phys_addr, 1)[0]

            elif byte_size == 2 and is_2byte_aligned:

                injector.jlink.memory_write16(target_phys_addr, [val_to_write])

                read_back = injector.jlink.memory_read16(target_phys_addr, 1)[0]

            else:

                # 【终极修复】：如果没有对齐，将数据拆解成单字节数组 (小端模式) 写入

                # 无论 byte_size 是 4 还是 2 还是 1，全部拆开！

                bytes_to_write = [(val_to_write >> (8 * i)) & 0xFF for i in range(byte_size)]

                injector.jlink.memory_write8(target_phys_addr, bytes_to_write)

                

                # 回读时也要按字节读取，并重新拼装成一个大整数

                read_bytes = injector.jlink.memory_read8(target_phys_addr, byte_size)

                read_back = sum(b << (8 * i) for i, b in enumerate(read_bytes))



            time.sleep(0.001)



            if (read_back & mask) != (val_to_write & mask):

                raise ValueError(f"参数 {param_name} 写入校验失败！")



            display_val = read_back - (1 << bits) if read_back >= (1 << (bits - 1)) else read_back

            result["injected"][param_name] = display_val



        # =================【4. 扣动扳机：完成协议】=================

        injector.jlink.memory_write8(ver_addr, [next_ver])

        

        timeout_t = time.time() + 0.5

        while time.time() < timeout_t:

            if injector.jlink.memory_read8(idx_addr, 1)[0] == target_idx:

                break

            time.sleep(0.01)

        else:

            raise ValueError(f"热更新超时！MCU 未响应索引切换 (预期: {target_idx})")



    except Exception as e:

        result["status"], result["verified"], result["error_msg"] = "error", False, str(e)

    finally:

        injector.disconnect()



    print(json.dumps(result, ensure_ascii=False))



if __name__ == "__main__":

    payload = sys.argv[1] if len(sys.argv) > 1 else '{"velocity_min": -10}'

    run_mcp_verification(payload)