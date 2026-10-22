"""
Markdown to PDF Conversion Toolkit
Supports multiple rendering backends: ReportLab, Pandoc, WeasyPrint
Designed for agentic tool integration (Pi, Hermes, Nanobot)

Usage:
  # As a library
  from md_to_pdf_toolkit import MarkdownToPDFConverter
  converter = MarkdownToPDFConverter()
  converter.convert("input.md", "output.pdf", style_preset="executive")

  # As a CLI tool
  python md_to_pdf_toolkit.py input.md output.pdf --style executive --backend reportlab
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Optional, Literal
from dataclasses import dataclass
from enum import Enum

# Try to import optional backends
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    import pypandoc
    PYPANDOC_AVAILABLE = True
except ImportError:
    PYPANDOC_AVAILABLE = False

try:
    import weasyprint
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False


class ConversionBackend(Enum):
    """Available conversion backends"""
    REPORTLAB = "reportlab"
    PANDOC = "pandoc"
    WEASYPRINT = "weasyprint"


class StylePreset(Enum):
    """Pre-defined style presets"""
    EXECUTIVE = "executive"
    TECHNICAL = "technical"
    MINIMAL = "minimal"
    ARTICLE = "article"


@dataclass
class ConversionConfig:
    """Configuration for markdown to PDF conversion"""
    backend: ConversionBackend = ConversionBackend.REPORTLAB
    style_preset: StylePreset = StylePreset.EXECUTIVE
    page_size: str = "letter"  # letter, a4
    include_toc: bool = False
    include_code_highlighting: bool = True
    metadata: Optional[Dict] = None
    output_quality: Literal["draft", "standard", "high"] = "standard"


class MarkdownToPDFConverter:
    """
    Markdown to PDF converter with multiple backend support.
    Designed to be used by agentic frameworks.
    """

    def __init__(self, config: Optional[ConversionConfig] = None):
        self.config = config or ConversionConfig()
        self.validate_backend()

    def validate_backend(self):
        """Check if selected backend is available"""
        backend = self.config.backend
        
        if backend == ConversionBackend.REPORTLAB and not REPORTLAB_AVAILABLE:
            raise RuntimeError("ReportLab not installed. Run: pip install reportlab")
        
        if backend == ConversionBackend.PANDOC and not PYPANDOC_AVAILABLE:
            raise RuntimeError("pypandoc not installed. Run: pip install pypandoc")
        
        if backend == ConversionBackend.WEASYPRINT and not WEASYPRINT_AVAILABLE:
            raise RuntimeError("weasyprint not installed. Run: pip install weasyprint")

    def convert(self, input_path: str, output_path: str) -> Dict:
        """
        Convert markdown file to PDF.
        
        Args:
            input_path: Path to .md file
            output_path: Path to output .pdf file
            
        Returns:
            Dict with status, file size, conversion time, etc.
        """
        input_path = Path(input_path)
        output_path = Path(output_path)

        if not input_path.exists():
            return {
                "success": False,
                "error": f"Input file not found: {input_path}",
                "input": str(input_path),
                "output": str(output_path)
            }

        try:
            if self.config.backend == ConversionBackend.REPORTLAB:
                return self._convert_reportlab(input_path, output_path)
            
            elif self.config.backend == ConversionBackend.PANDOC:
                return self._convert_pandoc(input_path, output_path)
            
            elif self.config.backend == ConversionBackend.WEASYPRINT:
                return self._convert_weasyprint(input_path, output_path)
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "input": str(input_path),
                "output": str(output_path)
            }

    def _convert_reportlab(self, input_path: Path, output_path: Path) -> Dict:
        """ReportLab backend (Python-native, highly customizable)"""
        import time
        start_time = time.time()

        # Read markdown
        with open(input_path, 'r', encoding='utf-8') as f:
            md_content = f.read()

        # Create PDF document
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )

        # Get style preset
        styles_dict = self._get_reportlab_styles()
        story = []

        # Parse markdown and build story
        lines = md_content.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Headers
            if line.startswith('# ') and not line.startswith('## '):
                story.append(Paragraph(line[2:], styles_dict['heading1']))
                story.append(Spacer(1, 0.15*inch))
            elif line.startswith('## '):
                story.append(Paragraph(line[3:], styles_dict['heading2']))
                story.append(Spacer(1, 0.1*inch))
            elif line.startswith('### '):
                story.append(Paragraph(line[4:], styles_dict['heading3']))
                story.append(Spacer(1, 0.08*inch))
            
            # Bullet points
            elif line.strip().startswith('- ') or line.strip().startswith('* '):
                story.append(Paragraph(line.strip()[2:], styles_dict['bullet']))
            
            # Code blocks
            elif line.strip().startswith('```'):
                code_block = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    code_block.append(lines[i])
                    i += 1
                code_text = '\n'.join(code_block)
                story.append(Paragraph(f"<font face='Courier' size=8><b>{code_text}</b></font>", styles_dict['code']))
                story.append(Spacer(1, 0.1*inch))
            
            # Horizontal rule / page break
            elif line.strip() in ['---', '***', '___']:
                story.append(PageBreak())
            
            # Regular paragraphs
            elif line.strip():
                story.append(Paragraph(line.strip(), styles_dict['body']))
                story.append(Spacer(1, 0.08*inch))
            
            i += 1

        # Build PDF
        doc.build(story)
        
        elapsed = time.time() - start_time
        file_size = output_path.stat().st_size

        return {
            "success": True,
            "backend": "reportlab",
            "input": str(input_path),
            "output": str(output_path),
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size / (1024*1024), 2),
            "conversion_time_seconds": round(elapsed, 2),
            "style_preset": self.config.style_preset.value
        }

    def _convert_pandoc(self, input_path: Path, output_path: Path) -> Dict:
        """Pandoc backend (if pypandoc installed)"""
        import time
        start_time = time.time()

        try:
            pypandoc.convert_file(
                str(input_path),
                'pdf',
                outputfile=str(output_path),
                extra_args=[
                    '--pdf-engine=pdflatex',
                    '--highlight-style=tango'
                ]
            )
            
            elapsed = time.time() - start_time
            file_size = output_path.stat().st_size
            
            return {
                "success": True,
                "backend": "pandoc",
                "input": str(input_path),
                "output": str(output_path),
                "file_size_bytes": file_size,
                "file_size_mb": round(file_size / (1024*1024), 2),
                "conversion_time_seconds": round(elapsed, 2),
                "note": "Pandoc provides LaTeX-quality output with code syntax highlighting"
            }
        except Exception as e:
            raise RuntimeError(f"Pandoc conversion failed: {str(e)}")

    def _convert_weasyprint(self, input_path: Path, output_path: Path) -> Dict:
        """WeasyPrint backend (HTML -> PDF via CSS)"""
        import time
        start_time = time.time()
        
        # Read markdown and convert to HTML first
        import markdown
        with open(input_path, 'r', encoding='utf-8') as f:
            md_content = f.read()
        
        html_content = markdown.markdown(md_content)
        
        # Wrap in HTML template with CSS
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, sans-serif; line-height: 1.6; }}
                h1 {{ color: #0a1f3b; font-size: 28px; margin-top: 20px; margin-bottom: 10px; }}
                h2 {{ color: #1565a8; font-size: 20px; margin-top: 15px; margin-bottom: 8px; }}
                h3 {{ color: #2d5aa6; font-size: 16px; }}
                code {{ background: #f5f5f5; padding: 2px 6px; font-family: 'Courier New'; }}
                pre {{ background: #f5f5f5; padding: 12px; overflow-x: auto; }}
                blockquote {{ border-left: 4px solid #0a1f3b; padding-left: 16px; color: #555; }}
                table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
                th {{ background: #0a1f3b; color: white; padding: 8px; text-align: left; }}
                td {{ border: 1px solid #ddd; padding: 8px; }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
        
        weasyprint.HTML(string=html_template).write_pdf(str(output_path))
        
        elapsed = time.time() - start_time
        file_size = output_path.stat().st_size
        
        return {
            "success": True,
            "backend": "weasyprint",
            "input": str(input_path),
            "output": str(output_path),
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size / (1024*1024), 2),
            "conversion_time_seconds": round(elapsed, 2),
            "note": "WeasyPrint provides CSS-based PDF styling, good for web-like layouts"
        }

    def _get_reportlab_styles(self) -> Dict:
        """Get ReportLab styles for given preset"""
        base_styles = getSampleStyleSheet()
        
        if self.config.style_preset == StylePreset.EXECUTIVE:
            return {
                'heading1': ParagraphStyle(
                    'H1',
                    parent=base_styles['Heading1'],
                    fontSize=18,
                    textColor=colors.HexColor('#0a1f3b'),
                    fontName='Helvetica-Bold'
                ),
                'heading2': ParagraphStyle(
                    'H2',
                    parent=base_styles['Heading2'],
                    fontSize=14,
                    textColor=colors.HexColor('#1565a8'),
                    fontName='Helvetica-Bold'
                ),
                'heading3': ParagraphStyle(
                    'H3',
                    parent=base_styles['Heading3'],
                    fontSize=12,
                    textColor=colors.HexColor('#2d5aa6'),
                    fontName='Helvetica-Bold'
                ),
                'body': ParagraphStyle(
                    'Body',
                    parent=base_styles['Normal'],
                    fontSize=10,
                    alignment=TA_JUSTIFY,
                    leading=12
                ),
                'bullet': ParagraphStyle(
                    'Bullet',
                    parent=base_styles['Normal'],
                    fontSize=9.5,
                    leftIndent=12,
                    leading=11
                ),
                'code': ParagraphStyle(
                    'Code',
                    parent=base_styles['Normal'],
                    fontSize=8,
                    fontName='Courier',
                    backColor=colors.HexColor('#f5f5f5')
                )
            }
        
        # Minimal preset
        if self.config.style_preset == StylePreset.MINIMAL:
            return {
                'heading1': base_styles['Heading1'],
                'heading2': base_styles['Heading2'],
                'heading3': base_styles['Heading3'],
                'body': base_styles['Normal'],
                'bullet': base_styles['Bullet'],
                'code': base_styles['Code']
            }
        
        return {
            'heading1': base_styles['Heading1'],
            'heading2': base_styles['Heading2'],
            'heading3': base_styles['Heading3'],
            'body': base_styles['Normal'],
            'bullet': base_styles['Bullet'],
            'code': base_styles['Code']
        }


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Convert Markdown to PDF",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic conversion
  python md_to_pdf_toolkit.py input.md output.pdf
  
  # With options
  python md_to_pdf_toolkit.py input.md output.pdf --style executive --backend reportlab
  
  # Check available backends
  python md_to_pdf_toolkit.py --check-backends
        """
    )
    
    parser.add_argument('input', nargs='?', help='Input .md file')
    parser.add_argument('output', nargs='?', help='Output .pdf file')
    parser.add_argument('--backend', choices=['reportlab', 'pandoc', 'weasyprint'], 
                       default='reportlab', help='Conversion backend')
    parser.add_argument('--style', choices=['executive', 'technical', 'minimal', 'article'],
                       default='executive', help='Style preset')
    parser.add_argument('--check-backends', action='store_true', help='Check available backends')
    parser.add_argument('--json', action='store_true', help='Output result as JSON')

    args = parser.parse_args()

    # Check backends
    if args.check_backends:
        print("\n📦 Available Backends:\n")
        print(f"  reportlab:  {'✓ Available' if REPORTLAB_AVAILABLE else '✗ Not installed'}")
        print(f"  pandoc:     {'✓ Available' if PYPANDOC_AVAILABLE else '✗ Not installed'}")
        print(f"  weasyprint: {'✓ Available' if WEASYPRINT_AVAILABLE else '✗ Not installed'}")
        print("\nInstall missing backends with:")
        print("  pip install reportlab pypandoc weasyprint")
        return

    if not args.input or not args.output:
        parser.print_help()
        return

    # Convert
    config = ConversionConfig(
        backend=ConversionBackend(args.backend),
        style_preset=StylePreset(args.style)
    )
    
    converter = MarkdownToPDFConverter(config)
    result = converter.convert(args.input, args.output)
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result['success']:
            print(f"\n✅ Conversion successful!")
            print(f"   Input:  {result['input']}")
            print(f"   Output: {result['output']}")
            print(f"   Size:   {result['file_size_mb']} MB")
            print(f"   Time:   {result['conversion_time_seconds']}s")
        else:
            print(f"\n❌ Conversion failed: {result['error']}")


if __name__ == '__main__':
    main()
