"""PRISMA Flow Diagram Generator for MedPaperHunter.

Generates PRISMA (Preferred Reporting Items for Systematic Reviews and Meta-Analyses)
flow diagrams based on literature screening results.
"""

from __future__ import annotations

import logging
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)


class PRISMAGenerator:
    """Generate PRISMA flow diagrams as PDF."""

    def __init__(self, width: float = A4[0], height: float = A4[1]) -> None:
        self.width = width
        self.height = height
        self.c: canvas.Canvas | None = None
        self.y_pos = height - 2 * cm

    def generate(
        self,
        output_path: str,
        database_counts: dict[str, int],
        duplicates_removed: int,
        screened_count: int,
        excluded_count: int,
        excluded_reasons: dict[str, int],
        full_text_assessed: int,
        full_text_excluded: int,
        included_count: int,
        meta_analysis_count: int = 0,
    ) -> None:
        """Generate PRISMA flow diagram PDF.

        Args:
            output_path: Output PDF file path.
            database_counts: Dict of database names to record counts.
            duplicates_removed: Number of duplicate records removed.
            screened_count: Number of records screened.
            excluded_count: Number excluded at title/abstract screening.
            excluded_reasons: Dict of exclusion reasons to counts.
            full_text_assessed: Number of full-text articles assessed.
            full_text_excluded: Number excluded at full-text assessment.
            included_count: Final number of studies included.
            meta_analysis_count: Number of studies in meta-analysis.
        """
        self.c = canvas.Canvas(output_path, pagesize=A4)
        self.y_pos = self.height - 2 * cm

        self._draw_title()
        self._draw_identification(database_counts, duplicates_removed)
        self._draw_screening(
            screened_count, excluded_count, excluded_reasons
        )
        self._draw_included(
            full_text_assessed,
            full_text_excluded,
            included_count,
            meta_analysis_count,
        )

        self.c.save()
        logger.info("PRISMA flow diagram saved to: %s", output_path)

    def _draw_title(self) -> None:
        """Draw PRISMA diagram title."""
        self.c.setFont("Helvetica-Bold", 16)
        self.c.drawCentredString(
            self.width / 2, self.y_pos, "PRISMA Flow Diagram"
        )
        self.y_pos -= 0.8 * cm

        self.c.setFont("Helvetica", 10)
        self.c.drawCentredString(
            self.width / 2,
            self.y_pos,
            "Systematic Review and Meta-Analysis Literature Screening",
        )
        self.y_pos -= 1.5 * cm

    def _draw_identification(
        self, database_counts: dict[str, int], duplicates_removed: int
    ) -> None:
        """Draw Identification phase."""
        total_records = sum(database_counts.values())

        box_width = 5 * cm
        box_height = 1.2 * cm
        x_left = 2 * cm

        self.c.setFont("Helvetica-Bold", 11)
        self.c.drawString(x_left, self.y_pos, "Identification")
        self.y_pos -= 0.5 * cm

        self.c.setStrokeColor(colors.orange)
        self.c.rect(x_left, self.y_pos - box_height, box_width, box_height)
        self.c.setFont("Helvetica", 9)
        self.c.drawString(
            x_left + 0.2 * cm,
            self.y_pos - 0.3 * cm,
            f"Records identified: {total_records}",
        )
        self.y_pos -= box_height + 0.3 * cm

        self.c.setFont("Helvetica", 8)
        for db, count in database_counts.items():
            self.c.drawString(
                x_left + 0.3 * cm, self.y_pos, f"{db}: {count}"
            )
            self.y_pos -= 0.35 * cm

        self.y_pos -= 0.3 * cm
        self.c.setStrokeColor(colors.black)
        self.c.line(x_left, self.y_pos, x_left + box_width, self.y_pos)
        self.y_pos -= 0.3 * cm

        box_height2 = 0.9 * cm
        self.c.rect(x_left, self.y_pos - box_height2, box_width, box_height2)
        self.c.setFont("Helvetica", 9)
        self.c.drawString(
            x_left + 0.2 * cm,
            self.y_pos - 0.3 * cm,
            f"Duplicates removed: {duplicates_removed}",
        )
        self.y_pos -= box_height2 + 0.3 * cm

        self.c.line(x_left, self.y_pos, x_left + box_width, self.y_pos)
        self.y_pos -= 0.3 * cm

        box_height3 = 0.9 * cm
        records_after = sum(database_counts.values()) - duplicates_removed
        self.c.setFillColor(colors.lightyellow)
        self.c.rect(
            x_left, self.y_pos - box_height3, box_width, box_height3, fill=1
        )
        self.c.setFillColor(colors.black)
        self.c.setFont("Helvetica-Bold", 9)
        self.c.drawString(
            x_left + 0.2 * cm,
            self.y_pos - 0.3 * cm,
            f"Records after dedup: {records_after}",
        )
        self.y_pos -= box_height3 + 0.3 * cm

    def _draw_screening(
        self, screened_count: int, excluded_count: int, excluded_reasons: dict[str, int]
    ) -> None:
        """Draw Screening phase."""
        box_width = 5 * cm
        x_right = self.width - 7 * cm

        self.c.setFont("Helvetica-Bold", 11)
        self.c.drawString(x_right, self.y_pos, "Screening")
        self.y_pos -= 0.5 * cm

        box_height = 1.2 * cm
        self.c.setStrokeColor(colors.green)
        self.c.rect(x_right, self.y_pos - box_height, box_width, box_height)
        self.c.setFont("Helvetica", 9)
        self.c.drawString(
            x_right + 0.2 * cm,
            self.y_pos - 0.3 * cm,
            f"Records screened: {screened_count}",
        )
        self.y_pos -= box_height + 0.3 * cm

        self.c.setFont("Helvetica", 8)
        for reason, count in excluded_reasons.items():
            self.c.drawString(
                x_right + 0.3 * cm, self.y_pos, f"{reason}: {count}"
            )
            self.y_pos -= 0.35 * cm

        self.y_pos -= 0.3 * cm
        self.c.setStrokeColor(colors.black)
        self.c.line(x_right, self.y_pos, x_right + box_width, self.y_pos)
        self.y_pos -= 0.3 * cm

        box_height2 = 0.9 * cm
        self.c.setFillColor(colors.lightyellow)
        self.c.rect(
            x_right, self.y_pos - box_height2, box_width, box_height2, fill=1
        )
        self.c.setFillColor(colors.black)
        self.c.setFont("Helvetica-Bold", 9)
        self.c.drawString(
            x_right + 0.2 * cm,
            self.y_pos - 0.3 * cm,
            f"Excluded: {excluded_count}",
        )
        self.y_pos -= box_height2 + 0.5 * cm

    def _draw_included(
        self,
        full_text_assessed: int,
        full_text_excluded: int,
        included_count: int,
        meta_analysis_count: int,
    ) -> None:
        """Draw Included phase."""
        box_width = 5 * cm
        x_final = self.width / 2 - box_width / 2
        self.y_pos = 15 * cm

        box_height = 1.5 * cm
        self.c.setStrokeColor(colors.blue)
        self.c.rect(x_final, self.y_pos - box_height, box_width, box_height)
        self.c.setFont("Helvetica-Bold", 10)
        self.c.drawCentredString(
            self.width / 2,
            self.y_pos - 0.5 * cm,
            f"Studies included: {included_count}",
        )
        self.y_pos -= box_height + 0.5 * cm

        if meta_analysis_count > 0:
            self.c.setFont("Helvetica", 8)
            self.c.drawCentredString(
                self.width / 2,
                self.y_pos,
                f"(Meta-analysis: {meta_analysis_count})",
            )

    def generate_svg(
        self,
        database_counts: dict[str, int],
        duplicates_removed: int,
        screened_count: int,
        excluded_count: int,
        excluded_reasons: dict[str, int],
        full_text_assessed: int,
        full_text_excluded: int,
        included_count: int,
        meta_analysis_count: int = 0,
    ) -> str:
        """Generate PRISMA diagram as SVG string.

        Args:
            Same as generate() method.

        Returns:
            SVG markup string.
        """
        total_records = sum(database_counts.values())
        records_after = total_records - duplicates_removed

        svg = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600">',
            '<style>',
            '.box { fill: white; stroke: #333; stroke-width: 2px; }',
            '.highlight { fill: #fffacd; }',
            '.header { font-size: 14px; font-weight: bold; }',
            '.text { font-size: 11px; }',
            '.count { font-size: 12px; font-weight: bold; }',
            '</style>',
            '<text x="400" y="30" text-anchor="middle" class="header">PRISMA Flow Diagram</text>',
            '<text x="400" y="50" text-anchor="middle" class="text">Systematic Review Literature Screening</text>',
        ]

        svg.append('<g id="identification" transform="translate(20, 70)">')
        svg.append('<text x="0" y="0" class="header">Identification</text>')
        svg.append(f'<rect x="0" y="10" width="200" height="60" class="box"/>')
        svg.append(f'<text x="10" y="35" class="count">Records identified: {total_records}</text>')

        y = 80
        for db, count in database_counts.items():
            svg.append(f'<text x="15" y="{y}" class="text">{db}: {count}</text>')
            y += 15

        svg.append(f'<line x1="0" y1="{y}" x2="200" y2="{y}" stroke="#333"/>')
        y += 20

        svg.append(f'<rect x="0" y="{y}" width="200" height="40" class="box"/>')
        svg.append(f'<text x="10" y="{y+25}" class="count">Duplicates removed: {duplicates_removed}</text>')
        y += 50

        svg.append(f'<line x1="0" y1="{y}" x2="200" y2="{y}" stroke="#333"/>')
        y += 20

        svg.append(f'<rect x="0" y="{y}" width="200" height="40" class="box highlight"/>')
        svg.append(f'<text x="10" y="{y+25}" class="count">After deduplication: {records_after}</text>')
        svg.append('</g>')

        svg.append('<g id="screening" transform="translate(580, 70)">')
        svg.append('<text x="0" y="0" class="header">Screening</text>')
        svg.append(f'<rect x="0" y="10" width="200" height="60" class="box"/>')
        svg.append(f'<text x="10" y="35" class="count">Records screened: {screened_count}</text>')

        y = 80
        for reason, count in excluded_reasons.items():
            svg.append(f'<text x="15" y="{y}" class="text">{reason}: {count}</text>')
            y += 15

        svg.append(f'<line x1="0" y1="{y}" x2="200" y2="{y}" stroke="#333"/>')
        y += 20

        svg.append(f'<rect x="0" y="{y}" width="200" height="40" class="box highlight"/>')
        svg.append(f'<text x="10" y="{y+25}" class="count">Excluded: {excluded_count}</text>')
        svg.append('</g>')

        svg.append('<g id="included" transform="translate(300, 450)">')
        svg.append('<rect x="0" y="0" width="200" height="60" class="box"/>')
        svg.append(f'<text x="100" y="25" text-anchor="middle" class="count">Studies included: {included_count}</text>')
        svg.append('</g>')

        svg.append('</svg>')
        return '\n'.join(svg)


def generate_prisma_data(screened_articles: list[dict[str, Any]]) -> dict[str, Any]:
    """Generate PRISMA statistics from screened articles.

    Args:
        screened_articles: List of article dicts with screening results.

    Returns:
        Dict containing PRISMA statistics.
    """
    included = [a for a in screened_articles if a.get("screening") == "included"]
    excluded = [a for a in screened_articles if a.get("screening") == "excluded"]

    reasons: dict[str, int] = {}
    for article in excluded:
        reason = article.get("screening_reason", "Unknown reason")
        reason_short = reason[:50] if reason else "No reason provided"
        reasons[reason_short] = reasons.get(reason_short, 0) + 1

    return {
        "total_screened": len(screened_articles),
        "included_count": len(included),
        "excluded_count": len(excluded),
        "exclusion_reasons": reasons,
        "databases_used": list(set(a.get("source", "unknown") for a in screened_articles)),
    }
