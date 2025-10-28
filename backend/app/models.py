import uuid
from typing import Any
import sqlalchemy as sa
from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Integer,
    Time,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    phone_number = Column(String)
    orcid_id = Column(String)
    two_factor_secret = Column(String)
    two_factor_enabled = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    last_digest = Column(DateTime, default=datetime.now(timezone.utc))
    digest_frequency = Column(String, default="daily", nullable=False)
    quiet_hours_enabled = Column(Boolean, default=False, nullable=False)
    quiet_hours_start = Column(Time, nullable=True)
    quiet_hours_end = Column(Time, nullable=True)

    teams = relationship("TeamMember", back_populates="user")
    notifications = relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan"
    )

class Team(Base):
    __tablename__ = "teams"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    members = relationship("TeamMember", back_populates="team")

class TeamMember(Base):
    __tablename__ = "team_members"
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    role = Column(String, default="member")

    user = relationship("User", back_populates="teams")
    team = relationship("Team", back_populates="members")


class Location(Base):
    __tablename__ = "locations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("locations.id"))
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    parent = relationship("Location", remote_side=[id])

class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_type = Column(String, nullable=False)
    name = Column(String, nullable=False)
    barcode = Column(String, unique=True)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"))
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    location_id = Column(UUID(as_uuid=True), ForeignKey("locations.id"))
    location = Column(JSON, default={})
    status = Column(String, default="available")
    custom_data = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

class FieldDefinition(Base):
    __tablename__ = "field_definitions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String, nullable=False)
    field_key = Column(String, nullable=False)
    field_label = Column(String, nullable=False)
    field_type = Column(String, nullable=False)
    is_required = Column(Boolean, default=False)
    options = Column(JSON)
    validation = Column(JSON)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"))

    __table_args__ = (
        sa.UniqueConstraint("entity_type", "field_key", "team_id"),
        {"sqlite_autoincrement": True},
    )


class ItemRelationship(Base):
    __tablename__ = "item_relationships"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_item = Column(
        UUID(as_uuid=True),
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
    )
    to_item = Column(
        UUID(as_uuid=True),
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
    )
    relationship_type = Column(String)
    meta = Column("metadata", JSON, default={})


class File(Base):
    __tablename__ = "files"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id = Column(UUID(as_uuid=True), ForeignKey("inventory_items.id", ondelete="CASCADE"))
    filename = Column(String)
    file_type = Column(String)
    file_size = Column(String)
    storage_path = Column(String)
    meta = Column("metadata", JSON, default={})
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class ProtocolTemplate(Base):
    __tablename__ = "protocol_templates"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    version = Column(String, default="1")
    content = Column(String, nullable=False)
    variables = Column(JSON, default=list)
    is_public = Column(Boolean, default=False)
    forked_from = Column(UUID(as_uuid=True), ForeignKey("protocol_templates.id"), nullable=True)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"))
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))


class ProtocolExecution(Base):
    __tablename__ = "protocol_executions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey("protocol_templates.id"))
    run_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    status = Column(String, default="pending")
    params = Column(JSON, default={})
    result = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    events = relationship(
        "ExecutionEvent",
        back_populates="execution",
        cascade="all, delete-orphan",
        order_by="ExecutionEvent.sequence",
    )
    template = relationship("ProtocolTemplate")
    runner = relationship("User")
    baseline_versions = relationship(
        "GovernanceBaselineVersion",
        back_populates="execution",
        cascade="all, delete-orphan",
        order_by="GovernanceBaselineVersion.created_at.desc()",
    )


