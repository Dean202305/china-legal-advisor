# 免责声明 · Disclaimer

**请在使用本项目前完整阅读本声明。**

## 一、本项目提供的是"法律信息"，不是"法律意见"

本项目（含技能指令、离线语料库、检索工具及其全部输出）旨在帮助使用者
**快速定位并核对中华人民共和国法律、行政法规与司法解释的条文原文**，
属于**一般性法律信息**的整理与检索工具。

它**不是**：

- 针对任何具体案件的法律意见或法律建议；
- 对诉讼、仲裁、谈判结果的预测或承诺；
- 律师服务，也不构成与任何使用者之间的委托代理关系。

**具体案件请委托执业律师。** 律师能够结合你的全部证据、当地裁审口径与最新司法政策作出判断，
这是任何工具都无法替代的。

## 二、不保证时效性与完整性

1. **语料库是快照。** 每个语料文件头部记录了 `version`、`effective`、`source` 与 `fetched`（抓取日期）。
   法律可能在此之后被修正、修订或废止，**引用前请务必核对现行有效版本**。
   官方核验渠道见 [`references/currency.md`](references/currency.md)。
2. **收录范围有限。** 语料库**不包含**地方性法规、地方政府规章、自治条例、
   各级法院的会议纪要与裁审指引、以及部分司法解释。
   涉及最低工资、社会平均工资、工伤待遇、加班费基数等**地方标准**时，必须按当地口径另行核验。
3. **不保证无错误。** 尽管本项目对每部法规做了条号连续性与交叉来源校验，
   仍可能存在抓取、清洗或解析错误。**任何条文均应以官方发布的正式文本为准。**

## 三、AI 输出的固有风险

当本项目作为技能被大语言模型调用时：

- 模型的**分析与推理可能出错**，条文引用也可能因模型行为而与语料库不一致；
- 请**始终回到 `references/raw/` 或官方来源核对条号与条文原文**；
- 不要仅凭 AI 输出作出诉讼、签约、离职、投资等重大决定。

## 四、责任限制

在适用法律允许的最大范围内，本项目作者与贡献者**不对**因使用或无法使用本项目
而产生的任何直接、间接、附带、特殊或后果性损害承担责任，
包括但不限于因依赖本项目输出而造成的经济损失、诉讼失利或权利丧失。

## 五、使用者的责任

使用本项目即表示你理解并同意：

1. 自行核实任何条文、标准与结论的**时效性与适用性**；
2. 就具体法律事务**咨询执业律师**；
3. 遵守你所在地区的法律法规与职业规范。

---

## Disclaimer (English)

This project provides **general legal information** — full texts of Chinese statutes,
administrative regulations and judicial interpretations, plus retrieval tooling.
It is **NOT legal advice**, does not create any attorney-client relationship, and
carries **no warranty** of accuracy, completeness or currency.

The bundled corpus is a **point-in-time snapshot**; laws may have been amended or
repealed since the `fetched` date recorded in each file. Always verify against the
official source before relying on any provision. When used as a skill by a large
language model, the model's reasoning and citations may be wrong — verify every
article against `references/raw/` or the official text.

**For any specific matter, consult a licensed lawyer.** To the maximum extent
permitted by law, the authors and contributors accept no liability for any damages
arising from the use of this project.
