from typing import Literal

from pydantic import BaseModel, Field


ReviewScope = Literal["current", "all"]
ENTITY_NAME_MAX_LENGTH = 200


class EntityCreate(BaseModel):
    base_version: int
    chunk_id: str
    name: str = Field(min_length=1, max_length=ENTITY_NAME_MAX_LENGTH)
    entity_type: str
    evidence_text: str = Field(min_length=1)


class EntityUpdate(BaseModel):
    base_version: int
    chunk_id: str
    scope: ReviewScope = "current"
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=ENTITY_NAME_MAX_LENGTH,
    )
    entity_type: str | None = None
    evidence_text: str | None = None
    status: Literal["pending", "accepted"] | None = None


class ChunkEntitySnapshot(BaseModel):
    entity_id: str = Field(min_length=1)
    # A batch snapshot must accept source data returned by the GET endpoint.
    # Length and emptiness are validated only when the name is actually edited.
    name: str
    entity_type: str
    evidence_text: str = ""
    rejected: bool = False
    approved: bool = False


class ChunkEntitySave(BaseModel):
    base_version: int
    entities: list[ChunkEntitySnapshot]


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
