#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mcp_server.py —— 把中国法律条文语料库暴露为 MCP（Model Context Protocol）工具。

零依赖（仅 Python 3.8+ 标准库），通过 stdio 与 MCP 客户端通信（换行分隔的 JSON-RPC 2.0）。

暴露的工具：
  search_law      关键词/条号检索条文（返回条文原文与规范引用）
  get_article     精确取某一条（可带前后条）
  list_laws       列出语料库全部法规（含版本与施行日期）
  get_playbook    读取技能文档（必问清单 / 领域检索地图 / 输出模板 / 时效清单）
  corpus_stats    语料库统计与完整性自检

在 MCP 客户端中的配置示例（Claude Desktop / Cursor / Cline / Cherry Studio 等）：

  {
    "mcpServers": {
      "china-legal-advisor": {
        "command": "python3",
        "args": ["/绝对路径/china-legal-advisor/scripts/mcp_server.py"]
      }
    }
  }

调试：
  python3 scripts/mcp_server.py --selftest    # 自检（不进入 stdio 循环）
  echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 scripts/mcp_server.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import law  # noqa: E402

SERVER_NAME = "china-legal-advisor"
SERVER_VERSION = "0.2.0"
DEFAULT_PROTOCOL = "2024-11-05"
SUPPORTED_PROTOCOLS = ("2024-11-05", "2025-03-26", "2025-06-18")

PLAYBOOKS = {
    "intake": ("先问后答：必问清单与话术", "intake-questions.md"),
    "labor": ("劳动法检索地图", "labor-playbook.md"),
    "company": ("公司法检索地图（含司法解释旧条号对照）", "company-playbook.md"),
    "civil": ("民法典检索地图", "civil-playbook.md"),
    "query-expansion": ("口语 → 法言法语检索词对照表", "query-expansion.md"),
    "templates": ("输出模板与「总结回答」模板", "output-templates.md"),
    "currency": ("时效核验、地方标准清单、语料更新流程", "currency.md"),
}

# --------------------------------------------------------------------------
# 工具实现
# --------------------------------------------------------------------------

def _doc_filter(docs: List[law.Document], doc: Optional[str], category: Optional[str]):
    if doc:
        docs = [law.resolve_doc(doc, docs)]
    if category:
        docs = [d for d in docs if d.category == category]
    return docs


def tool_search_law(args: Dict[str, Any]) -> str:
    query = (args.get("query") or "").strip()
    if not query:
        return "错误：query 不能为空。可传入关键词（如「竞业限制 违约金」）、条号（如「第五百八十八条」）或正则。"
    terms = query.split()
    mode = (args.get("mode") or "and").lower()
    regex = args.get("regex")
    limit = int(args.get("limit") or 8)
    docs = _doc_filter(law.load_corpus(), args.get("doc"), args.get("category"))
    if not docs:
        return "未找到匹配的法规文件；请先用 list_laws 查看可用法规。"

    results = []
    if regex:
        import re
        pattern = re.compile(regex, re.I)
        for d in docs:
            for art in d.articles:
                target = art.text + "\n" + art.label + "\n" + art.heading_path()
                m = pattern.search(target)
                if m:
                    results.append(((1000, 0), art, law.make_snippet(art.text, [m.group(0)])))
    else:
        for d in docs:
            for art in d.articles:
                sc = law.score_article(art, terms, require_all=(mode != "or"))
                if sc:
                    results.append((sc, art, law.make_snippet(art.text, terms)))

    results.sort(key=lambda r: (-r[0][0], r[1].doc.slug, r[1].no))
    results = results[:limit]
    if not results:
        return (f"未命中：{query}\n"
                "提示：法条使用描述性表述，学理名词常搜不到。"
                "例如「加速到期」应搜「未届出资期限」，「代通知金」应搜「额外支付劳动者一个月工资」。"
                "可换词重试，或改用 get_playbook 查看检索词对照表（name=query-expansion）。"
                "**不要据此断言「法律没有规定」。**")

    out = [f"命中 {len(results)} 条（关键词：{query}｜{'OR' if mode == 'or' else 'AND'}）：", ""]
    for i, (_, art, sn) in enumerate(results, 1):
        out.append(f"{i}. {law.fmt_article(art, sn)}")
        out.append("")
    out.append("提示：以上为离线语料库检索结果。引用前请用 get_article 取条文全文核对，"
               "并确认现行有效版本（地方标准与最新修法需另行核验）。")
    return "\n".join(out)


