export interface UserIdentity {
  id: string
  email: string
  full_name?: string | null
  phone_number?: string | null
  orcid_id?: string | null
  is_admin?: boolean
}

export interface InventoryItem {
  id: string
  item_type: string
  name: string
  barcode?: string
  team_id?: string
  owner_id?: string
  location: Record<string, any>
  custom_data: Record<string, any>
  status?: string
  created_at: string
  updated_at: string
}

export interface FieldOption {
  value: string
  label: string
}

export interface FieldDefinition {
  id: string
  entity_type: string
  field_key: string
  field_label: string
  field_type: 'text' | 'number' | 'date' | 'select'
  is_required: boolean
  options?: FieldOption[]
  validation?: Record<string, any>
}

export interface FileMeta {
  id: string
  filename: string
  file_type: string
  file_size: number
  storage_path: string
  item_id: string | null
  uploaded_by: string
  created_at: string
}

export interface GraphEdge {
  id: string
  from_item: string
  to_item: string
  relationship_type: string
  meta: Record<string, any>
}

export interface GraphData {
  nodes: InventoryItem[]
  edges: GraphEdge[]
}

export interface TroubleshootingArticle {
  id: string
  title: string
  category: string
  content: string
  created_by?: string
  success_count: number
  created_at: string
  updated_at: string
}

export interface KnowledgeArticle {
  id: string
  title: string
  content: string
  tags?: string[]
  created_by?: string
  created_at: string
  updated_at: string
}

export interface ProtocolTemplate {
  id: string
  name: string
  content: string
  version: string
  team_id?: string
  created_by?: string
  created_at: string
  updated_at: string
}

export interface ProtocolExecution {
  id: string
  template_id: string
  run_by?: string
  status: string
  params: Record<string, any>
  result: Record<string, any>
  created_at: string
  updated_at: string
}

export interface TimelineActor {
  id: string
  email: string
  full_name?: string | null
}

export interface ExecutionEvent {
  id: string
  execution_id: string
  event_type: string
  payload: Record<string, any>
  actor_id?: string | null
  actor?: TimelineActor | null
  sequence: number
  created_at: string
}

export interface NotebookEntry {
  id: string
  title: string
  content: string
  item_id?: string | null
  execution_id?: string | null
  created_by?: string
  created_at: string
  updated_at: string
}

export interface Comment {
  id: string
  content: string
  item_id?: string | null
  entry_id?: string | null
  created_by?: string
  created_at: string
  updated_at: string
}

export interface SequenceFeature {
  record_id: string
  type: string
  start: number
  end: number
  strand: number | null
  qualifiers: Record<string, string[]>
}

export interface ChromatogramData {
  sequence: string
  traces: Record<string, number[]>
}

export interface SequenceRead {
  id: string
  seq: string
  length: number
  gc_content: number
}

export interface BlastResult {
  query_aligned: string
  subject_aligned: string
  score: number
  identity: number
}

export interface SequenceJob {
  id: string
  status: string
  format: string
  result: SequenceRead[] | null
  created_at: string
  updated_at: string
}

export interface AssistantMessage {
  id: string
  is_user: boolean
  message: string
  created_at: string
}

export interface Project {
  id: string
  name: string
  description?: string
  start_date?: string
  end_date?: string
  team_id?: string
  created_by?: string
  created_at: string
  updated_at: string
}

export interface ProjectTask {
  id: string
  project_id: string
  name: string
  description?: string
  due_date?: string
  status: string
  created_by?: string
  created_at: string
  updated_at: string
}

export interface ItemTypeCount {
  item_type: string
  count: number
}

export interface ComplianceRecord {
  id: string
  item_id?: string | null
  user_id?: string | null
  record_type: string
  status: string
  notes?: string | null
  created_at: string
}

export interface StatusCount {
  status: string
  count: number
}

