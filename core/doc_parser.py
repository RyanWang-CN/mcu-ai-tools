import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv
from llama_cloud import LlamaCloud

def main():
    parser = argparse.ArgumentParser(description="MCU 数据手册清洗引擎 (就地清洗版)")
    parser.add_argument("-f", "--file", required=True, help="待清洗的 PDF 文件绝对或相对路径")
    parser.add_argument("-s", "--series", required=True, help="芯片系列名称 (如 HC32L021)")
    args = parser.parse_args()

    # 1. 加载 .env 密钥 (基于脚本自身位置，向上一级寻找)
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    env_path = project_root / ".env"
    load_dotenv(env_path)

    # 2. 路径解析与【就地路由】 (核心修改点)
    input_pdf_path = Path(args.file).resolve()
    series_name = args.series
    
    # 彻底抛弃硬编码的 knowledge_base！
    # 直接获取 PDF 所在的父目录，作为输出目录
    output_dir = input_pdf_path.parent
    
    # 拼接最终和临时文件的名字
    final_out_path = output_dir / f"{series_name}_RM.md"
    temp_out_path = output_dir / f"temp_{series_name}.md"

    # 3. 防呆检查
    if not input_pdf_path.exists():
        print(f"❌ [错误] 找不到输入文件: {input_pdf_path}")
        sys.exit(1)
        
    api_key = os.environ.get("LLAMA_CLOUD_API_KEY")
    if not api_key:
        print(f"❌ [错误] 缺失 API Key！请确保 {env_path} 存在且配置正确")
        sys.exit(1)

    print(f"[*] 任务启动: {input_pdf_path.name}")
    print(f"[*] 就地归档: 将在同目录下生成 {series_name}_RM.md")

    success = False

    try:
        client = LlamaCloud(api_key=api_key)
        
        print(" -> [1/3] 正在上传文件至云端...")
        file_obj = client.files.create(
            file=input_pdf_path, 
            purpose="parse"
        )
        
        print(" -> [2/3] 正在进行 Agentic 深度语义解析 (需等待几分钟)...")
        result = client.parsing.parse(
            file_id=file_obj.id,
            tier="agentic",          
            version="latest",        
            expand=["markdown"]      
        )
        
        print(" -> [3/3] 解析完毕，正在落盘...")
        with open(temp_out_path, 'w', encoding='utf-8') as f:
            for page in result.markdown.pages:
                f.write(page.markdown + "\n\n")
        
        # 原子替换
        temp_out_path.replace(final_out_path)
        success = True
        print(f"✅ [成功] Markdown 已安全着陆: {final_out_path}")
        
    except BaseException as e: 
        print(f"\n❌ [中断/异常] 任务已终止: {e}")
        sys.exit(1)
        
    finally:
        # 清理残次品
        if not success and temp_out_path.exists():
            try:
                temp_out_path.unlink()
                print("🧹 [清理] 发现未完成的临时文件，已清理。")
            except Exception:
                pass

if __name__ == "__main__":
    main()