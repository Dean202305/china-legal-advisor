#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""add_document.py —— 把一部新法规加入离线语料库（references/raw/）。

示例：
  # 从官方 URL 抓取（自动去 HTML 标签并清理）
  python3 scripts/add_document.py \
      --title "中华人民共和国社会保险法" --short "社会保险法" --category labor \
      --version "2018年12月29日修正" --effective 2019-01-01 \
      --source "https://www.gov.cn/..." --slug social-insurance-law \
      --from-url "https://www.gov.cn/..."

  # 从已清理好的本地文本导入
  python3 scripts/add_document.py --title "..." --short "..." --category company \
      --version "..." --effective 2025-01-01 --source "https://..." \
      --slug xxx --from-file /tmp/xxx.txt

写入后会立即做条号连续性校验，并提示重建索引。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import html
import re
import sys
import urllib.request
from pathlib import Path
from typing import List, Optional, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from law import ART_MARK_RE, cn2int, _clean_body, load_corpus  # noqa: E402

RAW_DIR = SCRIPT_DIR.parent / "references" / "raw"
CATEGORIES = {"labor", "company", "civil", "procedure", "other"}
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=45) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        data = resp.read()
    raw = data.decode(charset, errors="ignore")
    # 去脚本/样式，再把标签换成换行，保留段落结构
    raw = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?i)</(p|div|h[1-6]|li|tr)>", "\n", raw)
    raw = re.sub(r"(?s)<[^>]+>", "", raw)
    return html.unescape(raw)


def article_numbers(body: str) -> List[int]:
    """用与 law.py 相同的"递增序列"规则抽出条号，用于校验。"""
    nos: List[int] = []
    expected = 1
    for m in ART_MARK_RE.finditer(body):
        no = cn2int(m.group(1))
        if no == expected:
            nos.append(no)
            expected += 1
    return nos


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="向语料库添加一部法规")
    p.add_argument("--title", required=True, help="法规全称")
    p.add_argument("--short", required=True, help="简称")
    p.add_argument("--category", required=True, choices=sorted(CATEGORIES))
    p.add_argument("--version", required=True, help="通过/修正/修订说明（含日期）")
    p.add_argument("--effective", default="", help="施行日期 YYYY-MM-DD")
    p.add_argument("--source", required=True, help="来源 URL")
    p.add_argument("--source2", default="", help="交叉验证来源 URL")
    p.add_argument("--slug", required=True, help="文件名（不含 .txt），如 labor-contract-law")
    p.add_argument("--articles", type=int, default=0, help="声明的条文总数（可选，用于校验）")
    p.add_argument("--status", default="现行有效", help="现行有效/已修改/已废止")
    p.add_argument("--excerpt", default="", help="只保留正文某段（正则），用于去掉网页噪音")
    p.add_argument("--allow-unnumbered", action="store_true",
                   help="允许不设条号的文件（批复、决定等），写入 articles: 0")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-url", dest="from_url", help="从 URL 抓取")
    src.add_argument("--from-file", dest="from_file", help="从本地文本导入")
    args = p.parse_args(argv)

    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", args.slug):
        print("[add] slug 只能包含小写字母、数字和连字符", file=sys.stderr)
        return 2

    if args.from_url:
        print(f"[add] 抓取 {args.from_url}")
        try:
            text = fetch(args.from_url)
        except Exception as exc:  # noqa: BLE001
            print(f"[add] 抓取失败：{exc}", file=sys.stderr)
            return 1
    else:
        path = Path(args.from_file)
        if not path.exists():
            print(f"[add] 文件不存在：{path}", file=sys.stderr)
            return 1
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "<html" in text[:2000].lower():
            text = re.sub(r"(?is)<(script|style).*?</\1>", " ", text)
            text = re.sub(r"(?s)<[^>]+>", "\n", text)
            text = html.unescape(text)

    if args.excerpt:
        m = re.search(args.excerpt, text, re.S)
        if not m:
            print("[add] --excerpt 正则未匹配到内容", file=sys.stderr)
            return 1
        text = m.group(0)

    body = _clean_body(text)
    nos = article_numbers(body)
    if not nos and not args.allow_unnumbered:
        print("[add] 警告：未识别出任何条文（第X条）。请检查来源是否为全文、"
              "或正文是否由 JS 动态加载。未写入文件。\n"
              "      若该文件确实不设条号（批复、决定等），请加 --allow-unnumbered。",
              file=sys.stderr)
        return 1
    if not nos:
        print("[add] 注意：该文件不设条号，将以 articles: 0 写入（全文作为一条可检索内容）。")

    last = max(nos) if nos else 0
    # 序列号必须从 1 连续到 last
    missing = sorted(set(range(1, last + 1)) - set(nos))
    if missing:
        print(f"[add] 警告：条号不连续，缺失 {missing[:10]}"
              f"{' …' if len(missing) > 10 else ''}（共缺 {len(missing)} 条）", file=sys.stderr)
    if args.articles and args.articles != last:
        print(f"[add] 警告：声明 articles={args.articles}，实际末条为 {last}", file=sys.stderr)

    header = [
        "---",
        f"title: {args.title}",
        f"short: {args.short}",
        f"category: {args.category}",
        f"version: {args.version}",
        f"effective: {args.effective}",
        f"source: {args.source}",
    ]
    if args.source2:
        header.append(f"source2: {args.source2}")
    header += [
        f"fetched: {_dt.date.today().isoformat()}",
        f"articles: {args.articles or last}",
        f"status: {args.status}",
        "---",
        "",
    ]

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = RAW_DIR / f"{args.slug}.txt"
    out.write_text("\n".join(header) + body + "\n", encoding="utf-8")
    print(f"[add] 已写入 {out}（{len(body):,} 字，{last} 条）")

    # 立即复核解析结果
    docs = load_corpus(force=True)
    doc = next((d for d in docs if d.slug == args.slug), None)
    if doc is None:
        print("[add] 解析复核失败：文件未被载入", file=sys.stderr)
        return 1
    gaps = sorted(set(range(1, max((a.no for a in doc.articles), default=0) + 1))
                  - {a.no for a in doc.articles})
    print(f"[add] 复核：解析出 {len(doc.articles)} 条"
          f"{'，缺口 ' + str(gaps[:10]) if gaps else '，条号连续 ✓'}")
    print("[add] 下一步：python3 scripts/law.py index  # 重建 CORPUS.md 与 index.json")
    return 0 if not gaps else 1


if __name__ == "__main__":
    sys.exit(main())
