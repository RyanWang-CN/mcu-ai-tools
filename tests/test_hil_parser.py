import os
import json
from unittest.mock import MagicMock, PropertyMock, patch
from core.hil_parser import (
    get_whitelist_from_map,
    get_struct_die,
    parse_struct_layout_recursive,
    generate_symbols_json,
)


# ── helpers to build mock DIE objects ──

def _die(tag, attrs=None, children=None):
    """Build a mock pyelftools DIE."""
    m = MagicMock()
    type(m).tag = PropertyMock(return_value=tag)
    type(m).attributes = PropertyMock(return_value=attrs or {})
    m.iter_children.return_value = children or []
    return m


def _attr(v):
    m = MagicMock()
    m.value = v
    return m


# ── Map parsing ──

class TestWhitelist:
    def test_extracts_exposed(self, sample_map_path):
        w = get_whitelist_from_map(sample_map_path)
        assert "threshold" in w
        assert "velocity" in w
        assert "hil_cfg" in w
        assert "sensor_value" not in w

    def test_empty_when_no_expose(self, temp_project_dir):
        p = os.path.join(temp_project_dir, "e.map")
        with open(p, "w") as f:
            f.write("main  0x100  Thumb  4  main.o\n")
        assert get_whitelist_from_map(p) == set()


# ── DWARF struct layout (the core recursive algorithm) ──

class TestParseStructLayout:
    def test_flat(self):
        children = [
            _die("DW_TAG_member", {"DW_AT_name": _attr(b"freq"),
                "DW_AT_data_member_location": _attr(0)}),
            _die("DW_TAG_member", {"DW_AT_name": _attr(b"duty"),
                "DW_AT_data_member_location": _attr(4)}),
            _die("DW_TAG_member", {"DW_AT_name": _attr(b"mode"),
                "DW_AT_data_member_location": _attr(8)}),
        ]
        struct = _die("DW_TAG_structure_type", children=children)
        assert parse_struct_layout_recursive(struct) == {"freq": 0, "duty": 4, "mode": 8}

    def test_nested_flattened(self):
        inner = _die("DW_TAG_structure_type", children=[
            _die("DW_TAG_member", {"DW_AT_name": _attr(b"a"),
                "DW_AT_data_member_location": _attr(0)}),
            _die("DW_TAG_member", {"DW_AT_name": _attr(b"b"),
                "DW_AT_data_member_location": _attr(4)}),
        ])

        outer = _die("DW_TAG_structure_type", children=[
            _die("DW_TAG_member", {"DW_AT_name": _attr(b"id"),
                "DW_AT_data_member_location": _attr(0)}),
            _die("DW_TAG_member", {"DW_AT_name": _attr(b"base"),
                "DW_AT_data_member_location": _attr(4)}),
        ])
        # patch get_struct_die so child "base" returns inner struct
        with patch("core.hil_parser.get_struct_die", side_effect=[None, inner, None, None]):
            layout = parse_struct_layout_recursive(outer)
        assert "a" in layout and "b" in layout
        assert layout["a"] == 4
        assert layout["b"] == 8

    def test_base_offset_adds_to_all(self):
        children = [_die("DW_TAG_member", {"DW_AT_name": _attr(b"x"),
            "DW_AT_data_member_location": _attr(12)})]
        struct = _die("DW_TAG_structure_type", children=children)
        layout = parse_struct_layout_recursive(struct, base_offset=1000)
        assert layout["x"] == 1012


# ── get_struct_die ──

class TestGetStructDie:
    def test_follows_chain(self):
        s = _die("DW_TAG_structure_type")
        mid = _die("DW_TAG_pointer_type", {"DW_AT_type": _attr(s)})
        mid.get_DIE_from_attribute = MagicMock(return_value=s)
        top = _die("DW_TAG_variable", {"DW_AT_type": _attr(mid)})
        top.get_DIE_from_attribute = MagicMock(return_value=mid)
        assert get_struct_die(top) is s

    def test_none_when_no_struct(self):
        b = _die("DW_TAG_base_type")
        mid = _die("DW_TAG_const_type")
        mid.get_DIE_from_attribute = MagicMock(return_value=b)
        top = _die("DW_TAG_variable", {"DW_AT_type": _attr(mid)})
        top.get_DIE_from_attribute = MagicMock(return_value=mid)
        assert get_struct_die(top) is None


# ── Full pipeline ──

class TestGenerateSymbolsJson:
    def test_creates_json_with_meta(self, temp_project_dir, sample_map_path):
        # copy map without .hil_expose tags
        src = open(sample_map_path, "r").read().replace(".hil_expose", "")
        with open(os.path.join(temp_project_dir, "test.map"), "w") as f:
            f.write(src)
        with open(os.path.join(temp_project_dir, "test.axf"), "wb") as f:
            f.write(b"\x7fELF" + b"\x00" * 100)

        # write config
        with open(os.path.join(temp_project_dir, "project_config.yaml"), "w") as f:
            f.write("hardware:\n  mcu: HC32F460\n")

        cwd = os.getcwd()
        os.chdir(temp_project_dir)
        try:
            generate_symbols_json(temp_project_dir)
            path = os.path.join(temp_project_dir, ".hil_symbols.json")
            assert os.path.exists(path)
            data = json.load(open(path))
            assert "__META__" in data
            assert data["__META__"]["device"] == "HC32F460"
        finally:
            os.chdir(cwd)
