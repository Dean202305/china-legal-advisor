# CLAUDE.md

本项目的完整指令见 **`SKILL.md`**（技能主文件）与 **`AGENTS.md`**（通用 Agent 指令），
二者对本仓库同样适用。以下为 Claude Code 场景下的要点摘要。

## 作为技能使用

本仓库即一个 Agent Skill。安装到个人技能目录后即可被自动识别：

```bash
./install.sh --target claude
# 等价于：ln -s "$PWD" ~/.claude/skills/china-legal-advisor
```

也可仅对某个项目生效：把本目录放到 `<项目>/.claude/skills/china-legal-advisor/`，
或运行 `./install.sh --target project`。

## 回答中国法律问题时的行为约束

1. **先判断模式**：条文查询直接答；**个案咨询必须先提问收集关键事实**（最多 2 轮追问），
   再给综合分析；假设题可答但须标注假设。详见 `SKILL.md` 第二节。
2. **先查后答**：用 `python3 scripts/law.py search/article` 取到条文**原文**后再引用，
   **禁止凭记忆写法条**。
3. **末尾必附「总结回答」**：定性 → 最关键依据 → 能主张什么 → 最大风险 → 现在做什么 → 时效提醒。
4. 涉及时效性（地方标准、最新修法）时联网核验，并注明来源与查询日期。

## 常用命令

```bash
python3 scripts/law.py list
python3 scripts/law.py search 经济补偿 --doc 劳动合同法
python3 scripts/law.py article 公司法 88 --source
python3 scripts/law.py verify && python3 scripts/selftest.py
```

## 修改本项目时

- `scripts/*.py` 仅使用 Python 3.8+ 标准库；
- 提交前必须通过 `python3 scripts/selftest.py` 与 `python3 scripts/law.py verify`；
- 新增语料遵守 `CONTRIBUTING.md`（官方来源、禁止编造、不得改动条文内容）。

> 本项目提供的是法律信息而非法律意见，详见 `DISCLAIMER.md`。
