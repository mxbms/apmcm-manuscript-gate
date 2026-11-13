---
name: apmcm-manuscript-gate
description: 已成稿数学建模论文的双向验收、排版语言审查、加权评分、自动提分与交付签发闸门。This skill should be used only after modeling, coding, solving and manuscript writing are complete, when users need to identify unqualified sections, verify numerical and methodological claims, assess layout and language, calculate gate scores, automatically revise the working copy, re-run affected checks, or decide whether the final manuscript is ready for delivery. 采用G00—G12共13道硬闸门；无缺陷只是底线，必须同时提交正向能力证据，硬伤不能被高分抵消。
agent_created: true
---

# 数学建模论文双向验收闸门

## 目标与边界

对已成稿执行“原件保全 → 逐门验收 → 退回整改 → 影响范围复检 → 最终签发”。只依据原稿、题目、规则、数据、代码和实际运行证据判定，不凭论文宣称、模型名气或写作外观推定合格。

本 Skill 用于验收，不代替从空白开始建模。必须在分析、代码、求解和论文写作全部完成后启动，不在中途提供建模指导。需要修改时，在副本上实施最小必要修复并保留原稿；无法验证的内容标为 `NOT_VERIFIABLE`，不得猜判通过。

## 不可突破的规则

1. **双向验收**：每门同时检查缺陷拦截与正向能力证据。没有错误不等于合格，存在亮点不抵消失败。
2. **硬门不平均**：不采用百分制，不允许用其他门的高分抵消任一硬门失败。
3. **证据优先**：页码、公式、数据、代码、日志和独立复算优先于“已验证、结果合理、模型稳定”等声明。
4. **原稿只读**：记录原稿哈希；所有修改写入工作副本，保留修改位置和原因。
5. **不适用须举证**：`N/A`必须写客观理由；定量论文不得随意将数值复算或验证设计标为N/A。
6. **缺件不猜判**：关键证据缺失时使用`NOT_VERIFIABLE`，列出最小补件清单，不以“未见问题”代替通过。
7. **改后必复检**：修改任何模型、数值、图表、公式或结论后，重跑受影响闸门及G12；不得只改文字不复核计算。
8. **最终签发零未决**：所有适用门达到PASS/EXCELLENT，所有阻断项和整改项关闭后才能交付。

## 判定状态

### 单门状态

- `PENDING`：尚未完成检查或必交产物为空。
- `NOT_VERIFIABLE`：已执行可行检查，但缺必要证据，列出补件与可复现检查动作。
- `FAIL`：存在可整改缺陷，或缺少PASS要求的正向能力证据。
- `REJECT`：存在阻断交付的根本问题，如结果伪造、核心答案无效、无可行替代方案。
- `PASS`：底线检查通过，且正向能力证据完整。
- `EXCELLENT`：满足PASS，并达到该门独立、完整、可复核的优秀证据标准。
- `N/A`：客观不适用，已记录理由和批准人/复核者。

### 总评状态

按以下顺序判定，不前移：

1. `INCOMPLETE`：任何门为PENDING，或必交产物缺失。
2. `REJECT`：任何门为REJECT，或存在未关闭BLOCKER。
3. `RETURN_FOR_REVISION`：无REJECT，但存在FAIL或NOT_VERIFIABLE。
4. `ACCEPT`：全部适用门为PASS/EXCELLENT，整改项全部复检关闭。
5. `DISTINCTION`：满足ACCEPT，最终分数≥95，且G06、G07均为EXCELLENT，并在G04、G05、G08、G09、G10中至少三门为EXCELLENT。

`DISTINCTION`仍受全部硬门约束。任何后续改动均使G12回到PENDING，并触发影响范围内重审。

## 分值与自动提分

各门权重固定为：G00=3、G01=8、G02=6、G03=6、G04=6、G05=8、G06=12、G07=12、G08=7、G09=7、G10=6、G11=14、G12=5，总分100。G11排版、图表、章节与措辞为最高优先级单项。

