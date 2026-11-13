# APMCM Manuscript Gate

一个用于**数学建模已成稿论文评分、验收、自动整改与交付签发**的 WorkBuddy Skill。

本 Skill 从 **49篇亚太杯数学建模优秀论文**（2014—2020、2022—2025，共1761页）的全量分析中蒸馏而成：将论文的优点转化为各闸门的正向得分证据，将数值冲突、验证不足、数据泄漏、约束不可行、排版混乱和模板化措辞等问题转化为拦截与整改规则。它是论文质量审查工具，不代表竞赛官方评分标准。

## 适用时机

仅在**审题分析、数据处理、建模、代码求解和论文写作全部完成后**使用。它不负责中途指导建模，而是对最终成果执行：

```text
原件保全 → 13道双向闸门验收 → 100分评分 → 定位失分
→ 修改工作副本 → 补齐证据 → 复检受影响闸门 → 输出最终分与交付结论
```

## 核心能力

- **13道双向闸门**：同时检查缺陷底线和正向优点证据；没有错误不等于合格，亮点不能抵消硬伤。
- **100分加权评分**：独立复算、验证与证据等级各占12分；排版、图表、章节与措辞占14分。
- **硬门否决**：核心数值、独立验证、方案可行性等关键门失败时，即使总分较高也不能交付。
- **深度排版审查**：页面、字体、页边距、标题层级、图表数量与尺寸、三线表、公式、引用和附录。
- **语言与摘要审查**：检查逐问闭环、定量结论、证据对应和模板化措辞；整改时冻结数值、公式、单位和术语。
- **自动提分闭环**：输出初始分、失分位置、每轮修改、新增证据、复检结果和最终分；不通过编造结果或只改状态提分。
- **原稿保护**：记录SHA-256，所有修改在工作副本中进行。

## 闸门与权重

| 闸门 | 分值 | 验收重点 |
|---|---:|---|
| G00 | 3 | 输入、规则、原件与版本 |
| G01 | 8 | 题目逐问覆盖与跨问闭环 |
| G02 | 6 | 数据、参数与处理谱系 |
| G03 | 6 | 模型、假设、符号、量纲与边界 |
| G04 | 6 | 模型适配、基线与复杂模型增益 |
| G05 | 8 | 实际执行、日志与复现 |
| G06 | 12 | 独立复算与摘要—正文—图表—代码一致性 |
| G07 | 12 | 验证设计、数据泄漏与证据等级 |
| G08 | 7 | 约束可行性、最优性与方案回建 |
| G09 | 7 | 敏感性、稳健性与不确定性 |
| G10 | 6 | 结果、方案与摘要闭环 |
| G11 | 14 | 排版、图表、章节、引用与措辞 |
| G12 | 5 | 整改复检、最终稿与交付签发 |

单门状态包括 `PASS`、`EXCELLENT`、`FAIL`、`REJECT`、`NOT_VERIFIABLE`、`PENDING` 和有客观理由的 `N/A`。总评包括 `ACCEPT`、`DISTINCTION`、`RETURN_FOR_REVISION`、`REJECT` 和 `INCOMPLETE`。

## 获取与使用

```bash
git clone https://github.com/mxbms/apmcm-manuscript-gate.git
cd apmcm-manuscript-gate
```

### 1. 初始化审查目录

```bash
python scripts/gate_review.py init --manuscript <论文.pdf/docx/md> --out <审查目录>
```

支持 Markdown、TXT、PDF 和 DOCX。PDF提取需要 `PyMuPDF`，DOCX提取及自动排版需要 `python-docx`：

```bash
python -m pip install PyMuPDF python-docx
```

初始化只生成空白证据登记和审查结构，不会自动判定论文合格。随后依据 `references/gate_specifications.md` 和 `references/layout_and_language.md` 完成实际复算、验证、排版与语言检查，并填写证据。

### 2. 校验证据并计算分数

```bash
python scripts/gate_review.py verify --review <审查目录>
```

输出 `gate_verdict.json` 和 `gate_verdict.md`，包含逐门状态、得分、失分、总评和是否允许交付。只把门状态改成 `PASS` 而没有对应证据，仍会被拦截。

### 3. 自动整改并重新评分

```bash
python scripts/auto_improve.py cycle --review <审查目录>
```

针对DOCX工作副本执行页面、字体、题注、图片宽度和数据三线表整改：

```bash
python scripts/auto_improve.py docx --manuscript <原稿.docx> --out <工作副本.docx> --three-line-tables
```

自动工具只实施有边界的排版和措辞修改；模型、数值、验证、最优性和可行性必须重新运行或补充真实证据，之后再次执行 `verify`。

## 目录

```text
SKILL.md                    Skill入口与完整执行协议
references/                 逐门合格线、优秀线、专项检验、排版语言与评分规则
assets/templates/           21个验收、证据、整改与交付模板
scripts/gate_review.py      审查初始化、证据校验、评分与总评
scripts/audit_manuscript.py 中英文论文结构预检
scripts/auto_improve.py     有边界的自动整改与提分记录
```

## 最终交付

一次完整验收应交付最终稿、逐门评分表、优点证据、问题与整改登记、独立复算记录、验证材料、排版与语言审计、自动修改日志、最终分数及交付签发报告。
