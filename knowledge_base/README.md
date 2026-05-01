# MCU Knowledge Base

This directory contains MCU reference material used by the RAG knowledge retrieval system.

## Contents

- **SVD files** — CMSIS-SVD peripheral descriptions (freely distributable from HDSC)
- **Markdown manuals** — Generated from HDSC reference manuals

## Obtaining Reference Manuals

Due to copyright restrictions, HDSC (Huada) PDF reference manuals are **not distributed** with this repository.

To use the knowledge base:

1. Download the reference manual PDF for your MCU from [HDSC official website](http://www.hdsc.com.cn/)
2. Place the PDF in the corresponding chip directory (e.g., `knowledge_base/HC32F460/`)
3. Run the document parser to generate Markdown:

```bash
# Example: process a PDF for HC32L021
python core/doc_parser.py -f knowledge_base/HC32L021/RM_HC32L021_Rev1.00.pdf -s HC32L021
```

Or use the batch builder:
```bash
python build_kb.py -d knowledge_base
```
