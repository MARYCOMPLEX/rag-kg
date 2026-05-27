"""Frontend-facing knowledge graph workspace endpoints."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from apps._shared.factories import AppContainer
from apps.api.auth import Principal, get_current_principal
from apps.api.deps import get_container
from packages.core.errors import LibraryNotFoundError
from packages.core.models import Entity, Triple

router = APIRouter(prefix="/api/libraries/{library_id}/graph", tags=["libraries"])

type FrontendGraphLayout = Literal["static", "force", "webgl"]

_DEFAULT_LAYOUT: FrontendGraphLayout = "static"
_VALID_LAYOUTS: set[str] = {"static", "force", "webgl"}
_ENTITY_TYPE_KEY = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


@dataclass(frozen=True, slots=True)
class _GraphData:
    entities: dict[str, Entity]
    triples: tuple[Triple, ...]


class FrontendGraphEntityTypeFilter(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    label: str
    count: int = Field(ge=0)
    checked: bool
    tone: str


class FrontendGraphFilters(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    entity_types: list[FrontendGraphEntityTypeFilter] = Field(alias="entityTypes")
    min_confidence: float = Field(alias="minConfidence", ge=0.0, le=1.0)


class FrontendGraphNode(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    label: str
    type: str
    tone: str
    x: float
    y: float
    radius: float
    selected: bool | None = None
    faded: bool | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    degree: int | None = Field(default=None, ge=0)
    evidence_count: int | None = Field(default=None, alias="evidenceCount", ge=0)


class FrontendGraphEdge(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    source: str
    target: str
    label: str | None = None
    weight: float | None = Field(default=None, ge=0.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    muted: bool | None = None
    directed: bool | None = None


class FrontendGraphCanvas(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    nodes: list[FrontendGraphNode]
    edges: list[FrontendGraphEdge]
    layout: FrontendGraphLayout
    large_graph: bool = Field(alias="largeGraph")


class FrontendGraphSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    entity_count_label: str = Field(alias="entityCountLabel")
    triple_count_label: str = Field(alias="tripleCountLabel")
    confidence_label: str = Field(alias="confidenceLabel")
    warning_label: str | None = Field(default=None, alias="warningLabel")


class FrontendGraphWorkspace(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    filters: FrontendGraphFilters
    canvas: FrontendGraphCanvas
    summary: FrontendGraphSummary


class FrontendMentionsTrend(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    points: list[int]
    start_label: str = Field(alias="startLabel")
    end_label: str = Field(alias="endLabel")


class FrontendCoOccurringEntity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    name: str
    type: str
    count: int = Field(ge=0)


class FrontendGraphEntityDetail(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    id: str
    label: str
    kind: str
    stable_id: str = Field(alias="stableId")
    aliases: list[str]
    summary: str
    degree: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    incoming: int = Field(ge=0)
    mentions: int = Field(ge=0)
    evidence_count: int = Field(alias="evidenceCount", ge=0)
    mentions_trend: FrontendMentionsTrend = Field(alias="mentionsTrend")
    co_occurring: list[FrontendCoOccurringEntity] = Field(alias="coOccurring")


@router.get(
    "",
    response_model=FrontendGraphWorkspace,
    response_model_exclude_none=True,
)
async def get_frontend_graph_workspace(
    library_id: str,
    entity_types: str | None = Query(default=None, alias="entityTypes"),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0, alias="minConfidence"),
    limit: int = Query(default=100, ge=1, le=500),
    layout: str = Query(default=_DEFAULT_LAYOUT),
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> FrontendGraphWorkspace:
    await _ensure_library(container, library_id)
    graph_layout = _parse_layout(layout)
    selected_types = _parse_entity_types(entity_types)
    data = await _load_graph_data(container, library_id)
    return _workspace_from_graph(
        data,
        selected_types=selected_types,
        min_confidence=min_confidence,
        limit=limit,
        layout=graph_layout,
    )


@router.get(
    "/entities/{entity_id}",
    response_model=FrontendGraphEntityDetail,
)
async def get_frontend_graph_entity(
    library_id: str,
    entity_id: str,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> FrontendGraphEntityDetail:
    await _ensure_library(container, library_id)
    data = await _load_graph_data(container, library_id)
    entity = data.entities.get(entity_id)
    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Graph entity not found: {entity_id}",
        )
    return _entity_detail_from_graph(entity, data)


async def _ensure_library(container: AppContainer, library_id: str) -> None:
    if not await container.library_repo.exists(library_id):
        raise LibraryNotFoundError(library_id)


def _parse_layout(raw: str) -> FrontendGraphLayout:
    layout = raw.strip().lower()
    if layout not in _VALID_LAYOUTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported graph layout: {raw}",
        )
    return layout  # type: ignore[return-value]


def _parse_entity_types(raw: str | None) -> frozenset[str]:
    if raw is None or raw.strip() == "":
        return frozenset()
    parsed: list[str] = []
    invalid: list[str] = []
    for piece in raw.split(","):
        token = piece.strip().lower()
        if not token:
            continue
        if not _ENTITY_TYPE_KEY.fullmatch(token):
            invalid.append(token)
            continue
        parsed.append(token)
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid entity type filter: {', '.join(invalid)}",
        )
    return frozenset(parsed)


async def _load_graph_data(container: AppContainer, library_id: str) -> _GraphData:
    triples = await _safe_list_triples(container, library_id)
    listed_entities = await _safe_list_entities(container, library_id)
    entities = {entity.entity_id: entity for entity in listed_entities}
    for triple in triples:
        entities.setdefault(triple.head, _derived_entity(library_id, triple.head))
        entities.setdefault(triple.tail, _derived_entity(library_id, triple.tail))
    return _GraphData(entities=entities, triples=triples)


async def _safe_list_triples(container: AppContainer, library_id: str) -> tuple[Triple, ...]:
    try:
        return tuple(await container.graph_index.list_all_triples(library_id))
    except Exception:
        return ()


async def _safe_list_entities(container: AppContainer, library_id: str) -> tuple[Entity, ...]:
    try:
        return tuple(await container.graph_index.list_entities(library_id))
    except Exception:
        return ()


def _workspace_from_graph(
    data: _GraphData,
    *,
    selected_types: frozenset[str],
    min_confidence: float,
    limit: int,
    layout: FrontendGraphLayout,
) -> FrontendGraphWorkspace:
    type_counts = Counter(_type_key(entity.type) for entity in data.entities.values())
    visible_entity_ids = _visible_entity_ids(data, selected_types, min_confidence)
    ordered_ids = _rank_entity_ids(data, visible_entity_ids)[:limit]
    visible_limited = set(ordered_ids)
    edges = _canvas_edges(data, visible_limited, min_confidence)
    large_graph = len(visible_entity_ids) > limit
    return FrontendGraphWorkspace(
        filters=FrontendGraphFilters(
            entityTypes=_filters_from_counts(type_counts, selected_types),
            minConfidence=min_confidence,
        ),
        canvas=FrontendGraphCanvas(
            nodes=_canvas_nodes(data, ordered_ids),
            edges=edges,
            layout=layout,
            largeGraph=large_graph,
        ),
        summary=FrontendGraphSummary(
            entityCountLabel=_plural(len(data.entities), "entity"),
            tripleCountLabel=_plural(len(data.triples), "triple"),
            confidenceLabel=_confidence_label(data.triples),
            warningLabel=_warning_label(large_graph, len(visible_entity_ids), limit),
        ),
    )


def _visible_entity_ids(
    data: _GraphData,
    selected_types: frozenset[str],
    min_confidence: float,
) -> set[str]:
    confident_ids: set[str] = set()
    if data.triples:
        for triple in data.triples:
            if triple.confidence >= min_confidence:
                confident_ids.add(triple.head)
                confident_ids.add(triple.tail)
    elif min_confidence == 0:
        confident_ids.update(data.entities)

    if not selected_types:
        return confident_ids
    return {
        entity_id
        for entity_id in confident_ids
        if _type_key(data.entities[entity_id].type) in selected_types
    }


def _rank_entity_ids(data: _GraphData, entity_ids: set[str]) -> list[str]:
    degrees = _degree_counts(data.triples)
    return sorted(
        entity_ids,
        key=lambda entity_id: (
            -degrees[entity_id],
            data.entities[entity_id].name.casefold(),
            entity_id,
        ),
    )


def _filters_from_counts(
    counts: Counter[str],
    selected_types: frozenset[str],
) -> list[FrontendGraphEntityTypeFilter]:
    filters: list[FrontendGraphEntityTypeFilter] = []
    for key, count in sorted(counts.items()):
        filters.append(
            FrontendGraphEntityTypeFilter(
                key=key,
                label=_label_from_key(key),
                count=count,
                checked=not selected_types or key in selected_types,
                tone=_tone_for_key(key),
            )
        )
    return filters


def _canvas_nodes(data: _GraphData, entity_ids: list[str]) -> list[FrontendGraphNode]:
    degrees = _degree_counts(data.triples)
    confidences = _confidence_by_entity(data.triples)
    evidence_counts = _evidence_count_by_entity(data.triples)
    total = max(len(entity_ids), 1)
    nodes: list[FrontendGraphNode] = []
    for index, entity_id in enumerate(entity_ids):
        entity = data.entities[entity_id]
        angle = (2 * math.pi * index) / total
        degree = degrees[entity_id]
        nodes.append(
            FrontendGraphNode(
                id=entity_id,
                label=entity.name,
                type=_type_key(entity.type),
                tone=_tone_for_key(_type_key(entity.type)),
                x=round(50 + 40 * math.cos(angle), 2),
                y=round(50 + 40 * math.sin(angle), 2),
                radius=float(min(28, 10 + (degree * 2))),
                confidence=confidences.get(entity_id),
                degree=degree,
                evidenceCount=evidence_counts[entity_id],
            )
        )
    return nodes


def _canvas_edges(
    data: _GraphData,
    visible_entity_ids: set[str],
    min_confidence: float,
) -> list[FrontendGraphEdge]:
    edges: list[FrontendGraphEdge] = []
    for index, triple in enumerate(data.triples):
        if triple.confidence < min_confidence:
            continue
        if triple.head not in visible_entity_ids or triple.tail not in visible_entity_ids:
            continue
        edges.append(
            FrontendGraphEdge(
                id=f"edge-{index + 1}",
                source=triple.head,
                target=triple.tail,
                label=triple.relation,
                weight=max(1.0, len(triple.evidence)),
                confidence=triple.confidence,
                directed=True,
            )
        )
    return edges


def _entity_detail_from_graph(entity: Entity, data: _GraphData) -> FrontendGraphEntityDetail:
    incident = [triple for triple in data.triples if entity.entity_id in {triple.head, triple.tail}]
    evidence_ids = {item for triple in incident for item in triple.evidence}
    co_occurring = _co_occurring_entities(entity.entity_id, data)
    confidence = _average(triple.confidence for triple in incident)
    mentions = len(evidence_ids)
    return FrontendGraphEntityDetail(
        id=entity.entity_id,
        label=entity.name,
        kind=entity.type,
        stableId=entity.entity_id,
        aliases=list(entity.aliases),
        summary=entity.description or "",
        degree=len(incident),
        confidence=confidence,
        incoming=sum(1 for triple in incident if triple.tail == entity.entity_id),
        mentions=mentions,
        evidenceCount=mentions,
        mentionsTrend=FrontendMentionsTrend(
            points=[mentions],
            startLabel="Current",
            endLabel="Current",
        ),
        coOccurring=co_occurring,
    )


def _co_occurring_entities(entity_id: str, data: _GraphData) -> list[FrontendCoOccurringEntity]:
    counts: Counter[str] = Counter()
    for triple in data.triples:
        if triple.head == entity_id:
            counts[triple.tail] += 1
        if triple.tail == entity_id:
            counts[triple.head] += 1

    rows: list[FrontendCoOccurringEntity] = []
    for other_id, count in counts.most_common(8):
        entity = data.entities.get(other_id)
        if entity is None:
            entity = _derived_entity(data.entities[entity_id].library_id, other_id)
        rows.append(
            FrontendCoOccurringEntity(
                id=other_id,
                name=entity.name,
                type=_type_key(entity.type),
                count=count,
            )
        )
    return rows


def _degree_counts(triples: tuple[Triple, ...]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for triple in triples:
        counts[triple.head] += 1
        counts[triple.tail] += 1
    return counts


def _confidence_by_entity(triples: tuple[Triple, ...]) -> dict[str, float]:
    values: dict[str, list[float]] = {}
    for triple in triples:
        values.setdefault(triple.head, []).append(triple.confidence)
        values.setdefault(triple.tail, []).append(triple.confidence)
    return {entity_id: _average(items) for entity_id, items in values.items()}


def _evidence_count_by_entity(triples: tuple[Triple, ...]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for triple in triples:
        evidence_count = len(set(triple.evidence))
        counts[triple.head] += evidence_count
        counts[triple.tail] += evidence_count
    return counts


def _derived_entity(library_id: str, entity_id: str) -> Entity:
    entity_type = entity_id.split(":", 1)[0] if ":" in entity_id else "Entity"
    name = entity_id.split(":", 1)[-1].replace("_", " ").replace("-", " ").title()
    return Entity(
        library_id=library_id,
        entity_id=entity_id,
        name=name,
        type=entity_type.title(),
    )


def _type_key(entity_type: str) -> str:
    key = re.sub(r"[^a-z0-9_-]+", "-", entity_type.strip().lower()).strip("-")
    return key or "entity"


def _label_from_key(key: str) -> str:
    return " ".join(piece.capitalize() for piece in key.replace("_", "-").split("-") if piece)


def _tone_for_key(key: str) -> str:
    if key in {"method", "model", "algorithm"}:
        return "method"
    if key in {"dataset", "benchmark"}:
        return "dataset"
    if key in {"author", "person"}:
        return "author"
    if key in {"paper", "document", "citation"}:
        return "citation"
    return "concept"


def _confidence_label(triples: tuple[Triple, ...]) -> str:
    if not triples:
        return "No confidence data"
    return f"Avg confidence {round(_average(triple.confidence for triple in triples) * 100)}%"


def _warning_label(large_graph: bool, visible_count: int, limit: int) -> str | None:
    if not large_graph:
        return None
    return f"Showing {limit:,} of {visible_count:,} entities"


def _plural(value: int, noun: str) -> str:
    if noun == "entity":
        return f"{value:,} {'entity' if value == 1 else 'entities'}"
    suffix = "" if value == 1 else "s"
    return f"{value:,} {noun}{suffix}"


def _average(values: Iterable[float]) -> float:
    items = list(values)
    if not items:
        return 0.0
    return round(sum(items) / len(items), 4)