class ExperimentScenarioFolder(Base):
    __tablename__ = "experiment_preview_scenario_folders"

    # purpose: organize execution scenarios for collaborative review cycles
    # status: pilot
    # depends_on: protocol_executions, users, teams

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("protocol_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=True)
    visibility = Column(String, default="private", nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
        nullable=False,
    )

    execution = relationship("ProtocolExecution")
    owner = relationship("User")
    team = relationship("Team")
    scenarios = relationship(
        "ExperimentScenario",
        back_populates="folder",
        cascade="all, delete-orphan",
    )


class ExperimentScenario(Base):
    __tablename__ = "experiment_preview_scenarios"

    # purpose: persist scientist-authored preview scenarios scoped to executions
    # status: pilot
    # depends_on: protocol_executions, users, teams, execution_narrative_workflow_template_snapshots

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("protocol_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=True)
    workflow_template_snapshot_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "execution_narrative_workflow_template_snapshots.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    resource_overrides = Column(JSON, default=dict, nullable=False)
    stage_overrides = Column(JSON, default=list, nullable=False)
    folder_id = Column(
        UUID(as_uuid=True),
        ForeignKey("experiment_preview_scenario_folders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    cloned_from_id = Column(
        UUID(as_uuid=True),
        ForeignKey("experiment_preview_scenarios.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_shared = Column(Boolean, default=False, nullable=False)
    shared_team_ids = Column(JSON, default=list, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    timeline_event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("execution_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
        nullable=False,
    )

    execution = relationship("ProtocolExecution")
    owner = relationship("User")
    team = relationship("Team")
    snapshot = relationship("ExecutionNarrativeWorkflowTemplateSnapshot")
    cloned_from = relationship("ExperimentScenario", remote_side=[id])
    folder = relationship("ExperimentScenarioFolder", back_populates="scenarios")
    timeline_event = relationship("ExecutionEvent")


class ExecutionEvent(Base):
    __tablename__ = "execution_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("protocol_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = Column(String, nullable=False)
    payload = Column(JSON, default=dict)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    sequence = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    execution = relationship("ProtocolExecution", back_populates="events")
    actor = relationship("User")

    __table_args__ = (
        sa.UniqueConstraint("execution_id", "sequence", name="uq_execution_event_sequence"),
    )


class ExecutionNarrativeWorkflowTemplate(Base):
    __tablename__ = "execution_narrative_workflow_templates"

    # purpose: capture reusable approval ladder definitions for narrative exports
    # status: draft
    # depends_on: users

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_key = Column(String, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    stage_blueprint = Column(JSON, default=list, nullable=False)
    default_stage_sla_hours = Column(Integer, nullable=True)
    permitted_roles = Column(JSON, default=list, nullable=False)
    status = Column(String, default="draft", nullable=False)
    forked_from_id = Column(
        UUID(as_uuid=True),
        ForeignKey("execution_narrative_workflow_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
        nullable=False,
    )
    published_at = Column(DateTime, nullable=True)
    published_snapshot_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "execution_narrative_workflow_template_snapshots.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    is_latest = Column(Boolean, default=True, nullable=False)

    created_by = relationship("User")
    forked_from = relationship(
        "ExecutionNarrativeWorkflowTemplate", remote_side=[id]
    )
    assignments = relationship(
        "ExecutionNarrativeWorkflowTemplateAssignment",
        back_populates="template",
        cascade="all, delete-orphan",
    )
    published_snapshot = relationship(
        "ExecutionNarrativeWorkflowTemplateSnapshot",
        foreign_keys=[published_snapshot_id],
    )
    snapshots = relationship(
        "ExecutionNarrativeWorkflowTemplateSnapshot",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="ExecutionNarrativeWorkflowTemplateSnapshot.captured_at.desc()",
        foreign_keys="ExecutionNarrativeWorkflowTemplateSnapshot.template_id",
    )

    __table_args__ = (
        sa.UniqueConstraint("template_key", "version", name="uq_template_key_version"),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_template_lifecycle_status",
        ),
    )


class ExecutionNarrativeWorkflowTemplateSnapshot(Base):
    __tablename__ = "execution_narrative_workflow_template_snapshots"

    # purpose: persist immutable governance template payloads for lifecycle enforcement
    # status: pilot
    # depends_on: execution_narrative_workflow_templates

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "execution_narrative_workflow_templates.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    template_key = Column(String, nullable=False)
    version = Column(Integer, nullable=False)
    status = Column(String, nullable=False)
    captured_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)
    captured_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    snapshot_payload = Column(JSON, default=dict, nullable=False)

    template = relationship(
        "ExecutionNarrativeWorkflowTemplate",
        back_populates="snapshots",
        foreign_keys=[template_id],
    )
    captured_by = relationship("User")

    __table_args__ = (
        sa.UniqueConstraint(
            "template_id",
            "version",
            name="uq_template_snapshot_version",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_template_snapshot_status",
        ),
    )


class GovernanceTemplateAuditLog(Base):
    __tablename__ = "governance_template_audit_logs"

    # purpose: track governance template lifecycle events and export bindings
    # status: pilot
    # depends_on: execution_narrative_workflow_templates

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "execution_narrative_workflow_templates.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    snapshot_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "execution_narrative_workflow_template_snapshots.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)
    detail = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)

    template = relationship("ExecutionNarrativeWorkflowTemplate")
    snapshot = relationship("ExecutionNarrativeWorkflowTemplateSnapshot")
    actor = relationship("User")


class GovernanceBaselineVersion(Base):
    __tablename__ = "governance_baseline_versions"

    # purpose: catalog baseline lifecycle submissions for governance oversight
    # status: draft
    # depends_on: protocol_executions, protocol_templates, users, teams

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("protocol_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("protocol_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="submitted", nullable=False)
    labels = Column(JSON, default=list, nullable=False)
    reviewer_ids = Column(JSON, default=list, nullable=False)
    version_number = Column(Integer, nullable=True)
    is_current = Column(Boolean, default=False, nullable=False)
    submitted_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    submitted_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)
    reviewed_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)
    published_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    published_at = Column(DateTime, nullable=True)
    publish_notes = Column(Text, nullable=True)
    rollback_of_id = Column(
        UUID(as_uuid=True),
        ForeignKey("governance_baseline_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    rolled_back_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    rolled_back_at = Column(DateTime, nullable=True)
    rollback_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
        nullable=False,
    )

    execution = relationship("ProtocolExecution", back_populates="baseline_versions")
    template = relationship("ProtocolTemplate")
    team = relationship("Team")
    submitted_by = relationship("User", foreign_keys=[submitted_by_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])
    published_by = relationship("User", foreign_keys=[published_by_id])
    rolled_back_by = relationship("User", foreign_keys=[rolled_back_by_id])
    rollback_of = relationship("GovernanceBaselineVersion", remote_side=[id])
    events = relationship(
        "GovernanceBaselineEvent",
        back_populates="baseline",
        cascade="all, delete-orphan",
        order_by="GovernanceBaselineEvent.created_at.desc()",
    )

    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('submitted', 'approved', 'rejected', 'published', 'rolled_back')",
            name="ck_governance_baseline_status",
        ),
        sa.UniqueConstraint(
            "template_id",
            "version_number",
            name="uq_governance_baseline_template_version",
        ),
    )


class GovernanceBaselineEvent(Base):
    __tablename__ = "governance_baseline_events"

    # purpose: capture auditable baseline lifecycle transitions and metadata snapshots
    # status: draft
    # depends_on: governance_baseline_versions, users

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    baseline_id = Column(
        UUID(as_uuid=True),
        ForeignKey("governance_baseline_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action = Column(String, nullable=False)
    notes = Column(Text, nullable=True)
    detail = Column(JSON, default=dict, nullable=False)
    performed_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)

    baseline = relationship("GovernanceBaselineVersion", back_populates="events")
    actor = relationship("User")



class GovernanceOverrideAction(Base):
    __tablename__ = "governance_override_actions"

    # purpose: persist staffing override decisions and their execution lineage
    # status: pilot
    # depends_on: governance_baseline_versions, protocol_executions, users

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recommendation_id = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)
    status = Column(
        String,
        nullable=False,
        default="accepted",
    )
    execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("protocol_executions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    baseline_id = Column(
        UUID(as_uuid=True),
        ForeignKey("governance_baseline_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    target_reviewer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reversible = Column(Boolean, default=False, nullable=False)
    notes = Column(Text, nullable=True)
    meta = Column("metadata", JSON, default=dict, nullable=False)
    execution_hash = Column(String(64), nullable=True, unique=True)
    detail_snapshot = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
        nullable=False,
    )

    execution = relationship("ProtocolExecution")
    baseline = relationship("GovernanceBaselineVersion")
    target_reviewer = relationship("User", foreign_keys=[target_reviewer_id])
    actor = relationship("User", foreign_keys=[actor_id])
    lineage = relationship(
        "GovernanceOverrideLineage",
        back_populates="override",
        cascade="all, delete-orphan",
        uselist=False,
    )
    reversal_event = relationship(
        "GovernanceOverrideReversalEvent",
        back_populates="override",
        cascade="all, delete-orphan",
        uselist=False,
    )
    coaching_notes = relationship(
        "GovernanceCoachingNote",
        back_populates="override",
        cascade="all, delete-orphan",
        order_by="GovernanceCoachingNote.created_at",
    )
    reversal_lock_token = Column(String(64), index=True, nullable=True)
    reversal_lock_acquired_at = Column(DateTime, nullable=True)
    reversal_lock_actor_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reversal_lock_tier_key = Column(String, nullable=True)
    reversal_lock_tier = Column(String, nullable=True)
    reversal_lock_tier_level = Column(Integer, nullable=True)
    reversal_lock_scope = Column(String, nullable=True)
    reversal_lock_actor = relationship(
        "User", foreign_keys=[reversal_lock_actor_id], lazy="joined"
    )
    lock_events = relationship(
        "GovernanceOverrideLockEvent",
        back_populates="override",
        cascade="all, delete-orphan",
        order_by="GovernanceOverrideLockEvent.created_at",
    )

    @property
    def cooldown_expires_at(self) -> datetime | None:
        if self.reversal_event is None:
            return None
        return self.reversal_event.cooldown_expires_at

    @property
    def cooldown_window_minutes(self) -> int | None:
        if self.reversal_event is None:
            return None
        return self.reversal_event.cooldown_window_minutes

    @property
    def reversal_event_payload(self) -> dict[str, Any] | None:
        event = self.reversal_event
        if event is None:
            return None
        detail = dict(event.detail or {})
        diffs: list[dict[str, Any]] = []
        for item in detail.get("diffs", []) or []:
            key = str(item.get("key", ""))
            if not key:
                continue
            diffs.append(
                {
                    "key": key,
                    "before": item.get("before"),
                    "after": item.get("after"),
                }
            )
        payload: dict[str, Any] = {
            "id": str(event.id),
            "override_id": str(event.override_id),
            "baseline_id": str(event.baseline_id) if event.baseline_id else None,
            "created_at": event.created_at.isoformat() if event.created_at else None,
            "cooldown_expires_at": event.cooldown_expires_at.isoformat()
            if event.cooldown_expires_at
            else None,
            "cooldown_window_minutes": event.cooldown_window_minutes,
            "diffs": diffs,
            "previous_detail": detail.get("previous_detail", {}),
            "current_detail": detail.get("current_detail", {}),
            "metadata": dict(event.meta or {}),
        }
        if event.actor is not None:
            payload["actor"] = {
                "id": str(event.actor.id),
                "name": event.actor.full_name,
                "email": event.actor.email,
            }
        return payload

    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('accepted', 'declined', 'executed', 'reversed')",
            name="ck_governance_override_status",
        ),
        sa.UniqueConstraint(
            "execution_hash",
            name="uq_governance_override_execution_hash",
        ),
    )


