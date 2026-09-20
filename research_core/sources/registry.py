"""Which sources this process can search.

Built-in providers self-register on import. Add your own with `register()`;
anything satisfying `SourceProvider` works, including a wrapper around an
internal corpus or an MCP client.
"""

from __future__ import annotations

import logging

from .base import SourceProvider

log = logging.getLogger(__name__)

_REGISTRY: dict[str, SourceProvider] = {}


def register(provider: SourceProvider, *, replace: bool = False) -> None:
    if provider.name in _REGISTRY and not replace:
        raise ValueError(
            f"Source {provider.name!r} is already registered; pass replace=True"
        )
    _REGISTRY[provider.name] = provider


def unregister(name: str) -> None:
    _REGISTRY.pop(name, None)


def all_sources() -> dict[str, SourceProvider]:
    return dict(_REGISTRY)


def available_sources() -> dict[str, SourceProvider]:
    """Registered sources that are actually usable right now.

    A source with a missing API key stays registered but is excluded here, so
    a misconfigured environment degrades to the sources that do work instead
    of failing the run.
    """
    usable = {}
    for name, provider in _REGISTRY.items():
        ok, reason = provider.available()
        if ok:
            usable[name] = provider
        else:
            log.info("Source %r unavailable: %s", name, reason)
    return usable


def unavailable_sources() -> dict[str, str]:
    """Registered but unusable sources, mapped to why."""
    blocked = {}
    for name, provider in _REGISTRY.items():
        ok, reason = provider.available()
        if not ok:
            blocked[name] = reason
    return blocked


def load_builtins() -> None:
    """Register the bundled providers. Safe to call repeatedly."""
    from . import (  # noqa: F401  (import triggers registration)
        clinicaltrials,
        cms,
        crossref,
        openfda,
        patentsview,
        pubmed,
        sec_edgar,
        socrata,
    )


def find_by_id_label(label: str) -> SourceProvider | None:
    for provider in _REGISTRY.values():
        if provider.id_label.lower() == label.lower():
            return provider
    return None
