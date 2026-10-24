from __future__ import annotations

import re

from app.schemas import ArchitectureAnalysis


def _safe_id(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_]", "_", value)

    if not value:
        value = "node"

    if value[0].isdigit():
        value = f"n_{value}"

    return value[:80]


def _escape_label(value: str) -> str:
    return (
        value
        .replace('"', "'")
        .replace("\n", " ")
        .replace("|", "/")
        [:120]
    )


def architecture_to_mermaid(
    analysis: ArchitectureAnalysis,
) -> str:

    lines = ["flowchart LR"]

    id_map: dict[str, str] = {}

    for i, component in enumerate(analysis.components):

        node_id = _safe_id(
            component.id or f"component_{i}"
        )

        if node_id in id_map.values():
            node_id = f"{node_id}_{i}"

        id_map[component.id] = node_id

        name = _escape_label(component.name)
        technology = _escape_label(
            component.technology or ""
        )

        if technology:
            label = f"{name}<br/>{technology}"
        else:
            label = name

        lines.append(
            f'    {node_id}["{label}"]'
        )

    for connection in analysis.connections:

        source = id_map.get(connection.source)
        target = id_map.get(connection.target)

        if not source or not target:
            continue

        protocol = _escape_label(
            connection.protocol or ""
        )

        if protocol and protocol != "unknown":

            lines.append(
                f'    {source} -->|"{protocol}"| {target}'
            )

        else:

            lines.append(
                f"    {source} --> {target}"
            )

    if len(lines) == 1:
        lines.append(
            '    empty["No components detected"]'
        )

    return "\n".join(lines)