from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from AI.domain.analysis.blockers import Blocker
from AI.domain.analysis.models import AnalysisManifest

MAX_USER_REPORT_CHARS = 250


def ensure_complete_summary(summary: str, max_chars: int = MAX_USER_REPORT_CHARS) -> str:
    """Ensure the LLM summary is <= max_chars and ends on a complete sentence."""
    text = " ".join(summary.strip().split())
    if len(text) <= max_chars:
        return text

    window = text[:max_chars]
    for punct in (". ", "! ", "? "):
        idx = window.rfind(punct)
        if idx > 40:
            return window[: idx + 1].strip()
    if window.endswith((".", "!", "?")):
        return window
    last_space = window[: max_chars - 1].rfind(" ")
    if last_space > 40:
        return window[:last_space].rstrip(",;:-") + "."
    return window[: max_chars - 1] + "."


def generate_user_pdf_report(
    manifest: AnalysisManifest,
    output_path: str | Path,
    *,
    final_status: str = "succeeded",
    blockers: tuple[Blocker, ...] = (),
) -> Path:
    """Render a clean, human-readable PDF summary report for the user."""
    out = Path(output_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(out),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"CloudPilot Analysis Report - {manifest.repo.full_name}",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CPTitle",
        parent=styles["Heading1"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "CPSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#475569"),
        spaceAfter=12,
    )
    section_style = ParagraphStyle(
        "CPSection",
        parent=styles["Heading2"],
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#0F766E"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "CPBody",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#1E293B"),
    )
    summary_box_style = ParagraphStyle(
        "CPSummaryBox",
        parent=styles["Normal"],
        fontSize=10.5,
        leading=15,
        textColor=colors.HexColor("#0F172A"),
        backColor=colors.HexColor("#F0FDFA"),
        borderColor=colors.HexColor("#14B8A6"),
        borderWidth=1,
        borderPadding=8,
        spaceAfter=10,
    )

    story = []

    # Header
    story.append(Paragraph("CloudPilot — Repository Analysis Report", title_style))
    meta_line = (
        f"<b>Repository:</b> {escape(manifest.repo.full_name)} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Commit:</b> {escape(manifest.repo.commit_sha)} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Status:</b> {escape(final_status.upper())} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Topology:</b> {escape(manifest.topology)}"
    )
    story.append(Paragraph(meta_line, subtitle_style))

    # LLM Executive Summary (strictly <= 250 chars, complete sentence)
    summary_text = ensure_complete_summary(manifest.summary or "No summary provided.")
    story.append(
        Paragraph(
            f"AI Executive Summary ({len(summary_text)} / {MAX_USER_REPORT_CHARS} chars)",
            section_style,
        )
    )
    story.append(Paragraph(escape(summary_text), summary_box_style))

    # Detected Stack
    langs = ", ".join(lang.name for lang in manifest.languages) or "None"
    fws = ", ".join(manifest.frameworks) or "None"
    deps = ", ".join(d.name for d in manifest.dependencies[:10]) or "None"
    story.append(Paragraph("Technology Stack", section_style))
    stack_data = [
        [Paragraph("<b>Languages</b>", body_style), Paragraph(escape(langs), body_style)],
        [Paragraph("<b>Frameworks</b>", body_style), Paragraph(escape(fws), body_style)],
        [Paragraph("<b>Dependencies</b>", body_style), Paragraph(escape(deps), body_style)],
    ]
    stack_table = Table(stack_data, colWidths=[40 * mm, 134 * mm])
    stack_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F8FAFC")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(stack_table)

    # Components
    story.append(Paragraph(f"Detected Components ({len(manifest.components)})", section_style))
    for comp in manifest.components:
        env_summary = (
            ", ".join(
                f"{e.name} ({'secret' if e.is_secret else 'config'})" for e in comp.env_vars
            )
            or "None"
        )
        ev_summary = (
            "; ".join(
                f"{ev.field}: {ev.file}" + (f":{ev.lines[0]}-{ev.lines[1]}" if ev.lines else "")
                for ev in comp.evidence
            )
            or "None"
        )
        comp_rows = [
            [
                Paragraph("<b>Component</b>", body_style),
                Paragraph(
                    f"<b>{escape(comp.name)}</b> ({escape(comp.type.value)}, root: <code>{escape(comp.root_dir)}</code>)",
                    body_style,
                ),
            ],
            [
                Paragraph("<b>Language / Pkg Mgr</b>", body_style),
                Paragraph(
                    f"{escape(comp.language)} / {escape(comp.pkg_mgr or 'unknown')}",
                    body_style,
                ),
            ],
            [
                Paragraph("<b>Start Command</b>", body_style),
                Paragraph(escape(comp.start_cmd or "Not detected"), body_style),
            ],
            [
                Paragraph("<b>Port &amp; Health Path</b>", body_style),
                Paragraph(
                    f"Port: {escape(str(comp.port or 'unknown'))} &nbsp;|&nbsp; Health: {escape(comp.health_path or 'unknown')}",
                    body_style,
                ),
            ],
            [
                Paragraph("<b>Environment Vars</b>", body_style),
                Paragraph(escape(env_summary), body_style),
            ],
            [
                Paragraph("<b>Verified Evidence</b>", body_style),
                Paragraph(escape(ev_summary), body_style),
            ],
        ]
        comp_table = Table(comp_rows, colWidths=[40 * mm, 134 * mm])
        comp_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                    ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#F8FAFC")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("PADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(comp_table)
        story.append(Spacer(1, 6))

    # Open Questions or Blockers
    if manifest.open_questions:
        story.append(Paragraph("Open Questions for User", section_style))
        for q in manifest.open_questions:
            story.append(
                Paragraph(
                    f"• <b>[{escape(q.field_path)}]</b> {escape(q.question)} <i>({escape(q.reason)})</i>",
                    body_style,
                )
            )

    if blockers:
        story.append(Paragraph("Deployment Blockers", section_style))
        for b in blockers:
            story.append(Paragraph(f"• <b>{escape(b.value)}:</b> {escape(b.message)}", body_style))

    doc.build(story)
    return out
