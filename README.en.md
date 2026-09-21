# China Legal Advisor — a skill that cites statutes instead of inventing them

> An offline, article-level retrieval corpus of Chinese law (**33 statutes · 3,093 articles**)
> plus an agent skill that forces LLMs to **look up** statutory text rather than recall it.
> Zero dependencies. Works with Claude Code, Codex, Cursor, DSH and any other agent.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)

> 中文文档见 [README.md](README.md)。This is a condensed English overview.

## Why

The most common failure of LLMs on Chinese legal questions is **not bad analysis — it is bad citation**:
quoting repealed articles, inventing article numbers, or answering a local-standard question
(minimum wage, social average wage, work-injury benefits) with a national rule.

This project removes recall from the loop: every citation must be retrieved from an
**offline corpus of official full texts** before it can be used.

## What it covers

| Area | Highlights |
| --- | --- |
| **Labour & social security** | Employment contracts, termination, severance `N / N+1 / 2N`, overtime, annual leave, non-compete, work-injury, social insurance, labour arbitration |
| **Company law** | The **2023 revision** of the PRC Company Law (5-year capital contribution, accelerated maturity, shareholder & D&O liability, equity transfer, dissolution) |
| **Civil Code** | Full 1,260 articles, plus contract, tort, marriage/family, inheritance interpretations |
| **Procedure** | Civil Procedure Law (2023), Arbitration Law (2025), and the labour arbitration statute |

## Install

```bash
git clone https://github.com/Dean202305/china-legal-advisor.git
cd china-legal-advisor
./install.sh                     # auto-detect and install to all detected tools
./install.sh --target claude     # or: codex | dsh | cursor | project | all
```

| Tool | Integration | Install path |
| --- | --- | --- |
| Claude Code | Agent Skills | `~/.claude/skills/china-legal-advisor/` |
| OpenAI Codex | Agent Skills / `AGENTS.md` | `~/.codex/skills/china-legal-advisor/` |
| DSH | Agent Skills | `~/.dsh/skills/china-legal-advisor/` |
| Cursor | `.cursor/rules/*.mdc` | `<project>/.cursor/rules/china-legal-advisor.mdc` |
| Windsurf / Cline / Continue / Aider / Zed | `AGENTS.md` | repo root `AGENTS.md` |
| Any script or custom agent | Call `scripts/law.py` (supports `--json`) | no install needed |

## Use without an AI

```bash
python3 scripts/law.py list                               # browse the corpus
python3 scripts/law.py search 竞业限制 违约金              # keyword search across articles
python3 scripts/law.py article 劳动合同法 38               # fetch one article verbatim
python3 scripts/law.py article 民法典 第五百七十七条 -A 2   # with neighbouring articles
python3 scripts/law.py verify                             # integrity check
```

## How the skill behaves

1. **Look up first, never recall.** Article numbers, text and figures must come from retrieval.
   If the corpus lacks it, the skill says so instead of inventing a near-miss provision.
2. **Ask before answering.** For a concrete case it first asks a short set of
   decision-relevant questions (facts that change the legal characterisation, the amount,
   the limitation period, or the burden of proof), then answers — at most two rounds.
3. **Close with a summary** the user can act on: characterisation → key provisions →
   what can be claimed → biggest risk → what to do now → limitation period.
4. **Currency guardrails.** A "recent changes" table warns about the 2023 Company Law revision,
   the 2025 labour-dispute interpretation (II), the 2025 marriage/family interpretation (II)
   and the 2025 Arbitration Law revision, and flags every issue that needs local-standard verification.

## Corpus provenance

All texts were captured from official sources (State Council, NPC, Supreme People's Court,
MOHRSS, …); key statutes were **cross-verified article-by-article against two or three
independent official sources** (the Civil Code's 1,260 articles matched exactly).
Version, effective date, source URL and fetch date are recorded per file and listed in
[docs/SOURCES.md](docs/SOURCES.md).

Chinese statutes, administrative regulations and judicial interpretations are official
documents of a legislative/administrative/judicial nature and are **not subject to copyright**
under Article 5 of the PRC Copyright Law; no provision has been altered.

## Disclaimer

This project provides **general legal information, not legal advice**.
It creates no attorney-client relationship and comes with **no warranty** as to accuracy,
completeness or currency. The corpus is a point-in-time snapshot — always verify against the
official text. **For any specific matter, consult a licensed lawyer.**
See [DISCLAIMER.md](DISCLAIMER.md).

## Contributing

New statutes, amendments, retrieval improvements and documentation fixes are welcome.
Before opening a PR, run:

```bash
python3 scripts/selftest.py && python3 scripts/law.py verify
```

See [CONTRIBUTING.md](CONTRIBUTING.md) (in Chinese).

## License

MIT — see [LICENSE](LICENSE).
