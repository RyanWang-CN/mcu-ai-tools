import os
import sys
import json
import argparse
import subprocess
from pathlib import Path

def load_state(state_file: Path) -> dict:
    """加载知识库索引账本 (带防崩保护)"""
    if state_file.exists():
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️ [警告] 发现损坏的账本文件: {state_file.name}")
            print("⚠️ 正在自动重置为空账本，可能需要重新扫描...")
            return {}
    return {}

def save_state(state_file: Path, state: dict):
    """保存知识库索引账本 (原子化防掉电写入)"""
    # 先写到同目录的临时文件中
    temp_file = state_file.with_suffix('.json.tmp')
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=4, ensure_ascii=False)
    # 写入成功后，瞬间替换原账本，彻底杜绝写一半损坏的问题
    temp_file.replace(state_file)

def main():
    parser = argparse.ArgumentParser(description="MCU 知识库增量构建统筹引擎")
    parser.add_argument("-d", "--dir", default="knowledge_base", help="要扫描的目标资料夹相对或绝对路径 (默认: knowledge)")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    doc_parser_path = project_root / "core" / "doc_parser.py"
    state_file = project_root / ".kb_index.json"
    
    target_dir = Path(args.dir)
    if not target_dir.is_absolute():
        target_dir = project_root / target_dir

    if not target_dir.exists():
        print(f"❌ [错误] 扫描目标目录不存在: {target_dir}")
        sys.exit(1)

    if not doc_parser_path.exists():
        print(f"❌ [错误] 找不到清洗引擎: {doc_parser_path}")
        sys.exit(1)

    state = load_state(state_file)
    success_count = 0
    skip_count = 0
    fail_count = 0

    print(f"[*] 开始全盘增量扫描: {target_dir}")
    print("[*] 正在对比文件修改时间戳...")

    for pdf_file in target_dir.rglob("*.pdf"):
        pdf_path_str = str(pdf_file.resolve())
        # 【核心修复 1】抹平浮点数精度，强行取整精确到秒
        current_mtime = int(pdf_file.stat().st_mtime)
        series_name = pdf_file.parent.name

        if pdf_path_str in state and state[pdf_path_str] == current_mtime:
            skip_count += 1
            continue

        print(f"\n" + "="*50)
        print(f"🚀 [任务触发] 发现新加入或已更新的手册: {pdf_file.name}")
        print(f"📁 [归属系列] {series_name}")
        
        cmd = [
            sys.executable, 
            str(doc_parser_path),
            "-f", pdf_path_str,
            "-s", series_name
        ]

        result = subprocess.run(cmd)

        if result.returncode == 0:
            print(f"✅ [记账] {pdf_file.name} 知识入库成功，更新索引。")
            state[pdf_path_str] = current_mtime
            # 【核心修复 2】调用的 save_state 内部已经是原子化写入
            save_state(state_file, state)  
            success_count += 1
        else:
            print(f"⚠️ [警告] {pdf_file.name} 清洗失败或被中断。本次不记账，下次扫描将重试。")
            fail_count += 1

    print("\n" + "="*50)
    print(f"📊 [基建报告] 任务结束")
    print(f"   - 新增/更新入库 : {success_count} 份")
    print(f"   - 命中缓存跳过  : {skip_count} 份")
    print(f"   - 清洗失败/中断 : {fail_count} 份")
    print("="*50)

if __name__ == "__main__":
    main()