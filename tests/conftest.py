import os
import sys
import json
import tempfile
import pytest

# Add project root to sys.path so we can import core.* modules
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from tests.elf_builder import build_minimal_elf32


# ── Fixtures: sample files ──

@pytest.fixture
def samples_dir():
    return os.path.join(os.path.dirname(__file__), "samples")


@pytest.fixture
def sample_map_path(samples_dir):
    return os.path.join(samples_dir, "test.map")


@pytest.fixture
def sample_uvprojx_path(samples_dir):
    return os.path.join(samples_dir, "test.uvprojx")


@pytest.fixture
def temp_project_dir():
    """Create a temp directory simulating an MCU project."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def minimal_elf_path(temp_project_dir):
    """Generate a minimal valid ELF file for testing."""
    path = os.path.join(temp_project_dir, "test.axf")
    symbols = [
        ("p_cfg",       0x20000000, 32),
        ("threshold",   0x20000004, 4),
        ("velocity",    0x20000008, 2),
        ("g_active_idx", 0x20000500, 1),
    ]
    build_minimal_elf32(path, symbols)
    return path


@pytest.fixture
def symbol_dict():
    """A fake .hil_symbols.json for testing address resolution."""
    return {
        "__META__": {
            "device": "HC32L021",
            "map_source": "test.map",
            "generated_at": "2025-01-01 00:00:00"
        },
        "threshold": {
            "address": 0x20000004,
            "size": 4,
            "is_struct": False
        },
        "velocity": {
            "address": 0x20000008,
            "size": 2,
            "is_struct": False
        },
        "p_cfg": {
            "address": 0x20000000,
            "size": 32,
            "is_struct": True,
            "element_size": 32,
            "layout": {
                "mode": 0,
                "target_speed": 4,
                "pid_kp": 8,
                "pid_ki": 12,
                "pid_kd": 16,
                "threshold": 20
            }
        },
        "g_active_idx": {
            "address": 0x20000500,
            "size": 1,
            "is_struct": False
        },
        "g_config_version": {
            "address": 0x20000501,
            "size": 1,
            "is_struct": False
        }
    }


@pytest.fixture
def symbol_dict_file(temp_project_dir, symbol_dict):
    """Write a fake .hil_symbols.json to a temp directory."""
    path = os.path.join(temp_project_dir, ".hil_symbols.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(symbol_dict, f)
    return path
