"""Test MCUInjector address resolution logic (no J-Link hardware needed)."""
import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from core.mcu_mem_ctrl import MCUInjector


@pytest.fixture
def injector(temp_project_dir, symbol_dict_file):
    """MCUInjector 实例（不连接 J-Link，只测试符号解析）"""
    obj = MCUInjector.__new__(MCUInjector)
    obj.project_dir = temp_project_dir
    obj.symbols = json.load(open(symbol_dict_file))
    obj.jlink = None
    return obj


class TestResolveAddress:
    """测试智能地址解析引擎 _resolve_address"""

    def test_hex_address_passthrough(self, injector):
        """0x 开头的字符串直接返回整数"""
        addr = injector._resolve_address("0x20000004")
        assert addr == 0x20000004

    def test_symbol_from_dictionary(self, injector):
        """符号名从 .hil_symbols.json 查找"""
        addr = injector._resolve_address("threshold")
        assert addr == 0x20000004

    def test_symbol_from_dictionary_velocity(self, injector):
        addr = injector._resolve_address("velocity")
        assert addr == 0x20000008

    def test_unknown_symbol_raises(self, injector):
        """找不到的符号应抛异常"""
        with pytest.raises(ValueError, match="无法解析符号"):
            injector._resolve_address("nonexistent_symbol")

    def test_case_sensitive(self, injector):
        """大小写敏感"""
        with pytest.raises(ValueError):
            injector._resolve_address("Threshold")

    def test_small_hex(self, injector):
        """短十六进制地址也能解析"""
        addr = injector._resolve_address("0x100")
        assert addr == 0x100


class TestSymbolDictValidation:
    """符号字典结构验证"""

    def test_all_symbols_have_address_and_size(self, symbol_dict):
        for name, info in symbol_dict.items():
            if name == "__META__":
                continue
            assert "address" in info, f"{name} missing 'address'"
            assert "size" in info, f"{name} missing 'size'"
            assert isinstance(info["address"], int)
            assert isinstance(info["size"], int)

    def test_struct_has_layout(self, symbol_dict):
        p_cfg = symbol_dict["p_cfg"]
        assert p_cfg["is_struct"] is True
        assert "layout" in p_cfg
        assert "mode" in p_cfg["layout"]
        assert "threshold" in p_cfg["layout"]

    def test_meta_has_device(self, symbol_dict):
        assert symbol_dict["__META__"]["device"] == "HC32L021"


class TestInjectorInit:
    """测试 injector 初始化时加载符号字典"""

    def test_loads_symbols_from_file(self, temp_project_dir, symbol_dict_file):
        """init 时自动加载 .hil_symbols.json"""
        injector = MCUInjector(temp_project_dir)
        assert "threshold" in injector.symbols
        assert injector.symbols["threshold"]["address"] == 0x20000004

    def test_raises_when_no_symbols(self, temp_project_dir):
        """没有 .hil_symbols.json 时抛 FileNotFoundError"""
        with pytest.raises(FileNotFoundError, match="符号字典缺失"):
            MCUInjector(temp_project_dir)