单门计分比例为EXCELLENT=1.00、PASS=0.85、FAIL=0.40、NOT_VERIFIABLE=0.10、REJECT/PENDING=0，N/A从分母剔除。按`score=100×Σ(weight×ratio)/Σapplicable_weight`计算，保留两位小数。详细规则读取`references/scoring_and_improvement.md`。

- 85分为全部硬门合格的基准区间；只有全部硬门通过才可交付。
- DISTINCTION除既有条件外，还要求最终分数≥95。
- 最终必须输出初始分、每轮修改、最终分和剩余失分；不得只给分数不给证据。
- 默认目标为95分，但不得以删除负例、编造证据、机械换词或滥用N/A提分。

## 执行流程

### A. 建立审查工作区

1. 收集论文原稿、题目、当年提交规则、数据、代码和已有附件；缺哪项就登记哪项，不停止可执行的检查。
2. 保留原稿只读副本并计算SHA-256；PDF使用物理页码，DOCX使用段落/表号，Markdown/文本使用行号。
3. 运行初始化命令：

```bash
python scripts/gate_review.py init --manuscript <论文.md> --out <审查目录>
```

4. 按`references/gate_specifications.md`逐门检查；按`references/specialized_checks.md`执行相应任务类型的附加检验；按`references/layout_and_language.md`逐页检查排版、图表、章节与措辞。
5. 所有发现写入`finding_register.csv`，所有关键结论写入`claim_register.csv`，不得以散文评价代替登记；按`references/scoring_and_improvement.md`计算分值并执行自动提分闭环。

### B. 逐门验收

每门必须完成四件事：执行检查、提交正向证据、给出状态、生成规定文件。详细合格线和优秀线见`references/gate_specifications.md`。

| 闸门 | 分值 | PASS的最低合格标准 | EXCELLENT的正向证据 | 必交产物 |
|---|---:|---|---|---|
| G00 输入、规则与原件 | 3 | 原稿可读且哈希固定；题目、规则、审查范围和缺件登记完整 | 规则逐条映射到交付位置，页/段定位可回溯 | `G00_intake_manifest.json` |
| G01 题目覆盖 | 8 | 每个动作词均有对应模型、结果、单位、检验和回答，无漏问 | 跨问输入输出闭合，复用一致且每问有独立有效回答 | `G01_task_coverage.csv` |
| G02 数据与参数谱系 | 6 | 关键数据/参数可追溯；清洗、单位、异常、缺失和训练内变换无未说明处理 | 原始到结果全链可重建，另有数据质量与替代口径影响分析 | `G02_data_lineage.csv` |
| G03 模型规格 | 6 | 假设、符号、量纲、定义域、边界、逻辑与时间积分无矛盾，关键公式可计算 | 关键公式另有极限、守恒、不变量或小规模解析验证 | `G03_model_spec.md`、`G03_unit_checks.csv` |
| G04 模型适配与基线 | 6 | 模型适合数据/任务；同条件基线存在；复杂模型有增益或保留理由；无未执行模型宣称 | 多基线公平比较含成本、消融、失效边界，证明复杂度必要 | `G04_model_baselines.csv` |
| G05 执行与复现 | 8 | 关键结果实际运行；环境、配置、种子、版本、日志和输出路径齐全 | 干净环境一键重跑全部关键结果，数值在预定容差内一致 | `G05_run_manifest.json`、运行日志 |
| G06 独立复算与一致性 | 12 | 全部关键数值独立复算通过；摘要、结论、表、图、代码一致；区间/百分比正确 | 五点一致由脚本生成，另有独立方法/不变量交叉验证和容差依据 | `G06_recalculation.csv` |
| G07 验证与证据等级 | 12 | 切分无泄漏；指标适用；关键结论有匹配验证；因果、外部精度、稳定性不越界 | 独立时间/组外或外部真值验证覆盖最终模型，含反事实/安慰剂或跨过程证据 | `G07_validation_matrix.csv` |
| G08 可行性与最优性 | 7 | 推荐方案全约束可行；残差合格；最优/全局/Pareto表述有证据；压缩后回建验证 | 另有上下界/MIP gap、非支配检验、多初值和扰动后可行性证明 | `G08_constraint_residuals.csv`、`G08_optimality.md` |
| G09 敏感性与不确定性 | 7 | 关键参数/结构有扰动；报告输出变化、阈值和失效边界；区间类型正确；随机结果有分布 | 联合扰动、替代结构、多个种子及外部情景共同证明结论稳定 | `G09_sensitivity.csv`及图 |
| G10 结果与摘要闭环 | 6 | 每问有数值/方案、单位、条件、比较、验证和决策含义；负结果与不可行状态披露 | 唯一结果登记驱动摘要，方案含成本—性能—风险—可行性完整权衡 | `G10_result_register.csv` |
| G11 排版、图表、章节与措辞 | 14 | 页面、字体、标题、图表、三线表、引用和措辞一致且可读；无占位符、错引和模板残留 | 图表均承担论证功能，版式专业一致，摘要自然准确且无 unsupported claim | `G11_editorial_audit.md`、`G11_layout_audit.csv`、`G11_language_audit.csv` |
| G12 整改复检与最终交付 | 5 | 修改触发项已复检；最终PDF逐页检查；命名、匿名、附件、AI声明和清单合规；全部硬门通过 | 交付包在独立位置复核可打开、可运行、可定位，签发报告完整 | `G12_delivery_manifest.json`、`final_review_report.md` |

