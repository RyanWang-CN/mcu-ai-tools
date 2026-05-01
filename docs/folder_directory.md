.\                            <-- 【总指挥部】上位机自动化网关
│
├── mcp_server.py               <-- [AI 交互大脑] MCP 服务端，负责将下方 skills 暴露给 Roo Code 调用
│
├── core\                       <-- [基建引擎层] 干脏活累活的底层工具（只管物理和解析，不懂业务）
│   ├── auto_config_builder.py  # 自动构建配置
│   ├── hil_parser.py           # 物理字典提取器（深度解析 .map 和 .axf 展平 DWARF 嵌套结构体）
│   ├── keil_parser.py          # Keil 工程解析器
│   └── mcu_mem_ctrl.py         # J-Link 物理驱动引擎（安全读写内存，处理对齐）
│
├── skills\                     <-- [业务技能层] 面向具体任务的 API 集合（被 mcp_server 调度）
│   │
│   ├── build\                  <-- 【技能簇：工程构建与部署】
│   │   ├── compile_auto.py     # 自动化调用 Keil 命令行进行编译
│   │   ├── flash_auto.py       # 自动化调用 J-Flash/J-Link 烧录 Hex 固件
│   │   └── reset.py            # 硬件复位控制
│   │
│   ├── injection\              <-- 【技能簇：状态篡改与热更新】
│   │   └── mcp_hil_bridge.py   # HIL 核心桥梁（参数防倒灌克隆、字节拆解写入、协议号握手切换）
│   │
│   └── perception\             <-- 【技能簇：系统状态感知与反馈】
│       ├── monitor_rtt_auto.py # 自动化 RTT 监控
│       ├── rtt_exchange_auto.py# RTT 双向数据交换交互
│       └── rtt_listener.py     # RTT 后台监听守护进程
│
└── docs\                       <-- [文档库]
    ├── folder_directory.md     # 文件夹目录
    └── SYSTEM_ARCHITECTURE.md  # 架构说明文档


===================================================================================

.\your_mcu_project\            <-- 【目标工程目录】具体的单片机业务代码（如雷达、电机）
    │
    ├── .hil_symbols.json       # [动态生成] 物理内存字典（真理源泉：存放 HIL 变量的绝对物理地址与展平偏移量）
    ├── project_config.yaml     # 硬件配置文件（指明当前工程的 MCU 型号等元数据）
    │
    ├── HIL\                    <-- [HIL 本地组件] 单片机端的热更新底座代码
    │   ├── hil_config_user.h   # 用户设置区（定义大一统结构体 HIL_Global_Params_t，以及暴露白名单变量）
    │   ├── hil_inject.h        # 注入层头文件（声明 HIL_GET_ACTIVE_CFG 零开销宏与对外接口）
    │   └── hil_inject.c        # 注入层实现（包含 HIL_Inject_Task 哨兵任务，负责关中断执行原子化的版本翻转与指针同步）
    │
    ├── RTT\                    <-- [调试与通信组件] SEGGER RTT 库（用于系统状态的高速感知与输出）
    │   ├── SEGGER_RTT.h        # RTT 核心头文件
    │   ├── SEGGER_RTT.c        # RTT 核心实现（通过内存映射实现的高速打印与指令接收）
    │   └── SEGGER_RTT_Conf.h   # RTT 配置文件（定义 Buffer 大小及非阻塞模式等关键配置）
    │
    ├── Listings\               # Keil 编译生成的 .map 文件存放地（用于提取基地址）
    ├── Objects\                # Keil 编译生成的 .axf 和 .hex 文件存放（用于提取 DWARF 嵌套信息及烧录）
    └── src\                    # 单片机业务逻辑源码（内部纯净调用 p_cfg->xxx，与底层热更新完全解耦）







