"""Thin Railway Infrastructure as Code authoring helpers for Python.

Mirrors `railway/iac` (TypeScript). Compiles to the same RailwayGraph shape;
plan/apply stay in the CLI ChangeSet path. No Config as Code knowledge here.

Multi-repo: set module-level ``PARTIAL = "api"`` (same role as
``export const partial`` in TypeScript).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, MutableMapping, Sequence


@dataclass
class Service:
    name: str
    config: MutableMapping[str, Any] = field(default_factory=dict)

    def to_graph(self) -> dict[str, Any]:
        node: dict[str, Any] = {"type": "service", "name": self.name}
        node.update(self.config)
        return node


@dataclass
class Project:
    name: str
    resources: Sequence[Any]

    def to_graph(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "resources": [
                r.to_graph() if hasattr(r, "to_graph") else r for r in self.resources
            ],
        }


def service(name: str, **config: Any) -> Service:
    return Service(name=name, config=dict(config))


def project(name: str, *, resources: Sequence[Any]) -> Project:
    return Project(name=name, resources=list(resources))


def define_railway(
    program: Callable[..., Project],
) -> Callable[..., Project]:
    return program


# Aliases matching the TypeScript surface.
defineRailway = define_railway
