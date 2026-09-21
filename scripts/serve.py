#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""serve.py —— 把中国法律条文语料库暴露为 HTTP JSON API（零依赖）。

用途：让**支持函数调用 / HTTP 插件的聊天平台**（DeepSeek 开放平台、通义千问 API、
扣子 Coze 插件、豆包智能体等）能够真正"调用"本语料库。

启动：
  python3 scripts/serve.py                       # 默认 127.0.0.1:8848
  python3 scripts/serve.py --host 0.0.0.0 --port 8848 --token YOUR_SECRET
  python3 scripts/serve.py --open                # 启动后自动打开测试页面

接口：
  GET  /                      浏览器测试页（可直接搜索）
  GET  /health                健康检查
  GET  /stats                 语料库统计与完整性
  GET  /laws?category=labor   法规清单
  GET  /search?q=竞业限制+违约金&doc=&cat=&limit=8&mode=and
  GET  /article?doc=劳动合同法&no=38&before=0&after=0
  GET  /playbook?name=intake
  GET  /tools/openai.json     OpenAI / DeepSeek / 通义 兼容的 function calling 定义
  GET  /tools/mcp.json        MCP 风格的工具定义
  POST /search  {"query": "...", "doc": "...", "limit": 5}   （JSON body）

安全：默认只监听 127.0.0.1。若用 --host 0.0.0.0 暴露到公网，**务必**同时设置 --token，
否则任何人都能读取（虽然只是公开法条，但会被滥用）。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import law  # noqa: E402

# 复用 MCP 服务器里的工具实现，保证两个入口行为一致
import mcp_server as mcp  # noqa: E402

TOKEN = ""

# --------------------------------------------------------------------------
# OpenAI / DeepSeek / 通义 兼容的工具定义
# --------------------------------------------------------------------------

def openai_tools() -> List[Dict[str, Any]]:
    return [{"type": "function", "function": {
        "name": t["name"],
        "description": t["description"],
        "parameters": t["inputSchema"],
    }} for t in mcp.TOOLS]


def mcp_tools() -> Dict[str, Any]:
    return {"tools": mcp.TOOLS}


# --------------------------------------------------------------------------
# 请求处理
# --------------------------------------------------------------------------

def call_tool(name: str, args: Dict[str, Any]) -> str:
    handler = mcp.HANDLERS.get(name)
    if handler is None:
        return f"未知工具：{name}。可用：{', '.join(mcp.HANDLERS)}"
    return handler(args or {})


def _int(v: Optional[str], default: int = 0) -> int:
    try:
        return int(v) if v not in (None, "") else default
    except (TypeError, ValueError):
        return default


