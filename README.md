# MCU AI Tools

> AI-powered MCU automation gateway — control, debug, and test embedded systems through natural language.

MCU AI Tools bridges AI assistants (Claude Code, Roo Code, etc.) with MCU hardware via the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). It turns AI into the "brain" of your embedded development workflow, capable of compiling firmware, flashing, reading sensor data, injecting HIL test parameters, and hardware debugging — all through natural language commands.

## Architecture

```
+-------------------+     +-------------------+     +------------------+
|   AI Brain Layer  | --> |  MCP Skills Hub   | --> |   MCU Hardware   |
| (Claude/Roo Code) |     | (FastMCP Server)  |     | (HDSC HC32 MCU)  |
+-------------------+     +-------------------+     +------------------+
```

Three skill categories exposed as MCP tools:

| Category | Capabilities |
|----------|-------------|
| **Knowledge (RAG)** | Pin diagrams, SDK reference manuals |
| **Actions** | Init project config, build/flash firmware, hard reset, HIL parameter injection |
| **Sensors** | RTT log capture, bidirectional RTT communication, sensor snapshot analysis, live variable read |

## Requirements

### Hardware
- **MCU**: HDSC (Huada) HC32 series — tested on HC32F460, HC32L021
- **Debugger**: SEGGER J-Link (any model)
- **Target board**: HDSC MCU development board or custom PCB

### Software
- Python 3.10+
- [SEGGER J-Link Software](https://www.segger.com/downloads/jlink/) (v7.x+)
- [Keil MDK](https://www.keil.com/download/product/) v5 (for building/flashing)
- An AI assistant that supports MCP tools (Claude Code, Roo Code, etc.)

## Installation

```bash
# Clone the repository
git clone https://github.com/<your-username>/mcu-ai-tools.git
cd mcu-ai-tools

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# .\venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

## Configuration

### 1. Environment (optional)
Copy `.env.example` to `.env` if you plan to use the LlamaCloud PDF parser:
```bash
cp .env.example .env
# Edit .env and add your LlamaCloud API key
```

### 2. Project initialization
Navigate to your MCU project directory and run:
```bash
# Auto-detect MCU project and generate config
python -m core.auto_config_builder

# Generate HIL symbol dictionary from .map/.axf
python -m core.hil_parser
```

## Usage

### Start MCP Server
```bash
python mcp_server.py
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `init_project_config` | Auto-detect project structure, generate YAML config |
| `update_hil_dictionary` | Scan .map/.axf files, update physical memory dictionary |
| `build_project` | Compile Keil MDK project |
| `flash_project` | Flash compiled HEX to MCU |
| `hard_reset_mcu` | Physical hardware reset |
| `rtt_print` | Capture J-Link RTT output logs |
| `rtt_ask` | Send RTT command to MCU and listen for echo |
| `take_sensor_snapshot` | Blocking binary sensor frame capture with offline statistics |
| `inject_hil_parameters` | Hot-inject test parameters into MCU physical memory |
| `read_hil_variable` | Read a global variable value from MCU memory |
| `check_mcu_status` | Check MCU CPU run state (Running/Halted) |
| `get_hardware_probe_info` | Get J-Link probe info including target voltage |
| `scan_connected_probes` | List all connected J-Link probes |
| `check_rtt_health` | Probe RTT channel allocation in MCU memory |

### Debug Tools

| Tool | Description |
|------|-------------|
| `debug_run` | Resume MCU execution |
| `debug_halt` | Halt MCU and return PC pointer |
| `debug_step` | Single-step one machine instruction |
| `debug_set_breakpoint` | Set hardware breakpoint by address or symbol |
| `debug_clear_breakpoint` | Remove hardware breakpoint |
| `debug_clear_all_breakpoints` | Clear all hardware breakpoints |
| `debug_run_to_breakpoint` | Set breakpoint and run — awaits hit |

## HIL (Hardware-in-the-Loop) Injection

The HIL subsystem enables **non-intrusive parameter hot-swapping** while the MCU is running:

1. **Clone** — Read active config block, clone to inactive buffer
2. **Delta** — Write only the changed parameters
3. **Commit** — Flip version flag via atomic protocol handshake

Your MCU firmware must include the HIL injection stub (see `HIL/` directory in the target project).

## Project Structure

```
├── mcp_server.py              # MCP server entry point
├── core/                      # Infrastructure layer
│   ├── mcu_mem_ctrl.py        # J-Link physical memory driver
│   ├── hil_parser.py          # DWARF/map parser for symbol extraction
│   ├── keil_parser.py         # Keil project XML parser
│   ├── auto_config_builder.py # Auto project configuration
│   └── doc_parser.py          # PDF document parser (LlamaCloud)
├── skills/
│   ├── build/                 # Build, flash, reset
│   ├── injection/             # HIL parameter injection
│   ├── perception/            # RTT monitoring, communication
│   └── rag/                   # Knowledge retrieval
├── tests/                     # Unit tests (pytest)
│   ├── conftest.py
│   ├── elf_builder.py
│   ├── test_hil_parser.py
│   ├── test_keil_parser.py
│   ├── test_mcu_mem_ctrl.py
│   └── samples/
├── .github/workflows/         # CI (GitHub Actions)
│   └── test.yml
├── knowledge_base/            # MCU reference manuals (SVD files)
├── docs/                      # Documentation
├── build_kb.py                # Knowledge base builder
├── setup.bat                  # Windows setup (CMD)
├── setup.ps1                  # Windows setup (PowerShell)
├── requirements.txt           # Python dependencies
└── LICENSE
```

## License

[MIT](LICENSE)
