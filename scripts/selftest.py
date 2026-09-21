#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selftest.py —— 语料库与解析器的自检。

运行：python3 scripts/selftest.py
退出码 0 表示全部通过；非 0 表示有问题（会打印失败项）。
适合在更新语料库之后跑一遍。
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import law  # noqa: E402

FAILURES: list = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))
    if not ok:
        FAILURES.append(name)


FIXTURE = """---
title: 中华人民共和国测试法
short: 测试法
category: labor
version: 测试版本
effective: 2020-07-01
source: https://example.gov.cn/x
fetched: 2026-01-01
articles: 7
---

第一编 总则

第一章 基本规定

第一条 为了保护当事人的合法权益，制定本法。

第二条 本法所称协议，依照本法第三条的规定处理，但不得违反本法第七条的强制性规定。

第三条 民事主体的人身权利、财产权利受法律保护。

第二章 分则

第一节 一般规定

第四条 当事人订立协议，可以采用书面形式、口头形式或者其他形式。

第五条 本法的解释权属于全国人民代表大会常务委员会。

第六条 本法施行后，旧法不再适用。

第七条 本法自2020年7月1日起施行。
"""


CHAPTERS_FIXTURE = """---
title: 中华人民共和国章节测试法
short: 章节测试法
category: procedure
version: 测试
effective: 2026-03-01
source: https://example.gov.cn/y
fetched: 2026-01-01
articles: 4
---

第一章 总 则

第一条 为测试章节层级，制定本法。

第二章 仲裁机构

第二条 本章没有"编"这一层。

第一节 申请和受理

第三条 节应当挂在章下面。

第三章 附 则

第四条 本法自2026年3月1日起施行。
"""


def test_number_conversion() -> None:
    print("\n[1] 中文数字转换")
    cases = {10: "十", 11: "十一", 20: "二十", 38: "三十八", 100: "一百",
             105: "一百零五", 260: "二百六十", 1260: "一千二百六十",
             2024: "二千零二十四"}
    for num, cn in cases.items():
        check(f"int2cn({num}) == {cn}", law.int2cn(num) == cn, f"得到 {law.int2cn(num)}")
        check(f"cn2int({cn}) == {num}", law.cn2int(cn) == num, f"得到 {law.cn2int(cn)}")
    check("cn2int('两千零二十四') == 2024", law.cn2int("两千零二十四") == 2024)
    check("cn2int('abc') is None", law.cn2int("abc") is None)


def test_parser() -> None:
    print("\n[2] 条文切分（含行内援引歧义）")
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "raw"
        raw.mkdir()
        (raw / "fake-law.txt").write_text(FIXTURE, encoding="utf-8")
        (raw / "chapters-law.txt").write_text(CHAPTERS_FIXTURE, encoding="utf-8")
        law.RAW_DIR = raw
        docs = law.load_corpus(force=True)

    check("解析出 2 个文档", len(docs) == 2, f"得到 {len(docs)}")
    if not docs:
        return
    doc = next((d for d in docs if d.slug == "fake-law"), docs[0])
    nos = [a.no for a in doc.articles]
    check("条号 1..7 完整且有序", nos == [1, 2, 3, 4, 5, 6, 7], f"得到 {nos}")
    check("头部元数据解析正确", doc.title == "中华人民共和国测试法" and doc.category == "labor")
    check("简称解析正确", doc.short == "测试法")

    art2 = doc.by_no(2)
    check("第二条正文完整（未被行内援引切开）",
          art2 is not None and art2.text.endswith("强制性规定。"),
          f"得到 {art2.text[-12:] if art2 else None}")
    check("第二条正文包含行内援引原文",
          art2 is not None and "依照本法第三条的规定处理" in art2.text)

    art3 = doc.by_no(3)
    check("第三条正文未被污染（不包含第二条尾部文本）",
          art3 is not None and art3.text.startswith("民事主体的人身权利"),
          f"得到 {art3.text[:16] if art3 else None}")

    check("层级路径：编 › 章 › 节",
          art3 is not None and art3.headings == ["第一编 总则", "第一章 基本规定"],
          f"得到 {art3.headings if art3 else None}")
    art4 = doc.by_no(4)
    check("分则下层级路径正确",
          art4 is not None and art4.headings[-2:] == ["第二章 分则", "第一节 一般规定"],
          f"得到 {art4.headings if art4 else None}")

    print("\n[3] 条号查找 / 无「编」层级的章节")
    for needle in ("38", "第38条", "第三十八条"):
        check(f"找不到不存在的条号 {needle}", doc.find(needle) is None)
    check("find('第2条') 命中第二条", doc.find("第2条") is art2)
    check("find('第三条') 命中第三条", doc.find("第三条") is art3)

    chap = next(d for d in docs if d.slug == "chapters-law")
    c1, c2, c3, c4 = (chap.by_no(i) for i in (1, 2, 3, 4))
    check("带空格的章标题被识别（第一章 总 则）", c1.headings == ["第一章 总 则"], f"得到 {c1.headings}")
    check("无编层级时章占据第一层", c2.headings == ["第二章 仲裁机构"], f"得到 {c2.headings}")
    check("节挂在章之下且不叠加旧章",
          c3.headings == ["第二章 仲裁机构", "第一节 申请和受理"], f"得到 {c3.headings}")
    check("后续章替换前一章", c4.headings == ["第三章 附 则"], f"得到 {c4.headings}")
    check("条号连排时自动补空格", c1.text.startswith("为测试章节层级") and chap.by_no(4).text.startswith("本法自"))


def test_corpus() -> None:
    print("\n[4] 语料库完整性")
    law.RAW_DIR = SCRIPT_DIR.parent / "references" / "raw"
    try:
        docs = law.load_corpus(force=True)
    except SystemExit as exc:
        check("语料库可加载", False, str(exc))
        return
    check("语料库非空", len(docs) > 0, f"{len(docs)} 个文件")
    total = 0
    for doc in docs:
        nos = [a.no for a in doc.articles if a.no > 0]
        declared = doc.header.get("articles", "")
        declared_n = int("".join(ch for ch in declared if ch.isdigit()) or 0)
        if not nos:
            check(f"{doc.slug}: 无分条文件（批复/决定）声明为 0 且有正文",
                  declared_n == 0 and bool(doc.body.strip()),
                  f"articles={declared} 正文 {len(doc.body)} 字")
            continue
        total += len(nos)
        ok = nos == list(range(1, max(nos) + 1))
        check(f"{doc.slug}: 条号 1..{max(nos)} 连续", ok)
        if declared_n:
            check(f"{doc.slug}: 与头部 articles={declared_n} 一致", max(nos) == declared_n,
                  f"实际末条 {max(nos)}")
    print(f"\n  语料库合计 {len(docs)} 个文件 / {total} 条条文")


def main() -> int:
    print("=" * 60)
    print("china-legal-advisor 自检")
    print("=" * 60)
    test_number_conversion()
    test_parser()
    test_corpus()
    print("\n" + "=" * 60)
    if FAILURES:
        print(f"失败 {len(FAILURES)} 项：")
        for name in FAILURES:
            print(f"  - {name}")
        return 1
    print("全部通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
