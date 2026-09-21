# 接入指南：让豆包 / 千问 / DeepSeek 等聊天应用用上本语料库

> **先说清现实**：豆包、通义千问、DeepSeek 的**聊天窗口不支持安装本地技能**。
> 它们只提供三种可接入的入口。本仓库三条都实现了，按你的需求选：

| 路径 | 适用平台 | 是否"真调用" | 配置难度 | 需要公网 |
| --- | --- | --- | --- | --- |
| **① 知识库 + 系统提示词** | 豆包、千问、DeepSeek、Kimi、智谱、Coze 智能体……几乎所有支持"上传文件 + 自定义指令"的产品 | 否（检索增强，模型仍可能记错条号） | ★ 低 | 否 |
| **② MCP 服务器** | Claude Desktop、Cursor、Cline、Cherry Studio、ChatWise 等**支持 MCP 的客户端** | **是**（每次都取到条文原文） | ★★ 中 | 否 |
| **③ HTTP API + 函数调用** | DeepSeek 开放平台、通义千问 API、扣子 Coze 插件、豆包智能体、任何支持 function calling 的平台 | **是** | ★★★ 中高 | **是** |

> 平台功能会不定期调整，具体入口以各平台官方文档为准。

---

## 路径 ①：知识库 + 系统提示词（0 配置，最通用）

### 步骤

1. **生成知识库包**

   ```bash
   cd china-legal-advisor
   python3 scripts/build_kb.py --zip
   # 产出：dist/knowledge-base/*.md 与 dist/china-legal-advisor-kb.zip
   ```

   如果平台提示文件过大，改用切分模式：

   ```bash
   python3 scripts/build_kb.py --max-chars 200000
   ```

2. **粘贴系统提示词**

   打开 [`prompts/system-prompt-zh.md`](../prompts/system-prompt-zh.md)，把代码块里的全部内容
   粘贴到 App 的「自定义指令 / 角色设定 / 智能体系统提示词 / 人设与回复逻辑」。
   字数受限时用 [`prompts/system-prompt-lite.md`](../prompts/system-prompt-lite.md)。

3. **上传知识库**

   把 `dist/knowledge-base/` 里的文件上传为该 App 的**知识库 / 文档 / 附件**。
   至少上传 `00-使用说明.md`、`01-民法典.md`、`02-劳动与社会保障.md`；
   涉及公司或诉讼再加 `03`、`04`；`05-实务指南.md` 强烈建议上传（它包含提问清单与分析框架）。

4. **验证**

   问一句：「劳动合同法第三十八条怎么规定的？」
   如果 AI 回出条文原文且条号正确，说明知识库生效。

### 各平台入口（名称可能调整）

| 平台 | 上传知识库 | 自定义指令 |
| --- | --- | --- |
| 豆包 | 「我的 → 智能体 → 创建/编辑 → 知识库」上传文件 | 智能体的「人设与回复逻辑」 |
| 扣子 Coze | 智能体编排页 → 知识库 → 添加文档 | 智能体「人设」 |
| 通义千问 | 对话框上传文件；或百炼平台建知识库 | 「智能体」/ 系统指令 |
| DeepSeek | 对话框上传文件（附件） | 部分入口支持自定义指令 |
| Kimi / 智谱清言 | 对话框上传文件 / 知识库 | 智能体设定 |

### 局限（务必告知使用者）

- 这是**检索增强**，不是"硬约束"：模型仍可能引用错条号或漏看文档。
  提示词里已要求"引用前先检索、查不到就说需核验"，但仍建议**核对条文原文**。
- 模型只会看到被检索到的片段，长条文可能被截断。

---

## 路径 ②：MCP 服务器（本地客户端可真正调用）

适用客户端：Claude Desktop、Cursor、Cline、Cherry Studio、ChatWise、DeepChat 等
**支持 Model Context Protocol 的客户端**。

### 启动

```bash
python3 scripts/mcp_server.py --selftest    # 先自检
python3 scripts/mcp_server.py               # 由客户端自动拉起，无需手动运行
```

### 配置

把下面内容加进客户端的 MCP 配置文件（Claude Desktop 为
`~/Library/Application Support/Claude/claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "china-legal-advisor": {
      "command": "python3",
      "args": ["/绝对路径/china-legal-advisor/scripts/mcp_server.py"]
    }
  }
}
```

也可以直接用示例文件：[`examples/mcp_config.example.json`](../examples/mcp_config.example.json)。

### 暴露的工具

| 工具 | 作用 |
| --- | --- |
| `search_law` | 关键词/条号/正则检索条文，返回原文与规范引用 |
| `get_article` | 精确取某一条（可带前后条） |
| `list_laws` | 列出 33 部法规及版本、施行日期 |
| `get_playbook` | 读取必问清单、劳动/公司/民法典检索地图、输出模板、时效清单 |
| `corpus_stats` | 语料库统计与完整性自检 |

