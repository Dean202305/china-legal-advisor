# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 与
[语义化版本](https://semver.org/lang/zh-CN/)。

## [0.3.0] - 2026-09-21

面向**手机 App**（豆包 / 腾讯元宝 / 通义千问 / Kimi / 智谱清言 / DeepSeek / ChatGPT / Gemini）
优化接入体验。手机 App 运行在云端、无法调用本地程序，唯一可行路径是"上传知识库 + 粘贴指令"，
本版本把这条路径压缩到 2 分钟。

### 新增

- `scripts/build_kb.py` 支持 `--profile mobile`：生成**手机端单文件包**，含
  - `中国法律条文-核心版-民法典与劳动.docx`（≈246 KB，覆盖多数常见问题）
  - `中国法律条文-全量版-33部法规.docx`（≈339 KB）
  - 同时提供 `.txt` 版本（平台不认 docx 时的备选）
  - `01-系统提示词-可复制.txt`（直接粘贴到「人设 / 自定义指令」）
  - `00-先看这个-接入说明.md`（逐步操作卡片）
- **DOCX 生成能力（纯 Python 标准库）**：`.docx` 本质是 zip + XML，
  由 `zipfile` + 手写 OOXML 直接生成，**不引入 python-docx 等任何第三方依赖**；
  经 XML 解析与 `file` 校验，Word / WPS / Pages / Google Docs 均可打开。
  之所以需要它：**手机文件选择器常常不显示 `.md` 文件**，而 `.txt`/`.docx` 几乎所有 App 都认。
- `docs/PLATFORM-GUIDE.md` —— 8 个 App 的逐步操作卡片、把文件传到手机的 4 种方法、
  上传后的三步验证、局限说明。该文件同时被打包进手机端知识库包，**文档只有一份**
  （`build_kb.py` 直接读取它，不重复维护）。
- `build_kb.py` 新增 `--profile all` 与 `--format md,txt,docx`。

### 变更

- README 新增「📲 手机 App 专用」小节；目录结构补充 `docs/PLATFORM-GUIDE.md`。
- CI 的"知识库打包"步骤改为同时校验 desktop 与 mobile 两种形态的产物。
- 发布产物：Release 资产新增 `china-legal-advisor-kb-mobile.zip`（≈1.08 MB）。

## [0.2.0] - 2026-09-21

新增**聊天应用接入能力**：让豆包、通义千问、DeepSeek、Coze 等不支持本地技能的产品
也能用上本语料库。三条路径全部实现，详见 [`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md)。

### 新增 · 接入层（全部零第三方依赖）

- `scripts/mcp_server.py` —— **MCP 服务器**（stdio + 换行分隔 JSON-RPC 2.0），
  暴露 5 个工具：`search_law`、`get_article`、`list_laws`、`get_playbook`、`corpus_stats`；
  并通过 `initialize.instructions` 下发"先查后答 / 先问后答 / 附总结回答"的行为约束。
  适用于 Claude Desktop、Cursor、Cline、Cherry Studio、ChatWise 等 MCP 客户端。
  支持 `--selftest` 一键自检。
- `scripts/serve.py` —— **HTTP JSON API**（标准库 `http.server`），提供
  `/health`、`/stats`、`/laws`、`/search`、`/article`、`/playbook`、
  `/tools/openai.json`、`/tools/mcp.json` 与 `POST /tool`；
  自带浏览器测试页、CORS、可选 `--token` 鉴权；默认只监听 `127.0.0.1`。
  适用于 DeepSeek 开放平台、通义千问 API、扣子 Coze 插件、豆包智能体等函数调用场景。
- `scripts/build_kb.py` —— **知识库打包器**：把语料库渲染成可直接上传到聊天 App 的
  markdown 文件包（民法典 / 劳动 / 公司 / 程序法 / 实务指南 / 检索词与输出模板 /
  全量合集），支持 `--max-chars` 按平台限制切分与 `--zip` 打包。
- `prompts/system-prompt-zh.md`、`prompts/system-prompt-lite.md` ——
  可直接粘贴到聊天 App「自定义指令 / 角色设定」的**系统提示词**（完整版 + 精简版 + 极简版），
  把本技能的四条红线、先问后答协议、总结回答要求完整复刻到任意聊天应用。
- `examples/deepseek_function_calling.py` —— **可运行的 Function Calling 示例**
  （仅用 urllib，兼容 DeepSeek / 通义 / Moonshot / 智谱等 OpenAI 兼容接口），
  自动拉取工具定义、执行工具调用并多轮循环。
- `examples/mcp_config.example.json` —— MCP 客户端配置示例。
- `docs/INTEGRATIONS.md` —— 逐步接入指南：三条路径的适用场景对比、各平台入口位置、
  接口清单、Coze 插件配置、公网部署与安全注意事项。

### 变更

- CI 模板（`docs/ci.yml`）新增 5 个步骤：脚本编译检查（Python 3.8 兼容）、
  MCP 自检、MCP stdio 协议冒烟测试、HTTP API 冒烟测试、知识库打包测试。
- `SKILL.md` 增加"被问到如何接入聊天应用"的指引；README 增加接入章节与目录结构更新。
- `.gitignore` 忽略生成物 `dist/`。

## [0.1.0] - 2026-09-21

首个公开版本。

### 新增 · 语料库（33 部规范 / 3093 条条文）

- **民法典及配套**（6 部 / 1514 条）：《民法典》全文 1260 条；合同编通则解释（69）、
  侵权责任编解释（一）（26）、婚姻家庭编解释（一）（91）与（二）（23）、继承编解释（一）（45）
- **劳动与社会保障**（15 部 / 744 条）：劳动法（107）、劳动合同法（98）、实施条例（38）、
  劳动争议调解仲裁法（54）、社会保险法（98）、工伤保险条例（67）、带薪年休假条例（10）及实施办法（19）、
  女职工劳动保护特别规定（16）、工资支付暂行规定（20）、最低工资规定（15）、就业促进法（69）、
  工会法（58）、劳动争议解释（一）（54）与（二）（21）
- **公司与企业**（10 部 / 433 条）：公司法（2023 修订，266）、市场主体登记管理条例（55）、
  注册资本登记管理制度（13）、公司法时间效力规定（8）、第八十八条批复、
  公司法解释（一）～（五）（6/24/28/27/6）
- **程序法**（2 部 / 402 条）：民事诉讼法（2023 修正，306）、仲裁法（2025 修订，96）

所有语料抓取自官方来源（中国政府网、中国人大网、最高人民法院、人社部等），
关键法规以第二、第三独立来源**逐条交叉比对**（《民法典》1260 条全量比对 0 处不一致）；
来源、版本、施行日期与抓取日期见 `docs/SOURCES.md`。

### 新增 · 工具

- `scripts/law.py` —— 条文级检索 CLI（零依赖）：
  `search` / `article` / `list` / `verify` / `stats` / `index`，支持按条号命中、OR 语义、
  正则、`--json`、限定法规与类别。
- `scripts/add_document.py` —— 新增法规并自动校验条号连续性（支持不设条号的批复/决定）。
- `scripts/selftest.py` —— 解析器与语料库全量自检。

### 新增 · 技能与文档

- `SKILL.md` —— 技能主文件：四条红线、**先问后答交互协议**、标准工作流、
  领域检索入口、常见错误预防、时效核验、输出规范与「总结回答」。
- `references/intake-questions.md` —— 劳动 / 公司 / 民法典三套必问清单与提问话术。
- `references/labor-playbook.md`、`company-playbook.md`、`civil-playbook.md` —— 领域检索地图
  （含公司法司法解释**旧条号对照表**、2025 年劳动争议解释（二）要点）。
- `references/query-expansion.md` —— 口语 → 法言法语检索词对照表。
- `references/output-templates.md` —— 三类问题的输出模板与「总结回答」模板。
- `references/currency.md` —— 时效核验渠道、地方标准清单、语料库更新流程、**近期法律变动表**。
- `AGENTS.md` / `CLAUDE.md` / `.cursor/rules/` —— 跨 AI 工具的接入文件。
- `install.sh` —— 一键安装到 Claude Code / Codex / DSH / Cursor 等工具。
- `DISCLAIMER.md` —— 中英双语免责声明。
- `docs/ci.yml` —— CI 定义（语料完整性、自检、命令冒烟测试、元数据校验）；
  以模板形式分发，复制到 `.github/workflows/ci.yml` 即启用。

### 已知限制

- 不含地方性法规、地方政府规章、法院会议纪要与裁审指引；
- 语料为快照，引用前须核对现行有效版本；
- 公司法司法解释（一）～（五）截至本版本仍未与 2023 年修订的公司法作衔接修正，
  其正文沿用旧条号，引用时须对照 `references/company-playbook.md` 的对应表。

[0.3.0]: https://github.com/Dean202305/china-legal-advisor/releases/tag/v0.3.0
[0.2.0]: https://github.com/Dean202305/china-legal-advisor/releases/tag/v0.2.0
[0.1.0]: https://github.com/Dean202305/china-legal-advisor/releases/tag/v0.1.0