class Handler(BaseHTTPRequestHandler):
    server_version = "china-legal-advisor/0.2.0"
    protocol_version = "HTTP/1.1"

    # ---- 输出工具 ----
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def json_out(self, obj: Any, code: int = 200) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8"),
                   "application/json; charset=utf-8")

    def text_out(self, text: str, code: int = 200) -> None:
        self._send(code, text.encode("utf-8"), "text/plain; charset=utf-8")

    def html_out(self, html: str, code: int = 200) -> None:
        self._send(code, html.encode("utf-8"), "text/html; charset=utf-8")

    def log_message(self, fmt: str, *args: Any) -> None:  # 精简日志
        sys.stderr.write("[serve] %s %s\n" % (self.address_string(), fmt % args))

    # ---- 鉴权 ----
    def _authed(self, query: Dict[str, List[str]]) -> bool:
        if not TOKEN:
            return True
        supplied = query.get("token", [None])[0]
        if not supplied:
            auth = self.headers.get("Authorization", "")
            supplied = auth[7:].strip() if auth.startswith("Bearer ") else auth.strip()
        return supplied == TOKEN

    # ---- 路由 ----
    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send(204, b"", "text/plain")

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        q = urllib.parse.parse_qs(parsed.query)

        if not self._authed(q):
            return self.json_out({"error": "unauthorized", "hint": "缺少或错误的 token"}, 401)

        if path == "/":
            return self.html_out(INDEX_HTML)
        if path == "/health":
            docs = law.load_corpus()
            return self.json_out({"status": "ok", "files": len(docs),
                                  "articles": sum(1 for d in docs for a in d.articles if a.no > 0)})
        if path == "/stats":
            return self.json_out({"result": call_tool("corpus_stats", {})})
        if path == "/laws":
            return self.json_out({"result": call_tool(
                "list_laws", {"category": q.get("category", [None])[0]})})
        if path == "/search":
            return self.json_out({"result": call_tool("search_law", {
                "query": q.get("q", [""])[0] or q.get("query", [""])[0],
                "doc": q.get("doc", [None])[0],
                "category": q.get("cat", [None])[0] or q.get("category", [None])[0],
                "mode": q.get("mode", ["and"])[0],
                "regex": q.get("regex", [None])[0],
                "limit": _int(q.get("limit", [None])[0], 8),
            })})
        if path == "/article":
            return self.json_out({"result": call_tool("get_article", {
                "doc": q.get("doc", [""])[0],
                "article": q.get("no", [""])[0] or q.get("article", [""])[0],
                "before": _int(q.get("before", [None])[0], 0),
                "after": _int(q.get("after", [None])[0], 0),
            })})
        if path == "/playbook":
            return self.json_out({"result": call_tool(
                "get_playbook", {"name": q.get("name", [""])[0]})})
        if path == "/tools/openai.json":
            return self.json_out(openai_tools())
        if path == "/tools/mcp.json":
            return self.json_out(mcp_tools())

        return self.json_out({
            "error": "not_found",
            "endpoints": ["/health", "/stats", "/laws", "/search", "/article",
                          "/playbook", "/tools/openai.json", "/tools/mcp.json"],
        }, 404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        q = urllib.parse.parse_qs(parsed.query)
        if not self._authed(q):
            return self.json_out({"error": "unauthorized"}, 401)

        length = _int(self.headers.get("Content-Length"), 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError as exc:
            return self.json_out({"error": f"invalid_json: {exc}"}, 400)

        if path == "/search":
            return self.json_out({"result": call_tool("search_law", body)})
        if path == "/article":
            return self.json_out({"result": call_tool("get_article", body)})
        if path == "/tool":
            name = body.get("name") or body.get("tool")
            return self.json_out({"result": call_tool(name, body.get("arguments") or body.get("args") or {})})
        return self.json_out({"error": "not_found", "hint": "POST 支持 /search、/article、/tool"}, 404)


INDEX_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>中国法律条文检索 · china-legal-advisor</title>
<style>
  :root { color-scheme: light dark; }
  body { font: 15px/1.7 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
         max-width: 900px; margin: 0 auto; padding: 24px 18px 60px; }
  h1 { font-size: 20px; margin: 0 0 4px; }
  .sub { color: #888; font-size: 13px; margin-bottom: 18px; }
  form { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 18px; }
  input,select,button { font: inherit; padding: 9px 12px; border: 1px solid #bbb;
         border-radius: 8px; background: transparent; color: inherit; }
  input[type=text] { flex: 1 1 320px; }
  button { cursor: pointer; font-weight: 600; }
  pre { white-space: pre-wrap; word-break: break-word; background: rgba(127,127,127,.09);
        padding: 14px 16px; border-radius: 10px; font-size: 13.5px; }
  .hint { font-size: 12.5px; color: #888; }
  code { background: rgba(127,127,127,.15); padding: 1px 5px; border-radius: 4px; }
</style></head><body>
<h1>中国法律条文检索</h1>
<div class="sub">离线语料库 · 33 部规范 / 3093 条条文 · 零依赖本地服务</div>
<form onsubmit="run(event)">
  <input type="text" id="q" placeholder="关键词，如：竞业限制 违约金 / 第五百八十八条" autofocus>
  <select id="doc">
    <option value="">全部法规</option>
    <option>劳动合同法</option><option>民法典</option><option>公司法</option>
    <option>劳动法</option><option>民事诉讼法</option><option>劳动争议解释（二）</option>
  </select>
  <button type="submit">检索</button>
</form>
<div class="hint">提示：法条用描述性表述，"加速到期"要搜 <code>未届出资期限</code>，
"代通知金"要搜 <code>额外支付劳动者一个月工资</code>。</div>
<pre id="out">（结果会显示在这里）</pre>
<script>
async function run(e) {
  e.preventDefault();
  const q = document.getElementById('q').value.trim();
  const doc = document.getElementById('doc').value;
  const out = document.getElementById('out');
  if (!q) return;
  out.textContent = '检索中…';
  const url = `/search?q=${encodeURIComponent(q)}&limit=8` + (doc ? `&doc=${encodeURIComponent(doc)}` : '');
  try {
    const r = await fetch(url);
    const d = await r.json();
    out.textContent = d.result || JSON.stringify(d, null, 2);
  } catch (err) { out.textContent = '请求失败：' + err; }
}
</script></body></html>
"""


def main(argv: Optional[List[str]] = None) -> int:
    global TOKEN
    p = argparse.ArgumentParser(description="中国法律顾问 HTTP API 服务（零依赖）")
    p.add_argument("--host", default="127.0.0.1", help="监听地址，默认 127.0.0.1")
    p.add_argument("--port", type=int, default=8848, help="监听端口，默认 8848")
    p.add_argument("--token", default="", help="访问令牌；对外暴露时强烈建议设置")
    p.add_argument("--open", action="store_true", help="启动后打开浏览器测试页")
    args = p.parse_args(argv)

    TOKEN = args.token
    docs = law.load_corpus()
    total = sum(1 for d in docs for a in d.articles if a.no > 0)

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{'127.0.0.1' if args.host in ('0.0.0.0', '') else args.host}:{args.port}"
    print(f"[serve] 语料库：{len(docs)} 个文件 / {total} 条条文")
    print(f"[serve] 服务地址：{url}")
    print(f"[serve] 工具定义：{url}/tools/openai.json  （可导入 DeepSeek / 通义 / Coze）")
    print(f"[serve] 鉴权：{'已启用 token' if TOKEN else '未设置（仅建议本机使用）'}")
    if args.host == "0.0.0.0" and not TOKEN:
        print("[serve] ⚠️  你正在对外暴露服务但未设置 --token，任何人都可调用！", file=sys.stderr)
    print("[serve] Ctrl+C 停止")
    if args.open:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[serve] 已停止")
    return 0


if __name__ == "__main__":
    sys.exit(main())