def tool_get_article(args: Dict[str, Any]) -> str:
    doc_token = args.get("doc")
    art_token = args.get("article")
    if not doc_token or not art_token:
        return "错误：需要同时提供 doc（法规简称/全称）与 article（条号，如 38 / 第38条 / 第三十八条）。"
    docs = law.load_corpus()
    try:
        doc = law.resolve_doc(str(doc_token), docs)
    except SystemExit as exc:
        return f"错误：{exc}"
    art = doc.find(str(art_token))
    if art is None:
        return (f"错误：{doc.short} 中未找到 {art_token}（该文件共 "
                f"{sum(1 for a in doc.articles if a.no > 0)} 条）。")
    before = int(args.get("before") or 0)
    after = int(args.get("after") or 0)
    lo, hi = art.no - before, art.no + after
    picked = [a for a in doc.articles if lo <= a.no <= hi]
    out = []
    for a in picked:
        mark = "▶ " if a.no == art.no else "  "
        out.append(mark + law.fmt_article(a))
        out.append("")
    out.append(law.HEAD)
    out.append(f"《{doc.title}》{doc.header.get('version','')}｜施行：{doc.header.get('effective','')}"
               f"｜共 {sum(1 for a in doc.articles if a.no > 0)} 条")
    src = doc.header.get("source", "")
    if src:
        out.append(f"来源：{src}")
    note = doc.header.get("note", "")
    if note:
        out.append(f"⚠ 注意：{note}")
    out.append("")
    out.append(f"规范引用格式：{art.citation}")
    return "\n".join(out)


def tool_list_laws(args: Dict[str, Any]) -> str:
    docs = law.load_corpus()
    category = args.get("category")
    if category:
        docs = [d for d in docs if d.category == category]
    labels = {"labor": "劳动与社会保障", "company": "公司与企业",
              "civil": "民法典及配套", "procedure": "程序法", "other": "其他"}
    groups: Dict[str, List[law.Document]] = {}
    for d in docs:
        groups.setdefault(d.category, []).append(d)
    out = [f"语料库共 {len(docs)} 个文件（分类：{category or '全部'}）", ""]
    for cat in sorted(groups):
        out.append(f"## {labels.get(cat, cat)}（{cat}）")
        for d in sorted(groups[cat], key=lambda x: x.header.get("short", "")):
            n = sum(1 for a in d.articles if a.no > 0)
            ver = d.header.get("version", "")
            if len(ver) > 46:
                ver = ver[:46] + "…"
            count = f"{n} 条" if n else "无分条"
            out.append(f"- {d.short}｜{count}｜{ver}｜施行 {d.header.get('effective','')}")
        out.append("")
    out.append("用 get_article(doc=简称, article=条号) 取条文；用 search_law 关键词检索。")
    return "\n".join(out)


def tool_get_playbook(args: Dict[str, Any]) -> str:
    name = (args.get("name") or "").strip()
    if name not in PLAYBOOKS:
        key_list = "、".join(f"{k}（{v[0]}）" for k, v in PLAYBOOKS.items())
        return f"错误：未知的 name。可选：{key_list}"
    title, fname = PLAYBOOKS[name]
    path = SCRIPT_DIR.parent / "references" / fname
    if not path.exists():
        return f"错误：文件不存在 {path}（安装不完整？）"
    return f"# {title}\n\n" + path.read_text(encoding="utf-8", errors="ignore")


def tool_corpus_stats(args: Dict[str, Any]) -> str:
    docs = law.load_corpus()
    total = sum(1 for d in docs for a in d.articles if a.no > 0)
    chars = sum(len(d.body) for d in docs)
    per_cat: Dict[str, int] = {}
    problems = []
    for d in docs:
        nos = [a.no for a in d.articles if a.no > 0]
        if nos:
            per_cat[d.category] = per_cat.get(d.category, 0) + len(nos)
            if nos != list(range(1, max(nos) + 1)):
                problems.append(d.slug)
    out = [f"文件数：{len(docs)}｜条文总数：{total}｜正文字符数：{chars:,}", ""]
    labels = {"labor": "劳动与社会保障", "company": "公司与企业",
              "civil": "民法典及配套", "procedure": "程序法", "other": "其他"}
    for cat, n in sorted(per_cat.items()):
        out.append(f"- {labels.get(cat, cat)}：{n} 条")
    out.append("")
    out.append("完整性：" + ("全部通过 ✓" if not problems else "异常文件 " + ", ".join(problems)))
    return "\n".join(out)