class GovernanceOverrideLineage(Base):
    __tablename__ = "governance_override_lineages"

    # purpose: link override actions to authored scenarios and notebook provenance snapshots
    # status: pilot
    # depends_on: governance_override_actions, experiment_preview_scenarios, notebook_entries, users

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    override_id = Column(
        UUID(as_uuid=True),
        ForeignKey("governance_override_actions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    scenario_id = Column(
        UUID(as_uuid=True),
        ForeignKey("experiment_preview_scenarios.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    scenario_snapshot = Column(JSON, default=dict, nullable=False)
    notebook_entry_id = Column(
        UUID(as_uuid=True),
        ForeignKey("notebook_entries.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    notebook_snapshot = Column(JSON, default=dict, nullable=False)
    captured_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    captured_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)
    meta = Column("metadata", JSON, default=dict, nullable=False)

    override = relationship("GovernanceOverrideAction", back_populates="lineage")
    scenario = relationship("ExperimentScenario")
    notebook_entry = relationship("NotebookEntry")
    captured_by = relationship("User")


class GovernanceOverrideReversalEvent(Base):
    __tablename__ = "governance_override_reversal_events"

    # purpose: capture override reversal metadata, actor attribution, and cooldown policy
    # status: pilot
    # depends_on: governance_override_actions, governance_baseline_versions, users

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    override_id = Column(
        UUID(as_uuid=True),
        ForeignKey("governance_override_actions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    baseline_id = Column(
        UUID(as_uuid=True),
        ForeignKey("governance_baseline_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    reversed_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    detail = Column(JSON, default=dict, nullable=False)
    meta = Column("metadata", JSON, default=dict, nullable=False)
    cooldown_expires_at = Column(DateTime, nullable=True)
    cooldown_window_minutes = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)

    override = relationship("GovernanceOverrideAction", back_populates="reversal_event")
    baseline = relationship("GovernanceBaselineVersion")
    actor = relationship("User")

    __table_args__ = (
        sa.CheckConstraint(
            "cooldown_window_minutes IS NULL OR cooldown_window_minutes >= 0",
            name="ck_governance_override_reversal_events_window_non_negative",
        ),
    )


class GovernanceCoachingNote(Base):
    __tablename__ = "governance_coaching_notes"

    # purpose: persist reviewer coaching rationale threads tied to governance overrides
    # status: experimental
    # depends_on: governance_override_actions, governance_baseline_versions, protocol_executions, users

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    override_id = Column(
        UUID(as_uuid=True),
        ForeignKey("governance_override_actions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    baseline_id = Column(
        UUID(as_uuid=True),
        ForeignKey("governance_baseline_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("protocol_executions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    parent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("governance_coaching_notes.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    thread_root_id = Column(
        UUID(as_uuid=True),
        ForeignKey("governance_coaching_notes.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    author_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    body = Column(Text, nullable=False)
    moderation_state = Column(String, nullable=False, default="published")
    meta = Column("metadata", JSON, default=dict, nullable=False)
    last_edited_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
        nullable=False,
    )

    override = relationship("GovernanceOverrideAction", back_populates="coaching_notes")
    baseline = relationship("GovernanceBaselineVersion")
    execution = relationship("ProtocolExecution")
    author = relationship("User")
    parent = relationship(
        "GovernanceCoachingNote",
        remote_side=[id],
        foreign_keys=[parent_id],
        back_populates="replies",
    )
    thread_root = relationship(
        "GovernanceCoachingNote",
        remote_side=[id],
        foreign_keys=[thread_root_id],
    )
    replies = relationship(
        "GovernanceCoachingNote",
        foreign_keys=[parent_id],
        back_populates="parent",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        sa.CheckConstraint(
            "moderation_state IN ('draft', 'published', 'flagged', 'resolved', 'removed')",
            name="ck_governance_coaching_notes_state",
        ),
    )

class ExecutionNarrativeWorkflowTemplateAssignment(Base):
    __tablename__ = "execution_narrative_workflow_template_assignments"

    # purpose: link workflow templates to organizational contexts (teams/protocols)
    # status: draft
    # depends_on: execution_narrative_workflow_templates

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "execution_narrative_workflow_templates.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=True)
    protocol_template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("protocol_templates.id"),
        nullable=True,
    )
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)
    meta = Column("metadata", JSON, default=dict)

    template = relationship(
        "ExecutionNarrativeWorkflowTemplate", back_populates="assignments"
    )
    team = relationship("Team")
    protocol_template = relationship("ProtocolTemplate")
    created_by = relationship("User")

    __table_args__ = (
        sa.CheckConstraint(
            "(team_id IS NOT NULL) OR (protocol_template_id IS NOT NULL)",
            name="ck_template_assignment_target",
        ),
        sa.UniqueConstraint(
            "template_id",
            "team_id",
            name="uq_template_assignment_team",
        ),
        sa.UniqueConstraint(
            "template_id",
            "protocol_template_id",
            name="uq_template_assignment_protocol",
        ),
    )


class ExecutionNarrativeExport(Base):
    __tablename__ = "execution_narrative_exports"

    # purpose: persist serialized narrative exports with approvals and evidence bundles
    # status: pilot
    # depends_on: protocol_executions

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("protocol_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version = Column(Integer, default=1, nullable=False)
    format = Column(String, default="markdown", nullable=False)
    content = Column(Text, nullable=False)
    event_count = Column(Integer, default=0, nullable=False)
    generated_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)
    requested_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    approved_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approval_status = Column(String, default="pending", nullable=False)
    approval_signature = Column(String, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approval_completed_at = Column(DateTime, nullable=True)
    approval_stage_count = Column(Integer, default=0, nullable=False)
    workflow_template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("execution_narrative_workflow_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    workflow_template_snapshot_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "execution_narrative_workflow_template_snapshots.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    workflow_template_key = Column(String, nullable=True)
    workflow_template_version = Column(Integer, nullable=True)
    workflow_template_snapshot = Column(JSON, default=dict)
    current_stage_id = Column(
        UUID(as_uuid=True),
        ForeignKey("execution_narrative_approval_stages.id", ondelete="SET NULL"),
        nullable=True,
    )
    current_stage_started_at = Column(DateTime, nullable=True)
    notes = Column(String, nullable=True)
    meta = Column("metadata", JSON, default=dict)
    artifact_status = Column(String, default="queued", nullable=False)
    artifact_file_id = Column(
        UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="SET NULL"),
        nullable=True,
    )
    artifact_checksum = Column(String, nullable=True)
    artifact_error = Column(String, nullable=True)
    artifact_manifest_digest = Column(String, nullable=True)
    packaging_attempts = Column(Integer, default=0, nullable=False)
    packaged_at = Column(DateTime, nullable=True)
    retired_at = Column(DateTime, nullable=True)
    retention_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )

    execution = relationship("ProtocolExecution")
    requested_by = relationship("User", foreign_keys=[requested_by_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    artifact_file = relationship("File", foreign_keys=[artifact_file_id])
    workflow_template = relationship(
        "ExecutionNarrativeWorkflowTemplate",
        foreign_keys=[workflow_template_id],
    )
    workflow_template_snapshot_record = relationship(
        "ExecutionNarrativeWorkflowTemplateSnapshot",
        foreign_keys=[workflow_template_snapshot_id],
    )
    attachments = relationship(
        "ExecutionNarrativeExportAttachment",
        back_populates="export",
        cascade="all, delete-orphan",
    )
    approval_stages = relationship(
        "ExecutionNarrativeApprovalStage",
        back_populates="export",
        cascade="all, delete-orphan",
        order_by="ExecutionNarrativeApprovalStage.sequence_index",
        foreign_keys="ExecutionNarrativeApprovalStage.export_id",
    )
    current_stage = relationship(
        "ExecutionNarrativeApprovalStage",
        foreign_keys=[current_stage_id],
        post_update=True,
    )


class ExecutionNarrativeApprovalStage(Base):
    __tablename__ = "execution_narrative_approval_stages"

    # purpose: orchestrate multi-role approval ladder for narrative exports
    # status: pilot
    # depends_on: execution_narrative_exports

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    export_id = Column(
        UUID(as_uuid=True),
        ForeignKey("execution_narrative_exports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence_index = Column(Integer, nullable=False)
    name = Column(String, nullable=True)
    required_role = Column(String, nullable=False)
    status = Column(String, default="pending", nullable=False)
    sla_hours = Column(Integer, nullable=True)
    due_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    assignee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    delegated_to_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    overdue_notified_at = Column(DateTime, nullable=True)
    notes = Column(String, nullable=True)
    meta = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )

    export = relationship(
        "ExecutionNarrativeExport",
        back_populates="approval_stages",
        foreign_keys=[export_id],
    )
    assignee = relationship("User", foreign_keys=[assignee_id])
    delegated_to = relationship("User", foreign_keys=[delegated_to_id])
    actions = relationship(
        "ExecutionNarrativeApprovalAction",
        back_populates="stage",
        cascade="all, delete-orphan",
        order_by="ExecutionNarrativeApprovalAction.created_at",
    )

    __table_args__ = (
        sa.UniqueConstraint("export_id", "sequence_index"),
    )


class ExecutionNarrativeApprovalAction(Base):
    __tablename__ = "execution_narrative_approval_actions"

    # purpose: capture granular lifecycle actions performed on approval stages
    # status: pilot
    # depends_on: execution_narrative_approval_stages

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stage_id = Column(
        UUID(as_uuid=True),
        ForeignKey("execution_narrative_approval_stages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    action_type = Column(String, nullable=False)
    signature = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    delegation_target_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    meta = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)

    stage = relationship("ExecutionNarrativeApprovalStage", back_populates="actions")
    actor = relationship("User", foreign_keys=[actor_id])
    delegation_target = relationship("User", foreign_keys=[delegation_target_id])


class GovernanceOverrideLockEvent(Base):
    __tablename__ = "governance_override_lock_events"

    # purpose: capture reversal lock lifecycle events for governance operators
    # status: pilot
    # depends_on: governance_override_actions, teams, users

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    override_id = Column(
        UUID(as_uuid=True),
        ForeignKey("governance_override_actions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String, nullable=False)
    lock_token = Column(String(64), nullable=True)
    tier_key = Column(String, nullable=True)
    tier = Column(String, nullable=True)
    tier_level = Column(Integer, nullable=True)
    scope = Column(String, nullable=True)
    reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)

    override = relationship("GovernanceOverrideAction", back_populates="lock_events")
    team = relationship("Team")
    actor = relationship("User", foreign_keys=[actor_id])


class ExecutionNarrativeExportAttachment(Base):
    __tablename__ = "execution_narrative_export_attachments"

    # purpose: associate narrative exports with snapshot evidence references
    # status: enhanced
    # depends_on: execution_narrative_exports

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    export_id = Column(
        UUID(as_uuid=True),
        ForeignKey("execution_narrative_exports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evidence_type = Column(String, nullable=False)
    reference_id = Column(UUID(as_uuid=True), nullable=False)
    file_id = Column(
        UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="SET NULL"),
        nullable=True,
    )
    label = Column(String, nullable=True)
    snapshot = Column(JSON, default=dict)
    hydration_context = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    export = relationship("ExecutionNarrativeExport", back_populates="attachments")
    file = relationship("File", foreign_keys=[file_id])

class ProtocolMergeRequest(Base):
    __tablename__ = "protocol_merge_requests"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey("protocol_templates.id"))
    proposer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    content = Column(String, nullable=False)
    variables = Column(JSON, default=list)
    status = Column(String, default="open")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))


class TroubleshootingArticle(Base):
    __tablename__ = "troubleshooting_articles"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    category = Column(String, nullable=False)
    content = Column(String, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    success_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))


class NotebookEntry(Base):
    __tablename__ = "notebook_entries"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    content = Column(String, nullable=False)
    item_id = Column(UUID(as_uuid=True), ForeignKey("inventory_items.id"), nullable=True)
    execution_id = Column(UUID(as_uuid=True), ForeignKey("protocol_executions.id"), nullable=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    items = Column(JSON, default=list)
    protocols = Column(JSON, default=list)
    images = Column(JSON, default=list)
    blocks = Column(JSON, default=list)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    is_locked = Column(Boolean, default=False)
    signed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    signed_at = Column(DateTime, nullable=True)
    witness_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    witnessed_at = Column(DateTime, nullable=True)


class NotebookEntryVersion(Base):
    __tablename__ = "notebook_entry_versions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entry_id = Column(UUID(as_uuid=True), ForeignKey("notebook_entries.id"))
    title = Column(String, nullable=False)
    content = Column(String, nullable=False)
    blocks = Column(JSON, default=list)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class Comment(Base):
    __tablename__ = "comments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content = Column(String, nullable=False)
    item_id = Column(UUID(as_uuid=True), ForeignKey("inventory_items.id"), nullable=True)
    entry_id = Column(UUID(as_uuid=True), ForeignKey("notebook_entries.id"), nullable=True)
    knowledge_article_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_articles.id"), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))


class Resource(Base):
    __tablename__ = "resources"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(String)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class Booking(Base):
    __tablename__ = "bookings"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resource_id = Column(UUID(as_uuid=True), ForeignKey("resources.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    notes = Column(String)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    message = Column(String, nullable=False)
    title = Column(String, nullable=True)
    category = Column(String, nullable=True)  # inventory, protocols, projects, bookings, system, collaboration, compliance, equipment, marketplace
    priority = Column(String, default="medium")  # low, medium, high, urgent
    is_read = Column(Boolean, default=False)
    meta = Column(JSON, default=dict)  # Additional data like item_id, action, etc.
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    user = relationship("User", back_populates="notifications")

    @property
    def action_url(self) -> str | None:
        meta = self.meta or {}
        return meta.get("action_url")

class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        sa.UniqueConstraint("user_id", "pref_type", "channel"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    pref_type = Column(String, nullable=False)
    channel = Column(String, nullable=False, default="in_app")
    enabled = Column(Boolean, default=True)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    token = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class SequenceAnalysisJob(Base):
    __tablename__ = "sequence_jobs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    status = Column(String, default="pending")
    format = Column(String)
    result = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))


class Project(Base):
    __tablename__ = "projects"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(String)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))


class ProjectMember(Base):
    __tablename__ = "project_members"
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    role = Column(String, default="member")


class ProjectItem(Base):
    __tablename__ = "project_items"
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), primary_key=True)
    item_id = Column(UUID(as_uuid=True), ForeignKey("inventory_items.id"), primary_key=True)


class ProjectProtocol(Base):
    __tablename__ = "project_protocols"
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), primary_key=True)
    template_id = Column(UUID(as_uuid=True), ForeignKey("protocol_templates.id"), primary_key=True)


class ProjectTask(Base):
    __tablename__ = "project_tasks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"))
    name = Column(String, nullable=False)
    description = Column(String)
    due_date = Column(DateTime)
    status = Column(String, default="pending")
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))


class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    description = Column(String)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class AnalysisTool(Base):
    __tablename__ = "analysis_tools"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(String)
    code = Column(String, nullable=False)
    supported_types = Column(JSON, default=list)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))