export interface CalendarEvent {
  id: string
  title: string
  start_time: string
  end_time: string
  description?: string | null
  team_id?: string | null
  user_id?: string | null
  created_by?: string | null
  created_at: string
}

export interface Booking {
  id: string
  resource_id: string
  user_id: string
  start_time: string
  end_time: string
  notes?: string | null
  created_at: string
}

export interface Equipment {
  id: string
  name: string
  eq_type: string
  connection_info: Record<string, any>
  status: string
  team_id?: string | null
  created_by?: string | null
  created_at: string
}

export interface EquipmentReading {
  id: string
  timestamp: string
  data: Record<string, any>
}

export interface Lab {
  id: string
  name: string
  description?: string | null
  owner_id?: string | null
  created_at: string
}

export interface LabConnection {
  id: string
  from_lab: string
  to_lab: string
  status: string
  created_at: string
}

export interface MarketplaceListing {
  id: string
  item_id: string
  seller_id: string
  price?: number | null
  description?: string | null
  status: string
  created_at: string
}

export interface MarketplaceRequest {
  id: string
  listing_id: string
  buyer_id: string
  message?: string | null
  status: string
  created_at: string
}

export interface Post {
  id: string
  user_id: string
  content: string
  created_at: string
}

export interface Follow {
  follower_id: string
  followed_id: string
  created_at: string
}
export interface TrendingProtocol {
  template_id: string
  template_name: string
  count: number
}

export interface TrendingArticle {
  article_id: string
  title: string
  count: number
}

export interface TrendingItem {
  item_id: string
  name: string
  count: number
}

export interface TrendingThread {
  thread_id: string
  title: string
  count: number
}


export interface ProtocolDiff {
  diff: string
}

export type ExperimentStepState = 'pending' | 'in_progress' | 'completed' | 'skipped'

export interface ExperimentStepStatus {
  index: number
  instruction: string
  status: ExperimentStepState
  started_at?: string | null
  completed_at?: string | null
  blocked_reason?: string | null
  required_actions: string[]
  auto_triggers: string[]
}

export type ExperimentAnomalySeverity = 'info' | 'warning' | 'critical'

export interface EquipmentTelemetryChannel {
  equipment: Equipment
  status?: string | null
  stream_topics: string[]
  latest_reading?: EquipmentReading | null
}

export interface ExperimentAnomalySignal {
  equipment_id: string
  channel: string
  message: string
  severity: ExperimentAnomalySeverity
  timestamp: string
}

export interface ExperimentAutoLogEntry {
  source: string
  title: string
  body?: string | null
  created_at: string
}

export interface ExperimentExecutionSession {
  execution: ProtocolExecution
  protocol: ProtocolTemplate
  notebook_entries: NotebookEntry[]
  inventory_items: InventoryItem[]
  bookings: Booking[]
  steps: ExperimentStepStatus[]
  telemetry_channels: EquipmentTelemetryChannel[]
  anomaly_events: ExperimentAnomalySignal[]
  auto_log_entries: ExperimentAutoLogEntry[]
  timeline_preview: ExecutionEvent[]
}

export interface ExperimentPreviewResourceOverrides {
  inventory_item_ids?: string[]
  booking_ids?: string[]
  equipment_ids?: string[]
}

export interface ExperimentPreviewStageOverride {
  index: number
  assignee_id?: string | null
  delegate_id?: string | null
  sla_hours?: number | null
}

export interface ExperimentPreviewRequest {
  workflow_template_snapshot_id: string
  resource_overrides?: ExperimentPreviewResourceOverrides
  stage_overrides?: ExperimentPreviewStageOverride[]
}

