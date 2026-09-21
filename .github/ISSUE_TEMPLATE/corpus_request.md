---
name: 新增法规 / 修法更新
about: 提交新的法规语料，或申请补充某部法规
title: "[Corpus] "
labels: ["corpus"]
---

## 类型

- [ ] 新增法规语料（我已准备好文本，将提交 PR）
- [ ] 申请补充某部法规（我暂时没时间抓取）
- [ ] 修法更新（某部法规已被修正/修订/废止）

## 法规信息

- 法规全称：
- 简称：
- 类别：`labor` / `company` / `civil` / `procedure` / `other`
- 版本（含日期与文号）：
- 施行日期：
- 条数 / 末条条号：
- 官方来源 URL：
- 交叉验证来源 URL（建议提供）：

## 若为修法更新，请说明

- 修正/修订的依据（主席令、国务院令、法释文号）：
- 主要变化（新增/删除/修改了哪些条）：
- 旧版本是否需要保留并标注 `status: 已修改`：

## 自检

```bash
python3 scripts/add_document.py --help   # 新增语料请使用该脚本
python3 scripts/selftest.py
python3 scripts/law.py verify
```

- [ ] 我已确认文本来自官方来源，且**未改动任何条文内容**
- [ ] 我已运行上述自检命令并通过