服务器还会通过 `initialize` 的 `instructions` 字段下发"先查后答、先问后答、附总结回答"
的行为约束，客户端通常会自动注入到系统提示中。

### 验证

对客户端说：「用 china-legal-advisor 查一下劳动合同法第 38 条。」
应当看到一次真实的工具调用并返回条文原文。

---

## 路径 ③：HTTP API + 函数调用（DeepSeek / 通义 / Coze / 豆包）

适用于**开放平台 API 与插件体系**：DeepSeek 开放平台、阿里云百炼（通义）、
扣子 Coze 插件、豆包智能体等。

### 第 1 步：启动 API 服务

```bash
# 本机测试
python3 scripts/serve.py --open

# 对外提供服务（务必设置 token！）
python3 scripts/serve.py --host 0.0.0.0 --port 8848 --token 你的密钥
```

要在公网使用，需要让平台能访问到你的服务：云服务器，或用内网穿透工具
（frp / ngrok / cloudflared）把本地端口映射出去。

### 第 2 步：取得函数定义

```bash
curl http://127.0.0.1:8848/tools/openai.json      # OpenAI / DeepSeek / 通义 兼容格式
curl http://127.0.0.1:8848/tools/mcp.json         # MCP 风格
```

也可直接在平台里手动创建 5 个函数（参数同 MCP 工具表）。

### 第 3 步：接口清单

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | 健康检查 |
| GET | `/stats` | 语料库统计 |
| GET | `/laws?category=labor` | 法规清单 |
| GET | `/search?q=竞业限制+违约金&doc=&cat=&limit=8&mode=and` | 检索条文 |
| GET | `/article?doc=劳动合同法&no=38&before=0&after=0` | 取条文原文 |
| GET | `/playbook?name=intake` | 读取实务文档 |
| GET | `/tools/openai.json` | 函数定义 |
| POST | `/tool` `{"name":"search_law","arguments":{...}}` | 通用调用入口 |

带 token 时：加 `?token=xxx` 或请求头 `Authorization: Bearer xxx`。

### 第 4 步：接入

**DeepSeek / 通义（OpenAI 兼容接口）** —— 直接用示例脚本，把
`scripts/serve.py` 起的服务当作工具后端：

```bash
export DEEPSEEK_API_KEY=sk-xxx
python3 examples/deepseek_function_calling.py "公司欠我 6400 元工资，还让我月底走人，我该怎么办？"
```

完整可运行代码见 [`examples/deepseek_function_calling.py`](../examples/deepseek_function_calling.py)，
它同样适用于通义千问（DashScope OpenAI 兼容模式）、Moonshot、智谱等兼容接口。

**扣子 Coze / 豆包** —— 在「插件 → 创建插件 → 在线服务」里填：

- 接口地址：`https://你的域名/search`（GET）
- 入参：`q`（string，必填）、`doc`（string，选填）、`limit`（integer，选填）
- 出参：`result`（string）
- 鉴权：Header 鉴权，`Authorization: Bearer 你的密钥`

再在工作流/智能体里挂上该插件，并在人设中写明"回答法律问题前先调用该插件检索条文"。

### 安全注意

- 服务**默认只监听 127.0.0.1**；用 `--host 0.0.0.0` 暴露时**必须**设置 `--token`。
- 服务无 TLS，公网部署请放在 Nginx/Caddy 反代之后并启用 HTTPS。
- 语料是公开法条，但服务本身可能被滥用（刷流量），建议加 token 与访问频率限制。

---

## 路径 ④：不用 AI，直接查（命令行 / 自动化）

```bash
python3 scripts/law.py search 竞业限制 违约金
python3 scripts/law.py article 民法典 第五百七十七条 -A 2
python3 scripts/law.py search 违约金 --json        # 供程序消费
```

任何语言都可以通过 `subprocess` 调用，或直接读取 `references/raw/*.txt`。

---

## 选哪条？一句话建议

- **只想在豆包/千问/DeepSeek 聊天框里问** → 路径 ①（10 分钟搞定）。
- **用 Claude Desktop / Cursor / Cline / Cherry Studio 这类客户端** → 路径 ②，效果最好且无需公网。
- **要接开放平台 API 或扣子插件、要给别人用** → 路径 ③。
- **自己写脚本做批量分析** → 路径 ④。

> ⚠️ 无论哪条路径，本语料库都是**快照**且**不含地方性法规与法院裁审指引**；
> 涉及最低工资、社平工资、工伤待遇、加班费基数等地方标准时必须按当地口径核验。
> 本服务提供法律信息而非法律意见，具体争议请委托执业律师。