export interface ExperimentPreviewStageInsight {
  index: number
  name?: string | null
  required_role: string
  status: 'ready' | 'blocked'
  sla_hours?: number | null
  projected_due_at?: string | null
  blockers: string[]
  required_actions: string[]
  auto_triggers: string[]
  assignee_id?: string | null
  delegate_id?: string | null
  mapped_step_indexes: number[]
  gate_keys: string[]
  baseline_status?: 'ready' | 'blocked' | null
  baseline_sla_hours?: number | null
  baseline_projected_due_at?: string | null
  baseline_assignee_id?: string | null
  baseline_delegate_id?: string | null
  baseline_blockers: string[]
  delta_status?: 'cleared' | 'regressed' | 'unchanged' | null
  delta_sla_hours?: number | null
  delta_projected_due_minutes?: number | null
  delta_new_blockers: string[]
  delta_resolved_blockers: string[]
}

export interface ExperimentPreviewResponse {
  execution_id: string
  snapshot_id: string
  baseline_snapshot_id?: string | null
  generated_at: string
  template_name?: string | null
  template_version?: number | null
  stage_insights: ExperimentPreviewStageInsight[]
  narrative_preview: string
  resource_warnings: string[]
}

export type GovernanceRiskLevel = 'low' | 'medium' | 'high'

export interface GovernanceAnalyticsSlaSample {
  stage_index: number
  predicted_due_at?: string | null
  actual_completed_at?: string | null
  delta_minutes?: number | null
  within_target?: boolean | null
}

export interface GovernanceAnalyticsLatencyBand {
  label: string
  start_minutes?: number | null
  end_minutes?: number | null
  count: number
}

export type ReviewerLoadBand = 'light' | 'steady' | 'saturated'

export interface GovernanceReviewerCadenceSummary {
  reviewer_id: string
  reviewer_email?: string | null
  reviewer_name?: string | null
  assignment_count: number
  completion_count: number
  pending_count: number
  load_band: ReviewerLoadBand
  average_latency_minutes?: number | null
  latency_p50_minutes?: number | null
  latency_p90_minutes?: number | null
  latency_bands: GovernanceAnalyticsLatencyBand[]
  blocked_ratio_trailing?: number | null
  churn_signal?: number | null
  rollback_precursor_count: number
  publish_streak: number
  last_publish_at?: string | null
  streak_alert: boolean
}

export interface GovernanceReviewerLoadBandCounts {
  light: number
  steady: number
  saturated: number
}

export interface GovernanceReviewerCadenceTotals {
  reviewer_count: number
  streak_alert_count: number
  reviewer_latency_p50_minutes?: number | null
  reviewer_latency_p90_minutes?: number | null
  load_band_counts: GovernanceReviewerLoadBandCounts
}

export interface GovernanceAnalyticsPreviewSummary {
  execution_id: string
  preview_event_id: string
  snapshot_id?: string | null
  baseline_snapshot_id?: string | null
  generated_at: string
  stage_count: number
  blocked_stage_count: number
  blocked_ratio: number
  overrides_applied: number
  new_blocker_count: number
  resolved_blocker_count: number
  ladder_load: number
  sla_within_target_ratio?: number | null
  mean_sla_delta_minutes?: number | null
  sla_samples: GovernanceAnalyticsSlaSample[]
  blocker_heatmap: number[]
  risk_level: GovernanceRiskLevel
  baseline_version_count: number
  approval_latency_minutes?: number | null
  publication_cadence_days?: number | null
  rollback_count: number
  blocker_churn_index?: number | null
}

export interface GovernanceAnalyticsTotals {
  preview_count: number
  average_blocked_ratio: number
  total_new_blockers: number
  total_resolved_blockers: number
  average_sla_within_target_ratio?: number | null
  total_baseline_versions: number
  total_rollbacks: number
  average_approval_latency_minutes?: number | null
  average_publication_cadence_days?: number | null
  reviewer_count: number
  streak_alert_count: number
  reviewer_latency_p50_minutes?: number | null
  reviewer_latency_p90_minutes?: number | null
  reviewer_load_band_counts: GovernanceReviewerLoadBandCounts
}

