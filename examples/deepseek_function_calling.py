#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deepseek_function_calling.py —— Function Calling 示例：让 DeepSeek / 通义 等模型
真正"调用"本地中国法律语料库（而不是凭记忆背法条）。

适用任何兼容 OpenAI Chat Completions 接口的服务：
  - DeepSeek 开放平台      https://api.deepseek.com
  - 阿里云百炼（通义千问）  https://dashscope.aliyuncs.com/compatible-mode/v1
  - Moonshot / 智谱 / 本地 vLLM 等

准备工作：
  1. 启动本地 API 服务：
       python3 scripts/serve.py --port 8848            # 默认 127.0.0.1
  2. 设置环境变量：
       export DEEPSEEK_API_KEY=sk-xxxx
       # 如用通义：
       # export OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
       # export OPENAI_MODEL=qwen-plus
  3. 运行：
       python3 examples/deepseek_function_calling.py "劳动合同法第38条怎么规定的？"
       python3 examples/deepseek_function_calling.py "公司欠我6400元工资还让我月底走，我该怎么办？"

注意：本脚本只用 Python 标准库（urllib）调用 OpenAI 兼容接口，不依赖 openai SDK。
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List

API_BASE = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com").rstrip("/")
API_KEY = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
MODEL = os.environ.get("OPENAI_MODEL", "deepseek-chat")
LEGAL_API = os.environ.get("LEGAL_API_BASE", "http://127.0.0.1:8848").rstrip("/")
LEGAL_TOKEN = os.environ.get("LEGAL_API_TOKEN", "")

SYSTEM_PROMPT = """你是一名严谨的中国法律顾问助手，专长劳动法、公司法与民法典。铁律：

1. 先查后答：回答任何法律问题前，必须先调用工具检索法条原文；
   引用时写成《法规全称》第X条并附条文原文，严禁凭记忆编造条号或条文内容。
   检索不到就明确说「语料库未收录，需核验」，不得用相近条文顶替。
2. 个案先问后答：当用户描述的是发生在他身上的事，先用不超过 8 个问题确认关键事实
   （时间节点 / 书面文件与签字情况 / 金额构成 / 证据 / 诉求），最多追问两轮，
   然后必须给出结论；信息不全时列出假设再回答，不得拒绝回答。
3. 每个回答末尾附「总结回答」：情况定性 / 最关键条号 / 能主张什么 / 最大风险 /
   现在就要做 / 时效提醒。
4. 学理名词检索不到时换成法条里的说法：「加速到期」→「未届出资期限」；
   「代通知金」→「额外支付劳动者一个月工资」。
5. 地方标准（最低工资、社平工资、工伤待遇、加班费基数）必须提示按当地口径核验。
6. 你提供的是法律信息而非法律意见，具体案件建议委托执业律师。"""


# --------------------------------------------------------------------------
# 工具执行：把模型的 function call 转发给本地法律 API
# --------------------------------------------------------------------------

def call_local_api(name: str, args: Dict[str, Any]) -> str:
    payload = json.dumps({"name": name, "arguments": args}, ensure_ascii=False).encode("utf-8")
    url = f"{LEGAL_API}/tool"
    req = urllib.request.Request(url, data=payload, method="POST",
                                headers={"Content-Type": "application/json"})
    if LEGAL_TOKEN:
        req.add_header("Authorization", f"Bearer {LEGAL_TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("result", json.dumps(data, ensure_ascii=False))
    except urllib.error.URLError as exc:
        return (f"调用本地法律 API 失败：{exc}。"
                f"请确认已运行 python3 scripts/serve.py（当前地址 {LEGAL_API}）。")


def fetch_tools() -> List[Dict[str, Any]]:
    url = f"{LEGAL_API}/tools/openai.json"
    req = urllib.request.Request(url)
    if LEGAL_TOKEN:
        req.add_header("Authorization", f"Bearer {LEGAL_TOKEN}")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def chat(messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> Dict[str, Any]:
    payload = json.dumps({
        "model": MODEL,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.2,
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{API_BASE}/chat/completions", data=payload, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {API_KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")[:500]
        raise SystemExit(f"模型接口报错 HTTP {exc.code}：{detail}")


def main() -> int:
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        print(__doc__)
        return 2
    if not API_KEY:
        print("请先设置环境变量 DEEPSEEK_API_KEY（或 OPENAI_API_KEY）", file=sys.stderr)
        return 2

    try:
        tools = fetch_tools()
    except Exception as exc:  # noqa: BLE001
        print(f"无法获取工具定义（{exc}）。请先启动：python3 scripts/serve.py", file=sys.stderr)
        return 1

    print(f"模型：{MODEL}｜法律 API：{LEGAL_API}｜可用工具：{[t['function']['name'] for t in tools]}")
    print(f"\n用户：{question}\n")

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    for turn in range(1, 7):  # 最多 6 轮工具调用
        resp = chat(messages, tools)
        choice = resp["choices"][0]["message"]
        messages.append(choice)

        tool_calls = choice.get("tool_calls") or []
        if not tool_calls:
            print("=" * 70)
            print(choice.get("content") or "（模型没有返回内容）")
            return 0

        for tc in tool_calls:
            fn = tc["function"]["name"]
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            print(f"  [第 {turn} 轮] 调用工具 {fn}({json.dumps(args, ensure_ascii=False)})")
            result = call_local_api(fn, args)
            preview = result.replace("\n", " ")[:110]
            print(f"             → {preview}…")
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

    print("已达到工具调用轮次上限，以下是模型最后一轮输出：")
    print(messages[-1].get("content") or "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
