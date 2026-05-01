#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
华大单片机 RTT 纯抓取脚本 (Attach 模式)
职责：连接目标板，原样抓取指定时间内的 RTT 缓冲区内容并返回 JSON。
不设关键字，不作任何逻辑判断，判断工作交由上层 AI 完成。
"""

import sys
import time
import os
import glob
import json
import argparse
import yaml
import pylink
from pathlib import Path
#name:monitor_rtt_auto.py
EXIT_SUCCESS = 0
EXIT_SYS_ERROR = 1

def find_jlink_dll_fallback():
    env_path = os.environ.get("JLINK_DLL_PATH")
    if env_path and os.path.exists(env_path):
        return env_path
    search_paths = [
        r"C:\Program Files\SEGGER\JLink*\JLink_x64.dll",
        r"C:\Program Files\SEGGER\JLink*\JLinkARM.dll", 
        r"C:\Program Files (x86)\SEGGER\JLink*\JLinkARM.dll",
        r"C:\Keil_v5\ARM\Segger\JLinkARM.dll"
    ]
    for pattern in search_paths:
        matches = glob.glob(pattern)
        if matches:
            return max(matches, key=os.path.getmtime) 
    return None

def monitor_rtt(mcu, speed, rtt_addr, rtt_size, timeout_sec):
    dll_path = find_jlink_dll_fallback()
    if not dll_path:
        return {"status": "error", "message": "J-Link DLL not found."}
        
    jlink = pylink.JLink(lib=pylink.Library(dllpath=dll_path))
    
    try:
        jlink.open()
    except Exception as e:
        return {"status": "error", "message": f"Failed to open J-Link: {e}"}

    collected_log = ""
    
    try:
        jlink.set_tif(pylink.enums.JLinkInterfaces.SWD)
        try:
            jlink.connect(mcu, speed=speed)
        except:
            jlink.connect("Cortex-M0+", speed=speed)
            
        # 纯 Attach 模式，不复位
        search_size = "0x4000" if rtt_size == "0x1000" else rtt_size
        if rtt_addr:
            try:
                jlink.exec_command(f"SetRTTSearchRanges {rtt_addr} {search_size}")
            except:
                pass

        for _ in range(40):
            try:
                try: jlink.rtt_stop() 
                except: pass
                jlink.rtt_start()
                jlink.rtt_read(0, 1)
                break
            except:
                pass
            time.sleep(0.05)
            
    except Exception as e:
        return {"status": "error", "message": "Hardware connection failed", "details": str(e)}

    # 核心逻辑：无脑抓取 timeout_sec 秒
    start_time = time.time()
    try:
        while (time.time() - start_time) < timeout_sec:
            try:
                data = jlink.rtt_read(0, 1024)
                if data:
                    text = bytes(data).decode('utf-8', errors='ignore')
                    collected_log += text
            except Exception:
                pass 
            time.sleep(0.05) 
            
        # 抓取结束，无论有没有内容，都正常返回
        clean_log = collected_log.strip()
        if clean_log:
            return {
                "status": "success",
                "message": f"Successfully captured RTT logs for {timeout_sec}s.",
                "output_log": clean_log
            }
        else:
            return {
                "status": "success", # 注意这里依然是 success，因为脚本执行没报错
                "message": f"Listened for {timeout_sec}s, but RTT buffer was empty.",
                "output_log": ""
            }

    finally:
        try:
            jlink.rtt_stop()
            jlink.close()
        except:
            pass

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=3, help="Duration to listen (seconds)")
    parser.add_argument("--config", default="project_config.yaml")
    args = parser.parse_args()

    mcu = "HC32L021"
    speed = 4000
    rtt_addr = "0x20000000"
    rtt_size = "0x4000"
    timeout = args.timeout

    try:
        if Path(args.config).exists():
            with open(args.config, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f)
                if cfg:
                    if 'hardware' in cfg:
                        mcu = cfg['hardware'].get('mcu', mcu)
                        speed = cfg['hardware'].get('jlink_speed', speed)
                    if 'verify' in cfg:
                        rtt_addr = cfg['verify'].get('rtt_address', rtt_addr)
                        rtt_size = cfg['verify'].get('rtt_size', rtt_size)
    except Exception as e:
        print(json.dumps({"status": "error", "message": f"Config error: {e}"}))
        sys.exit(EXIT_SYS_ERROR)

    result_json = monitor_rtt(mcu, speed, rtt_addr, rtt_size, timeout)
    
    print(json.dumps(result_json, ensure_ascii=False, indent=2))
    sys.exit(EXIT_SUCCESS if result_json["status"] == "success" else EXIT_SYS_ERROR)

if __name__ == "__main__":
    main()