import os
import json
import shutil
from core.keil_parser import find_map_file_path, get_or_update_map_path


def test_find_map_path_and_device(samples_dir):
    map_path, device = find_map_file_path(samples_dir)
    assert device == "HC32L021"
    assert map_path.endswith("TestTarget.map")


def test_device_not_fallback_cortex_m0(samples_dir):
    """型号不应是兜底默认值"""
    _, device = find_map_file_path(samples_dir)
    assert device != "Cortex-M0+"


def test_map_path_is_absolute(samples_dir):
    map_path, _ = find_map_file_path(samples_dir)
    assert os.path.isabs(map_path)


def test_no_uvprojx_raises(temp_project_dir):
    import pytest
    with pytest.raises(FileNotFoundError):
        find_map_file_path(temp_project_dir)


def test_cache_writes_device_info(sample_uvprojx_path, temp_project_dir):
    dest = os.path.join(temp_project_dir, "test.uvprojx")
    shutil.copy(sample_uvprojx_path, dest)

    get_or_update_map_path(temp_project_dir, force_update=True)
    cache = os.path.join(temp_project_dir, ".hil_cache.json")
    assert os.path.exists(cache)

    with open(cache, "r") as f:
        data = json.load(f)
    assert data["device"] == "HC32L021"
