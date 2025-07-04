import uuid
import sqlalchemy as sa
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, JSON, Integer
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

    teams = relationship("TeamMember", back_populates="user")

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
    meta = Column(JSON, default={})  # Additional data like item_id, action, etc.
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

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
