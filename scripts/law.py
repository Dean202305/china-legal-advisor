#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""law.py —— 中国法律法规条文级检索工具（离线，零依赖，Python 3.8+）

语料位于 ../references/raw/*.txt，每个文件一部法律/法规/司法解释，
文件头为 "---" 包裹的元数据（见 references/raw 内文件），其后为正文。

用法示例：
    python3 law.py list                      # 列出语料库全部文件
    python3 law.py search 竞业限制 违约金        # 全文检索（默认 AND，返回相关条文）
    python3 law.py search 试用期 --doc 劳动合同法
    python3 law.py search "严重违反" --or 辞退 解除
    python3 law.py article 劳动合同法 38        # 精确取条文
    python3 law.py article 民法典 第五百七十七条 -A 2
    python3 law.py verify                    # 校验条号完整性（缺口/重复/与头部不符）
    python3 law.py stats                     # 语料库统计
    python3 law.py index                     # 生成 index.json 与 CORPUS.md

所有命令都支持 --json，便于程序化消费。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

RAW_DIR = Path(__file__).resolve().parent.parent / "references" / "raw"

# --------------------------------------------------------------------------
# 中文数字 <-> 整数
# --------------------------------------------------------------------------

_CN_DIGITS = {
    "零": 0, "〇": 0, "一": 1, "壹": 1, "二": 2, "两": 2, "贰": 2, "三": 3, "叁": 3,
    "四": 4, "肆": 4, "五": 5, "伍": 5, "六": 6, "陆": 6, "七": 7, "柒": 7,
    "八": 8, "捌": 8, "九": 9, "玖": 9,
}
_CN_UNITS = {"十": 10, "拾": 10, "百": 100, "佰": 100, "千": 1000, "仟": 1000}


def cn2int(text: str) -> Optional[int]:
    """把 '一千二百六十' / '三十八' / '十' 转成整数；失败返回 None。"""
    if not text:
        return None
    if text.isdigit():
        return int(text)
    total, current, seen = 0, 0, False
    for ch in text:
        if ch in _CN_DIGITS:
            current = _CN_DIGITS[ch]
            seen = True
        elif ch in _CN_UNITS:
            unit = _CN_UNITS[ch]
            if not seen:
                current = 1
            total += current * unit
            current = 0
            seen = True
        else:
            return None
    return total + current


def int2cn(num: int) -> str:
    """把整数转成中文数字（用于生成引用串），支持 1-99999。"""
    if num <= 0:
        return str(num)
    if num < 10:
        return "一二三四五六七八九"[num - 1]
    units = ["", "十", "百", "千", "万"]
    digits = "零一二三四五六七八九"
    s = str(num)
    n = len(s)
    out: List[str] = []
    zero_pending = False
    for i, ch in enumerate(s):
        d = int(ch)
        pos = n - i - 1
        if d == 0:
            zero_pending = True
            continue
        if zero_pending and out:
            out.append("零")
        zero_pending = False
        out.append(digits[d] + units[pos])
    text = "".join(out)
    # 中文习惯：十/十一 而非 一十/一十一
    if text.startswith("一十"):
        text = text[1:]
    return text


# --------------------------------------------------------------------------
# 数据结构
# --------------------------------------------------------------------------

HEADING_RE = re.compile(r"^第[一二三四五六七八九十百千零〇]+(?:分编|编|章|节)\s*\S[\s\S]{0,40}$")
ATTACH_RE = re.compile(r"^(附则|总则)\s*$")
# 标题行不含句读；用于把"第四章规定的……"这类正文行排除掉
HEADING_PUNCT_RE = re.compile(r"[。；，、,;：:]")
ART_MARK_RE = re.compile(r"第([一二三四五六七八九十百千零〇两]+)条")
# 检索用户输入时允许阿拉伯数字（"第38条"/"38"），但正文切分只用中文数字
ART_LOOKUP_RE = re.compile(r"第\s*([一二三四五六七八九十百千零〇两]+|\d+)\s*条")
NOISE_PREFIXES = ("扫一扫", "责任编辑", "分享到", "上一篇", "下一篇", "相关阅读", "返回顶部")


@dataclass
class Article:
    doc: "Document"
    no: int
    label: str
    text: str
    headings: List[str] = field(default_factory=list)
    order: int = 0

    @property
    def citation(self) -> str:
        if self.no == 0:
            return f"《{self.doc.title}》"
        return f"《{self.doc.title}》第{int2cn(self.no)}条"

    def heading_path(self) -> str:
        return " › ".join(self.headings)

    def to_dict(self, snippet: str = "") -> Dict[str, object]:
        return {
            "citation": self.citation,
            "doc": self.doc.slug,
            "short": self.doc.short,
            "title": self.doc.title,
            "no": self.no,
            "label": self.label,
            "headings": self.headings,
            "text": self.text,
            "snippet": snippet,
            "source": self.doc.header.get("source", ""),
            "version": self.doc.header.get("version", ""),
            "effective": self.doc.header.get("effective", ""),
            "note": self.doc.header.get("note", ""),
        }


@dataclass
class Document:
    slug: str
    path: Path
    header: Dict[str, str]
    body: str
    articles: List[Article] = field(default_factory=list)

    @property
    def title(self) -> str:
        return self.header.get("title") or self.slug

    @property
    def short(self) -> str:
        return self.header.get("short") or self.title

    @property
    def category(self) -> str:
        return (self.header.get("category") or "other").strip()

    def by_no(self, no: int) -> Optional[Article]:
        for art in self.articles:
            if art.no == no:
                return art
        return None

    def find(self, needle: str) -> Optional[Article]:
        """按条号/条标签查找，接受 '38'、'第38条'、'三十八'、'第三十八条'。"""
        needle = needle.strip()
        m = ART_LOOKUP_RE.search(needle)
        if m:
            no = cn2int(m.group(1))
        else:
            no = cn2int(needle)
        if no is None:
            return None
        return self.by_no(no)


# --------------------------------------------------------------------------
# 语料解析
# --------------------------------------------------------------------------

def _clean_body(body: str) -> str:
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    body = re.sub(r"[\u00a0\u3000]", " ", body)
    body = re.sub(r"[ \t]+", " ", body)
    lines = []
    for line in body.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith(NOISE_PREFIXES):
            continue
        if line in {"目录", "全文", "正文"}:
            continue
        # 有些官方页面把条号与正文连排（"第一条为了……"），补一个空格便于引用
        line = re.sub(r"^(第[一二三四五六七八九十百千零〇]+条)(?=[^\s])", r"\1 ", line)
        lines.append(line)
    return "\n".join(lines)


def _is_heading(line: str) -> bool:
    if len(line) > 60:
        return False
    if HEADING_PUNCT_RE.search(line):
        return False
    return bool(HEADING_RE.match(line) or ATTACH_RE.match(line))


def _level_of(stack: Sequence[str], kinds: Sequence[str]) -> int:
    """返回 stack 中最靠下的、属于给定类别的层级（1 起）；没有则返回 0。"""
    for i in range(len(stack) - 1, -1, -1):
        if any(k in stack[i] for k in kinds):
            return i + 1
    return 0


def _heading_depth(line: str, stack: Sequence[str]) -> int:
    """判断标题层级，用于维护"编 › 分编 › 章 › 节"的层级路径。

    层级必须相对于**当前已有的层级**来判断，而不是写死：
    仲裁法只有"章"没有"编"，此时"第二章"应当占据第一层，
    否则后续章节会层层叠加成 "第二章 › 第三章 › …"。
    """
    if line in ("附则", "总则"):
        return 1
    if "分编" in line:
        return 2 if _level_of(stack, ("编",)) == 1 else 1
    if "编" in line:
        return 1
    if "章" in line:
        return _level_of(stack, ("编", "分编")) + 1
    if "节" in line:
        chapter = _level_of(stack, ("章",))
        if chapter:
            return chapter + 1
        return _level_of(stack, ("编", "分编")) + 1
    return len(stack) + 1


def _heading_snapshots(body: str) -> List[Tuple[int, Tuple[str, ...]]]:
    """返回 [(偏移量, 到该标题为止的层级路径), ...]，按偏移升序。"""
    events: List[Tuple[int, str]] = []
    pos = 0
    for line in body.split("\n"):
        if _is_heading(line):
            events.append((pos, line))
        pos += len(line) + 1
    snaps: List[Tuple[int, Tuple[str, ...]]] = []
    stack: List[str] = []
    for pos, line in events:
        depth = _heading_depth(line, stack)
        stack = stack[: depth - 1]
        stack.append(line)
        snaps.append((pos, tuple(stack)))
    return snaps


def _context_at(snaps: Sequence[Tuple[int, Tuple[str, ...]]], offset: int) -> List[str]:
    """取 offset 之前最后一个标题路径。"""
    lo, hi, found = 0, len(snaps) - 1, None
    while lo <= hi:
        mid = (lo + hi) // 2
        if snaps[mid][0] < offset:
            found = snaps[mid]
            lo = mid + 1
        else:
            hi = mid - 1
    return list(found[1]) if found else []


def _split_articles(doc: Document, body: str) -> List[Article]:
    """按条号**递增序列**切分条文。

    正文里的"第X条"有时只是条文内部的援引（例如"依照本法第三十九条的规定"），
    单纯正则切分会切碎。这里只接受条号等于"下一条应有条号"的位置，
    因此跳过的必然是援引；这也顺带校验了条号是否连续。

    当某个"第X条"出现在行首时，几乎可以确定是条文标题；出现在行中间的，
    通常是援引。为了处理"援引的条号恰好等于应有条号"这种歧义
    （如第二条正文里写"依照本法第三条的规定处理"），若该条号在**后面**
    还有行首出现，则跳过当前这个行中间的匹配。
    """
    candidates: List[Tuple[int, int, int, bool]] = []  # (start, end, no, line_start)
    for m in ART_MARK_RE.finditer(body):
        no = cn2int(m.group(1))
        if no is None:
            continue
        i = m.start()
        line_start = i == 0 or body[i - 1] == "\n"
        if not line_start:
            # 允许行首缩进/标点空白
            j = i - 1
            while j >= 0 and body[j] in " \t\u3000":
                j -= 1
            line_start = j < 0 or body[j] == "\n"
        candidates.append((i, m.end(), no, line_start))

    # 记录每个条号在"行首"出现的位置，用于上面的前瞻判断
    line_start_positions: Dict[int, List[int]] = {}
    for idx, (_, _, no, ls) in enumerate(candidates):
        if ls:
            line_start_positions.setdefault(no, []).append(idx)

    accepted: List[Tuple[int, int, int]] = []
    expected = 1
    for idx, (start, end, no, ls) in enumerate(candidates):
        if no != expected:
            continue
        if not ls:
            later = line_start_positions.get(no, [])
            if any(j > idx for j in later):
                # 后面还有行首的同条号匹配，那才是真正的条文标题
                continue
        accepted.append((start, end, no))
        expected += 1
    if not accepted:
        return []

    snaps = _heading_snapshots(body)
    articles: List[Article] = []
    for idx, (start, end, no) in enumerate(accepted):
        seg_end = accepted[idx + 1][0] if idx + 1 < len(accepted) else len(body)
        segment = body[end:seg_end]
        seg_lines = [ln for ln in segment.split("\n") if ln.strip()]

        # 段尾的"第X编/章/节"标题属于**下一条**，从本条正文里剥掉
        while seg_lines and _is_heading(seg_lines[-1]):
            seg_lines.pop()
        text = "\n".join(seg_lines).strip()

        art = Article(
            doc=doc, no=no, label=f"第{int2cn(no)}条", text=text,
            headings=_context_at(snaps, start), order=len(articles),
        )
        articles.append(art)
    return articles


def parse_document(path: Path) -> Document:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    header: Dict[str, str] = {}
    body = raw
    if raw.lstrip().startswith("---"):
        stripped = raw.lstrip()
        end = stripped.find("\n---", 3)
        if end != -1:
            block = stripped[3:end]
            body = stripped[end + 4:]
            for line in block.split("\n"):
                line = line.strip()
                if not line or line.startswith("#") or ":" not in line:
                    continue
                key, _, value = line.partition(":")
                header[key.strip().lower()] = value.strip()
    slug = path.stem
    doc = Document(slug=slug, path=path, header=header, body=body)
    doc.body = _clean_body(body)
    doc.articles = _split_articles(doc, doc.body)
    if not doc.articles and doc.body.strip():
        # 批复、决定等短文件可能不设条号，把全文作为一条伪条文，保证仍可被检索
        doc.articles = [Article(
            doc=doc, no=0, label="全文", text=doc.body.strip(), headings=[], order=0,
        )]
    return doc


def has_numbered_articles(doc: Document) -> bool:
    return bool(doc.articles) and doc.articles[0].no != 0


_CORPUS: Optional[List[Document]] = None


def load_corpus(force: bool = False) -> List[Document]:
    global _CORPUS
    if _CORPUS is not None and not force:
        return _CORPUS
    if not RAW_DIR.exists():
        raise SystemExit(f"[law] 语料目录不存在：{RAW_DIR}")
    docs: List[Document] = []
    for path in sorted(RAW_DIR.glob("*.txt")):
        try:
            docs.append(parse_document(path))
        except Exception as exc:  # noqa: BLE001
            print(f"[law] 解析失败 {path.name}: {exc}", file=sys.stderr)
    _CORPUS = docs
    return docs


def resolve_doc(token: str, docs: Sequence[Document]) -> Document:
    """按 slug / 简称 / 全称子串解析文档，歧义时取最短匹配并提示。"""
    t = token.strip().lower()
    exact = [d for d in docs if d.slug.lower() == t or d.short.lower() == t]
    if exact:
        return exact[0]
    subs = [d for d in docs if t in d.short.lower() or t in d.title.lower() or t in d.slug.lower()]
    if not subs:
        raise SystemExit(f"[law] 未找到法规：{token}\n可用：{', '.join(d.short for d in docs)}")
    subs.sort(key=lambda d: len(d.short))
    if len(subs) > 1:
        print(f"[law] '{token}' 匹配到多个文件，使用：{subs[0].short}", file=sys.stderr)
    return subs[0]


# --------------------------------------------------------------------------
# 输出格式
# --------------------------------------------------------------------------

HEAD = "─" * 72


def fmt_article(art: Article, snippet: str = "", show_source: bool = False) -> str:
    meta = [art.doc.short]
    if art.headings:
        meta.append(art.heading_path())
    head = f"【{art.citation}】({' ｜ '.join(meta)})"
    body = snippet or art.text
    lines = [head, body]
    if show_source:
        src = art.doc.header.get("source", "")
        ver = art.doc.header.get("version", "")
        eff = art.doc.header.get("effective", "")
        lines.append(f"  ↳ 版本：{ver}｜施行：{eff}｜来源：{src}")
        note = art.doc.header.get("note", "")
        if note:
            lines.append(f"  ⚠ 注意：{note}")
    return "\n".join(lines)


def make_snippet(text: str, terms: Sequence[str], width: int = 220) -> str:
    if not terms:
        return text[:width]
    low = text.lower()
    pos = -1
    for term in terms:
        pos = low.find(term.lower())
        if pos != -1:
            break
    if pos == -1:
        return text[:width]
    start = max(0, pos - width // 3)
    end = min(len(text), start + width)
    out = text[start:end]
    if start > 0:
        out = "…" + out
    if end < len(text):
        out = out + "…"
    return out


# --------------------------------------------------------------------------
# 检索
# --------------------------------------------------------------------------

def score_article(art: Article, terms: Sequence[str], require_all: bool) -> Optional[Tuple[int, int]]:
    hay = art.text.lower()
    head = art.heading_path().lower()
    title = (art.doc.short + art.doc.title).lower()
    hits, total, best = 0, 0, 0
    for term in terms:
        # 直接按条号检索（"第五百八十八条"、"第38条"）时精确命中该条
        m = ART_LOOKUP_RE.search(term)
        by_number = bool(m) and cn2int(m.group(1)) == art.no
        c = hay.count(term.lower())
        if c == 0 and not by_number:
            c = head.count(term.lower()) + title.count(term.lower())
        if c > 0 or by_number:
            hits += 1
        elif require_all:
            return None
        total += c + (5 if by_number else 0)
        best = max(best, c)
    if require_all and hits < len(terms):
        return None
    if hits == 0:
        return None
    # 命中词种类优先，其次总频次；标题命中加权
    head_bonus = sum(1 for t in terms if t.lower() in head or t.lower() in title)
    return (hits * 100 + head_bonus * 40 + min(total, 60) + min(best, 10), total)


def cmd_search(args: argparse.Namespace) -> int:
    docs = load_corpus()
    terms = [t for t in args.terms if t.strip()]
    if not terms and not args.regex:
        print("[law] 请提供检索词", file=sys.stderr)
        return 2
    if args.doc:
        docs = [resolve_doc(args.doc, docs)]
    if args.cat:
        docs = [d for d in docs if d.category == args.cat]
        if not docs:
            print(f"[law] 没有 category={args.cat} 的文件", file=sys.stderr)
            return 2

    results: List[Tuple[Tuple[int, int], Article, str]] = []
    if args.regex:
        pattern = re.compile(args.regex, re.I)
        for doc in docs:
            for art in doc.articles:
                target = art.text + "\n" + art.label + "\n" + art.heading_path()
                m = pattern.search(target)
                if m:
                    results.append(((1000, 0), art, make_snippet(art.text, [m.group(0)])))
    else:
        for doc in docs:
            for art in doc.articles:
                sc = score_article(art, terms, require_all=not args.or_)
                if sc:
                    results.append((sc, art, make_snippet(art.text, terms)))

    results.sort(key=lambda r: (-r[0][0], r[1].doc.slug, r[1].no))
    results = results[: args.limit]

    if args.json:
        print(json.dumps(
            [art.to_dict(snippet=sn) for _, art, sn in results],
            ensure_ascii=False, indent=2,
        ))
        return 0 if results else 1
    if not results:
        what = args.regex if args.regex else " ".join(terms)
        print(f"[law] 未命中：{what}", file=sys.stderr)
        return 1
    label = f"正则 {args.regex}" if args.regex else "检索词：" + " ".join(terms) + \
        ("，OR" if args.or_ else "，AND")
    print(f"命中 {len(results)} 条（{label}）：\n")
    for i, (_, art, sn) in enumerate(results, 1):
        print(f"{i}. " + fmt_article(art, sn, show_source=args.source))
        print()
    print(HEAD)
    print("提示：以上为离线语料库检索结果，引用前请核对现行有效版本（见 references/currency.md）。")
    return 0


def cmd_article(args: argparse.Namespace) -> int:
    docs = load_corpus()
    doc = resolve_doc(args.doc, docs)
    art = doc.find(args.article)
    if art is None:
        print(f"[law] {doc.short} 中未找到 {args.article}（该文件共 {len(doc.articles)} 条）", file=sys.stderr)
        return 1
    lo = max(1, art.no - (args.before or 0))
    hi = art.no + (args.after or 0)
    picked = [a for a in doc.articles if lo <= a.no <= hi]
    if args.json:
        print(json.dumps([a.to_dict() for a in picked], ensure_ascii=False, indent=2))
        return 0
    for a in picked:
        mark = "▶ " if a.no == art.no else "  "
        print(mark + fmt_article(a, show_source=args.source))
        print()
    if args.source:
        return 0
    ver = doc.header.get("version", "")
    eff = doc.header.get("effective", "")
    src = doc.header.get("source", "")
    print(HEAD)
    print(f"《{doc.title}》 {ver}｜施行：{eff}｜共 {len(doc.articles)} 条")
    if src:
        print(f"来源：{src}")
    note = doc.header.get("note", "")
    if note:
        print(f"⚠ 注意：{note}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    docs = load_corpus()
    if args.json:
        print(json.dumps([{
            "slug": d.slug, "title": d.title, "short": d.short, "category": d.category,
            "articles": len(d.articles), "version": d.header.get("version", ""),
            "effective": d.header.get("effective", ""), "status": d.header.get("status", "现行有效"),
        } for d in docs], ensure_ascii=False, indent=2))
        return 0
    cats: Dict[str, List[Document]] = {}
    for d in docs:
        cats.setdefault(d.category, []).append(d)
    label = {"labor": "劳动与社会保障", "company": "公司与企业", "civil": "民法典", "procedure": "程序法", "other": "其他"}
    for cat in sorted(cats):
        print(f"## {label.get(cat, cat)}（{cat}）")
        for d in sorted(cats[cat], key=lambda x: x.title):
            eff = d.header.get("effective", "")
            ver = d.header.get("version", "")
            n = sum(1 for a in d.articles if a.no > 0)
            count = f"{n:>4} 条" if n else " 无分条"
            extra = f"｜施行 {eff}" if eff else ""
            print(f"  - {d.short:<28} {count}  {ver}{extra}")
        print()
    print(f"共 {len(docs)} 个文件。检索：python3 law.py search <关键词>")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    docs = load_corpus()
    problems = 0
    rows = []
    for d in docs:
        nos = [a.no for a in d.articles if a.no > 0]
        declared = d.header.get("articles", "")
        try:
            declared_n = int(re.sub(r"\D", "", declared) or 0)
        except ValueError:
            declared_n = 0
        if not nos:
            # 不设条号的批复/决定类文件：只校验有正文、且声明为 0
            ok = bool(d.body.strip()) and declared_n == 0
            problems += 0 if ok else 1
            rows.append({
                "slug": d.slug, "short": d.short, "articles": 0, "last": 0,
                "declared": declared_n, "gaps": [], "gap_count": 0, "dupes": [],
                "ok": ok, "chars": len(d.body), "expected_last": 0, "unnumbered": True,
            })
            continue
        gaps = sorted(set(range(1, (max(nos) if nos else 0) + 1)) - set(nos))
        dupes = sorted({n for n in nos if nos.count(n) > 1})
        expect_last = declared_n or (max(nos) if nos else 0)
        ok = bool(nos) and not gaps and not dupes and (not declared_n or max(nos) == declared_n)
        if not ok:
            problems += 1
        rows.append({
            "slug": d.slug, "short": d.short, "articles": len(nos),
            "last": max(nos) if nos else 0, "declared": declared_n,
            "gaps": gaps[:20], "gap_count": len(gaps), "dupes": dupes,
            "ok": ok, "chars": len(d.body), "expected_last": expect_last,
            "unnumbered": False,
        })
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0 if problems == 0 else 1
    print(f"{'文件':<34}{'条数':>6}{'末条':>7}{'声明':>7}{'缺口':>6}  状态")
    print("-" * 78)
    for r in rows:
        flag = "OK" if r["ok"] else ("缺口:" + ",".join(map(str, r["gaps"][:5])) if r["gaps"] else "不一致")
        print(f"{r['slug']:<34}{r['articles']:>6}{r['last']:>7}{r['declared']:>7}{r['gap_count']:>6}  {flag}")
    print("-" * 78)
    print(f"共 {len(rows)} 个文件，{problems} 个有问题。")
    return 0 if problems == 0 else 1


def cmd_stats(args: argparse.Namespace) -> int:
    docs = load_corpus()
    total_art = sum(1 for d in docs for a in d.articles if a.no > 0)
    total_chars = sum(len(d.body) for d in docs)
    per_cat: Dict[str, int] = {}
    for d in docs:
        per_cat[d.category] = per_cat.get(d.category, 0) + sum(1 for a in d.articles if a.no > 0)
    print(f"文件数：{len(docs)}｜条文总数：{total_art}｜正文字符数：{total_chars:,}")
    for cat, n in sorted(per_cat.items()):
        print(f"  {cat:<10} {n:>6} 条")
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    docs = load_corpus()
    out_dir = RAW_DIR.parent
    index = [{
        "slug": d.slug, "title": d.title, "short": d.short, "category": d.category,
        "version": d.header.get("version", ""), "effective": d.header.get("effective", ""),
        "status": d.header.get("status", "现行有效"), "source": d.header.get("source", ""),
        "article_count": sum(1 for a in d.articles if a.no > 0),
        "first_article": next((a.text[:80] for a in d.articles if a.no > 0), ""),
        "last_article_no": max((a.no for a in d.articles), default=0),
    } for d in docs]
    (out_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# 语料库目录（自动生成，勿手改）", "",
             f"共 {len(docs)} 个文件，{sum(len(d.articles) for d in docs)} 条条文。", ""]
    label = {"labor": "劳动与社会保障", "company": "公司与企业", "civil": "民法典",
             "procedure": "程序法", "other": "其他"}
    cats: Dict[str, List[Document]] = {}
    for d in docs:
        cats.setdefault(d.category, []).append(d)
    for cat in sorted(cats):
        lines.append(f"## {label.get(cat, cat)}")
        lines.append("")
        lines.append("| 文件 | 简称 | 条数 | 版本 | 施行日期 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for d in sorted(cats[cat], key=lambda x: x.title):
            ver = d.header.get("version", "").replace("|", "／")
            if len(ver) > 44:
                ver = ver[:44] + "…"
            n = sum(1 for a in d.articles if a.no > 0)
            lines.append(f"| `{d.slug}.txt` | {d.short} | {n} | "
                         f"{ver} | {d.header.get('effective','')} |")
        lines.append("")
    (out_dir / "CORPUS.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"[law] 已写入 {out_dir/'index.json'} 和 {out_dir/'CORPUS.md'}")
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="law.py", description="中国法律法规条文级离线检索",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="全文检索条文（默认 AND 语义）")
    s.add_argument("terms", nargs="*", help="检索词，可多个；含空格的短语请加引号")
    s.add_argument("-d", "--doc", help="限定某部法规（slug/简称/全称子串）")
    s.add_argument("-c", "--cat", help="限定类别：labor/company/civil/procedure")
    s.add_argument("-n", "--limit", type=int, default=8, help="返回条数上限，默认 8")
    s.add_argument("--or", dest="or_", action="store_true", help="改为 OR 语义")
    s.add_argument("--regex", help="使用正则表达式检索")
    s.add_argument("--source", action="store_true", help="附带版本与来源链接")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_search)

    a = sub.add_parser("article", help="精确取某一条（可带前后条）")
    a.add_argument("doc", help="法规 slug/简称/全称子串")
    a.add_argument("article", help="条号：38 / 第38条 / 第三十八条")
    a.add_argument("-A", "--after", type=int, default=0, help="同时显示其后 N 条")
    a.add_argument("-B", "--before", type=int, default=0, help="同时显示其前 N 条")
    a.add_argument("--source", action="store_true")
    a.add_argument("--json", action="store_true")
    a.set_defaults(func=cmd_article)

    l = sub.add_parser("list", help="列出语料库文件")
    l.add_argument("--json", action="store_true")
    l.set_defaults(func=cmd_list)

    v = sub.add_parser("verify", help="校验条号完整性")
    v.add_argument("--json", action="store_true")
    v.set_defaults(func=cmd_verify)

    st = sub.add_parser("stats", help="语料库统计")
    st.set_defaults(func=cmd_stats)

    ix = sub.add_parser("index", help="生成 index.json 与 CORPUS.md")
    ix.set_defaults(func=cmd_index)
    return p


def _reorder_search_argv(argv: Sequence[str]) -> List[str]:
    """argparse 的 nargs="*" 位置参数被选项打断时会报错，
    例如 `search 定金 --or 违约金`。这里把选项（连同其取值）挪到位置参数之前，
    使 `search [选项] 词1 词2` 与 `search 词1 --or 词2` 都能正常工作。
    """
    argv = list(argv)
    if not argv or argv[0] != "search":
        return argv
    value_opts = {"-d", "--doc", "-c", "--cat", "-n", "--limit", "--regex"}
    opts: List[str] = []
    pos: List[str] = []
    rest = argv[1:]
    i = 0
    while i < len(rest):
        tok = rest[i]
        if tok == "--":
            pos.extend(rest[i + 1:])
            break
        if tok.startswith("-") and tok != "-":
            opts.append(tok)
            key = tok.split("=", 1)[0]
            if "=" not in tok and key in value_opts and i + 1 < len(rest):
                opts.append(rest[i + 1])
                i += 1
        else:
            pos.append(tok)
        i += 1
    return ["search"] + opts + pos


def main(argv: Optional[Sequence[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    argv = _reorder_search_argv(argv)
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
