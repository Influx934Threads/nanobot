# Markdown to PDF Conversion Skill

## Purpose

Convert Markdown documents to professionally styled PDFs using multiple rendering backends. Designed for agentic workflows — CLI and Python API modes.

## Requirements

- **reportlab** (primary backend, already installed on this system)
- **pandoc** (optional, for LaTeX-quality output)
- **weasyprint** (optional, for CSS-based styling)

## Usage

### As a Skill (Agent/CLI)

```bash
# Check available backends
python3 /home/anshin/.nanobot/workspace/skills/md-to-pdf/md_to_pdf_toolkit.py --check-backends

# Basic conversion (uses ReportLab by default)
python3 /home/anshin/.nanobot/workspace/skills/md-to-pdf/md_to_pdf_toolkit.py input.md output.pdf

# With style preset
python3 /home/anshin/.nanobot/workspace/skills/md-to-pdf/md_to_pdf_toolkit.py input.md output.pdf --style executive

# With specific backend
python3 /home/anshin/.nanobot/workspace/skills/md-to-pdf/md_to_pdf_toolkit.py input.md output.pdf --backend reportlab

# JSON output for programmatic use
python3 /home/anshin/.nanobot/workspace/skills/md-to-pdf/md_to_pdf_toolkit.py input.md output.pdf --json
```

### As a Python Library

```python
from md_to_pdf_toolkit import MarkdownToPDFConverter

converter = MarkdownToPDFConverter()
result = converter.convert("document.md", "document.pdf", style_preset="executive")
print(result)
# { "success": True, "output": "document.pdf", "file_size_mb": 0.15, ... }
```

## Style Presets

| Preset | Description | Use Case |
|---|---|---|
| **executive** | Corporate blue theme, justified body text | Reports, briefings, official docs |
| **technical** | Clean, functional styling | Technical docs, specs, manuals |
| **minimal** | Default styles, no color | Print-friendly, minimal output |
| **article** | Newspaper-style layout | Articles, blog posts, publications |

## Backends

| Backend | Pros | Cons | Install |
|---|---|---|---|
| **ReportLab** (default) | Pure Python, fast, no system deps | Manual markdown parsing | `pip install reportlab` |
| **Pandoc** | LaTeX-quality, syntax highlighting | Requires LaTeX system | `apt install pandoc texlive` |
| **WeasyPrint** | CSS-based, HTML rendering | Requires system deps | `pip install weasyprint` |

## Workflow

1. **Check backends** — `--check-backends` to see what's available
2. **Choose style** — `--style executive|technical|minimal|article`
3. **Convert** — `python3 md_to_pdf_toolkit.py input.md output.pdf`
4. **Verify** — Check output file exists and has reasonable size

## Notes

- Default backend is ReportLab (already installed)
- Output is a single-pass conversion (no intermediate files)
- Supports headers (h1-h3), bullet points, code blocks, horizontal rules
- Tables and advanced markdown may render differently across backends
- For complex documents, Pandoc backend produces the highest quality output
