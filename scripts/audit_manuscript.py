#!/usr/bin/env python3
"""Rule-based preflight audit for a Chinese mathematical-modeling Markdown manuscript.

This checks completeness and cross-reference signals only; it does not prove that
models, derivations, computations, or conclusions are mathematically correct.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CHECKS = {
    "abstract": ("摘要/Abstract", r"(?m)^(?:#{1,6}\s*)?(?:摘要|abstract|summary(?:\s*sheet)?)\s*$"),
    "problem_analysis": ("问题重述/问题分析", r"问题重述|问题分析|问题背景|problem restatement|problem analysis|problem background|introduction"),
    "assumptions": ("模型假设", r"模型假设|基本假设|假设说明|model assumptions?|basic assumptions?|assumptions?"),
    "symbols": ("符号说明", r"符号说明|符号表|记号说明|symbol description|symbols?|notation|nomenclature"),
    "model_construction": ("模型建立/构建", r"模型.{0,4}(建立|构建)|建立.{0,6}模型|构建.{0,6}模型|model construction|establishment of .{0,30}model|modeling|models?"),
    "solution": ("模型求解/算法", r"模型求解|求解算法|算法步骤|求解过程|模型计算|model solution|solving|solution steps|algorithm|computational"),
    "validation": ("检验/验证/敏感性", r"模型检验|模型验证|结果检验|误差分析|敏感性分析|灵敏度分析|鲁棒性分析|稳健性分析|model validation|model verification|model testing|error analysis|sensitivity analysis|robustness analysis|validation"),
    "conclusions": ("结论/评价", r"结论|模型评价|优缺点|模型展望|conclusions?|model evaluation|strengths?|weaknesses?|limitations?"),
    "references": ("参考文献", r"参考文献|references|bibliography"),
    "appendix": ("附录/代码", r"附录|源代码|代码清单|appendix|source code"),
}

PLACEHOLDER_PATTERN = re.compile(r"TODO|TBD|FIXME|XXX+|待补充|待完善|此处省略|待填写|插入图|插入表|\?\?+", re.I)


def line_number(text: str, position: int) -> int:
    return text.count("\n", 0, position) + 1


def extract_abstract(text: str) -> str:
    match = re.search(
        r"(?ims)^(?:#{1,6}\s*)?(?:摘要|abstract|summary(?:\s*sheet)?)\s*$\n(.*?)(?=^#{1,6}\s|^关键词|^关键字|^key\s*words?\b|\Z)",
        text,
    )
    return match.group(1).strip() if match else ""


def audit(text: str) -> dict:
    sections = []
    for key, (label, pattern) in CHECKS.items():
        match = re.search(pattern, text, flags=re.I)
        sections.append({
            "id": key,
            "label": label,
            "found": bool(match),
            "line": line_number(text, match.start()) if match else None,
        })

    placeholders = [
        {"line": line_number(text, match.start()), "text": match.group(0)}
        for match in PLACEHOLDER_PATTERN.finditer(text)
    ]
    abstract = extract_abstract(text)
    abstract_for_numbers = re.sub(r"\b(?:problem|question|q)\s*\d+\b|\b(?:19|20)\d{2}\b", "", abstract, flags=re.I)
    numeric_fragments = re.findall(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?\s*(?:%|％|万|亿|元|个|次|种|天|小时|分钟|秒|米|千米|公里|kg|km|m)?", abstract_for_numbers, flags=re.I)
    abstract_sentences = [s.strip() for s in re.split(r"[。！？!?]+|(?<!\d)\.(?=\s|$)|\n+", abstract) if s.strip()]

    figure_caption_lines = []
    table_caption_lines = []
    for number, line in enumerate(text.splitlines(), start=1):
        if re.search(r"(?:^|\s)(?:图\s*\d+|fig(?:ure)?\.?\s*\d+)", line, flags=re.I):
            figure_caption_lines.append(number)
        if re.search(r"(?:^|\s)(?:表\s*\d+|table\s*\d+)", line, flags=re.I):
            table_caption_lines.append(number)

    reference_marks = set(re.findall(r"\[(\d+(?:\s*[-,，]\s*\d+)*)\]", text))
    unresolved_reference_style = len(reference_marks) == 0 and bool(re.search(r"参考文献|references|bibliography", text, flags=re.I))

    failures = []
    warnings = []
    found = {item["id"]: item["found"] for item in sections}
    for required in ["abstract", "assumptions", "model_construction", "solution", "validation", "conclusions", "references"]:
        if not found[required]:
            failures.append(f"缺少必要信号：{dict((x['id'], x['label']) for x in sections)[required]}")
    if placeholders:
        failures.append(f"发现 {len(placeholders)} 个占位符/未完成标记")
    if abstract and len(numeric_fragments) < 2:
        warnings.append("摘要中的定量结果信号少于 2 个；逐问核查是否给出关键数值、单位和结论")
    if abstract and len(abstract_sentences) < 3:
        warnings.append("摘要过短或句子过少；核查是否覆盖所有子问题")
    if not found["appendix"]:
        warnings.append("未见附录/代码信号；若规则或篇幅不允许附录，应至少在结果登记中保留复现路径")
    if unresolved_reference_style:
        warnings.append("有参考文献章节但未检出 [n] 型正文引文；若采用其他引用格式请人工核查")
    if not figure_caption_lines:
        warnings.append("未检出图号；纯解析题可忽略，否则核查关键模型与结果是否可视化")
    if not table_caption_lines:
        warnings.append("未检出表号；核查符号、参数或结果是否需要表格化")

    return {
        "status": "FAIL" if failures else "PASS_WITH_WARNINGS" if warnings else "PASS",
        "scope": "结构、占位符与交叉信号审计；不证明数学或数值正确性",
        "characters": len(text),
        "sections": sections,
        "abstract": {
            "characters": len(abstract),
            "sentences": len(abstract_sentences),
            "numeric_fragments": numeric_fragments,
        },
        "figure_caption_lines": figure_caption_lines,
        "table_caption_lines": table_caption_lines,
        "placeholders": placeholders,
        "failures": failures,
        "warnings": warnings,
    }


def to_markdown(report: dict, source: Path) -> str:
    lines = [
        "# 论文提交前规则审计",
        "",
        f"- 文件：`{source}`",
        f"- 结论：**{report['status']}**",
        f"- 范围：{report['scope']}",
        "",
        "## 必需结构",
        "",
        "| 项目 | 状态 | 行号 |",
        "|---|---|---:|",
    ]
    for item in report["sections"]:
        lines.append(f"| {item['label']} | {'检出' if item['found'] else '未见'} | {item['line'] or '—'} |")
    lines.extend(["", "## 阻断项", ""])
    lines.extend(f"- {item}" for item in report["failures"]) if report["failures"] else lines.append("- 无")
    lines.extend(["", "## 人工复核项", ""])
    lines.extend(f"- {item}" for item in report["warnings"]) if report["warnings"] else lines.append("- 无")
    lines.extend([
        "",
        "## 摘要信号",
        "",
        f"- 字符数：{report['abstract']['characters']}",
        f"- 句子数：{report['abstract']['sentences']}",
        f"- 数字/单位片段：{', '.join(report['abstract']['numeric_fragments']) or '未检出'}",
        "",
        "> 通过规则审计后仍须完成任务—模型—结果—检验闭环和数值复算。",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manuscript", type=Path, help="UTF-8 Markdown or plain-text manuscript")
    parser.add_argument("--json", type=Path, dest="json_path", help="Optional JSON report path")
    parser.add_argument("--markdown", type=Path, dest="markdown_path", help="Optional Markdown report path")
    args = parser.parse_args()
    text = args.manuscript.read_text(encoding="utf-8-sig")
    report = audit(text)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(rendered, encoding="utf-8")
    if args.markdown_path:
        args.markdown_path.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_path.write_text(to_markdown(report, args.manuscript), encoding="utf-8")
    print(rendered)
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
