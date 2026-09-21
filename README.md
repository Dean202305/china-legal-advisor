# 中国法律顾问技能 · China Legal Advisor

> 让 AI 助手**查法条**而不是**编法条**——离线、可检索、可核验的中国法律条文级知识库 + 技能。
> 覆盖《民法典》《劳动合同法》《公司法》等 33 部规范、**3093 条条文**，零依赖、开箱即用。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Corpus](https://img.shields.io/badge/corpus-33%20laws%20%7C%203093%20articles-green.svg)](docs/SOURCES.md)
[![Tools](https://img.shields.io/badge/works%20with-Claude%20Code%20%C2%B7%20Codex%20%C2%B7%20Cursor%20%C2%B7%20DSH%20%C2%B7%20any%20agent-purple.svg)](#-支持的-ai-工具)

---

## 为什么需要它

大模型回答法律问题时最常见的失败**不是分析错，而是引错法条**：

- 引用**已被修订或废止**的条文（例如 2018 年旧《公司法》的条号）；
- 条号对不上、条文内容凭记忆生成；
- 用全国性规定回答**地方标准**问题（最低工资、社平工资、工伤待遇）；
- 把"经济补偿"和"赔偿金"、"诉讼时效"和"除斥期间"混为一谈。

本技能把这些全部交给**离线语料库 + 条文级检索**：任何条号、条文、数字都必须从官方全文里取，
先读到原文，再谈分析。

## 能做什么

| 领域 | 覆盖内容 |
| --- | --- |
| **劳动与社会保障** | 劳动合同订立与解除、经济补偿 N/N+1/2N、加班费、工时与年休假、竞业限制、工伤认定与待遇、社会保险、劳动仲裁程序 |
| **公司与企业** | 2023 修订《公司法》：五年认缴、出资加速到期、股东权利与责任、股权转让、董监高忠实勤勉义务、决议瑕疵、解散清算、法定代表人 |
| **民法典与民事纠纷** | 合同效力与违约、违约金与定金、借贷与保证、侵权赔偿、人格权、婚姻家庭（含共同债务）、继承、诉讼时效 |
| **程序与配套** | 民事诉讼法、仲裁法、劳动争议调解仲裁法、合同编通则解释、婚姻家庭编解释（一）（二）、公司法时间效力规定等 |

**不只是"查法条"**，技能还内置：

- **总则式工作流**：定性 → 检索 → 取原文 → 补配套 → 核时效 → 出结论；
- **交互协议（先问后答）**：个案先提问补齐关键事实，避免按错误前提分析；
- **「总结回答」**：每次回答末尾附一段可独立阅读的结论（定性＋依据＋金额＋风险＋动作＋时效）；
- **时效防线**：内置"近期法律变动表"（公司法 2023 修订、劳动争议解释（二）2025、婚姻家庭编解释（二）2025、仲裁法 2025 修订等），防止引用变动前的旧规则；
- **地方标准提醒**：明确标注哪些事项必须按当地口径核验，并给出官方核验渠道。

## 🚀 30 秒上手

```bash
git clone https://github.com/Dean202305/china-legal-advisor.git
cd china-legal-advisor

# 安装到你的 AI 工具（自动检测已安装的工具）
./install.sh

# 或者只装到指定工具
./install.sh --target claude      # Claude Code
./install.sh --target codex       # OpenAI Codex
./install.sh --target dsh         # DSH
./install.sh --target cursor      # 当前项目的 Cursor 规则
```

**不用 AI 也能直接查**（零依赖，只需 Python 3.8+）：

```bash
python3 scripts/law.py list                              # 看语料库有什么
python3 scripts/law.py search 竞业限制 违约金             # 关键词检索条文
python3 scripts/law.py search 试用期 --doc 劳动合同法     # 限定法规
python3 scripts/law.py article 劳动合同法 38              # 取条文原文
python3 scripts/law.py article 民法典 第五百七十七条 -A 2  # 带前后条
python3 scripts/law.py verify                            # 语料完整性自检
```

## 🔌 支持的 AI 工具

本技能遵循 **Agent Skills** 约定（`SKILL.md` + `references/` + `scripts/`），
并为不识别该约定的工具提供适配文件：

| 工具 | 接入方式 | 安装位置 |
| --- | --- | --- |
| **Claude Code** | Agent Skills | `~/.claude/skills/china-legal-advisor/`（个人）或 `<项目>/.claude/skills/…`（项目） |
| **OpenAI Codex** | Agent Skills / `AGENTS.md` | `~/.codex/skills/china-legal-advisor/`；仓库根 `AGENTS.md` |
| **DSH** | Agent Skills | `~/.dsh/skills/china-legal-advisor/` |
| **Cursor** | `.cursor/rules/*.mdc` 规则 | `<项目>/.cursor/rules/china-legal-advisor.mdc` |
| **Windsurf / Cline / Continue / Aider / Zed 等** | 通用 `AGENTS.md` | 把 `AGENTS.md` 放到项目根，或将其内容粘入工具的规则设置 |
| **任何脚本 / CLI / 自建 Agent** | 直接调用 `scripts/law.py`（支持 `--json`） | 无需安装，任意语言 `subprocess` 调用 |

> `install.sh` 默认用**符号链接**安装，因此 `git pull` 即可让所有 AI 工具同步更新；
> 若你的工具不支持符号链接，加 `--copy`。

## 💬 使用示例

技能启用后，直接用自然语言提问即可。它会**先查条文、按需反问、最后给总结**：

> **你**：公司说月底北京不留员工了，我的劳动合同签的 3 年，只签了离职证明，还欠我 6400 元工资，这样违法吗？
>
> **AI**（先按交互协议反问）：
> 为了给你准确结论，我需要先确认几件事——这些答案会直接改变适用条文和金额：
> **一、合同与时间**：① 入职日和结束日？② 试用期约定了多久？③ 签完之后你拿到合同文本了吗？
> **二、钱**：④ 工资构成？⑤ 哪几个月少发或扣款、各多少？⑥ 有工资条吗？
> **三、解除经过**：⑦ 谁先提出？公司给的理由？有书面通知吗？⑧ 你签过什么字、上面写了什么？
> **四、诉求**：⑨ 你想拿补偿、恢复工作，还是先评估风险？

收集到足够信息后，技能会给出**带条号原文的综合分析**，并在末尾附上：

```markdown
### 总结回答
**你的情况属于**：3 年期劳动合同在第 4 个月被单方解除 + 拖欠工资
**最关键依据**：《劳动合同法》第 38 条第(二)项、第 46 条第(一)项、第 87 条
**你能主张**：拖欠工资 6,400 元 + 经济补偿 5,000 元（或违法解除赔偿金 10,000 元）
**最大风险**：公司若拿出你签字的录用条件与考核不合格证据，"违法解除"可能不成立
**现在就要做**：1) 今天发出书面催告函并保留 EMS 凭证 2) …
**时效提醒**：自劳动关系终止之日起 1 年内申请劳动仲裁
```

更多示例与输出规范见 [`references/output-templates.md`](references/output-templates.md)。

## 📚 语料库

| 类别 | 文件数 | 条文数 | 代表规范 |
| --- | ---: | ---: | --- |
| 民法典及配套 | 6 | 1514 | 《民法典》全文 1260 条、合同编通则解释、侵权/婚姻家庭/继承编解释 |
| 劳动与社会保障 | 15 | 744 | 劳动法、劳动合同法、实施条例、劳动争议调解仲裁法、社保法、工伤保险条例、年休假条例 |
| 公司与企业 | 10 | 433 | 公司法（2023 修订）、时间效力规定、第八十八条批复、解释（一）～（五）、市场主体登记管理条例 |
| 程序法 | 2 | 402 | 民事诉讼法（2023 修正）、仲裁法（2025 修订） |
| **合计** | **33** | **3093** | 约 33 万字 |

**每部法规的来源、版本、施行日期、抓取日期与交叉验证链接**见
[`docs/SOURCES.md`](docs/SOURCES.md)；人读目录见 [`references/CORPUS.md`](references/CORPUS.md)。

- 语料全部**真实抓取自官方来源**（中国政府网、中国人大网、最高人民法院、人社部等），
  关键法规用第二、第三独立来源**逐条交叉比对**（如《民法典》1260 条全量比对，0 处不一致）。
- 法律、行政法规、司法解释属具有立法/行政/司法性质的官方文件，依《著作权法》第五条不适用著作权法，
  可自由收录；本仓库不改动任何条文内容。

## 🧭 工作方式

```
用户提问
   │
   ├─ 判断模式：条文查询 → 直接答｜个案咨询 → 先问后答｜假设题 → 标注假设
   │
   ├─ 先问后答：只问"能改变结论"的事实（定性 / 金额 / 时效程序 / 举证责任）
   │           第一轮 5～8 问，最多追问 2 轮，之后必须给结论
   │
   ├─ 检索：search 定位 → article 读原文（禁止凭记忆写法条）
   │
   ├─ 核时效：查近期法律变动表 + 地方标准联网核验
   │
   └─ 输出：法律依据（原文＋条号＋版本）→ 要件与事实对照 → 计算 → 风险 → 下一步
            └─ 「总结回答」收尾（可独立阅读）
```

## 📁 目录结构

```
china-legal-advisor/
├── SKILL.md                      # 技能主文件（Agent Skills 入口）
├── AGENTS.md                     # 通用 Agent 指令（Codex/Cursor/Cline/…）
├── CLAUDE.md                     # Claude Code 项目记忆
├── install.sh                    # 一键安装到各 AI 工具
├── references/
│   ├── raw/*.txt                 # 33 部法规全文（检索语料，含元数据头）
│   ├── CORPUS.md / index.json    # 自动生成的语料目录与索引
│   ├── intake-questions.md       # 先问后答：三类领域必问清单
│   ├── labor-playbook.md         # 劳动法问题 → 检索词/条文地图
│   ├── company-playbook.md       # 公司法问题 → 检索词/条文地图（含新旧条号对照）
│   ├── civil-playbook.md         # 民法典问题 → 检索词/条文地图
│   ├── query-expansion.md        # 口语 → 法言法语检索词对照表
│   ├── output-templates.md       # 输出模板与「总结回答」模板
│   └── currency.md               # 时效核验、地方标准清单、语料更新流程
├── scripts/
│   ├── law.py                    # 条文级检索 CLI（零依赖）
│   ├── add_document.py           # 新增法规并自动校验条号
│   └── selftest.py               # 解析器 + 语料库自检
├── docs/SOURCES.md               # 语料来源与著作权说明
├── docs/ci.yml                   # CI 定义（模板，复制到 .github/workflows/ 即启用）
├── NOTICE.md                     # 权利状态与来源声明
├── DISCLAIMER.md                 # 免责声明（中英双语）
└── .github/                      # Issue / PR 模板
```

## 🔄 更新语料库

修法后自行补充（脚本会校验条号连续性并提示重建索引）：

```bash
python3 scripts/add_document.py \
  --title "中华人民共和国XX法" --short "XX法" --category labor \
  --version "2026年X月X日修正" --effective 2026-XX-XX \
  --source "https://www.gov.cn/..." --slug xx-law \
  --from-url "https://www.gov.cn/..."

python3 scripts/law.py verify && python3 scripts/law.py index
python3 scripts/selftest.py
```

> ⚠️ 语料库是**快照**。每个文件头部记录了 `fetched` 日期与来源 URL；
> 引用前请核对现行有效版本（核验渠道见 [`references/currency.md`](references/currency.md)）。

## ❓ 常见问题

**Q：它会不会编造法条？**
A：技能的第一条红线就是"先查后答，禁止凭记忆写法条"；检索不到时会明确说"语料库未收录，需核验"，
而不是用相近条文顶替。所有条号都可回到 `references/raw/` 用 `article` 命令核对。

**Q：能替代律师吗？**
A：**不能。** 它提供的是**法律信息**（条文、要件、计算、风险提示），不是针对个案的正式法律意见。
具体争议请委托执业律师。见 [`DISCLAIMER.md`](DISCLAIMER.md)。

**Q：语料库不包含什么？**
A：地方性法规、地方政府规章、各级法院会议纪要与裁审指引、以及部分司法解释。
遇到这些内容技能会提示需联网核验。

**Q：支持其他语言/其他法域吗？**
A：当前仅覆盖中国大陆法律。语料与技能均为中文，交互也以中文为主。

## 🤝 贡献

欢迎提交新的法规语料、修法更新、检索词优化与文档改进。
请先阅读 [`CONTRIBUTING.md`](CONTRIBUTING.md)——**提交前必须通过 `python3 scripts/selftest.py`**。

## 📄 许可证与免责

- 代码与文档：[MIT](LICENSE)
- 收录的法规文本：依《中华人民共和国著作权法》第五条不适用著作权法（见 [NOTICE.md](NOTICE.md) 与 [docs/SOURCES.md](docs/SOURCES.md)）
- **重要**：本项目不构成法律意见，使用前请阅读 [DISCLAIMER.md](DISCLAIMER.md)

---

<sub>如果你的这个项目帮到了你，欢迎 Star ⭐ —— 也欢迎提交你所在领域的法规语料。</sub>