export interface GovernanceAnalyticsReport {
  results: GovernanceAnalyticsPreviewSummary[]
  reviewer_cadence: GovernanceReviewerCadenceSummary[]
  totals: GovernanceAnalyticsTotals
}

export interface GovernanceReviewerCadenceReport {
  reviewers: GovernanceReviewerCadenceSummary[]
  totals: GovernanceReviewerCadenceTotals
}

export type GovernanceOverrideAction = 'reassign' | 'cooldown' | 'escalate'
export type GovernanceOverridePriority = 'low' | 'medium' | 'high'

export interface GovernanceOverrideRecommendation {
  recommendation_id: string
  rule_key: string
  action: GovernanceOverrideAction
  priority: GovernanceOverridePriority
  summary: string
  detail?: string | null
  reviewer_id?: string | null
  reviewer_name?: string | null
  reviewer_email?: string | null
  triggered_at: string
  related_execution_ids: string[]
  metrics: Record<string, any>
  allow_opt_out: boolean
}

export interface GovernanceOverrideRecommendationReport {
  generated_at: string
  recommendations: GovernanceOverrideRecommendation[]
}

export interface BaselineLifecycleLabel {
  key: string
  value: string
}

export interface GovernanceBaselineEvent {
  id: string
  baseline_id: string
  action: string
  notes?: string | null
  detail: Record<string, any>
  performed_by_id: string
  created_at: string
}

export type GovernanceBaselineStatus =
  | 'submitted'
  | 'approved'
  | 'rejected'
  | 'published'
  | 'rolled_back'

export interface GovernanceBaselineVersion {
  id: string
  execution_id: string
  template_id?: string | null
  team_id?: string | null
  name: string
  description?: string | null
  status: GovernanceBaselineStatus
  labels: BaselineLifecycleLabel[]
  reviewer_ids: string[]
  version_number?: number | null
  is_current: boolean
  submitted_by_id: string
  submitted_at: string
  reviewed_by_id?: string | null
  reviewed_at?: string | null
  review_notes?: string | null
  published_by_id?: string | null
  published_at?: string | null
  publish_notes?: string | null
  rollback_of_id?: string | null
  rolled_back_by_id?: string | null
  rolled_back_at?: string | null
  rollback_notes?: string | null
  created_at: string
  updated_at: string
  events: GovernanceBaselineEvent[]
}

export interface GovernanceBaselineCollection {
  items: GovernanceBaselineVersion[]
}

export interface BaselineSubmissionDraft {
  execution_id: string
  name: string
  description?: string | null
  reviewer_ids: string[]
  labels: BaselineLifecycleLabel[]
}

export interface BaselineReviewDecision {
  decision: 'approve' | 'reject'
  notes?: string | null
}

export interface BaselinePublishRequest {
  notes?: string | null
}

export interface BaselineRollbackRequest {
  reason: string
  target_version_id?: string | null
}

export interface ExperimentScenario {
  id: string
  execution_id: string
  owner_id: string
  team_id?: string | null
  workflow_template_snapshot_id: string
  name: string
  description?: string | null
  resource_overrides?: ExperimentPreviewResourceOverrides
  stage_overrides: ExperimentPreviewStageOverride[]
  cloned_from_id?: string | null
  folder_id?: string | null
  is_shared: boolean
  shared_team_ids: string[]
  expires_at?: string | null
  timeline_event_id?: string | null
  created_at: string
  updated_at: string
}

export interface ExperimentScenarioFolder {
  id: string
  execution_id: string
  name: string
  description?: string | null
  owner_id?: string | null
  team_id?: string | null
  visibility: 'private' | 'team' | 'execution'
  created_at: string
  updated_at: string
}

export interface ExperimentScenarioFolderCreateRequest {
  name: string
  description?: string | null
  visibility?: 'private' | 'team' | 'execution'
  team_id?: string | null
}

export interface ExperimentScenarioFolderUpdateRequest {
  name?: string | null
  description?: string | null
  visibility?: 'private' | 'team' | 'execution'
  team_id?: string | null
}

