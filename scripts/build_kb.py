#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_kb.py —— 把语料库打包成"可直接上传到聊天 App 知识库"的文件包。

适用平台：豆包 / 扣子 Coze 知识库、通义千问、DeepSeek（支持上传文件的对话与知识库功能）、
以及任何支持"上传文档作为知识库"的产品。

用法：
  python3 scripts/build_kb.py                       # 输出到 dist/knowledge-base/
  python3 scripts/build_kb.py --max-chars 200000    # 按字符数切分大文件（适配平台大小限制）
  python3 scripts/build_kb.py --zip                 # 额外生成 zip 便于整体上传
  python3 scripts/build_kb.py --out /tmp/kb
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

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

HEADER = """# {title}

> **本文件是离线法律条文语料，用于上传到 AI 知识库检索。**
> 收录范围：{count} 部规范 / {articles} 条条文｜生成日期：{today}
> 条文来源与版本见仓库 `docs/SOURCES.md`。

## ⚠️ 使用须知（请连同本文件一起上传，或在对话中告知 AI）

1. **回答法律问题前必须引用本文件中的条文原文**，格式为 `《法规全称》第X条`，
   不得凭记忆写法条，不得编造条号或条文内容。
2. 本文件是**快照**：法律可能已被修订，涉及具体案件请核对现行有效版本。
3. 本文件**不含地方性法规、地方政府规章、法院会议纪要与裁审指引**；
   涉及最低工资、社平工资、工伤待遇、加班费基数等**地方标准**时，必须按当地口径另行核验。
4. 本文件提供**法律信息**，不构成法律意见；具体争议请委托执业律师。

---

"""

USAGE_DOC = """# 使用说明 · 中国法律顾问知识库

这是 `china-legal-advisor` 生成的知识库包，用于让**豆包 / 通义千问 / DeepSeek / Coze 等
聊天应用**能够检索到权威的中国法律条文，而不是凭记忆编造。

## 一、先读这个：把它当作"AI 的系统提示词"

多数聊天 App 支持设置「自定义指令 / 角色设定 / 智能体系统提示词」。
把下面的内容粘贴进去（也可用同目录 `系统提示词.md`）：

```
你是一名中国法律顾问助手，必须遵守以下规则：

1. 先查后答：回答任何法律问题前，先检索知识库中的法律条文原文；
   引用格式为《法规全称》第X条（如《中华人民共和国劳动合同法》第三十八条）。
   严禁凭记忆引用法条，严禁编造条号或条文内容。
2. 检索不到时，明确说"知识库未收录，需核验"，不得用相近条文顶替。
3. 个案先问后答：当用户描述的是"发生在他身上的事"，先用不超过 8 个问题
   确认关键事实（时间节点、书面文件与签字情况、金额构成、证据、诉求），
   最多追问两轮，然后必须给出结论；信息不全时列出假设再回答。
4. 每个回答末尾附「总结回答」：你的情况属于 / 最关键依据 / 你能主张 /
   最大风险 / 现在就要做 / 时效提醒。
5. 涉及地方标准（最低工资、社平工资、工伤待遇、加班费基数）时，
   提示需按当地口径核验，不要给出未经核验的具体数字。
6. 你提供的是法律信息而非法律意见，具体案件建议委托执业律师。
```

## 二、上传哪些文件

| 文件 | 内容 | 建议 |
| --- | --- | --- |
| `00-使用说明.md` | 本文件（含系统提示词） | **必传** |
| `01-民法典.md` | 《民法典》全文 1260 条 | 必传 |
| `02-劳动与社会保障.md` | 劳动合同法、劳动法、社保、工伤、年休假等 | 必传 |
| `03-公司法与企业.md` | 2023 修订公司法及配套司法解释 | 按需 |
| `04-程序法.md` | 民事诉讼法、仲裁法 | 按需 |
| `05-实务指南.md` | 必问清单、三大领域检索地图 | **强烈建议** |
| `06-检索词与输出模板.md` | 口语→法言法语对照、输出模板 | 强烈建议 |
| `全部法规合集.md` | 上述全部条文合为一个文件 | 平台限制文件数时使用 |

> **平台大小限制提示**：若上传失败，用 `python3 scripts/build_kb.py --max-chars 200000`
> 重新生成，会按字符数自动切分成多个分卷。

## 三、检索技巧（重要）

法条使用**描述性表述**，学理名词往往搜不到。遇到查不到时，让 AI 换词：

| 你要问的 | 让 AI 搜 |
| --- | --- |
| 出资加速到期 | 未届出资期限 / 提前缴纳 |
| 代通知金 | 额外支付劳动者一个月工资 |
| 自甘风险 | 自愿参加具有一定风险的文体活动 |
| 试用期上限 | 试用期 不得超过 |
| 经济补偿封顶 | 三倍 十二年 |

## 四、想要更强的效果？

知识库是"检索增强"，模型仍可能记错条号。若需要**真正调用**（每次都取到条文原文），用：

- **MCP 服务器**：`python3 scripts/mcp_server.py`（Claude Desktop / Cursor / Cline / Cherry Studio 等）
- **HTTP API**：`python3 scripts/serve.py`（配合 DeepSeek / 通义 / Coze 的函数调用）

详见仓库 `docs/INTEGRATIONS.md`。
"""


