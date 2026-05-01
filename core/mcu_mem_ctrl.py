#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HIL 自动化框架 - 模块 3：内存级变量控制器 (J-Link Injector)
职责：基于 Layer 2 的字典缓存，通过 J-Link 物理总线直接读写单片机 RAM。
"""

import os
import sys
import json
import glob
import argparse
import pylink
#name:mcu_mem_ctrl.py
SYMBOLS_CACHE_FILE = ".hil_symbols.json"

def find_jlink_dll():
    """复用之前极其稳定的 DLL 查找逻辑"""
    paths = [
        r"C:\Program Files\SEGGER\JLink*\JLink_x64.dll",
        r"C:\Program Files\SEGGER\JLink*\JLinkARM.dll",
        r"C:\Keil_v5\ARM\Segger\JLinkARM.dll"
    ]
    for p in paths:
        m = glob.glob(p)
        if m: return max(m, key=os.path.getmtime)
    return None

class MCUInjector:
    def __init__(self, project_dir):
        self.project_dir = os.path.abspath(project_dir)
        self.symbols = self._load_symbols()
        self.jlink = None

    def _load_symbols(self):
        cache_path = os.path.join(self.project_dir, SYMBOLS_CACHE_FILE)
        if not os.path.exists(cache_path):
            raise FileNotFoundError(f"[错误] 符号字典缺失！请先编译工程并运行 map_parser.py\n预期路径: {cache_path}")
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    # 【核心修改 1】：不再写死 HC32L021，而是从字典的 __META__ 中动态读取单片机型号
    def connect(self):
        """动态连接策略：字典 > YAML > 通用内核"""
        target_mcu = "Cortex-M0+" # 最底层兜底
        
        # 1. 优先从解析器生成的字典中读取型号
        # 注意：兼容有些框架把 symbols 写在 self 里的情况
        if hasattr(self, 'symbols') and self.symbols and "__META__" in self.symbols:
            target_mcu = self.symbols["__META__"].get("device", target_mcu)
        
        # 2. 如果字典里没拿到，尝试去项目总体配置文件里捞
        if target_mcu == "Cortex-M0+" and hasattr(self, 'config') and self.config:
            target_mcu = self.config.get("hardware", {}).get("mcu", "Cortex-M0+")

        print(f"-> 尝试连接目标 MCU: {target_mcu}")
        try:
            # 【核心修复】：把我不小心删掉的 J-Link 实例化加回来！
            if not hasattr(self, 'jlink') or self.jlink is None:
                self.jlink = pylink.JLink()
                
            self.jlink.open()
            self.jlink.set_tif(pylink.enums.JLinkInterfaces.SWD)
            # 尝试用精准型号连接（以解锁特定 Flash/RAM 算法）
            self.jlink.connect(target_mcu, speed=4000)
            print(f"✅ J-Link 物理连接成功！")
        except pylink.errors.JLinkException as e:
            print(f"⚠️ 精准型号连接失败 ({e})，正在降级为通用 {target_mcu} 内核盲连...")
            try:
                self.jlink.connect("Cortex-M0+", speed=4000)
                print(f"✅ J-Link 降级连接成功！")
            except Exception as fallback_e:
                raise RuntimeError(f"❌ 致命错误：J-Link 物理连接彻底失败。{fallback_e}")

    def disconnect(self):
        if self.jlink:
            self.jlink.close()

    def write_var(self, var_name, value):
        """精准写入内存"""
        if var_name not in self.symbols:
            raise ValueError(f"[错误] 变量 '{var_name}' 不存在于符号字典中，是不是名字拼错了？")
            
        sym = self.symbols[var_name]
        addr = sym['address']
        size = sym['size']

        # 智能适配写入位宽
        if size == 4:
            self.jlink.memory_write32(addr, [value])
        elif size == 2:
            self.jlink.memory_write16(addr, [value])
        elif size == 1:
            self.jlink.memory_write8(addr, [value])
        else:
            raise TypeError(f"[错误] 不支持对 {size} 字节大小的变量进行注入！")
        
        return addr, size

    def read_var(self, var_name):
        """精准读取内存"""
        if var_name not in self.symbols:
            raise ValueError(f"[错误] 变量 '{var_name}' 不存在于符号字典中！")
            
        sym = self.symbols[var_name]
        addr = sym['address']
        size = sym['size']

        # 智能适配读取位宽
        if size == 4:
            val = self.jlink.memory_read32(addr, 1)[0]
        elif size == 2:
            val = self.jlink.memory_read16(addr, 1)[0]
        elif size == 1:
            val = self.jlink.memory_read8(addr, 1)[0]
        else:
            raise TypeError(f"[错误] 不支持读取 {size} 字节大小的变量！")
            
        return val, addr, size


#新增功能
    def get_status(self):
        """获取当前 MCU 运行状态 (Halted 或 Running)"""
        if not self.jlink or not self.jlink.connected():
            return "Disconnected"
        try:
            # 【修复】：没上电或死机时，halted() 可能会抛出异常
            return "Halted" if self.jlink.halted() else "Running"
        except pylink.errors.JLinkException:
            return "Error: Cannot read CPU state (请检查硬件供电和 SWD 接线)"

    def get_probe_info(self):
        """获取探针详细信息（用于诊断硬件掉电或线缆松动）"""
        if not self.jlink or not self.jlink.connected():
            raise RuntimeError("[错误] 探针未连接")
        
        info = {
            "emulator_sn": getattr(self.jlink, 'serial_number', 'Unknown')
        }
        
        # 安全读取电压
        try:
            info["target_voltage_mV"] = self.jlink.target_voltage
        except Exception:
            info["target_voltage_mV"] = "Read Failed"
            
        # 安全读取 CPU 内核名称
        try:
            info["target_cpu"] = self.jlink.core_name()
        except pylink.errors.JLinkException:
            info["target_cpu"] = "Unknown (Target not responding, 可能是掉电或接线错误)"
            
        return info

    @staticmethod
    def list_probes():
        """静态方法：列出当前电脑插了多少个 J-Link 探针"""
        jlk = pylink.JLink()
        # 【修复】：安全提取 SerialNumber 属性，防止库版本差异报错
        return [getattr(emu, 'SerialNumber', str(emu)) for emu in jlk.connected_emulators()]

    def get_rtt_channels(self):
        """探测当前单片机内存中的 RTT 控制块，返回可用通道数"""
        if not self.jlink or not self.jlink.connected():
            raise RuntimeError("[错误] 探针未连接")
        try:
            self.jlink.rtt_start()
            num_up = self.jlink.rtt_get_num_up_buffers()
            num_down = self.jlink.rtt_get_num_down_buffers()
            return {
                "status": "success",
                "up_channels": num_up,
                "down_channels": num_down
            }
        except Exception as e:
            return {"status": "error", "message": f"未找到 RTT 控制块或通信失败: {str(e)}"}





# ==================== 智能寻址引擎 ====================
    def _resolve_address(self, addr_input):
        """将输入（Hex字符串或C语言符号名）动态解析为十进制原始地址"""
        import re
        import glob
        import os
        
        addr_str = str(addr_input).strip()

        # 1. 已经是绝对物理地址 (0x 开头)
        if addr_str.lower().startswith("0x"):
            return int(addr_str, 16)

        # 2. 检查 .hil_symbols.json 内存字典缓存
        if self.symbols and addr_str in self.symbols:
            return self.symbols[addr_str]['address']

        # 3. 暴力扫盲：去 .map 文件里扒
        map_files = glob.glob(os.path.join(self.project_dir, "**/*.map"), recursive=True)
        if not map_files:
            raise ValueError(f"无法解析符号 '{addr_str}'：非绝对地址，且工程中未找到 .map 文件！")

        latest_map = max(map_files, key=os.path.getmtime)
        
        # 编译防注入正则，精确匹配 Keil Map 文件格式
        pattern = re.compile(rf"^\s*{re.escape(addr_str)}\s+(0x[0-9a-fA-F]+)\s+(Thumb Code|ARM Code|Code|Data|Number)", re.IGNORECASE)

        with open(latest_map, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                match = pattern.search(line)
                if match:
                    return int(match.group(1), 16) # 直接返回最原始的解析地址

        raise ValueError(f"符号解析失败：在字典及 {os.path.basename(latest_map)} 中均未查找到 '{addr_str}'！")



    # ==================== 调试平面 (硬件操作) ====================
    def halt_mcu(self):
        """停止 CPU 执行并抓取 PC 指针"""
        if not self.jlink or not self.jlink.connected(): raise RuntimeError("探针未连接")
        
        if not self.jlink.halted():
            self.jlink.halt()
            
        try:
            pc = self.jlink.register_read(15)
            return f"MCU 已暂停。当前 PC 指针: {hex(pc)}"
        except Exception:
            return "MCU 已暂停，PC 指针读取失败。"

    def run_mcu(self):
        """恢复 CPU 执行 (异步非阻塞，带双重兼容防御)"""
        if not self.jlink or not self.jlink.connected(): raise RuntimeError("探针未连接")
        if not self.jlink.halted(): 
            return "MCU 当前已在运行状态。"
            
        if hasattr(self.jlink, 'go'):
            self.jlink.go()
        elif hasattr(self.jlink, 'restart'):
            self.jlink.restart()
        else:
            raise RuntimeError("当前的 pylink 库缺少恢复执行的接口")
        return "MCU 已恢复运行。"

    def step_mcu(self):
        """单指令步进"""
        if not self.jlink or not self.jlink.connected(): raise RuntimeError("探针未连接")
        if not self.jlink.halted(): raise RuntimeError("步进前必须先执行 halt_mcu 暂停 MCU。")
        
        self.jlink.step()
        try:
            pc = self.jlink.register_read(15)
            return f"单步执行成功。当前 PC 指针: {hex(pc)}"
        except Exception:
            return "单步执行成功。"

    def set_breakpoint(self, target_symbol):
        """设置硬件断点 (终极防弹版)"""
        if not self.jlink or not self.jlink.connected(): raise RuntimeError("探针未连接")
        
        raw_addr = self._resolve_address(target_symbol)
        
        # 【核心护城河】：强制清零 LSB，抹平 Thumb 指令的奇数地址，完美对齐 Cortex-M 硬件比较器
        aligned_addr = raw_addr & ~1
        
        try:
            self.jlink.breakpoint_set(aligned_addr)
            return f"已成功在 '{target_symbol}' (物理对齐地址 {hex(aligned_addr)}) 设置断点。"
        except pylink.errors.JLinkException as e:
            if "limit" in str(e).lower() or "breakpoint" in str(e).lower():
                raise RuntimeError("Cortex-M0+ 硬件断点数量已达上限(最多4个)。请调用 clear_all_bp 清除后重试。")
            raise e

    def clear_breakpoint(self, target_symbol):
        """精确移除断点"""
        if not self.jlink or not self.jlink.connected(): raise RuntimeError("探针未连接")
        
        raw_addr = self._resolve_address(target_symbol)
        aligned_addr = raw_addr & ~1  # 强制对齐寻找 Handle
        
        handle = self.jlink.breakpoint_find(aligned_addr)
        if handle < 0:
            return f"未在 '{target_symbol}' (物理地址 {hex(aligned_addr)}) 找到断点。"
            
        self.jlink.breakpoint_clear(handle)
        return f"已移除 '{target_symbol}' 的断点。"

    def clear_all_breakpoints(self):
        """一键清除所有断点"""
        if not self.jlink or not self.jlink.connected(): raise RuntimeError("探针未连接")
        self.jlink.breakpoint_clear_all()
        return "所有硬件断点已清除。"


    def run_to_breakpoint(self, target_symbol, timeout_s=3):
        """【原子操作】设置断点 -> 恢复运行 -> 阻塞等待命中 -> 清理现场"""
        import time
        if not self.jlink or not self.jlink.connected(): raise RuntimeError("探针未连接")

        # 1. 解析地址并强行对齐
        raw_addr = self._resolve_address(target_symbol)
        aligned_addr = raw_addr & ~1

        # 2. 必须先 halt 才能设断点
        if not self.jlink.halted():
            self.jlink.halt()

        # 3. 设置断点
        try:
            self.jlink.breakpoint_set(aligned_addr)
        except pylink.errors.JLinkException as e:
            raise RuntimeError(f"设置断点失败: {e}")

        # 4. 恢复运行
        if hasattr(self.jlink, 'go'):
            self.jlink.go()
        else:
            self.jlink.restart()

        # 5. 阻塞死等触发
        start_time = time.time()
        triggered = False
        hit_pc = 0

        while time.time() - start_time < timeout_s:
            if self.jlink.halted():
                triggered = True
                try:
                    hit_pc = self.jlink.register_read(15)
                    # ====================================================
                    # 【物理验证专用补丁】
                    print(f"\n[物理验证] 🎯 已命中断点！单片机现已强制挂起！")
                    print(f"[物理验证] 正在执行 6 秒死锁保活，请立刻去看板子/量电压...")
                    print(f"[物理验证] 验证完毕后，请手动在终端按 Ctrl+C 强退本脚本。")
                    time.sleep(6)  # <--- 加在这里！死死攥住 J-Link 不放！
                # ====================================================
                except Exception:
                    pass
                break
            time.sleep(0.1)

        # 6. 无论是否命中，必须打扫战场清除该断点，释放硬件配额
        handle = self.jlink.breakpoint_find(aligned_addr)
        if handle >= 0:
            self.jlink.breakpoint_clear(handle)

        # 7. 返回战报
        if triggered:
            return f"🎯 命中！已在 '{target_symbol}' (物理地址 0x{aligned_addr:X}) 触发断点并暂停 MCU。当前 PC: {hex(hit_pc)}"
        else:
            # 没命中则保持原样，直接返回
            return f"⏳ 超时未命中：在 {timeout_s} 秒的监听期内，代码未能运行到 '{target_symbol}'。"



# ================= 命令行交互入口 =================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="单片机内存与探针诊断工具")
    

    # 完整涵盖 13 个底层指令
    parser.add_argument("action", choices=[
        "read", "write", "status", "probe_info", "list_probes", "rtt_channels",
        "halt", "run", "step", "set_bp", "clear_bp", "clear_all_bp", "run_to_bp"  # <--- 加上它！
    ], help="操作类型")
    
    parser.add_argument("payload", type=str, nargs='?', default="", help="附加参数")
    parser.add_argument("--dir", type=str, default=".", help="Keil工程根目录")
    
    args = parser.parse_args()

    # 静态命令拦截
    if args.action == "list_probes":
        try:
            print(json.dumps({"status": "success", "data": MCUInjector.list_probes()}))
        except Exception as e:
            print(json.dumps({"status": "error", "message": f"扫描探针失败: {str(e)}"}))
        sys.exit(0)

    # 实例化及路由
    injector = None
    try:
        injector = MCUInjector(args.dir)
        injector.connect()
        
        if args.action == "write":
            try:
                write_dict = json.loads(args.payload)
            except json.JSONDecodeError:
                raise ValueError("[错误] write 必须传入合法的 JSON 字符串！")
            results = []
            for v_name, v_val in write_dict.items():
                addr, size = injector.write_var(v_name, v_val)
                results.append(f"{v_name}({hex(addr)})->{v_val}")
            print(json.dumps({"status": "success", "message": f"注入成功: {', '.join(results)}"}))
            
        elif args.action == "read":
            val, addr, size = injector.read_var(args.payload)
            print(json.dumps({"status": "success", "value": val}))
            
        elif args.action == "status":
            print(json.dumps({"status": "success", "cpu_state": injector.get_status()}))
            
        elif args.action == "probe_info":
            print(json.dumps({"status": "success", "probe": injector.get_probe_info()}))
            
        elif args.action == "rtt_channels":
            print(json.dumps(injector.get_rtt_channels()))
            
        elif args.action == "halt":
            print(json.dumps({"status": "success", "message": injector.halt_mcu()}))
            
        elif args.action == "run":
            print(json.dumps({"status": "success", "message": injector.run_mcu()}))
            
        elif args.action == "step":
            print(json.dumps({"status": "success", "message": injector.step_mcu()}))


        elif args.action == "run_to_bp":
            if not args.payload: raise ValueError("必须提供目标符号名或地址")
            print(json.dumps({"status": "success", "message": injector.run_to_breakpoint(args.payload)}))

            
        elif args.action == "set_bp":
            if not args.payload: raise ValueError("必须提供目标地址(Hex)或符号名")
            print(json.dumps({"status": "success", "message": injector.set_breakpoint(args.payload)}))
            
        elif args.action == "clear_bp":
            if not args.payload: raise ValueError("必须提供目标地址(Hex)或符号名")
            print(json.dumps({"status": "success", "message": injector.clear_breakpoint(args.payload)}))
            
        elif args.action == "clear_all_bp":
            print(json.dumps({"status": "success", "message": injector.clear_all_breakpoints()}))

    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False))
        sys.exit(1)
    finally:
        if injector is not None:
            injector.disconnect()