export interface ExperimentScenarioSnapshot {
  id: string
  template_id: string
  template_key: string
  version: number
  status: string
  captured_at: string
  captured_by_id: string
  template_name?: string | null
}

export interface ExperimentScenarioExecutionSummary {
  id: string
  template_id?: string | null
  template_name?: string | null
  template_version?: string | null
  run_by_id?: string | null
  status?: string | null
}

export interface ExperimentScenarioWorkspace {
  execution: ExperimentScenarioExecutionSummary
  snapshots: ExperimentScenarioSnapshot[]
  scenarios: ExperimentScenario[]
  folders: ExperimentScenarioFolder[]
}

export interface ExperimentScenarioCreateRequest {
  name: string
  description?: string | null
  workflow_template_snapshot_id: string
  resource_overrides?: ExperimentPreviewResourceOverrides
  stage_overrides?: ExperimentPreviewStageOverride[]
  folder_id?: string | null
  is_shared?: boolean
  shared_team_ids?: string[]
  expires_at?: string | null
  timeline_event_id?: string | null
}

export interface ExperimentScenarioUpdateRequest {
  name?: string | null
  description?: string | null
  workflow_template_snapshot_id?: string
  resource_overrides?: ExperimentPreviewResourceOverrides
  stage_overrides?: ExperimentPreviewStageOverride[]
  folder_id?: string | null
  is_shared?: boolean
  shared_team_ids?: string[]
  expires_at?: string | null
  timeline_event_id?: string | null
  transfer_owner_id?: string | null
}

export interface ExperimentScenarioCloneRequest {
  name?: string | null
  description?: string | null
}

export interface NarrativeExportAttachmentInput {
  event_id?: string
  file_id?: string
  label?: string | null
}

export interface ExecutionNarrativeAttachment {
  id: string
  evidence_type: 'timeline_event' | 'file'
  reference_id: string
  label?: string | null
  snapshot: Record<string, any>
  file?: FileMeta | null
  created_at: string
}

export interface ExecutionNarrativeApprovalAction {
  id: string
  stage_id: string
  action_type: 'approved' | 'rejected' | 'delegated' | 'reassigned' | 'reset' | 'comment'
  signature?: string | null
  notes?: string | null
  actor: UserIdentity
  delegation_target?: UserIdentity | null
  metadata: Record<string, any>
  created_at: string
}

export interface ExecutionNarrativeApprovalStage {
  id: string
  export_id: string
  sequence_index: number
  name?: string | null
  required_role: string
  status: 'pending' | 'in_progress' | 'approved' | 'rejected' | 'delegated' | 'reset'
  sla_hours?: number | null
  due_at?: string | null
  started_at?: string | null
  completed_at?: string | null
  assignee?: UserIdentity | null
  delegated_to?: UserIdentity | null
  overdue_notified_at?: string | null
  notes?: string | null
  metadata: Record<string, any>
  actions: ExecutionNarrativeApprovalAction[]
}

export interface ExecutionNarrativeExportRecord {
  id: string
  execution_id: string
  version: number
  format: 'markdown'
  generated_at: string
  event_count: number
  content: string
  approval_status: 'pending' | 'approved' | 'rejected'
  approval_signature?: string | null
  approved_at?: string | null
  approval_completed_at?: string | null
  approval_stage_count: number
  workflow_template_id?: string | null
  current_stage?: ExecutionNarrativeApprovalStage | null
  current_stage_started_at?: string | null
  requested_by: UserIdentity
  approved_by?: UserIdentity | null
  notes?: string | null
  approval_stages: ExecutionNarrativeApprovalStage[]
  attachments: ExecutionNarrativeAttachment[]
  metadata: Record<string, any>
  artifact_status: 'queued' | 'processing' | 'ready' | 'retrying' | 'failed' | 'expired'
  artifact_checksum?: string | null
  artifact_error?: string | null
  artifact_file?: FileMeta | null
  artifact_download_path?: string | null
  created_at: string
  updated_at: string
}

