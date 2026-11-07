# -*- coding: utf-8 -*-
"""会议材料提取：PDF / DOCX / TXT / MD -> 纯文本。

用法：
    python extract_input.py <文件> [--output out.txt] [--speakers] [--max-chars N]

PDF 按 pdfplumber -> PyPDF2 -> pymupdf 顺序降级，任一可用即停止。
--speakers 只对带 "[mm:ss] 姓名:" 形式的转写原文有效，用于把"发言人1"还原成真人。
"""
import argparse
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')


def from_pdf(path):
    try:
        import pdfplumber
        with pdfplumber.open(str(path)) as pdf:
            return '\n'.join((p.extract_text() or '') for p in pdf.pages), 'pdfplumber'
    except Exception:
        pass
    try:
        import PyPDF2
        r = PyPDF2.PdfReader(str(path))
        return '\n'.join((p.extract_text() or '') for p in r.pages), 'PyPDF2'
    except Exception:
        pass
    try:
        import pymupdf
        d = pymupdf.open(str(path))
        return '\n'.join(p.get_text() for p in d), 'pymupdf'
    except Exception as e:
        raise RuntimeError('PDF 提取失败，三个引擎都不可用：%s' % e)


def from_docx(path):
    from docx import Document
    d = Document(str(path))
    parts = [p.text for p in d.paragraphs]
    for t in d.tables:
        for row in t.rows:
            parts.append(' | '.join(c.text for c in row.cells))
    return '\n'.join(parts), 'python-docx'


SPEAKER_RE = re.compile(r'^\s*[\[【]?(\d{1,2}:\d{2}(?::\d{2})?)[\]】]?\s*([^:：]{1,20})[:：]')


def speakers(text):
    c = Counter()
    for line in text.splitlines():
        m = SPEAKER_RE.match(line)
        if m:
            c[m.group(2).strip()] += 1
    return c


def main():
    ap = argparse.ArgumentParser(description='提取会议材料文本')
    ap.add_argument('path')
    ap.add_argument('--output', help='写入文件；不指定则打印到标准输出')
    ap.add_argument('--speakers', action='store_true', help='统计发言人及出现次数')
    ap.add_argument('--max-chars', type=int, default=0, help='截断到前 N 字符，0 表示不截断')
    args = ap.parse_args()

    p = Path(args.path)
    if not p.exists():
        print('文件不存在: %s' % p)
        return 2

    ext = p.suffix.lower()
    if ext == '.pdf':
        text, engine = from_pdf(p)
    elif ext in ('.docx', '.doc'):
        text, engine = from_docx(p)
    elif ext in ('.txt', '.md', '.markdown'):
        text, engine = p.read_text(encoding='utf-8', errors='replace'), 'plain'
    else:
        print('不支持的格式: %s（支持 pdf/docx/txt/md）' % ext)
        return 2

    if args.max_chars and len(text) > args.max_chars:
        text = text[:args.max_chars] + '\n...[已截断]'

    if args.output:
        Path(args.output).write_text(text, encoding='utf-8')
        print('引擎: %s；字符数: %d；已写入: %s' % (engine, len(text), args.output))
    else:
        print(text)

    if args.speakers:
        print('\n=== 发言人统计 ===')
        for name, n in speakers(text).most_common():
            print('%6d  %s' % (n, name))
    return 0


if __name__ == '__main__':
    sys.exit(main())