def render_doc(doc: law.Document, max_chars: int) -> List[str]:
    """把一部法规渲染成一个或多个 markdown 文本块。"""
    title = doc.title
    header = (f"# {title}\n\n"
              f"> 版本：{doc.header.get('version','')}\n"
              f"> 施行日期：{doc.header.get('effective','')}\n"
              f"> 来源：{doc.header.get('source','')}\n"
              f"> 抓取日期：{doc.header.get('fetched','')}\n"
              f"> 收录条数：{sum(1 for a in doc.articles if a.no > 0)}\n")
    note = doc.header.get("note", "")
    if note:
        header += f">\n> ⚠️ **注意**：{note}\n"
    header += "\n---\n\n"

    blocks: List[str] = []
    for art in doc.articles:
        if art.no == 0:
            body = f"## {title}（全文）\n\n{art.text}\n"
        else:
            ctx = f"\n*（{' › '.join(art.headings)}）*\n" if art.headings else ""
            body = f"### {title} {art.label}{ctx}\n{art.text}\n"
        blocks.append(body)

    if max_chars <= 0:
        return [header + "\n".join(blocks)]

    parts: List[str] = []
    cur = header
    for b in blocks:
        if len(cur) + len(b) > max_chars and cur != header:
            parts.append(cur)
            cur = f"# {title}（续）\n\n"
        cur += b
    if cur.strip():
        parts.append(cur)
    return parts


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="生成可上传到聊天 App 知识库的语料包")
    p.add_argument("--out", default=str(ROOT / "dist" / "knowledge-base"),
                   help="输出目录，默认 dist/knowledge-base")
    p.add_argument("--max-chars", type=int, default=0,
                   help="单个文件最大字符数；>0 时自动切分（适配平台大小限制）")
    p.add_argument("--zip", action="store_true", help="额外生成 zip")
    args = p.parse_args(argv)

    docs = law.load_corpus()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    total_articles = sum(1 for d in docs for a in d.articles if a.no > 0)
    (out / "00-使用说明.md").write_text(USAGE_DOC, encoding="utf-8")

    written: List[Path] = [out / "00-使用说明.md"]
    idx = 1
    for cat, label in CATEGORIES:
        group = sorted([d for d in docs if d.category == cat],
                       key=lambda x: x.header.get("short", ""))
        if not group:
            continue
        chunk_count = sum(1 for d in group for a in d.articles if a.no > 0)
        head = HEADER.format(title=f"{label} · 法规条文汇编", count=len(group),
                             articles=chunk_count, today=date.today().isoformat())
        body_parts: List[str] = []
        for d in group:
            body_parts.extend(render_doc(d, args.max_chars))
        text = head + "\n\n".join(body_parts)
        chunks = [text]
        if args.max_chars > 0 and len(text) > args.max_chars:
            chunks, cur = [], ""
            for piece in body_parts:
                if len(cur) + len(piece) > args.max_chars and cur:
                    chunks.append(cur)
                    cur = ""
                cur += piece
            if cur:
                chunks.append(cur)
        for i, chunk in enumerate(chunks, 1):
            suffix = f"-{i}" if len(chunks) > 1 else ""
            fn = out / f"{idx:02d}-{label}{suffix}.md"
            fn.write_text((head + chunk) if i == 1 else
                          (HEADER.format(title=f"{label} · 法规条文汇编（续）", count=len(group),
                                         articles=chunk_count, today=date.today().isoformat()) + chunk),
                          encoding="utf-8")
            written.append(fn)
        idx += 1

    # 实务指南
    guide = [HEADER.format(title="实务指南 · 必问清单与检索地图", count=0, articles=0,
                           today=date.today().isoformat())]
    for fname, title in [("intake-questions.md", "先问后答：必问清单与提问话术"),
                         ("labor-playbook.md", "劳动法检索地图"),
                         ("company-playbook.md", "公司法检索地图"),
                         ("civil-playbook.md", "民法典检索地图")]:
        f = ROOT / "references" / fname
        if f.exists():
            guide.append(f"\n\n---\n\n# {title}\n\n" + f.read_text(encoding="utf-8"))
    gp = out / f"{idx:02d}-实务指南.md"
    gp.write_text("".join(guide), encoding="utf-8")
    written.append(gp); idx += 1

    # 检索词与输出模板
    combo = [HEADER.format(title="检索词对照与输出模板", count=0, articles=0,
                           today=date.today().isoformat())]
    for fname, title in [("query-expansion.md", "口语 → 法言法语检索词对照表"),
                         ("output-templates.md", "输出模板与「总结回答」模板"),
                         ("currency.md", "时效核验与地方标准清单")]:
        f = ROOT / "references" / fname
        if f.exists():
            combo.append(f"\n\n---\n\n# {title}\n\n" + f.read_text(encoding="utf-8"))
    cp = out / f"{idx:02d}-检索词与输出模板.md"
    cp.write_text("".join(combo), encoding="utf-8")
    written.append(cp); idx += 1

    # 全量合集
    allin = [HEADER.format(title="全部法规合集", count=len(docs), articles=total_articles,
                           today=date.today().isoformat())]
    for d in sorted(docs, key=lambda x: (x.category, x.header.get("short", ""))):
        allin.extend(render_doc(d, 0))
    ap = out / "全部法规合集.md"
    ap.write_text("\n\n".join(allin), encoding="utf-8")
    written.append(ap)

    print(f"[kb] 输出目录：{out}")
    print(f"[kb] 语料：{len(docs)} 部法规 / {total_articles} 条条文")
    for f in written:
        size = f.stat().st_size
        print(f"  · {f.name:<34} {size/1024:>8.1f} KB")

    if args.zip:
        zpath = out.parent / "china-legal-advisor-kb.zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for f in written:
                z.write(f, arcname=f.name)
        print(f"[kb] 已打包：{zpath}（{zpath.stat().st_size/1024:.1f} KB）")
    print("\n[kb] 下一步：把 00-使用说明.md 里的系统提示词粘贴到聊天 App 的"
          "「自定义指令/角色设定」，再把本目录文件上传为知识库。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