class AssistantMessage(Base):
    __tablename__ = "assistant_messages"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    is_user = Column(Boolean, default=True)
    message = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    action = Column(String, nullable=False)
    target_type = Column(String)
    target_id = Column(UUID(as_uuid=True))
    details = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class Equipment(Base):
    __tablename__ = "equipment"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    eq_type = Column(String)
    connection_info = Column(JSON, default={})
    status = Column(String, default="offline")
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class EquipmentReading(Base):
    __tablename__ = "equipment_readings"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    equipment_id = Column(
        UUID(as_uuid=True), ForeignKey("equipment.id", ondelete="CASCADE")
    )
    timestamp = Column(DateTime, default=datetime.now(timezone.utc))
    data = Column(JSON, default={})


class EquipmentMaintenance(Base):
    __tablename__ = "equipment_maintenance"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    equipment_id = Column(
        UUID(as_uuid=True), ForeignKey("equipment.id", ondelete="CASCADE")
    )
    due_date = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    task_type = Column(String, default="maintenance")
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class SOP(Base):
    __tablename__ = "sops"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    version = Column(Integer, default=1)
    content = Column(String, nullable=False)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"))
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class TrainingRecord(Base):
    __tablename__ = "training_records"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    sop_id = Column(UUID(as_uuid=True), ForeignKey("sops.id"))
    equipment_id = Column(UUID(as_uuid=True), ForeignKey("equipment.id"))
    trained_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    trained_at = Column(DateTime, default=datetime.now(timezone.utc))