### C. 退回整改与复检

1. 每个不合格项登记：`finding_id、gate_id、severity、location、evidence、why_fail、required_fix、required_positive_evidence、owner、retest、status`。
2. 严重度使用：
   - `BLOCKER`：结果伪造、漏题、核心数值无依据、关键方案不可行、核心结论被泄漏或错误验证根本推翻。
   - `MAJOR`：影响关键结论可信度或可复现性的缺陷，以及缺少PASS正向证据。
   - `MINOR`：不改变核心结论的表达、格式或局部说明问题。
3. 整改必须同时交付“修改内容”和“证明修改有效的证据”；只改措辞不消除计算或验证缺陷。
4. 按`references/remediation_and_delivery.md`执行影响矩阵和复检，不得默认全门无需重查。
5. 所有MAJOR/BLOCKER关闭；MINOR若保留，必须不影响交付且记录理由，否则不得签发。
6. 每轮整改后重新计算分数，按“硬门优先、失分权重次之”选择下一项，自动修改工作副本并补齐正向证据，直到达到目标分或只剩需要新增数据/实验的NOT_VERIFIABLE项。每轮记录初始分、修改文件、新证据、复检门、最终分和分差，禁止只改状态提分。
7. G11自动排版和语言修改后，冻结数值、公式、单位和术语，必须重跑G06、G10、G11和G12，并对最终PDF逐页视觉复核。

### D. 机器校验与签发

完成人工验收后运行：

```bash
python scripts/gate_review.py verify --review <审查目录>
```

需要执行一轮有边界的自动排版/措辞整改时运行：

```bash
python scripts/auto_improve.py cycle --review <审查目录>
```

需要对DOCX工作副本统一A4页面、页边距、字体、题注、图片宽度，并在人工选定后转换数据三线表时运行：

```bash
python scripts/auto_improve.py docx --manuscript <原稿.docx> --out <工作副本.docx> --three-line-tables
```

脚本检查必交文件、登记完整性、占位符、门状态和总评规则，生成`gate_verdict.json`与`gate_verdict.md`及0—100分。自动整改只修改工作副本并生成证据，不得直接把语义门标为PASS；必须复检后才更新状态并重新计分。脚本只验证证据链和判定一致性，不替代数学复算、外部验证、最终PDF视觉复核或人工领域判断。

最终回复必须依次给出：

1. 初始分、最终分、总提升及总评状态，明确是否允许交付。
2. 各门状态、得分、失分和优点证据摘要。
3. 不合格项的位置、原因、自动整改内容、正向证据和复检结果。
4. 实际运行与未执行/不可验证事项，以及达到95分或停止自动修改的原因。
5. 最终稿、审查报告、评分记录、证据登记、日志和交付包路径。
