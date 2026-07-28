from typing import Literal

from pydantic import BaseModel, Field


ReviewScope = Literal["current", "all"]


class EntityCreate(BaseModel):
    base_version: int
    chunk_id: str
    name: str = Field(min_length=1, max_length=200)
    entity_type: str
    evidence_text: str = Field(min_length=1)


class EntityUpdate(BaseModel):
    base_version: int
    chunk_id: str
    scope: ReviewScope = "current"
    name: str | None = Field(default=None, min_length=1, max_length=200)
    entity_type: str | None = None
    evidence_text: str | None = None
    status: Literal["pending", "accepted"] | None = None


class RelationCreate(BaseModel):
    base_version: int
    chunk_id: str
    start_entity_id: str
    relation_type: str
    end_entity_id: str
    evidence_text: str = Field(min_length=1)


class RelationUpdate(BaseModel):
    base_version: int
    chunk_id: str
    start_entity_id: str | None = None
    relation_type: str | None = None
    end_entity_id: str | None = None
    evidence_text: str | None = None
    status: Literal["pending", "accepted"] | None = None


class MutationRequest(BaseModel):
    base_version: int
    chunk_id: str


class ApproveRequest(BaseModel):
    base_version: int


class RestoreRequest(BaseModel):
    base_version: int
    chunk_id: str
