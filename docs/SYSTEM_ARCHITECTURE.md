```mermaid
graph TD
    %% AI 大脑层
    Brain["<b>【AI 大脑层 (The Brain)】</b><br>(Claude Code CLI / Roo Code Extension / 本地 Qwen2.5)<br>职责：理解自然语言需求 -> 决定调用哪个 Skill -> 分析返回的 JSON"]

    %% MCP 网关层
    Gateway["<b>【MCP 技能网关层 (Skills Hub)】</b><br>(用 FastMCP 写的本地服务，将下方Python 脚本注册为 AI 可用的技能)"]

    %% 大脑到网关的通信
    Brain -- "(通过 MCP 标准协议通信)" --> Gateway

    %% 技能库分类
    SkillA["<b>技能库 A：查阅<br>(Knowledge RAG)</b><hr>1. 查引脚图<br>2. 查SDK手册<br>(读 Markdown)"]

    SkillB["<b>技能库 B：动作<br>(Acts)</b><hr>1. init_project_config（嗅探工程和编译产物，生成 project_config.yaml）<br>2. update_hil_dictionary（扫描 .map 和 .axf 文件，更新物理内存寻址字典）<br>3. build_project（编译 Keil 工程）<br>4. flash_project（将编译好的 Hex 固件烧录到单片机中）<br>5. hard_reset_mcu（物理硬复位单片机）<br>6. inject_hil_parameters（极速向单片机物理内存注入 HIL 测试参数）"]

    SkillC["<b>技能库 C：感知<br>(Sensors)</b><hr>1. rtt_print（纯抓取 J-Link RTT 输出日志）<br>2. rtt_ask（向单片机下发 RTT 字符串指令，并保持连接同步监听其回显日志）<br>3. take_sensor_snapshot（阻塞式抓取传感器的纯二进制数据帧，并离线解算返回统计特征）<br>4. read_hil_variable（通过物理内存直接读取单片机中某一个全局变量的当前真实值）"]

    %% 网关下发到技能库
    Gateway --> SkillA
    Gateway --> SkillB
    Gateway --> SkillC

    %% 硬件层 (修正了原图中缺失的左括号)
    Hardware["<b>真实MCU硬件</b><br>(华大HC32)"]

    %% 技能库到底层硬件
    SkillA --> Hardware
    SkillB --> Hardware
    SkillC --> Hardware

    %% 样式调整宽度
