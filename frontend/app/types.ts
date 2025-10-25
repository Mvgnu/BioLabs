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
  item_id: string
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
}

export interface ExperimentExecutionSession {
  execution: ProtocolExecution
  protocol: ProtocolTemplate
  notebook_entries: NotebookEntry[]
  inventory_items: InventoryItem[]
  bookings: Booking[]
  steps: ExperimentStepStatus[]
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