class ComplianceRecord(Base):
    __tablename__ = "compliance_records"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id = Column(UUID(as_uuid=True), ForeignKey("inventory_items.id"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    record_type = Column(String, nullable=False)
    status = Column(String, default="pending")
    notes = Column(String)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class KnowledgeArticle(Base):
    __tablename__ = "knowledge_articles"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    content = Column(String, nullable=False)
    tags = Column(JSON, default=list)
    is_public = Column(Boolean, default=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))


class KnowledgeArticleView(Base):
    __tablename__ = "knowledge_article_views"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    article_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_articles.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    viewed_at = Column(DateTime, default=datetime.now(timezone.utc))


class KnowledgeArticleStar(Base):
    __tablename__ = "knowledge_article_stars"
    article_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_articles.id"), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class Workflow(Base):
    __tablename__ = "workflows"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(String)
    steps = Column(JSON, default=list)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.id"))
    item_id = Column(UUID(as_uuid=True), ForeignKey("inventory_items.id"))
    run_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    status = Column(String, default="pending")
    result = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))


class Lab(Base):
    __tablename__ = "labs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(String)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class LabConnection(Base):
    __tablename__ = "lab_connections"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_lab = Column(UUID(as_uuid=True), ForeignKey("labs.id"))
    to_lab = Column(UUID(as_uuid=True), ForeignKey("labs.id"))
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class ResourceShare(Base):
    __tablename__ = "resource_shares"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resource_id = Column(UUID(as_uuid=True), ForeignKey("resources.id"))
    from_lab = Column(UUID(as_uuid=True), ForeignKey("labs.id"))
    to_lab = Column(UUID(as_uuid=True), ForeignKey("labs.id"))
    status = Column(String, default="pending")
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class MarketplaceListing(Base):
    __tablename__ = "marketplace_listings"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id = Column(UUID(as_uuid=True), ForeignKey("inventory_items.id"))
    seller_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    price = Column(Integer, nullable=True)
    description = Column(String)
    status = Column(String, default="open")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class MarketplaceRequest(Base):
    __tablename__ = "marketplace_requests"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("marketplace_listings.id"))
    buyer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    message = Column(String)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class Post(Base):
    __tablename__ = "posts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    content = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class Follow(Base):
    __tablename__ = "follows"
    follower_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    followed_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class PostReport(Base):
    __tablename__ = "post_reports"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id = Column(UUID(as_uuid=True), ForeignKey("posts.id"))
    reporter_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    reason = Column(String, nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class ForumThread(Base):
    __tablename__ = "forum_threads"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class ForumPost(Base):
    __tablename__ = "forum_posts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id = Column(UUID(as_uuid=True), ForeignKey("forum_threads.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    content = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class PostLike(Base):
    __tablename__ = "post_likes"
    post_id = Column(UUID(as_uuid=True), ForeignKey("posts.id"), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class ProtocolStar(Base):
    __tablename__ = "protocol_stars"
    protocol_id = Column(UUID(as_uuid=True), ForeignKey("protocol_templates.id"), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class ServiceListing(Base):
    __tablename__ = "service_listings"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    name = Column(String, nullable=False)
    description = Column(String)
    price = Column(Integer, nullable=True)
    status = Column(String, default="open")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class ServiceRequest(Base):
    __tablename__ = "service_requests"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("service_listings.id"))
    requester_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    item_id = Column(UUID(as_uuid=True), ForeignKey("inventory_items.id"), nullable=True)
    message = Column(String)
    result_file_id = Column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=True)
    payment_status = Column(String, default="pending")
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

class ItemType(Base):
    __tablename__ = "item_types"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