TOOLS: List[Dict[str, Any]] = [
    {
        "name": "search_law",
        "description": (
            "在中国法律法规离线语料库（33 部规范、3093 条条文）中检索条文，返回条文原文与规范引用。"
            "支持关键词（默认 AND 语义）、条号（如「第五百八十八条」）与正则。"
            "回答任何中国法律问题前都应先调用本工具取得条文原文，不要凭记忆引用法条。"
            "命中为零时请换用同义的法律表述重试，不要据此断言「法律没有规定」。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string",
                          "description": "检索词，可多个用空格分隔（如「竞业限制 违约金」）；也可是条号或正则"},
                "doc": {"type": "string", "description": "限定某部法规（简称/全称子串，如「劳动合同法」）"},
                "category": {"type": "string", "enum": ["labor", "company", "civil", "procedure"],
                             "description": "限定类别"},
                "mode": {"type": "string", "enum": ["and", "or"], "description": "多词逻辑，默认 and"},
                "regex": {"type": "string", "description": "改用正则检索（与 query 二选一）"},
                "limit": {"type": "integer", "description": "返回条数上限，默认 8"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_article",
        "description": (
            "精确获取某一条法规的全文（可带前后条）。引用条文前必须调用本工具拿到原文，"
            "并连同条号、版本与施行日期一起引用。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "doc": {"type": "string", "description": "法规简称/全称子串，如「劳动合同法」「民法典」"},
                "article": {"type": "string", "description": "条号：38 / 第38条 / 第三十八条"},
                "before": {"type": "integer", "description": "同时显示其前 N 条"},
                "after": {"type": "integer", "description": "同时显示其后 N 条"},
            },
            "required": ["doc", "article"],
        },
    },
    {
        "name": "list_laws",
        "description": "列出语料库收录的全部法规（含条数、版本、施行日期），可按类别筛选。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": ["labor", "company", "civil", "procedure"]},
            },
        },
    },
    {
        "name": "get_playbook",
        "description": (
            "读取本技能的实务文档：先问后答的必问清单、劳动/公司/民法典领域的检索地图与条文索引、"
            "口语到法言法语的检索词对照表、输出模板与总结回答模板、时效核验与地方标准清单。"
            "在分析具体案件前建议先读 intake 与对应领域 playbook。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "enum": list(PLAYBOOKS.keys()),
                         "description": "intake=必问清单；labor/company/civil=领域地图；"
                                        "query-expansion=检索词对照；templates=输出模板；currency=时效与地方标准"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "corpus_stats",
        "description": "语料库统计与完整性自检（文件数、条文数、分类分布、条号连续性）。",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

HANDLERS = {
    "search_law": tool_search_law,
    "get_article": tool_get_article,
    "list_laws": tool_list_laws,
    "get_playbook": tool_get_playbook,
    "corpus_stats": tool_corpus_stats,
}

# --------------------------------------------------------------------------
# JSON-RPC / MCP 协议
# --------------------------------------------------------------------------

def _result(req_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def handle_message(msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    method = msg.get("method")
    req_id = msg.get("id")
    params = msg.get("params") or {}

    # 通知（无 id）不需要回复
    if req_id is None and method and method.startswith("notifications/"):
        return None

    if method == "initialize":
        requested = params.get("protocolVersion")
        version = requested if requested in SUPPORTED_PROTOCOLS else DEFAULT_PROTOCOL
        return _result(req_id, {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "instructions": (
                "中国法律顾问：回答中国法律问题前，先用 search_law 检索、再用 get_article 取条文原文，"
                "禁止凭记忆引用法条。个案咨询应先按 get_playbook(name=intake) 的清单提问补齐关键事实，"
                "收集足够信息后再给综合分析，并在末尾附「总结回答」。"
                "引用格式：《法规全称》第X条。检索不到时明说「语料库未收录，需核验」，不得编造。"
                "本服务提供法律信息而非法律意见，具体案件建议委托执业律师。"
            ),
        })

    if method == "ping":
        return _result(req_id, {})

    if method == "tools/list":
        return _result(req_id, {"tools": TOOLS})

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        handler = HANDLERS.get(name)
        if handler is None:
            return _error(req_id, -32602, f"未知工具：{name}")
        try:
            text = handler(args)
        except Exception as exc:  # noqa: BLE001
            return _result(req_id, {
                "content": [{"type": "text", "text": f"工具执行出错：{type(exc).__name__}: {exc}"}],
                "isError": True,
            })
        return _result(req_id, {"content": [{"type": "text", "text": text}], "isError": False})

    if method in ("resources/list", "prompts/list"):
        key = "resources" if method.startswith("resources") else "prompts"
        return _result(req_id, {key: []})

    return _error(req_id, -32601, f"不支持的方法：{method}")


def serve() -> int:
    """stdio 主循环：每行一个 JSON-RPC 消息。"""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as exc:
            sys.stdout.write(json.dumps(_error(None, -32700, f"JSON 解析失败：{exc}")) + "\n")
            sys.stdout.flush()
            continue
        try:
            reply = handle_message(msg if isinstance(msg, dict) else {})
        except Exception as exc:  # noqa: BLE001
            reply = _error(msg.get("id") if isinstance(msg, dict) else None,
                           -32603, f"内部错误：{exc}")
        if reply is not None:
            sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


def selftest() -> int:
    """不进入 stdio 循环，直接验证工具可用性。"""
    docs = law.load_corpus()
    print(f"语料库：{len(docs)} 个文件")
    checks = [
        ("initialize", {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": DEFAULT_PROTOCOL}}),
        ("tools/list", {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
        ("search_law", {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                        "params": {"name": "search_law",
                                   "arguments": {"query": "竞业限制 违约金", "limit": 2}}}),
        ("search_law(条号)", {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                              "params": {"name": "search_law",
                                         "arguments": {"query": "第五百八十八条"}}}),
        ("search_law(无命中)", {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                                "params": {"name": "search_law",
                                           "arguments": {"query": "加速到期"}}}),
        ("get_article", {"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                         "params": {"name": "get_article",
                                    "arguments": {"doc": "劳动合同法", "article": "38"}}}),
        ("list_laws", {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                       "params": {"name": "list_laws", "arguments": {"category": "labor"}}}),
        ("get_playbook", {"jsonrpc": "2.0", "id": 8, "method": "tools/call",
                          "params": {"name": "get_playbook", "arguments": {"name": "intake"}}}),
        ("corpus_stats", {"jsonrpc": "2.0", "id": 9, "method": "tools/call",
                          "params": {"name": "corpus_stats", "arguments": {}}}),
        ("未知方法", {"jsonrpc": "2.0", "id": 10, "method": "bogus/method"}),
        ("通知(应无回复)", {"jsonrpc": "2.0", "method": "notifications/initialized"}),
    ]
    failed = 0
    for label, msg in checks:
        reply = handle_message(msg)
        if label.startswith("通知"):
            ok = reply is None
            detail = "正确返回 None" if ok else "错误地返回了响应"
        else:
            ok = bool(reply) and ("result" in reply or "error" in reply)
            if label == "tools/list":
                ok = ok and len(reply["result"]["tools"]) == len(TOOLS)
            if label.startswith("search_law") and label != "search_law(无命中)":
                txt = reply["result"]["content"][0]["text"]
                ok = ok and ("【《" in txt)
            if label == "search_law(无命中)":
                txt = reply["result"]["content"][0]["text"]
                ok = ok and ("未命中" in txt) and ("不要据此断言" in txt)
            if label == "get_article":
                txt = reply["result"]["content"][0]["text"]
                ok = ok and ("第三十八条" in txt) and ("规范引用格式" in txt)
            if label == "未知方法":
                ok = ok and ("error" in reply)
            detail = ""
        print(f"  {'PASS' if ok else 'FAIL'}  {label} {detail}")
        if not ok:
            failed += 1
    print("\n" + ("全部通过 ✓" if not failed else f"失败 {failed} 项"))
    return 0 if not failed else 1


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="中国法律顾问 MCP 服务器（stdio）")
    p.add_argument("--selftest", action="store_true", help="运行自检后退出")
    args = p.parse_args(argv)
    if args.selftest:
        return selftest()
    return serve()


if __name__ == "__main__":
    sys.exit(main())