export interface ExecutionNarrativeExportHistory {
  exports: ExecutionNarrativeExportRecord[]
}

export interface ExecutionNarrativeStageDefinition {
  name?: string | null
  required_role: string
  assignee_id?: string | null
  delegate_id?: string | null
  sla_hours?: number | null
  metadata?: Record<string, any>
}

export interface ExecutionNarrativeExportCreate {
  notes?: string | null
  metadata?: Record<string, any>
  attachments?: NarrativeExportAttachmentInput[]
  workflow_template_id?: string | null
  approval_stages?: ExecutionNarrativeStageDefinition[]
}

export interface ExecutionNarrativeApprovalRequest {
  status: 'approved' | 'rejected'
  signature: string
  approver_id?: string | null
  stage_id?: string | null
  notes?: string | null
  metadata?: Record<string, any>
}

export interface ExecutionNarrativeDelegationRequest {
  delegate_id: string
  due_at?: string | null
  notes?: string | null
  metadata?: Record<string, any>
}

export interface ExecutionNarrativeStageResetRequest {
  notes?: string | null
  metadata?: Record<string, any>
}

export interface ExperimentRemediationResult {
  action: string
  status: 'executed' | 'scheduled' | 'skipped' | 'failed'
  message?: string | null
}

export interface ExperimentRemediationResponse {
  session: ExperimentExecutionSession
  results: ExperimentRemediationResult[]
}

export interface ExperimentRemediationRequest {
  actions?: string[]
  auto?: boolean
  context?: Record<string, any>
}

export interface ExperimentExecutionSessionCreate {
  template_id: string
  title?: string
  inventory_item_ids?: string[]
  booking_ids?: string[]
  parameters?: Record<string, any>
  auto_create_notebook?: boolean
}

export interface ExperimentStepStatusUpdate {
  status: ExperimentStepState
  started_at?: string | null
  completed_at?: string | null
}

export interface ExperimentTimelinePage {
  events: ExecutionEvent[]
  next_cursor?: string | null
}

// governance template modeling
export interface GovernanceStageBlueprint {
  // purpose: stage blueprint definition consumed by governance UI
  // inputs: governance author ladder builder state
  // outputs: serialized stage blueprint sent to backend
  // status: experimental
  name?: string | null
  required_role: string
  sla_hours?: number | null
  stage_step_indexes?: number[]
  stage_gate_keys?: string[]
  metadata?: Record<string, any>
}

export interface GovernanceTemplate {
  // purpose: unify workflow template payload for admin workspace
  // inputs: backend governance template responses
  // outputs: typed React state for template editor
  // status: experimental
  id: string
  template_key: string
  name: string
  description?: string | null
  version: number
  status: string
  default_stage_sla_hours?: number | null
  permitted_roles: string[]
  stage_blueprint: GovernanceStageBlueprint[]
  forked_from_id?: string | null
  is_latest: boolean
  created_at: string
  updated_at: string
  published_at?: string | null
  created_by_id: string
}

export interface GovernanceTemplateDraft {
  // purpose: capture mutable authoring state before persistence
  // inputs: governance editor form values
  // outputs: payload for template create API
  // status: experimental
  template_key: string
  name: string
  description?: string | null
  default_stage_sla_hours?: number | null
  permitted_roles: string[]
  stage_blueprint: GovernanceStageBlueprint[]
  forked_from_id?: string | null
  publish?: boolean
}

export interface GovernanceTemplateAssignment {
  // purpose: describe assignment targets for governance mapping
  // inputs: backend assignment responses
  // outputs: UI assignment tables
  // status: experimental
  id: string
  template_id: string
  team_id?: string | null
  protocol_template_id?: string | null
  metadata: Record<string, any>
  created_at: string
  created_by_id: string
}
