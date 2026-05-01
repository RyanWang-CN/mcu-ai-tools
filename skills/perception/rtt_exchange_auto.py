#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
华大单片机 RTT 交互脚本 (修复版)
关键修复：数据格式转换、RTT地址显式指定、增强时序控制
"""
import sys, time, os, glob, json, argparse, pylink
#name:rtt_exchange_auto.py
def find_jlink_dll():
    paths = [
        r"C:\Program Files\SEGGER\JLink*\JLink_x64.dll",
        r"C:\Program Files\SEGGER\JLink*\JLinkARM.dll",
        r"C:\Keil_v5\ARM\Segger\JLinkARM.dll"
    ]
    for p in paths:
        m = glob.glob(p)
        if m:
            return max(m, key=os.path.getmtime)
    return None

def rtt_exchange(mcu, speed, command, timeout_sec, rtt_block_addr=None):
    """
    rtt_block_addr: RTT控制块地址，从map文件查找 _SEGGER_RTT 符号获得
                   例如：0x20000100 (必须根据实际map文件填写！)
    """
    dll = find_jlink_dll()
    if not dll:
        return {"status": "error", "message": "J-Link DLL missing"}

    jlink = pylink.JLink(lib=pylink.Library(dllpath=dll))
    
    try:
        jlink.open()
        jlink.set_tif(pylink.enums.JLinkInterfaces.SWD)
        
        # 连接目标
        try:
            jlink.connect(mcu, speed=speed)
        except:
            jlink.connect("Cortex-M0+", speed=speed)
        
        # 确保目标运行（关键！）
        if jlink.halted():
            jlink.go()
            time.sleep(0.1)  # 给单片机启动时间
        
        # ========== RTT 启动（关键修复）==========
        # 方式1：如果知道RTT控制块地址（推荐，最稳定）
        if rtt_block_addr:
            jlink.rtt_start(rtt_block_addr)
        else:
            # 方式2：自动搜索，但设置正确的搜索范围
            # HC32L021 RAM: 0x20000000 - 0x20004000 (16KB)
            try:
                jlink.exec_command("SetRTTSearchRanges 0x20000000 0x4000")
            except:
                pass
            jlink.rtt_start()
        
        # 等待RTT控制块被发现（轮询检查）
        max_retries = 50
        for i in range(max_retries):
            try:
                num_up = jlink.rtt_get_num_up_buffers()
                num_down = jlink.rtt_get_num_down_buffers()
                if num_up > 0 and num_down > 0:
                    break
            except pylink.errors.JLinkRTTException:
                pass
            time.sleep(0.05)
        else:
            return {"status": "error", "message": "RTT control block not found, check if MCU has initialized RTT"}
        
        # 清空历史残留数据
        try:
            jlink.rtt_read(0, 4096)
        except:
            pass
        
        # ========== 关键修复：正确的数据格式 ==========
        # pylink 要求 list of ints，不是 bytes！
        # 不再添加 \r\n，仅发送原始命令
        cmd_bytes = list(bytearray(command.encode('utf-8')))
        
        # 分批写入（防止超过down buffer大小，默认通常16-64字节）
        buffer_size = 64  # 根据 SEGGER_RTT_Conf.h 中的 BUFFER_SIZE_DOWN 调整
        bytes_written = 0
        
        while bytes_written < len(cmd_bytes):
            chunk = cmd_bytes[bytes_written:bytes_written + buffer_size]
            written = jlink.rtt_write(0, chunk)
            if written == 0:
                return {"status": "error", "message": "RTT write failed, down buffer may be full or not configured"}
            bytes_written += written
            time.sleep(0.02)  # 给单片机处理时间
        
        # ========== 关键修复：等待单片机响应 ==========
        # 第一阶段：给单片机处理命令和执行printf的时间
        time.sleep(0.1)  # 100ms 基础处理时间
        
        # 第二阶段：持续轮询读取，直到超时
        start_t = time.time()
        log_parts = []
        
        while (time.time() - start_t) < timeout_sec:
            try:
                # 每次读取1024字节
                rx = jlink.rtt_read(0, 1024)
                if rx:
                    # rx 是 list of ints，转换为bytes再解码
                    chunk = bytes(rx).decode('utf-8', errors='ignore')
                    log_parts.append(chunk)
                    
                    # 如果检测到提示符或特定结束标记，可提前退出
                    # if ">" in chunk or "OK" in chunk:
                    #     break
            except Exception as e:
                pass
            
            time.sleep(0.05)  # 50ms轮询间隔
        
        full_log = "".join(log_parts)
        
        return {
            "status": "success",
            "message": f"Sent '{command}' successfully",
            "output_log": full_log.strip(),
            "bytes_sent": bytes_written
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}
        
    finally:
        try:
            jlink.rtt_stop()
            jlink.close()
        except:
            pass

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("command", type=str)
    p.add_argument("--timeout", type=int, default=3)
    p.add_argument("--rtt-addr", type=lambda x: int(x, 0), default=None,
                   help="RTT control block address, e.g., 0x20000100")
    args = p.parse_args()
    
    res = rtt_exchange("HC32L021", 4000, args.command, args.timeout, args.rtt_addr)
    print(json.dumps(res, ensure_ascii=True))
    sys.exit(0 if res["status"] == "success" else 1)
