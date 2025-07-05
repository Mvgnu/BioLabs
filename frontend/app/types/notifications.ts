export interface Notification {
  id: string
  user_id: string
  message: string
  title?: string
  category?: string
  priority: string
  is_read: boolean
  meta: Record<string, any>
  created_at: string
}

export interface NotificationPreference {
  id: string
  user_id: string
  pref_type: string
  channel: string
  enabled: boolean
}

export interface NotificationStats {
  total: number
  unread: number
  by_category: {
    inventory: number
    protocols: number
    projects: number
    bookings: number
    system: number
    collaboration: number
    compliance: number
    equipment: number
    marketplace: number
  }
  by_priority: {
    low: number
    medium: number
    high: number
    urgent: number
  }
}

export interface NotificationFilters {
  is_read?: boolean
  category?: string
  date_from?: string
  date_to?: string
}

export interface NotificationCreate {
  user_id: string
  message: string
  title?: string
  category?: string
  priority?: string
  meta?: Record<string, any>
}

export interface NotificationSettings {
  email_enabled: boolean
  push_enabled: boolean
  in_app_enabled: boolean
  digest_frequency: 'immediate' | 'hourly' | 'daily' | 'weekly'
  quiet_hours: {
    enabled: boolean
    start: string
    end: string
  }
  categories: Record<string, {
    email: boolean
    push: boolean
    in_app: boolean
  }>
}

// Real-time event types
export interface NotificationEvent {
  type: 'notification_created' | 'notification_read' | 'notification_deleted'
  data: Notification
  timestamp: string
}

export interface WebSocketMessage {
  type: string
  data: any
  timestamp: string
}

// Contextual notification types
export interface InventoryNotification extends Notification {
  category: 'inventory'
  metadata: {
    item_id?: string
    item_name?: string
    action?: 'low_stock' | 'expired' | 'maintenance_due' | 'location_changed'
    quantity?: number
    threshold?: number
  }
}

export interface ProtocolNotification extends Notification {
  category: 'protocols'
  metadata: {
    protocol_id?: string
    protocol_name?: string
    action?: 'execution_completed' | 'execution_failed' | 'merge_request' | 'updated'
    status?: string
    error?: string
  }
}

export interface ProjectNotification extends Notification {
  category: 'projects'
  metadata: {
    project_id?: string
    project_name?: string
    action?: 'task_assigned' | 'task_completed' | 'deadline_approaching' | 'member_added'
    task_id?: string
    task_name?: string
    due_date?: string
  }
}

export interface BookingNotification extends Notification {
  category: 'bookings'
  metadata: {
    booking_id?: string
    resource_id?: string
    resource_name?: string
    action?: 'created' | 'cancelled' | 'modified' | 'reminder'
    start_time?: string
    end_time?: string
  }
}

export interface SystemNotification extends Notification {
  category: 'system'
  metadata: {
    action?: 'maintenance' | 'update' | 'backup' | 'error'
    severity?: 'info' | 'warning' | 'error' | 'critical'
    component?: string
  }
}

export interface CollaborationNotification extends Notification {
  category: 'collaboration'
  metadata: {
    action?: 'comment' | 'mention' | 'share' | 'invite'
    target_type?: 'item' | 'protocol' | 'project' | 'notebook'
    target_id?: string
    target_name?: string
    user_id?: string
    user_name?: string
  }
} 