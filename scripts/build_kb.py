#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_kb.py —— 把语料库打包成"可直接上传到聊天 App 知识库"的文件包。

支持两种输出形态，覆盖手机端与桌面端：

  desktop  按类别分文件的 markdown（适合 ChatGPT / Gemini Gems / Coze 网页端）
  mobile   单文件版 + DOCX + TXT（适合豆包/元宝/千问/Kimi/智谱/DeepSeek 手机 App
           —— 手机文件选择器往往不认 .md，只认 .txt/.docx/.pdf）

用法：
  python3 scripts/build_kb.py                          # 默认 desktop 形态
  python3 scripts/build_kb.py --profile mobile         # 手机端单文件包（含 docx）
  python3 scripts/build_kb.py --profile all --zip      # 全部生成并打包
  python3 scripts/build_kb.py --format txt,docx        # 指定格式
  python3 scripts/build_kb.py --max-chars 200000       # 按平台限制切分

产物：
  dist/knowledge-base/     desktop 形态（分类 markdown）
  dist/kb-mobile/          手机端形态（单文件 txt/docx + 接入说明 + 系统提示词）
  dist/china-legal-advisor-*.zip   （--zip；使用 --out 时压缩包写到 --out 目录）
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from html import escape as xesc
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import law  # noqa: E402

CATEGORIES = [
    ("civil", "民法典"),
    ("labor", "劳动与社会保障"),
    ("company", "公司法与企业"),
    ("procedure", "程序法"),
    ("other", "其他"),
]

CORE_CATEGORIES = ("civil", "labor")

DISCLAIMER_BLOCK = """⚠️ 使用须知（请让 AI 也遵守）

1. 回答法律问题前必须引用本文档中的条文原文，格式为《法规全称》第X条，
   不得凭记忆写法条，不得编造条号或条文内容。
2. 本文档是快照，法律可能已被修订；具体案件请核对现行有效版本。
3. 本文档不含地方性法规、地方政府规章、法院会议纪要与裁审指引；
   涉及最低工资、社平工资、工伤待遇、加班费基数等地方标准时，必须按当地口径另行核验。
4. 本文档提供法律信息，不构成法律意见；具体争议请委托执业律师。
"""

# --------------------------------------------------------------------------
# DOCX 写入（纯标准库：.docx 本质是 zip + XML，无需第三方依赖）
# --------------------------------------------------------------------------

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""

_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

_DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr>
<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="宋体"/>
<w:sz w:val="21"/></w:rPr></w:rPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
</w:styles>"""

_SIZE_PT = {"title": 36, "h1": 30, "h2": 26, "h3": 23, "p": 21}


def _para(style: str, text: str) -> str:
    size = _SIZE_PT.get(style, 21)
    bold = "<w:b/>" if style in ("title", "h1", "h2", "h3") else ""
    spacing = ('<w:spacing w:before="120" w:after="60"/>'
               if style == "title" or style.startswith("h") else "")
    rpr = f'<w:rFonts w:eastAsia="宋体"/>{bold}<w:sz w:val="{size}"/>'
    return (f"<w:p><w:pPr>{spacing}<w:rPr>{rpr}</w:rPr></w:pPr>"
            f'<w:r><w:rPr>{rpr}</w:rPr><w:t xml:space="preserve">{xesc(text)}</w:t></w:r></w:p>')


def write_docx(path: Path, blocks: Sequence[Tuple[str, str]]) -> None:
    """把 (style, text) 序列写成最小可用的 .docx（Word / WPS / Pages / Google Docs 均可打开）。"""
    body = "".join(_para(style, text) for style, text in blocks)
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                f"<w:body>{body}<w:sectPr/></w:body></w:document>")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("_rels/.rels", _ROOT_RELS)
        z.writestr("word/_rels/document.xml.rels", _DOC_RELS)
        z.writestr("word/styles.xml", _STYLES)
        z.writestr("word/document.xml", document)


# --------------------------------------------------------------------------
# 渲染
# --------------------------------------------------------------------------

def doc_to_text(doc: law.Document) -> str:
    lines = ["", "=" * 68, doc.title, "=" * 68,
             f"版本：{doc.header.get('version', '')}",
             f"施行日期：{doc.header.get('effective', '')}",
             f"来源：{doc.header.get('source', '')}",
             f"收录条数：{sum(1 for a in doc.articles if a.no > 0)}", ""]
    if doc.header.get("note"):
        lines += [f"⚠️ 注意：{doc.header['note']}", ""]
    for art in doc.articles:
        if art.no == 0:
            lines += [f"【{doc.title}（全文）】", art.text, ""]
            continue
        ctx = f"（{' › '.join(art.headings)}）" if art.headings else ""
        lines += [f"《{doc.title}》{art.label}{ctx}", art.text, ""]
    return "\n".join(lines)


def doc_to_blocks(doc: law.Document) -> List[Tuple[str, str]]:
    blocks: List[Tuple[str, str]] = [
        ("h1", doc.title),
        ("p", f"版本：{doc.header.get('version', '')}"),
        ("p", f"施行日期：{doc.header.get('effective', '')}"),
        ("p", f"收录条数：{sum(1 for a in doc.articles if a.no > 0)}"),
    ]
    if doc.header.get("note"):
        blocks.append(("p", f"⚠️ 注意：{doc.header['note']}"))
    for art in doc.articles:
        if art.no == 0:
            blocks.append(("h2", f"{doc.title}（全文）"))
            blocks += [("p", p) for p in art.text.split("\n")]
            continue
        ctx = f"（{' › '.join(art.headings)}）" if art.headings else ""
        blocks.append(("h3", f"《{doc.title}》{art.label}{ctx}"))
        blocks += [("p", p) for p in art.text.split("\n")]
    return blocks


def md_doc(doc: law.Document) -> str:
    head = (f"# {doc.title}\n\n"
            f"> 版本：{doc.header.get('version','')}\n"
            f"> 施行日期：{doc.header.get('effective','')}\n"
            f"> 来源：{doc.header.get('source','')}\n"
            f"> 抓取日期：{doc.header.get('fetched','')}\n"
            f"> 收录条数：{sum(1 for a in doc.articles if a.no > 0)}\n")
    if doc.header.get("note"):
        head += f">\n> ⚠️ **注意**：{doc.header['note']}\n"
    body: List[str] = []
    for art in doc.articles:
        if art.no == 0:
            body.append(f"## {doc.title}（全文）\n\n{art.text}\n")
            continue
        ctx = f"\n*（{' › '.join(art.headings)}）*\n" if art.headings else ""
        body.append(f"### {doc.title} {art.label}{ctx}\n{art.text}\n")
    return head + "\n---\n\n" + "\n".join(body)


def md_to_blocks(text: str) -> List[Tuple[str, str]]:
    blocks: List[Tuple[str, str]] = []
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            continue
        if s.startswith("#### "):
            blocks.append(("h3", s[5:].replace("**", "").replace("`", "")))
        elif s.startswith("### "):
            blocks.append(("h3", s[4:].replace("**", "").replace("`", "")))
        elif s.startswith("## "):
            blocks.append(("h2", s[3:].replace("**", "").replace("`", "")))
        elif s.startswith("# "):
            blocks.append(("h1", s[2:].replace("**", "").replace("`", "")))
        else:
            blocks.append(("p", s.replace("**", "").replace("`", "")))
    return blocks


# --------------------------------------------------------------------------
# 手机端接入说明
# --------------------------------------------------------------------------

_MOBILE_README_FALLBACK = """# 手机端接入说明

