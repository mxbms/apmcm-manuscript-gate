#!/usr/bin/env python3
"""Apply bounded layout/language improvements and log the evidence for re-review.

Semantic/model gates are never marked PASS by this script. It only changes a
working copy and produces evidence; the reviewer must rerun the affected gates.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

SAFE_REPLACEMENTS = [
    (re.compile(r"\bThis paper conducts a comprehensive and in-depth study of\b", re.I), "This study examines"),
    (re.compile(r"\bThis paper comprehensively and deeply analyzes\b", re.I), "This paper analyzes"),
    (re.compile(r"\bsuccessfully established\b", re.I), "established"),
    (re.compile(r"\bsuccessfully achieved\b", re.I), "achieved"),
    (re.compile(r"^\s*(?:In conclusion|Overall|Furthermore|Moreover)\s*,\s*", re.I), ""),
]
CAPTION_RE = re.compile(r"^(?:图\s*\d+|表\s*\d+|fig(?:ure)?\.?\s*\d+|table\s*\d+)", re.I)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def improve_markdown(source: Path, output: Path) -> dict:
    text = source.read_text(encoding="utf-8-sig")
    changes = []
    for index, (pattern, replacement) in enumerate(SAFE_REPLACEMENTS, start=1):
        # Apply replacements line-by-line to keep a precise audit trail.
        lines = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            revised = pattern.sub(replacement, line)
            if revised != line:
                changes.append({"location": f"line {line_number}", "issue_type": "bounded_language", "original": line, "revised": revised, "reason": "删除机械措辞，保留技术内容", "numbers_frozen": True, "terms_frozen": True, "retest_status": "RECHECK_REQUIRED"})
            lines.append(revised)
        text = "\n".join(lines)
    lines = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        revised = re.sub(r"^(Figure|Table)(\d+)", r"\1 \2", line, flags=re.I)
        revised = revised.rstrip()
        if revised != line:
            changes.append({"location": f"line {line_number}", "issue_type": "caption_spacing", "original": line, "revised": revised, "reason": "统一题注编号空格", "numbers_frozen": True, "terms_frozen": True, "retest_status": "RECHECK_REQUIRED"})
        lines.append(revised)
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    return changes


def improve_docx(source: Path, output: Path, three_line_tables: bool) -> dict:
    try:
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        from docx.shared import Mm, Pt
    except ImportError as exc:
        raise RuntimeError("DOCX layout improvement requires python-docx") from exc
    document = Document(source)
    changes = []
    for section_index, section in enumerate(document.sections, start=1):
        section.page_width, section.page_height = Mm(210), Mm(297)
        section.left_margin = section.right_margin = Mm(31.75)
        section.top_margin = section.bottom_margin = Mm(25.4)
        changes.append({"object": f"section {section_index}", "action": "A4; margins 31.75/25.4mm"})
    def format_run(run, size: float, bold: bool | None = None):
        run.font.name = "Times New Roman"
        run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "宋体")
        run.font.size = Pt(size)
        if bold is not None:
            run.bold = bold
    normal = document.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "宋体")
    normal.font.size = Pt(12)
    normal.paragraph_format.line_spacing = 1.25
    for index, paragraph in enumerate(document.paragraphs, start=1):
        text = paragraph.text.strip()
        style_name = paragraph.style.name if paragraph.style else ""
        if style_name.startswith("Heading 1"):
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in paragraph.runs:
                format_run(run, 14, True)
        elif style_name.startswith(("Heading 2", "Heading 3", "Heading 4")):
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            for run in paragraph.runs:
                format_run(run, 12, True)
        elif CAPTION_RE.match(text):
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.keep_with_next = text.lower().startswith(("table", "表"))
            if text.lower().startswith(("figure", "fig", "图")) and index > 1:
                document.paragraphs[index - 2].paragraph_format.keep_with_next = True
            for run in paragraph.runs:
                format_run(run, 10.5)
            changes.append({"object": f"paragraph {index}", "action": "caption 10.5pt centered"})
        else:
            for run in paragraph.runs:
                format_run(run, 12)
    for index, shape in enumerate(document.inline_shapes, start=1):
        if shape.width > Mm(140):
            ratio = Mm(140) / shape.width
            shape.width, shape.height = Mm(140), int(shape.height * ratio)
            changes.append({"object": f"inline_shape {index}", "action": "scale to 140mm width"})
    if three_line_tables:
        for table_index, table in enumerate(document.tables, start=1):
            table.alignment = 1
            table.autofit = True
            tbl_pr = table._tbl.tblPr
            for old in tbl_pr.findall(qn("w:tblBorders")):
                tbl_pr.remove(old)
            borders = OxmlElement("w:tblBorders")
            for edge in ["top", "insideH", "bottom"]:
                element = OxmlElement(f"w:{edge}")
                element.set(qn("w:val"), "single")
                element.set(qn("w:sz"), "6")
                element.set(qn("w:color"), "000000")
                borders.append(element)
            for edge in ["left", "right", "insideV"]:
                element = OxmlElement(f"w:{edge}")
                element.set(qn("w:val"), "nil")
                borders.append(element)
            tbl_pr.append(borders)
            if table.rows:
                tr_pr = table.rows[0]._tr.get_or_add_trPr()
                header = OxmlElement("w:tblHeader")
                header.set(qn("w:val"), "true")
                tr_pr.append(header)
                for cell in table.rows[0].cells:
                    for paragraph in cell.paragraphs:
                        for run in paragraph.runs:
                            run.bold = True
            changes.append({"object": f"table {table_index}", "action": "three-line borders; repeat header"})
    output.parent.mkdir(parents=True, exist_ok=True)
    document.save(output)
    return changes


def append_improvement_log(review: Path, before_score: float, after_score: float, action: str, changed: list[Path], evidence: list[Path]) -> None:
    path = review / "02_registers" / "improvement_log.csv"
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        if not exists:
            writer.writerow(["iteration", "before_score", "selected_finding", "action", "changed_files", "new_evidence", "retest_gates", "after_score", "delta", "remaining_blockers", "remaining_not_verifiable", "decision"])
        writer.writerow([1, before_score, "G11 bounded auto improvement", action, ";".join(map(str, changed)), ";".join(map(str, evidence)), "G06/G10/G11/G12", after_score, round(after_score - before_score, 2), "see gate_verdict.json", "see gate_verdict.json", "RECHECK_REQUIRED"])


def cycle(args: argparse.Namespace) -> int:
    review = args.review.resolve()
    gate_script = Path(__file__).resolve().parent / "gate_review.py"
    subprocess.run([sys.executable, str(gate_script), "verify", "--review", str(review)], capture_output=True, text=True)
    verdict_path = review / "gate_verdict.json"
    before = json.loads(verdict_path.read_text(encoding="utf-8"))["score"] if verdict_path.exists() else 0.0
    source = review / "00_intake" / "manuscript.md"
    changes = improve_markdown(source, source)
    language_path = review / "01_gates" / "G11_language_audit.csv"
    with language_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["location", "issue_type", "original", "revised", "reason", "numbers_frozen", "terms_frozen", "retest_status"])
        writer.writeheader()
        writer.writerows(changes)
    if not changes:
        language_path.write_text("location,issue_type,original,revised,reason,numbers_frozen,terms_frozen,retest_status\nno_change,bounded_language,no_change,no_change,未发现安全自动替换项,True,True,RECHECK_REQUIRED\n", encoding="utf-8-sig")
    layout_path = review / "01_gates" / "G11_layout_audit.csv"
    captions = []
    for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
        if CAPTION_RE.match(line.strip()):
            captions.append({"object_id": f"line_{line_number}", "kind": "caption", "page": f"line {line_number}", "caption": line.strip(), "page_size": "see final PDF", "font_size": "see final PDF", "width_mm": "see final PDF", "height_mm": "see final PDF", "position": "normalized", "border_style": "manual review", "first_reference": "manual review", "argument_role": "manual review", "readability": "final PDF visual recheck required", "action": "recheck"})
    with layout_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["object_id", "kind", "page", "caption", "page_size", "font_size", "width_mm", "height_mm", "position", "border_style", "first_reference", "argument_role", "readability", "action"])
        writer.writeheader()
        writer.writerows(captions or [{"object_id": "no_caption", "kind": "layout", "page": "all", "caption": "未检出题注", "page_size": "manual", "font_size": "manual", "width_mm": "manual", "height_mm": "manual", "position": "manual", "border_style": "manual", "first_reference": "manual", "argument_role": "manual", "readability": "manual", "action": "recheck"}])
    subprocess.run([sys.executable, str(gate_script), "verify", "--review", str(review)], capture_output=True, text=True)
    after = json.loads(verdict_path.read_text(encoding="utf-8"))["score"]
    append_improvement_log(review, before, after, "bounded Markdown language/caption normalization", [source], [language_path, layout_path])
    print(json.dumps({"before_score": before, "after_score": after, "changes": len(changes), "decision": "RECHECK_REQUIRED", "note": "分数只有在复核证据并更新门状态后才变化；不得直接把本步当PASS。", "next": f"python scripts/gate_review.py verify --review \"{review}\""}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    cycle_parser = sub.add_parser("cycle", help="Run one bounded improvement cycle in a review workspace")
    cycle_parser.add_argument("--review", type=Path, required=True)
    cycle_parser.set_defaults(func=cycle)
    docx_parser = sub.add_parser("docx", help="Apply bounded layout changes to a DOCX working copy")
    docx_parser.add_argument("--manuscript", type=Path, required=True)
    docx_parser.add_argument("--out", type=Path, required=True)
    docx_parser.add_argument("--three-line-tables", action="store_true")
    def run_docx(args):
        source, output = args.manuscript.resolve(), args.out.resolve()
        if source == output:
            raise ValueError("Output must differ from the original manuscript")
        changes = improve_docx(source, output, args.three_line_tables)
        report = {"source": str(source), "source_sha256": sha256(source), "output": str(output), "output_sha256": sha256(output), "changes": changes, "retest": "G06/G10/G11/G12; final PDF visual review"}
        report_path = output.with_suffix(output.suffix + ".layout_changes.json")
        write_json(report_path, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    docx_parser.set_defaults(func=run_docx)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(json.dumps({"error": str(exc), "type": type(exc).__name__}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)
