#!/usr/bin/env python3
"""Initialize and verify a two-sided mathematical-modeling manuscript review.

The verifier checks evidence completeness and verdict consistency. It does not
prove mathematical correctness; G06/G07 still require independent human/code checks.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from audit_manuscript import audit as structural_audit

GATES = [f"G{i:02d}" for i in range(13)]
STATUSES = {"PENDING", "NOT_VERIFIABLE", "FAIL", "REJECT", "PASS", "EXCELLENT", "N/A"}
GATE_WEIGHTS = {
    "G00": 3, "G01": 8, "G02": 6, "G03": 6, "G04": 6, "G05": 8,
    "G06": 12, "G07": 12, "G08": 7, "G09": 7, "G10": 6, "G11": 14, "G12": 5,
}
STATUS_RATIOS = {"EXCELLENT": 1.0, "PASS": 0.85, "FAIL": 0.4, "NOT_VERIFIABLE": 0.1, "REJECT": 0.0, "PENDING": 0.0}
PLACEHOLDERS = ("PENDING", "待填写", "待补充", "TODO", "TBD", "FIXME")

TEMPLATE_MAP = {
    "gate_decisions.csv": "02_registers/gate_decisions.csv",
    "claim_register.csv": "02_registers/claim_register.csv",
    "finding_register.csv": "02_registers/finding_register.csv",
    "task_coverage.csv": "01_gates/G01_task_coverage.csv",
    "data_lineage.csv": "01_gates/G02_data_lineage.csv",
    "model_spec.md": "01_gates/G03_model_spec.md",
    "unit_checks.csv": "01_gates/G03_unit_checks.csv",
    "model_baselines.csv": "01_gates/G04_model_baselines.csv",
    "run_manifest.json": "01_gates/G05_run_manifest.json",
    "recalculation.csv": "01_gates/G06_recalculation.csv",
    "validation_matrix.csv": "01_gates/G07_validation_matrix.csv",
    "constraint_residuals.csv": "01_gates/G08_constraint_residuals.csv",
    "optimality.md": "01_gates/G08_optimality.md",
    "sensitivity.csv": "01_gates/G09_sensitivity.csv",
    "result_register.csv": "01_gates/G10_result_register.csv",
    "editorial_audit.md": "01_gates/G11_editorial_audit.md",
    "layout_audit.csv": "01_gates/G11_layout_audit.csv",
    "language_audit.csv": "01_gates/G11_language_audit.csv",
    "improvement_log.csv": "02_registers/improvement_log.csv",
    "delivery_manifest.json": "04_delivery/G12_delivery_manifest.json",
    "final_review_report.md": "04_delivery/final_review_report.md",
}

ARTIFACTS = {gate: [] for gate in GATES}
ARTIFACTS.update({
    "G00": ["00_intake/G00_intake_manifest.json"],
    "G01": ["01_gates/G01_task_coverage.csv"],
    "G02": ["01_gates/G02_data_lineage.csv"],
    "G03": ["01_gates/G03_model_spec.md", "01_gates/G03_unit_checks.csv"],
    "G04": ["01_gates/G04_model_baselines.csv"],
    "G05": ["01_gates/G05_run_manifest.json"],
    "G06": ["01_gates/G06_recalculation.csv"],
    "G07": ["01_gates/G07_validation_matrix.csv"],
    "G08": ["01_gates/G08_constraint_residuals.csv", "01_gates/G08_optimality.md"],
    "G09": ["01_gates/G09_sensitivity.csv"],
    "G10": ["01_gates/G10_result_register.csv"],
    "G11": ["01_gates/G11_editorial_audit.md", "01_gates/G11_layout_audit.csv", "01_gates/G11_language_audit.csv"],
    "G12": ["04_delivery/G12_delivery_manifest.json", "04_delivery/final_review_report.md"],
})


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def blank_or_placeholder(path: Path) -> bool:
    if not path.exists() or not path.is_file() or path.stat().st_size == 0:
        return True
    text = path.read_text(encoding="utf-8-sig", errors="replace").strip()
    if not text:
        return True
    upper = text.upper()
    return any(marker in upper for marker in PLACEHOLDERS)


def extract_manuscript(source: Path, target: Path) -> dict:
    suffix = source.suffix.lower()
    if suffix in {".md", ".txt", ".markdown"}:
        shutil.copyfile(source, target)
        return {"format": suffix.lstrip("."), "locator": "line", "units": len(source.read_text(encoding="utf-8-sig").splitlines())}
    if suffix == ".pdf":
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("PDF extraction requires PyMuPDF (fitz)") from exc
        chunks = []
        with fitz.open(source) as doc:
            for index, page in enumerate(doc, start=1):
                chunks.append(f"\n\n[PDF_PAGE {index}]\n\n{page.get_text('text', sort=True)}")
            units = len(doc)
        target.write_text(f"# {source.stem}\n" + "".join(chunks), encoding="utf-8")
        return {"format": "pdf", "locator": "PDF_PAGE", "units": units}
    if suffix == ".docx":
        try:
            from docx import Document
        except ImportError as exc:
            raise RuntimeError("DOCX extraction requires python-docx") from exc
        doc = Document(source)
        chunks = []
        for index, paragraph in enumerate(doc.paragraphs, start=1):
            if paragraph.text.strip():
                chunks.append(f"[PARAGRAPH {index}] {paragraph.text}")
        for index, table in enumerate(doc.tables, start=1):
            chunks.append(f"\n[TABLE {index}]")
            for row in table.rows:
                chunks.append(" | ".join(cell.text for cell in row.cells))
        target.write_text("\n\n".join(chunks), encoding="utf-8")
        return {"format": "docx", "locator": "PARAGRAPH/TABLE", "units": len(doc.paragraphs)}
    raise ValueError("Supported manuscript formats: .md, .markdown, .txt, .pdf, .docx")


def init_review(args: argparse.Namespace) -> int:
    source = args.manuscript.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    out = args.out.expanduser().resolve()
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"Review directory is not empty: {out}")
    for directory in ["00_intake", "01_gates", "02_registers", "03_logs", "04_delivery/final"]:
        (out / directory).mkdir(parents=True, exist_ok=True)
    extracted = out / "00_intake" / "manuscript.md"
    extraction = extract_manuscript(source, extracted)
    templates = Path(__file__).resolve().parent.parent / "assets" / "templates"
    for template_name, relative in TEMPLATE_MAP.items():
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(templates / template_name, target)
    manifest = {
        "status": "PENDING",
        "original_manuscript": str(source),
        "original_sha256": sha256(source),
        "working_copy": "00_intake/manuscript.md",
        "working_copy_sha256": sha256(extracted),
        "extraction": extraction,
        "problem_statement": "PENDING",
        "submission_rules": "PENDING",
        "review_scope": "PENDING",
        "inputs": [{"path": str(source), "role": "manuscript"}],
        "missing_inputs": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (out / "00_intake" / "G00_intake_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"review_dir": str(out), "manuscript": str(extracted), "sha256": manifest["original_sha256"], "next": f"python scripts/gate_review.py verify --review \"{out}\""}, ensure_ascii=False, indent=2))
    return 0


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def missing_value(value: str | None) -> bool:
    if value is None or not value.strip():
        return True
    upper = value.strip().upper()
    return any(marker in upper for marker in PLACEHOLDERS)


def verify_review(args: argparse.Namespace) -> int:
    review = args.review.expanduser().resolve()
    issues = []

    def add(code: str, gate: str, severity: str, message: str) -> None:
        issues.append({"code": code, "gate_id": gate, "severity": severity, "message": message})

    decision_path = review / "02_registers" / "gate_decisions.csv"
    rows = read_csv(decision_path)
    decisions = {}
    for row in rows:
        gate = row.get("gate_id", "").strip()
        if gate in decisions:
            add("DUPLICATE_GATE", gate, "INCOMPLETE", "重复的门状态记录")
        decisions[gate] = row
    for gate in GATES:
        if gate not in decisions:
            add("MISSING_GATE", gate, "INCOMPLETE", "缺少门状态记录")
    for gate in sorted(set(decisions) - set(GATES)):
        add("UNKNOWN_GATE", gate, "INCOMPLETE", "未知闸门编号")

    for gate in GATES:
        row = decisions.get(gate)
        if not row:
            continue
        status = row.get("status", "").strip().upper()
        if status not in STATUSES:
            add("INVALID_STATUS", gate, "INCOMPLETE", f"非法状态：{status or '空'}")
            continue
        if status == "PENDING":
            add("PENDING", gate, "INCOMPLETE", "尚未完成验收")
            continue
        if status == "N/A":
            if missing_value(row.get("n_a_reason")):
                add("MISSING_NA_REASON", gate, "INCOMPLETE", "N/A缺少客观理由")
            continue
        if status in {"FAIL", "NOT_VERIFIABLE"}:
            add(status, gate, "RETURN", row.get("notes", "").strip() or "存在待整改或不可验证事项")
            continue
        if status == "REJECT":
            add("REJECT", gate, "REJECT", row.get("notes", "").strip() or "闸门拒绝交付")
            continue
        for field in ["reviewer", "evidence", "positive_evidence"]:
            if missing_value(row.get(field)):
                add("MISSING_POSITIVE_EVIDENCE", gate, "INCOMPLETE", f"{status}缺少{field}，不能只填状态")
        for relative in ARTIFACTS[gate]:
            artifact = review / relative
            if blank_or_placeholder(artifact):
                add("MISSING_ARTIFACT", gate, "INCOMPLETE", f"必交产物为空或含占位符：{relative}")

    run_manifest = review / "01_gates" / "G05_run_manifest.json"
    if decisions.get("G05", {}).get("status", "").upper() in {"PASS", "EXCELLENT"}:
        logs = [p for p in (review / "03_logs").glob("**/*") if p.is_file() and not blank_or_placeholder(p)] if (review / "03_logs").exists() else []
        runs = []
        try:
            runs = json.loads(run_manifest.read_text(encoding="utf-8-sig")).get("runs", [])
        except Exception:
            pass
        if not logs and not runs:
            add("MISSING_RUN_LOG", "G05", "INCOMPLETE", "PASS/EXCELLENT需要实际运行日志或runs记录")

    if decisions.get("G12", {}).get("status", "").upper() in {"PASS", "EXCELLENT"}:
        final_dir = review / "04_delivery" / "final"
        final_files = [p for p in final_dir.glob("**/*") if p.is_file()] if final_dir.exists() else []
        if not final_files:
            add("MISSING_FINAL_FILES", "G12", "INCOMPLETE", "最终交付目录没有文件")

    finding_path = review / "02_registers" / "finding_register.csv"
    if not finding_path.exists():
        add("MISSING_FINDING_REGISTER", "G00", "INCOMPLETE", "缺少问题登记表")
        findings = []
    else:
        findings = read_csv(finding_path)
    for finding in findings:
        status = finding.get("status", "").strip().upper()
        severity = finding.get("severity", "").strip().upper()
        if status != "CLOSED" and severity == "BLOCKER":
            add("OPEN_BLOCKER", finding.get("gate_id", ""), "REJECT", f"未关闭BLOCKER：{finding.get('finding_id', '')}")
        elif status != "CLOSED" and severity == "MAJOR":
            add("OPEN_MAJOR", finding.get("gate_id", ""), "RETURN", f"未关闭MAJOR：{finding.get('finding_id', '')}")

    manuscript = review / "00_intake" / "manuscript.md"
    structural = {"status": "NOT_RUN", "failures": ["原稿不存在"], "warnings": []}
    if manuscript.exists():
        structural = structural_audit(manuscript.read_text(encoding="utf-8-sig"))
    structural_path = review / "01_gates" / "G11_structural_audit.json"
    structural_path.write_text(json.dumps(structural, ensure_ascii=False, indent=2), encoding="utf-8")
    if decisions.get("G11", {}).get("status", "").upper() in {"PASS", "EXCELLENT"} and structural["status"] == "FAIL":
        add("STRUCTURAL_FAIL", "G11", "RETURN", "G11判通过，但结构审计为FAIL：" + "；".join(structural.get("failures", [])))

    earned_weight = 0.0
    applicable_weight = 0.0
    gate_scores = {}
    for gate in GATES:
        status = decisions.get(gate, {}).get("status", "PENDING").upper()
        if status == "N/A":
            gate_scores[gate] = {"weight": GATE_WEIGHTS[gate], "ratio": None, "earned": None, "lost": None}
            continue
        ratio = STATUS_RATIOS.get(status, 0.0)
        earned = GATE_WEIGHTS[gate] * ratio
        lost = GATE_WEIGHTS[gate] * (1.0 - ratio)
        earned_weight += earned
        applicable_weight += GATE_WEIGHTS[gate]
        gate_scores[gate] = {"weight": GATE_WEIGHTS[gate], "ratio": ratio, "earned": round(earned, 4), "lost": round(lost, 4)}
    score = round(100 * earned_weight / applicable_weight, 2) if applicable_weight else 0.0
    if score < 60:
        score_band = "INSUFFICIENT"
    elif score < 70:
        score_band = "WEAK"
    elif score < 85:
        score_band = "REVISION_REQUIRED"
    elif score < 95:
        score_band = "QUALIFIED_RANGE"
    else:
        score_band = "EXCELLENT_RANGE"

    severities = {issue["severity"] for issue in issues}
    if "INCOMPLETE" in severities:
        verdict = "INCOMPLETE"
    elif "REJECT" in severities:
        verdict = "REJECT"
    elif "RETURN" in severities:
        verdict = "RETURN_FOR_REVISION"
    else:
        core_excellent = all(decisions[gate]["status"].upper() == "EXCELLENT" for gate in ["G06", "G07"])
        extra_excellent = sum(decisions[gate]["status"].upper() == "EXCELLENT" for gate in ["G04", "G05", "G08", "G09", "G10"])
        verdict = "DISTINCTION" if score >= 95 and core_excellent and extra_excellent >= 3 else "ACCEPT"

    report = {
        "verdict": verdict,
        "allow_delivery": verdict in {"ACCEPT", "DISTINCTION"},
        "score": score,
        "score_band": score_band,
        "applicable_weight": applicable_weight,
        "gate_scores": gate_scores,
        "review_dir": str(review),
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "gate_decisions": {gate: decisions.get(gate, {}).get("status", "MISSING") for gate in GATES},
        "structural_audit": {"status": structural["status"], "failures": structural.get("failures", []), "warnings": structural.get("warnings", [])},
        "issues": issues,
        "rule": "INCOMPLETE > REJECT > RETURN_FOR_REVISION > DISTINCTION/ACCEPT；DISTINCTION要求score>=95、G06/G07 EXCELLENT且指定五门中至少三门EXCELLENT。",
    }
    (review / "gate_verdict.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# 论文验收判定", "", f"- 总评：**{verdict}**", f"- 允许交付：**{'是' if report['allow_delivery'] else '否'}**",
        f"- 最终得分：**{score:.2f}/100**（{score_band}）", "- 说明：分数不覆盖硬门失败；存在未决问题时仍不得交付。", "",
        "## 逐门状态与分值", "", "| 闸门 | 状态 | 权重 | 得分 | 失分 |", "|---|---|---:|---:|---:|",
    ]
    for gate in GATES:
        item = gate_scores[gate]
        lines.append(f"| {gate} | {report['gate_decisions'][gate]} | {item['weight']} | {item['earned'] if item['earned'] is not None else 'N/A'} | {item['lost'] if item['lost'] is not None else 'N/A'} |")
    lines.extend(["", f"## 结构审计：{structural['status']}", "", "## 未决问题", ""])
    if issues:
        lines.extend(f"- **{i['severity']} / {i['gate_id']} / {i['code']}**：{i['message']}" for i in issues)
    else:
        lines.append("- 无")
    lines.extend(["", "> 机器判定只检查证据完整性与规则一致性，不替代数学复算和领域验证。", ""])
    (review / "gate_verdict.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["allow_delivery"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Create a non-destructive review workspace")
    init.add_argument("--manuscript", type=Path, required=True)
    init.add_argument("--out", type=Path, required=True)
    init.set_defaults(func=init_review)
    verify = sub.add_parser("verify", help="Verify evidence and derive the overall verdict")
    verify.add_argument("--review", type=Path, required=True)
    verify.set_defaults(func=verify_review)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(json.dumps({"error": str(exc), "type": type(exc).__name__}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)
