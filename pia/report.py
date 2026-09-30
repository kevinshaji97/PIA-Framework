"""Terminal rendering of assessments."""

import textwrap

import click

from .analysis import Assessment

GRADE_COLOURS = {"Strong": "green", "Adequate": "cyan", "Weak": "yellow", "Poor": "red"}


def _points_colour(points: float, max_points: float) -> str:
    ratio = points / max_points if max_points else 0
    return "green" if ratio >= 0.75 else "yellow" if ratio >= 0.4 else "red"


def _wrap(text: str, indent: str, first: str | None = None) -> str:
    return textwrap.fill(text, width=96, initial_indent=first or indent, subsequent_indent=indent)


def render(a: Assessment) -> str:
    colour = GRADE_COLOURS.get(a.grade, "white")
    out = [
        "",
        click.style(f"Privacy Impact Assessment: {a.dependency} {a.version}", bold=True),
        f"  Policy:   {a.policy_url}",
        f"  Owner:    {a.policy_owner}" + (f" (updated {a.policy_last_updated})" if a.policy_last_updated else ""),
        f"  Analysed: {a.provider} / {a.model} at {a.created_at}",
        "",
        "  PIA score: " + click.style(f"{a.score:g} / {a.max_score:g}  ({a.grade})", fg=colour, bold=True)
        + "   10 = most privacy-protective",
    ]
    if not a.applies_to_dependency:
        out.append(click.style("  ! This policy may not cover the dependency itself; the score may not be meaningful.",
                               fg="yellow"))
    if a.summary:
        out += ["", _wrap(a.summary, "  ")]
    if a.data_collected:
        out += ["", "  Personal data collected:", _wrap(", ".join(a.data_collected), "    ")]

    out += ["", click.style("  Breakdown", bold=True)]
    for c in a.criteria:
        pts = click.style(f"{f'{c.points:g}/{c.max_points:g}':>8}", fg=_points_colour(c.points, c.max_points))
        out.append(f"  {pts}  {c.title:<24} {c.rating}")
        if c.rationale:
            out.append(_wrap(c.rationale, "            "))
        if c.evidence:
            mark = "" if c.evidence_verified else click.style(" [unverified]", fg="yellow")
            out.append(_wrap(f'"{c.evidence}"', "            ") + mark)

    if a.warnings:
        out += ["", click.style("  Warnings", fg="yellow", bold=True)]
        out += [_wrap(w, "    ", first="  - ") for w in a.warnings]
    out.append("")
    return "\n".join(out)
