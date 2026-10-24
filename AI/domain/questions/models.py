from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Choice:
    value: str
    label: str


@dataclass(frozen=True)
class Question:
    id: str
    text: str
    choices: tuple[Choice, ...] = ()
