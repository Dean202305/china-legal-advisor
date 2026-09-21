# AGENTS.md

本文件为**通用 AI 编码助手**（OpenAI Codex、Cursor、Cline、Continue、Aider、Zed、
Windsurf、Devin、Jules 等支持 `AGENTS.md` 的工具）提供项目指令。

---

## 项目是什么

`china-legal-advisor` 是一个**中国法律条文级检索技能**：内置 33 部法规、3093 条条文的
离线权威语料库，以及零依赖的检索 CLI。它服务于"回答中国法律问题时**查法条**而不是**编法条**"
这一目标。

## 当用户提出中国法律问题时

1. **先判断模式**（见 `SKILL.md` 第二节）：
   - 条文查询（"第 X 条怎么规定"）→ 直接答；
   - **个案咨询**（涉及具体当事人/时间/金额）→ **先提问补齐关键事实**，最多 2 轮，再回答；
   - 假设/科普 → 可直接答，但标注假设。
2. **先查后答**：任何条号、条文、数字都必须来自实际检索，**禁止凭记忆写法条**。
3. **回答末尾必须附「总结回答」**（定性＋依据＋金额＋风险＋动作＋时效）。

```bash
python3 scripts/law.py list                       # 语料库概览
python3 scripts/law.py search 竞业限制 违约金      # 关键词检索条文
python3 scripts/law.py article 劳动合同法 38       # 取条文原文（引用前必做）
python3 scripts/law.py search 第五百七十七条        # 按条号命中
python3 scripts/law.py verify                     # 语料完整性
python3 scripts/selftest.py                       # 解析器 + 语料自检
```

细化的领域检索地图与必问清单：

- `references/intake-questions.md` —— 先问后答：劳动 / 公司 / 民法典三套必问清单
- `references/labor-playbook.md` —— 劳动法问题 → 检索词/条文地图
- `references/company-playbook.md` —— 公司法问题 → 检索词/条文地图（含司法解释**旧条号对照表**）
- `references/civil-playbook.md` —— 民法典问题 → 检索词/条文地图
- `references/query-expansion.md` —— 口语 → 法言法语检索词对照
- `references/output-templates.md` —— 输出模板与「总结回答」模板
- `references/currency.md` —— 时效核验、地方标准清单、语料更新流程

## 当用户要求开发/修改本项目时

- `scripts/*.py` **只能使用 Python 3.8+ 标准库**（零第三方依赖是核心承诺）；
- 修改条文切分逻辑后，**必须**在 `scripts/selftest.py` 中补充对应用例；
- 提交前必须通过：`python3 scripts/selftest.py && python3 scripts/law.py verify`；
- 新增语料请用 `python3 scripts/add_document.py`，并遵守 `CONTRIBUTING.md` 的
  "必须来自官方来源、禁止凭记忆生成、不得改动条文内容"三条硬性要求。

## 三条不可违反的红线

1. **禁止编造法条**——检索不到就说"语料库未收录，需核验"，不得用相近条文顶替。
2. **禁止无条号引用**——不得出现"根据相关法律规定""依据我国法律"这类空心引用。
3. **区分法律信息与法律意见**——不预测胜负、不承诺结果，具体案件建议委托执业律师。

完整规范见 `SKILL.md`；免责声明见 `DISCLAIMER.md`。