本文件由 scripts/build_kb.py 生成。完整版见仓库 docs/PLATFORM-GUIDE.md。
请上传 `中国法律条文-核心版*.docx` 到 App 的知识库，
并把 `01-系统提示词-可复制.txt` 粘贴到「人设 / 自定义指令」。
"""


def mobile_readme() -> str:
    """优先读取仓库内的 docs/PLATFORM-GUIDE.md，保证文档只有一份。"""
    doc = ROOT / "docs" / "PLATFORM-GUIDE.md"
    if doc.exists():
        return doc.read_text(encoding="utf-8")
    return _MOBILE_README_FALLBACK



# --------------------------------------------------------------------------
# 构建
# --------------------------------------------------------------------------

def build_desktop(out: Path, docs: List[law.Document], max_chars: int,
                  formats: Sequence[str]) -> List[Path]:
    out.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    guide = ROOT / "prompts" / "system-prompt-zh.md"
    usage = out / "00-使用说明.md"
    usage.write_text("# 使用说明\n\n" + DISCLAIMER_BLOCK + "\n\n---\n\n"
                     + (guide.read_text(encoding="utf-8") if guide.exists() else ""),
                     encoding="utf-8")
    written.append(usage)

    idx = 1
    for cat, label in CATEGORIES:
        group = sorted([d for d in docs if d.category == cat],
                       key=lambda x: x.header.get("short", ""))
        if not group:
            continue
        pieces = [md_doc(d) for d in group]
        text = "\n\n".join(pieces)
        limit = max_chars if max_chars > 0 else len(text) + 1
        chunks, cur = [], ""
        for p in pieces:
            if len(cur) + len(p) > limit and cur:
                chunks.append(cur); cur = ""
            cur += p + "\n\n"
        if cur.strip():
            chunks.append(cur)
        for i, chunk in enumerate(chunks, 1):
            suffix = f"-{i}" if len(chunks) > 1 else ""
            head = f"# {label} · 法规条文汇编{suffix}\n\n{DISCLAIMER_BLOCK}\n\n---\n\n"
            if "md" in formats:
                f = out / f"{idx:02d}-{label}{suffix}.md"
                f.write_text(head + chunk, encoding="utf-8"); written.append(f)
            if "txt" in formats:
                f = out / f"{idx:02d}-{label}{suffix}.txt"
                f.write_text((head + chunk).replace("**", ""), encoding="utf-8"); written.append(f)
            if "docx" in formats:
                f = out / f"{idx:02d}-{label}{suffix}.docx"
                blocks: List[Tuple[str, str]] = [("h1", f"{label} · 法规条文汇编"),
                                                 ("p", DISCLAIMER_BLOCK)]
                for d in group:
                    blocks.extend(doc_to_blocks(d))
                write_docx(f, blocks); written.append(f)
        idx += 1

    for name, files in [("实务指南", ["intake-questions.md", "labor-playbook.md",
                                      "company-playbook.md", "civil-playbook.md"]),
                        ("检索词与输出模板", ["query-expansion.md", "output-templates.md",
                                              "currency.md"])]:
        parts = [f"# {name}\n\n"]
        for fn in files:
            p = ROOT / "references" / fn
            if p.exists():
                parts += [p.read_text(encoding="utf-8"), "\n\n---\n\n"]
        content = "".join(parts)
        f = out / f"{idx:02d}-{name}.md"
        f.write_text(content, encoding="utf-8"); written.append(f)
        if "docx" in formats:
            f = out / f"{idx:02d}-{name}.docx"
            write_docx(f, md_to_blocks(content)); written.append(f)
        idx += 1

    allin = [f"# 全部法规合集\n\n{DISCLAIMER_BLOCK}\n\n---\n\n"] + \
            [md_doc(d) for d in sorted(docs, key=lambda x: (x.category, x.header.get("short", "")))]
    f = out / "全部法规合集.md"
    f.write_text("\n\n".join(allin), encoding="utf-8"); written.append(f)
    print(f"[kb] desktop 形态：{len(written)} 个文件 → {out}")
    return written


GUIDE_FILES = [("intake-questions.md", "先问后答：必问清单与提问话术"),
               ("labor-playbook.md", "劳动法检索地图"),
               ("company-playbook.md", "公司法检索地图"),
               ("civil-playbook.md", "民法典检索地图"),
               ("query-expansion.md", "口语 → 法言法语检索词对照表"),
               ("output-templates.md", "输出模板与「总结回答」模板")]


def build_mobile(out: Path, docs: List[law.Document], formats: Sequence[str]) -> List[Path]:
    out.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []

    r = out / "00-先看这个-接入说明.md"
    r.write_text(mobile_readme(), encoding="utf-8"); written.append(r)

    pt = out / "01-系统提示词-可复制.txt"
    src = ROOT / "prompts" / "system-prompt-zh.md"
    if src.exists():
        t = src.read_text(encoding="utf-8")
        blocks = re.findall(r"```text\n(.*?)```", t, re.S)
        pt.write_text((blocks[0].strip() if blocks else t), encoding="utf-8")
    else:
        pt.write_text("（未找到 prompts/system-prompt-zh.md）", encoding="utf-8")
    written.append(pt)

    def pack(name: str, sel: List[law.Document]) -> None:
        text_parts = ["", "=" * 68, name, "=" * 68, DISCLAIMER_BLOCK, ""]
        blocks: List[Tuple[str, str]] = [("title", name), ("p", DISCLAIMER_BLOCK)]
        for fn, title in GUIDE_FILES:
            p = ROOT / "references" / fn
            if not p.exists():
                continue
            content = p.read_text(encoding="utf-8")
            text_parts += ["", "=" * 68, title, "=" * 68, "", content]
            blocks += [("h1", title)] + md_to_blocks(content)
        for d in sorted(sel, key=lambda x: (x.category, x.header.get("short", ""))):
            text_parts.append(doc_to_text(d))
            blocks.extend(doc_to_blocks(d))
        for fmt in formats:
            f = out / f"{name}.{fmt}"
            if fmt == "docx":
                write_docx(f, blocks)
            else:
                f.write_text("\n".join(text_parts).replace("**", ""), encoding="utf-8")
            written.append(f)

    core = [d for d in docs if d.category in CORE_CATEGORIES]
    pack("中国法律条文-核心版-民法典与劳动", core)
    pack("中国法律条文-全量版-33部法规", docs)
    print(f"[kb] mobile 形态：{len(written)} 个文件 → {out}")
    return written


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="生成可上传到聊天 App 知识库的语料包")
    p.add_argument("--out", default="", help="输出目录（默认按 profile 自动决定）")
    p.add_argument("--profile", default="desktop", choices=["desktop", "mobile", "all"])
    p.add_argument("--format", default="", help="md,txt,docx 逗号分隔；mobile 默认 txt,docx")
    p.add_argument("--max-chars", type=int, default=0, help="desktop 单文件最大字符数，>0 时切分")
    p.add_argument("--zip", action="store_true", help="额外生成 zip")
    args = p.parse_args(argv)

    docs = law.load_corpus()
    total = sum(1 for d in docs for a in d.articles if a.no > 0)
    print(f"[kb] 语料：{len(docs)} 部法规 / {total} 条条文")

    written: List[Path] = []
    groups: List[Tuple[str, List[Path]]] = []

    if args.profile in ("desktop", "all"):
        fmt = [f.strip() for f in args.format.split(",") if f.strip()] or ["md"]
        out = Path(args.out) if args.out else ROOT / "dist" / "knowledge-base"
        w = build_desktop(out, docs, args.max_chars, fmt)
        written += w; groups.append(("knowledge-base", w))

    if args.profile in ("mobile", "all"):
        fmt = [f.strip() for f in args.format.split(",") if f.strip()] or ["txt", "docx"]
        out = Path(args.out) / "mobile" if args.out else ROOT / "dist" / "kb-mobile"
        w = build_mobile(out, docs, fmt)
        written += w; groups.append(("kb-mobile", w))

    print()
    for f in written:
        print(f"  · {f.name:<52} {f.stat().st_size/1024:>8.1f} KB")

    if args.zip:
        zip_base = Path(args.out) if args.out else ROOT / "dist"
        for label, files in groups:
            zpath = zip_base / f"china-legal-advisor-{label}.zip"
            zpath.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
                for f in files:
                    z.write(f, arcname=f.name)
            try:
                shown = zpath.relative_to(ROOT)
            except ValueError:          # --out 指向仓库外时无法相对化
                shown = zpath
            print(f"[kb] 已打包：{shown}（{zpath.stat().st_size/1024:.1f} KB）")

    print("\n[kb] 手机端：上传 `中国法律条文-核心版-*.docx` 到知识库，"
          "把 `01-系统提示词-可复制.txt` 粘贴到人设 / 自定义指令。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
