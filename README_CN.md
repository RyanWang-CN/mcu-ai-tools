# MCU AI Tools

> AI 驱动的单片机自动化网关 — 通过自然语言控制、调试和测试嵌入式系统。

MCU AI Tools 通过 [MCP 协议](https://modelcontextprotocol.io/) 将 AI 助手（Claude Code、Roo Code 等）与单片机硬件连接起来。它把 AI 变成嵌入式开发的"大脑"，能够完成编译固件、烧录、传感器数据读取、HIL 测试参数注入、硬件调试等操作 — 全通过自然语言指令完成。

## 架构

```
+-------------------+     +-------------------+     +------------------+
|   AI 大脑层       | --> |  MCP 技能网关     | --> |   MCU 硬件       |
| (Claude/Roo Code) |     | (FastMCP 服务端)  |     | (华大 HC32 系列) |
+-------------------+     +-------------------+     +------------------+
```

三类技能以 MCP Tool 的形式暴露给 AI：

| 类别 | 功能 |
|------|------|
| **查阅 (Knowledge RAG)** | 引脚图、SDK 参考手册 |
| **动作 (Actions)** | 初始化工程配置、编译烧录固件、硬复位、HIL 参数注入 |
| **感知 (Sensors)** | RTT 日志捕获、双向 RTT 通信、传感器快照分析、实时变量读取 |

## 软硬件要求

### 硬件
- **MCU**: 华大 HC32 系列（已实测 HC32F460、HC32L021）
- **调试器**: SEGGER J-Link（任意型号）
- **目标板**: 华大单片机开发板或自研 PCB

### 软件
- Python 3.10+
- [SEGGER J-Link Software](https://www.segger.com/downloads/jlink/)（v7.x+）
- [Keil MDK](https://www.keil.com/download/product/) v5（用于编译和烧录）
- 支持 MCP Tool 的 AI 助手（Claude Code、Roo Code 等）

## 安装

```bash
# 克隆仓库
git clone https://github.com/<你的用户名>/mcu-ai-tools.git
cd mcu-ai-tools

# 创建并激活虚拟环境
python -m venv venv
# Windows:
.\venv\Scripts\activate
# 或在 PowerShell: .\venv\Scripts\Activate.ps1

# 安装依赖
pip install -r requirements.txt
```

Windows 用户也可直接双击 `setup.bat` 一键完成上述操作。

## 配置

### 1. 环境变量（可选）
如果用 LlamaCloud 的 PDF 解析功能，复制 `.env.example` 为 `.env` 并填入 API Key：
```bash
copy .env.example .env
```

### 2. 工程初始化
进入你的 Keil 工程目录，依次执行：

```bash
# 自动嗅探工程结构，生成配置文件
python -m core.auto_config_builder

# 扫描 .map/.axf 生成 HIL 物理内存字典
python -m core.hil_parser
```

## 使用流程

### 启动 MCP Server
```bash
python mcp_server.py
```

### MCP 工具一览

| 工具 | 说明 |
|------|------|
| `init_project_config` | 自动嗅探工程结构，生成 YAML 配置 |
| `update_hil_dictionary` | 扫描 .map/.axf，更新物理内存寻址字典 |
| `build_project` | 编译 Keil MDK 工程 |
| `flash_project` | 烧录 Hex 固件到单片机 |
| `hard_reset_mcu` | 物理硬复位单片机 |
| `rtt_print` | 抓取 J-Link RTT 输出日志 |
| `rtt_ask` | 向单片机下发 RTT 指令并监听回显 |
| `take_sensor_snapshot` | 阻塞式抓取传感器二进制数据帧，离线解算统计特征 |
| `inject_hil_parameters` | 向单片机物理内存热注入 HIL 测试参数 |
| `read_hil_variable` | 读取单片机中全局变量的当前值 |
| `check_mcu_status` | 检查单片机 CPU 运行状态（Running/Halted） |
| `get_hardware_probe_info` | 获取 J-Link 探针信息（含目标板电压） |
| `scan_connected_probes` | 扫描 USB 接口上所有 J-Link 仿真器 |
| `check_rtt_health` | 探测单片机内存中 RTT 通道分配情况 |

### 调试工具

| 工具 | 说明 |
|------|------|
| `debug_run` | 恢复单片机运行 |
| `debug_halt` | 暂停单片机并返回 PC 指针 |
| `debug_step` | 单步执行一条机器指令 |
| `debug_set_breakpoint` | 设置硬件断点（支持地址或符号名） |
| `debug_clear_breakpoint` | 移除硬件断点 |
| `debug_clear_all_breakpoints` | 一键清除所有硬件断点 |
| `debug_run_to_breakpoint` | 设断点后恢复运行，阻塞等待命中后自动清理 |

## HIL 热注入

HIL 子系统实现了**不停止单片机运行**的参数热替换机制，采用三阶段原子化注入策略：

1. **克隆 (Clone)** — 读取当前激活的配置块，全量拷贝到备用缓冲区
2. **差分 (Delta)** — 只写入改动的参数
3. **提交 (Commit)** — 通过协议号握手原子切换版本

你的单片机固件需要包含 HIL 注入底座代码（详见目标工程中的 `HIL/` 目录）。

## 项目结构

```
├── mcp_server.py              # MCP 服务入口
├── core/                      # 基建引擎层
│   ├── mcu_mem_ctrl.py        # J-Link 物理内存驱动
│   ├── hil_parser.py          # DWARF/.map 解析器（展平嵌套结构体）
│   ├── keil_parser.py         # Keil 工程 XML 解析器
│   ├── auto_config_builder.py # 自动配置构建
│   └── doc_parser.py          # PDF 文档清洗（LlamaCloud）
├── skills/
│   ├── build/                 # 编译、烧录、复位
│   ├── injection/             # HIL 参数注入
│   ├── perception/            # RTT 监控、双向通信
│   └── rag/                   # 知识检索（预留）
├── tests/                     # 单元测试 (pytest)
│   ├── conftest.py
│   ├── elf_builder.py
│   ├── test_hil_parser.py
│   ├── test_keil_parser.py
│   ├── test_mcu_mem_ctrl.py
│   └── samples/
├── .github/workflows/         # CI (GitHub Actions)
│   └── test.yml
├── knowledge_base/            # MCU 参考手册（SVD 文件）
├── docs/                      # 文档
├── build_kb.py                # 知识库增量构建器
├── setup.bat                  # Windows 一键安装脚本 (CMD)
├── setup.ps1                  # Windows 一键安装脚本 (PowerShell)
├── requirements.txt           # Python 依赖清单
└── LICENSE
```

## 许可

[MIT](LICENSE)
