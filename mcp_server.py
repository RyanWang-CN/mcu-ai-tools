#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
华大单片机 HIL 全局自动化网关 (Global MCP Server)
存放位置：D:/MCU_AI_Tools/mcp_server.py 
"""
import subprocess
import os
import json
from mcp.server.fastmcp import FastMCP

# 初始化 MCP 服务器
mcp = FastMCP("HDSC_HIL_Global")

# 获取工具箱的绝对根目录 (D:\MCU_AI_Tools)
TOOLS_ROOT = os.path.dirname(os.path.abspath(__file__))

def run_module(module_name, extra_args=None):
    """全局调用执行器：通过包名(-m)调用子文件夹中的脚本"""
    cmd_list = ["python", "-u", "-m", module_name]
    
    if extra_args:
        cmd_list.extend(extra_args)
        
    try:
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        # 【关键 1】：强行把 D:\MCU_AI_Tools 加入环境变量
        # 这样无论脚本在哪，都能顺利 from core.mcu_mem_ctrl import xxx
        if 'PYTHONPATH' in env:
            env['PYTHONPATH'] = f"{TOOLS_ROOT};{env['PYTHONPATH']}"
        else:
            env['PYTHONPATH'] = TOOLS_ROOT

        # 【关键 2】：cwd 必须是 os.getcwd() 
        # 这保证了脚本运行在当前打开的雷达工程目录（如 try - just_play）中
        # 从而能精准找到工程专属的 project_config.yaml 和 .hil_symbols.json
        result = subprocess.run(
            cmd_list, 
            capture_output=True, 
            text=True, 
            encoding='utf-8',
            cwd=os.getcwd(), 
            stdin=subprocess.DEVNULL,                
            creationflags=subprocess.CREATE_NO_WINDOW,   
            timeout=150,
            env=env                                      
        )
        
        stdout_str = result.stdout.strip() if result.stdout else ""
        stderr_str = result.stderr.strip() if result.stderr else ""
        
        if result.returncode != 0:
            error_msg = stderr_str or stdout_str or "Unknown Error"
            return json.dumps({
                "status": "error", 
                "message": f"Module {module_name} crashed (Code: {result.returncode}).\nLog:\n{error_msg}"
            }, ensure_ascii=False)

        return stdout_str or stderr_str or '{"status": "success", "message": "Executed with empty output"}'
        
    except subprocess.TimeoutExpired:
        return json.dumps({"status": "error", "message": f"Subprocess timeout while executing {module_name}"})
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Failed to call {module_name}: {str(e)}"})

# ==================== 1. 基建与环境平面 ====================

@mcp.tool()
def init_project_config() -> str:
    """自动嗅探工程和编译产物，生成 project_config.yaml。"""
    return run_module("core.auto_config_builder")

@mcp.tool()
def update_hil_dictionary() -> str:
    """扫描 .map 和 .axf 文件，更新物理内存寻址字典。"""
    return run_module("core.hil_parser")

# ==================== 2. 执行与部署平面 ====================

@mcp.tool()
def build_project() -> str:
    """编译 Keil 工程。修改 C 语言代码后必须调用此工具。"""
    return run_module("skills.build.compile_auto")

@mcp.tool()
def flash_project() -> str:
    """将编译好的 Hex 固件烧录到单片机中。"""
    return run_module("skills.build.flash_auto")

@mcp.tool()
def hard_reset_mcu() -> str:
    """【救援】物理硬复位单片机。"""
    return run_module("skills.build.reset")

# ==================== 3. 交互与感知平面 ====================

@mcp.tool()
def rtt_print(timeout: int = 3) -> str:
    """纯抓取 J-Link RTT 输出日志，不做逻辑判断。"""
    return run_module("skills.perception.monitor_rtt_auto", ["--timeout", str(timeout)])

@mcp.tool()
def rtt_ask(command: str, timeout: int = 3) -> str:
    """向单片机下发 RTT 字符串指令，并监听其回显日志。"""
    return run_module("skills.perception.rtt_exchange_auto", [command, "--timeout", str(timeout)])

@mcp.tool()
def take_sensor_snapshot(duration_ms: int = 500) -> str:
    """阻塞式抓取传感器的纯二进制数据帧，并离线解算返回统计特征。"""
    return run_module("skills.perception.rtt_listener", ["--duration", str(duration_ms)])

# ==================== 4. 物理内存注入平面 ====================

@mcp.tool()

def inject_hil_parameters(payload_json: str) -> str:
    """
    【强制规范】：向单片机动态注入业务参数。
    1. 严禁修改 g_config_version、g_active_idx 等底层控制变量，底层脚本会自动处理热更新握手。
    2. 你只能修改存在于 .hil_symbols.json 的 layout 字典中的业务变量。
    3. payload 必须是标准的 JSON 字符串，例如: '{"threshold": 8000}'。
    """
    """极速向单片机物理内存注入 HIL 测试参数，并执行回读校验。"""
    return run_module("skills.injection.mcp_hil_bridge", [payload_json])

@mcp.tool()
def read_hil_variable(var_name: str) -> str:

    """通过物理内存直接读取单片机中某一个全局变量的当前真实值。"""
    return run_module("core.mcu_mem_ctrl", ["read", var_name])


# ==================== 5. 硬件诊断与自愈平面 ====================

@mcp.tool()
def check_mcu_status() -> str:
    """
    【诊断首选工具】：获取当前单片机 CPU 的物理运行状态 (Running 或 Halted)。
    [AI 触发条件]：当你调用 inject_hil_parameters 出现“超时”报错，或者 rtt_print 突然读不到任何数据时，你必须立刻、首先调用此工具！
    [AI 处置逻辑]：如果返回 "Halted"，说明单片机遇死机，你应当紧接着调用 hard_reset_mcu 尝试自愈复位。
    """
    return run_module("core.mcu_mem_ctrl", ["status"])

@mcp.tool()
def get_hardware_probe_info() -> str:
    """
    【电源/硬件探伤工具】：获取 J-Link 探针的底层物理信息，特别是目标板的实时供电电压 (target_voltage_mV)。
    [AI 触发条件]：当发生底层的通信断连，或者连 status 都查不到时。
    [AI 处置逻辑]：重点检查返回的电压，如果 target_voltage_mV 接近 0，你应当立刻停止测试，并提示人类工程师："物理供电断开，请检查电源线或杜邦线是否松动！"
    """
    return run_module("core.mcu_mem_ctrl", ["probe_info"])

@mcp.tool()
def scan_connected_probes() -> str:
    """
    扫描并返回当前电脑物理 USB 接口上插着的所有 J-Link 仿真器的 SN 序列号。
    """
    return run_module("core.mcu_mem_ctrl", ["list_probes"])

@mcp.tool()
def check_rtt_health() -> str:
    """
    探测单片机内存中 RTT 通道的分配情况。
    [AI 触发条件]：当确认 CPU 是 Running 状态，但 rtt_print 依然抓不到数据时调用。
    [AI 处置逻辑]：如果返回未找到控制块，说明 C 代码中忘了初始化 RTT，请提醒人类修改 C 代码。
    """
    return run_module("core.mcu_mem_ctrl", ["rtt_channels"])





# ==================== 6. 调试平面 (Debug Mode) ====================

@mcp.tool()
def debug_halt() -> str:
    """
    【危险指令】停止单片机运行，并返回当前 PC 指针地址。
    """
    return run_module("core.mcu_mem_ctrl", ["halt"])

@mcp.tool()
def debug_run() -> str:
    """
    【危险指令】恢复单片机运行。
    [AI 策略]：此工具是非阻塞的。如果需要确认程序是否触碰到了之前设置的断点，请在此工具返回后，主动调用 check_mcu_status 查看 CPU 状态，或调用 debug_halt 抓取最新的 PC 指针。
    """
    return run_module("core.mcu_mem_ctrl", ["run"])

@mcp.tool()
def debug_step() -> str:
    """
    【危险指令】执行一条机器指令并返回新的 PC 地址。单片机必须预先处于 halt 状态。
    """
    return run_module("core.mcu_mem_ctrl", ["step"])

@mcp.tool()
def debug_set_breakpoint(target: str) -> str:
    """
    【危险指令】设置硬件断点。
    [参数增强]：target 可以是十六进制物理地址(如 "0x1234")，也可以直接是 C 语言的函数名或全局变量名(如 "main", "Motor_ISR")。系统会自动解析 .map 文件寻址。
    限制：Cortex-M0+ 芯片最多仅支持 4 个硬件断点。
    """
    return run_module("core.mcu_mem_ctrl", ["set_bp", target])

@mcp.tool()
def debug_clear_breakpoint(target: str) -> str:
    """
    【危险指令】移除指定位置的硬件断点。
    [参数增强]：target 支持十六进制地址或 C 语言符号名。
    """
    return run_module("core.mcu_mem_ctrl", ["clear_bp", target])

@mcp.tool()
def debug_clear_all_breakpoints() -> str:
    """
    【危险指令】一键清除单片机上所有的硬件断点。
    [AI 策略]：当收到 M0+ 芯片断点配额已满的报错时，强制调用此工具进行恢复。
    """
    return run_module("core.mcu_mem_ctrl", ["clear_all_bp"])

@mcp.tool()
def debug_run_to_breakpoint(target: str) -> str:
    """
    【首选断点调试工具】自动化狙击式断点。
    [说明]：由于 J-Link 底层会在进程退出时自动清除断点，因此不能分开调用设断点和运行。必须使用此工具！
    [逻辑]：它会在 target (符号名或物理地址) 处设置断点，恢复单片机运行，并阻塞监听最多 3 秒。如果触碰断点将立刻返回命中信息，随后自动清理该断点。
    """
    return run_module("core.mcu_mem_ctrl", ["run_to_bp", target])




if __name__ == "__main__":
    mcp.run()