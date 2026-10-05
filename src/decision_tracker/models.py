"""Versioned validated records; unknown fields are never silently discarded."""
from datetime import datetime, timezone
from typing import Literal, Annotated
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator

def now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")

ReferenceText = Annotated[str, Field(min_length=1,max_length=1024)]

class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

class Evidence(Model):
    status: str = Field(max_length=160)
    evidence_refs: list[ReferenceText] = Field(default_factory=list, max_length=32)
    responsible_role: str | None = Field(default=None, max_length=160)

class EvidenceState(Model):
    implementation: Evidence | None = None
    verification: Evidence | None = None
    acceptance: Evidence | None = None

class Decision(Model):
    key: str = Field(pattern=r"^D[0-9]{6}$")
    title: str = Field(min_length=1, max_length=160)
    question: str = Field(min_length=1, max_length=8192)
    answer: str | None = Field(default=None, max_length=32768)
    rationale: str | None = Field(default=None, max_length=32768)
    status: Literal["open", "closed", "deprecated"] = "open"
    locked: bool = False
    baseline: str | None = Field(default=None, max_length=160)
    work_tag: Literal["queued", "under-investigation", "deferred"] | None = "queued"
    contested: bool = False
    owner_role: str | None = Field(default=None, max_length=160)
    defer_reason: str | None = Field(default=None, max_length=8192)
    resume_trigger: str | None = Field(default=None, max_length=8192)
    deprecation_kind: Literal["superseded", "obsolete", "withdrawn", "duplicate", "error"] | None = None
    deprecation_reason: str | None = Field(default=None, max_length=8192)
    replacement_key: str | None = None
    authority_refs: list[ReferenceText] = Field(default_factory=list, max_length=33)
    occurred_at: datetime | None = None
    created_at: str = Field(default_factory=now)
    updated_at: str = Field(default_factory=now)
    revision: int = Field(default=1, ge=1)
    evidence_state: EvidenceState = Field(default_factory=EvidenceState)

    @model_validator(mode="after")
    def state(self):
        if not self.title.strip() or not self.question.strip():
            raise ValueError("Title and question cannot be blank.")
        if self.locked and (self.status != "closed" or not self.baseline):
            raise ValueError("A locked decision needs a closed baseline.")
        if (self.status == "open") != (self.work_tag is not None):
            raise ValueError("Only open decisions have a work tag.")
        if self.contested and self.work_tag not in ("under-investigation", "deferred"):
            raise ValueError("A challenge requires investigation or deferral.")
        if self.work_tag == "deferred" and not (self.defer_reason and self.resume_trigger):
            raise ValueError("Deferral requires a reason and resumption trigger.")
        if self.status == "closed" and not (self.answer and self.answer.strip() and self.rationale and self.rationale.strip() and self.authority_refs):
            raise ValueError("Closing requires answer, rationale and authority.")
        if self.status == "deprecated" and not (self.deprecation_kind and self.deprecation_reason):
            raise ValueError("Deprecation requires a subtype and reason.")
        if self.occurred_at is not None and self.occurred_at.utcoffset() is None:
            raise ValueError("Occurred time requires a timezone.")
        return self

class Option(Model):
    id: UUID
    decision_key: str
    position: int = Field(default=0, ge=0)
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=8192)
    benefit: str = Field(default="", max_length=8192)
    cost: str = Field(default="", max_length=8192)
    disposition: Literal["unselected", "selected", "rejected", "retired"] = "unselected"
    reason: str | None = Field(default=None, max_length=8192)
    revision: int = Field(default=1, ge=1)

class Reference(Model):
    id: UUID
    decision_key: str
    position: int = Field(default=0, ge=0)
    label: str = Field(min_length=1, max_length=160)
    locator: str = Field(min_length=1, max_length=8192)
    kind: Literal["evidence", "authority", "external-decision"] = "evidence"
    version: str | None = Field(default=None, max_length=160)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    availability: Literal["known", "unavailable", "unknown"] = "unknown"
    authenticity: Literal["verified", "unverified", "unknown"] = "unknown"
    limitations: str = Field(default="", max_length=8192)
    retired: bool = False
    revision: int = Field(default=1, ge=1)

class Link(Model):
    id: UUID
    source_key: str
    target_key: str
    type: Literal["relates_to", "depends_on", "supersedes", "amends"]
    active: bool = True
    reason: str = Field(default="", max_length=8192)
    revision: int = Field(default=1, ge=1)
    impact: str | None = Field(default=None, max_length=8192)
    baseline_disposition: Literal["continue", "pause"] | None = None

OperationName = Literal[
    "decision.create", "decision.edit", "decision.edit-resolution", "decision.close",
    "decision.reopen", "decision.lock", "decision.amend", "decision.deprecate",
    "decision.defer", "decision.resume", "decision.challenge", "decision.resolve-challenge",
    "decision.set-work", "option.add", "option.edit", "option.retire",
    "reference.add", "reference.edit", "reference.retire", "link.add", "link.unlink"]

class Operation(Model):
    op: OperationName
    key: str | None = None
    id: str | None = None
    client_ref: str | None = None
    data: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def data_types(self):
        text_fields={"title","question","answer","rationale","owner_role","work_tag","defer_reason","resume_trigger",
                     "impact","baseline","baseline_disposition","kind","replacement_key","target_key","type","selected_option",
                     "description","benefit","cost","disposition","reason","label","locator","version","sha256","availability","authenticity","limitations"}
        for name,value in self.data.items():
            if name in text_fields and value is not None and not isinstance(value,str):
                raise ValueError("Operation text fields must be strings.")
        return self

class Change(Model):
    expected_ledger_uuid: UUID
    expected_revision: int = Field(ge=0)
    expected_decision_revisions: dict[str, int] = Field(default_factory=dict)
    request_id: UUID
    reason: str = Field(min_length=1, max_length=8192)
    authority_refs: list[ReferenceText] = Field(default_factory=list, max_length=32)
    attribution: dict[str, str] = Field(default_factory=dict)
    occurred_at: datetime | None = None
    operations: list[Operation] = Field(min_length=1, max_length=25)
    validate_only: bool = False

    @model_validator(mode="after")
    def bounds(self):
        if len(self.attribution)>16 or any(len(k)>160 or len(v)>1024 for k,v in self.attribution.items()):
            raise ValueError("Attribution exceeds its bounded metadata limit.")
        if self.occurred_at is not None and self.occurred_at.utcoffset() is None:
            raise ValueError("Occurred time requires a timezone.")
        if len(self.expected_decision_revisions)>25 or any(v<1 for v in self.expected_decision_revisions.values()):
            raise ValueError("Expected decision revisions must be positive, with at most25 entries.")
        return self

class ProjectChange(Model):
    kind: Literal["create", "register"] = "create"
    project_id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,47}$")
    name: str = Field(min_length=1, max_length=160)
    relative_path: str | None = None
    expected_catalog_revision: int = Field(ge=0)
    request_id: UUID

class ProjectState(Model):
    enabled: bool
    expected_catalog_revision: int = Field(ge=0)
    request_id: UUID
