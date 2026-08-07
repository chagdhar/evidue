from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DocumentRelationType(StrEnum):
    AMENDS = "amends"
    SUPERSEDES = "supersedes"
    INCORPORATES = "incorporates"


class AgreementDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    text: str = Field(min_length=1)
    effective_from: datetime
    effective_until: datetime | None = None
    precedence: int = 0
    source_hash: str


class DocumentRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_document_id: str
    target_document_id: str
    relation: DocumentRelationType


class AgreementBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    parties: dict[str, str]
    documents: list[AgreementDocument] = Field(min_length=1)
    relations: list[DocumentRelation] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> AgreementBundle:
        document_ids = [item.id for item in self.documents]
        if len(document_ids) != len(set(document_ids)):
            raise ValueError("agreement bundle document IDs must be unique")
        known = set(document_ids)
        graph: dict[str, set[str]] = {document_id: set() for document_id in known}
        for relation in self.relations:
            if relation.source_document_id not in known or relation.target_document_id not in known:
                raise ValueError("agreement bundle relation references an unknown document")
            if relation.source_document_id == relation.target_document_id:
                raise ValueError("agreement bundle relation cannot reference the same document")
            graph[relation.source_document_id].add(relation.target_document_id)

        visited: set[str] = set()
        active: set[str] = set()

        def visit(node: str) -> None:
            if node in active:
                raise ValueError("agreement bundle contains a circular document relation")
            if node in visited:
                return
            active.add(node)
            for target in graph[node]:
                visit(target)
            active.remove(node)
            visited.add(node)

        for document_id in known:
            visit(document_id)
        return self


def applicable_documents(bundle: AgreementBundle, at: datetime) -> list[AgreementDocument]:
    applicable = [
        item
        for item in bundle.documents
        if item.effective_from <= at and (item.effective_until is None or at < item.effective_until)
    ]
    superseded = {
        relation.target_document_id
        for relation in bundle.relations
        if relation.relation == DocumentRelationType.SUPERSEDES
        and relation.source_document_id in {item.id for item in applicable}
    }
    retained = [item for item in applicable if item.id not in superseded]
    return sorted(retained, key=lambda item: (item.precedence, item.effective_from), reverse=True)


def resolved_bundle_text(bundle: AgreementBundle, at: datetime) -> str:
    """Render the effective agreement packet without losing document/version provenance."""

    documents = applicable_documents(bundle, at)
    if not documents:
        raise ValueError("Agreement bundle has no documents effective at the requested time")
    relations_by_source: dict[str, list[DocumentRelation]] = {}
    for relation in bundle.relations:
        relations_by_source.setdefault(relation.source_document_id, []).append(relation)
    sections = []
    for document in documents:
        relations = relations_by_source.get(document.id, [])
        relation_text = ", ".join(
            f"{relation.relation.value}:{relation.target_document_id}" for relation in relations
        ) or "none"
        sections.append(
            f"DOCUMENT ID: {document.id}\n"
            f"TITLE: {document.title}\n"
            f"PRECEDENCE: {document.precedence}\n"
            f"EFFECTIVE FROM: {document.effective_from.isoformat()}\n"
            f"SOURCE HASH: {document.source_hash}\n"
            f"RELATIONS: {relation_text}\n"
            "---\n"
            f"{document.text.strip()}"
        )
    return "\n\n===== NEXT AGREEMENT DOCUMENT =====\n\n".join(sections)
