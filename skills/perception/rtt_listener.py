#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HIL 自动化框架 - 模块 4：AI 专用传感器快照提取器 (Snapshot Mode)
职责：按需启动，获取全局锁，阻塞式抓取 RTT 纯二进制流，离线提纯特征，单次输出 JSON。
"""

import sys
import os
import time
import json
import struct
import glob
import re
import argparse
import statistics
import pylink

# 尝试引入跨进程文件锁
try:
    from filelock import FileLock, Timeout
    HAS_FILELOCK = True
except ImportError:
    HAS_FILELOCK = False
    print(json.dumps({"status": "warning", "message": "Missing 'filelock' library. Multi-process J-Link collision may occur. Run 'pip install filelock'."}))

FRAME_SIZE = 70
CACHE_FILE_NAME = ".hil_cache.json"
LOCK_FILE_NAME = ".jlink_hardware.lock"

# ================= 1. 基建：型号识别 =================
def get_target_device(proj_dir="."):
    """智能获取目标单片机型号"""
    cache_path = os.path.join(proj_dir, CACHE_FILE_NAME)
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f).get("device", "Cortex-M0+")
        except: pass

    uv_files = glob.glob(os.path.join(proj_dir, "*.uvprojx"))
    if uv_files:
        try:
            with open(uv_files[0], 'r', encoding='utf-8', errors='ignore') as f:
                match = re.search(r'<Device>([^<]+)</Device>', f.read(), re.IGNORECASE)
                if match: return match.group(1).strip()
        except: pass
    
    return "Cortex-M0+"

# ================= 2. 核心：抓取与特征离线解算 =================
def _execute_snapshot(duration_ms, proj_dir):
    """底层的实际抓取逻辑，被锁包裹"""
    device_name = get_target_device(proj_dir)
    jlink = pylink.JLink()
    
    try:
        jlink.open()
        jlink.set_tif(pylink.enums.JLinkInterfaces.SWD)
        # 兼容性连接，防止精确型号连不上
        try:
            jlink.connect(device_name, speed=4000)
        except:
            jlink.connect("Cortex-M0+", speed=4000)
    except Exception as e:
        return {"status": "error", "message": f"硬件连接失败: {e}"}

    # 【防死机校验】如果系统意外挂起，强制重启运行并等待
    if jlink.halted():
        jlink.go()
        time.sleep(0.1) # 等待 C 语言端 RTT 初始化完成
        
    try:
        # HC32L021 的 RAM 范围，设置搜索区间加速寻找 RTT 控制块
        try: jlink.exec_command("SetRTTSearchRanges 0x20000000 0x4000")
        except: pass
        jlink.rtt_start()
    except Exception as e:
        jlink.close()
        return {"status": "error", "message": f"RTT启动失败: {e}"}

    # ================= [阶段 1] 闭眼狂吸 (纯物理隔离) =================
    duration_sec = duration_ms / 1000.0
    start_time = time.time()
    raw_buffer = bytearray()
    
    # 清空可能存在的历史残留脏数据
    try: jlink.rtt_read(0, 4096)
    except: pass
    
    while time.time() - start_time < duration_sec:
        try:
            chunk = jlink.rtt_read(0, 4096)
            if chunk:
                raw_buffer.extend(bytes(chunk))
        except:
            pass
        # 极速轮询，只让出 2ms 给系统，防止 RTT 向上缓冲区溢出丢包
        time.sleep(0.002) 

    # 抓取结束，光速断开，把 J-Link 释放给其它脚本
    try:
        jlink.rtt_stop()
        jlink.close()
    except:
        pass

    # ================= [阶段 2] 离线解包与对齐 =================
    sync_head = b'\xaa\xaa'
    sync_tail = b'\x55\x55'
    
    p1_peaks = []
    p2_peaks = []
    
    buffer = raw_buffer
    while len(buffer) >= FRAME_SIZE:
        head_idx = buffer.find(sync_head)
        if head_idx == -1: 
            break
        
        if head_idx > 0:
            buffer = buffer[head_idx:]
            continue
            
        if len(buffer) >= FRAME_SIZE:
            frame_bytes = buffer[:FRAME_SIZE]
            if frame_bytes[-2:] == sync_tail:
                try:
                    # 解包 35 个 unsigned short (< 符号代表小端模式)
                    data_tuple = struct.unpack('<' + 'H'*35, frame_bytes)
                    # 提取单帧内 P1(18位) 和 P2(15位) 的最大能量峰值
                    p1_peaks.append(max(data_tuple[1:19]))
                    p2_peaks.append(max(data_tuple[19:34]))
                except:
                    pass
                buffer = buffer[FRAME_SIZE:]
            else:
                buffer = buffer[2:] # 帧尾不对，向后错位寻找

    # ================= [阶段 3] 降维提纯 (统计学特征) =================
    if len(p1_peaks) < 5:
        return {
            "status": "error",
            "message": "有效帧极少。请检查：1. MCU是否死机; 2. C端RTT频率是否太低; 3. 数据结构长度是否严格为70字节。",
            "frames_captured": len(p1_peaks)
        }
        
    return {
        "status": "success",
        "duration_ms": duration_ms,
        "frames_analyzed": len(p1_peaks),
        "P1": {
            "min": min(p1_peaks),
            "max": max(p1_peaks),
            "mean": round(statistics.mean(p1_peaks), 1),
            "variance": round(statistics.variance(p1_peaks), 1) if len(p1_peaks) > 1 else 0,
            "noise_band": max(p1_peaks) - min(p1_peaks)
        },
        "P2": {
            "min": min(p2_peaks),
            "max": max(p2_peaks),
            "mean": round(statistics.mean(p2_peaks), 1),
            "variance": round(statistics.variance(p2_peaks), 1) if len(p2_peaks) > 1 else 0,
            "noise_band": max(p2_peaks) - min(p2_peaks)
        }
    }

def take_sensor_snapshot(duration_ms, proj_dir):
    """带全局互斥锁的包裹函数，彻底防止 J-Link 碰撞"""
    if HAS_FILELOCK:
        lock_path = os.path.join(proj_dir, LOCK_FILE_NAME)
        lock = FileLock(lock_path, timeout=15) # 最多等待别的进程用完 15 秒
        try:
            with lock:
                result = _execute_snapshot(duration_ms, proj_dir)
        except Timeout:
            result = {"status": "error", "message": "获取J-Link全局锁超时。可能被其它脚本卡死了。"}
    else:
        # 如果没装 filelock，就裸跑
        result = _execute_snapshot(duration_ms, proj_dir)
        
    # 【铁律】仅有一行 JSON 输出
    print(json.dumps(result, ensure_ascii=False, separators=(',', ':')))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HIL AI-Native 传感器静态快照器")
    parser.add_argument("--duration", type=int, default=500, help="抓取时长(毫秒)，默认 500ms")
    parser.add_argument("--dir", type=str, default=".", help="工程根目录")
    args = parser.parse_args()
    
    # 强制让系统以 UTF-8 输出，防止 Windows 控制台乱码导致 AI 解析失败
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
        
    take_sensor_snapshot(args.duration, args.dir)