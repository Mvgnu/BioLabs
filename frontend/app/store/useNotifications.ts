import { create } from 'zustand'
import { subscribeWithSelector } from 'zustand/middleware'
import type {
  Notification,
  NotificationPreference,
  NotificationCategory,
  NotificationPriority,
  NotificationStats,
  NotificationFilters,
  RealTimeNotification,
  NotificationEvent
} from '../types/notifications'

interface NotificationState {
  // Notifications
  notifications: Notification[]
  realTimeNotifications: RealTimeNotification[]
  
  // UI State
  isOpen: boolean
  isLoading: boolean
  error: string | null
  
  // Filters and Settings
  filters: NotificationFilters
  preferences: NotificationPreference[]
  
  // Stats
  stats: NotificationStats
  
  // Actions
  setOpen: (open: boolean) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  
  // Notification Management
  addNotification: (notification: Notification) => void
  addRealTimeNotification: (notification: RealTimeNotification) => void
  markAsRead: (id: string) => void
  markAllAsRead: () => void
  deleteNotification: (id: string) => void
  clearAll: () => void
  
  // Filtering
  setFilters: (filters: Partial<NotificationFilters>) => void
  clearFilters: () => void
  
  // Preferences
  setPreferences: (preferences: NotificationPreference[]) => void
  updatePreference: (prefType: string, channel: string, enabled: boolean) => void
  
  // Stats
  updateStats: (stats: NotificationStats) => void
  
  // Real-time
  handleNotificationEvent: (event: NotificationEvent) => void
  
  // Computed
  getFilteredNotifications: () => Notification[]
  getUnreadCount: () => number
  getNotificationsByCategory: (category: NotificationCategory) => Notification[]
  getNotificationsByPriority: (priority: NotificationPriority) => Notification[]
}

const defaultFilters: NotificationFilters = {
  is_read: undefined,
  category: undefined,
  priority: undefined,
  date_from: undefined,
  date_to: undefined,
}

const defaultStats: NotificationStats = {
  total: 0,
  unread: 0,
  by_category: {
    inventory: 0,
    protocols: 0,
    projects: 0,
    bookings: 0,
    system: 0,
    collaboration: 0,
    compliance: 0,
    equipment: 0,
    marketplace: 0,
  },
  by_priority: {
    low: 0,
    medium: 0,
    high: 0,
    urgent: 0,
  },
}

export const useNotifications = create<NotificationState>()(
  subscribeWithSelector((set, get) => ({
    // Initial State
    notifications: [],
    realTimeNotifications: [],
    isOpen: false,
    isLoading: false,
    error: null,
    filters: defaultFilters,
    preferences: [],
    stats: defaultStats,

    // UI Actions
    setOpen: (open) => set({ isOpen: open }),
    setLoading: (loading) => set({ isLoading: loading }),
    setError: (error) => set({ error }),

    // Notification Management
    addNotification: (notification) =>
      set((state) => ({
        notifications: [notification, ...state.notifications],
        stats: {
          ...state.stats,
          total: state.stats.total + 1,
          unread: state.stats.unread + (notification.is_read ? 0 : 1),
          by_category: {
            ...state.stats.by_category,
            [notification.category || 'system']: 
              (state.stats.by_category[notification.category || 'system'] || 0) + 1,
          },
        },
      })),

    addRealTimeNotification: (notification) =>
      set((state) => ({
        realTimeNotifications: [notification, ...state.realTimeNotifications].slice(0, 10), // Keep last 10
      })),

    markAsRead: (id) =>
      set((state) => {
        const updatedNotifications = state.notifications.map((n) =>
          n.id === id ? { ...n, is_read: true } : n
        )
        
        const updatedStats = {
          ...state.stats,
          unread: Math.max(0, state.stats.unread - 1),
        }
        
        return {
          notifications: updatedNotifications,
          stats: updatedStats,
        }
      }),

    markAllAsRead: () =>
      set((state) => ({
        notifications: state.notifications.map((n) => ({ ...n, is_read: true })),
        stats: {
          ...state.stats,
          unread: 0,
        },
      })),

    deleteNotification: (id) =>
      set((state) => {
        const notification = state.notifications.find((n) => n.id === id)
        if (!notification) return state

        const updatedNotifications = state.notifications.filter((n) => n.id !== id)
        const updatedStats = {
          ...state.stats,
          total: Math.max(0, state.stats.total - 1),
          unread: Math.max(0, state.stats.unread - (notification.is_read ? 0 : 1)),
          by_category: {
            ...state.stats.by_category,
            [notification.category || 'system']: 
              Math.max(0, (state.stats.by_category[notification.category || 'system'] || 0) - 1),
          },
        }

        return {
          notifications: updatedNotifications,
          stats: updatedStats,
        }
      }),

    clearAll: () =>
      set({
        notifications: [],
        realTimeNotifications: [],
        stats: defaultStats,
      }),

    // Filtering
    setFilters: (filters) =>
      set((state) => ({
        filters: { ...state.filters, ...filters },
      })),

    clearFilters: () => set({ filters: defaultFilters }),

    // Preferences
    setPreferences: (preferences) => set({ preferences }),
    
    updatePreference: (prefType, channel, enabled) =>
      set((state) => {
        const updatedPreferences = state.preferences.map((p) =>
          p.pref_type === prefType && p.channel === channel
            ? { ...p, enabled }
            : p
        )
        
        // If preference doesn't exist, add it
        const exists = updatedPreferences.some(
          (p) => p.pref_type === prefType && p.channel === channel
        )
        
        if (!exists) {
          updatedPreferences.push({
            id: `${prefType}-${channel}`,
            user_id: '', // Will be set by API
            pref_type: prefType,
            channel,
            enabled,
          })
        }
        
        return { preferences: updatedPreferences }
      }),

    // Stats
    updateStats: (stats) => set({ stats }),

    // Real-time
    handleNotificationEvent: (event) => {
      const { type, data } = event
      
      switch (type) {
        case 'notification_created':
          get().addNotification(data as Notification)
          break
        case 'notification_read':
          get().markAsRead(data.id)
          break
        case 'notification_deleted':
          get().deleteNotification(data.id)
          break
      }
    },

    // Computed
    getFilteredNotifications: () => {
      const { notifications, filters } = get()
      
      return notifications.filter((notification) => {
        if (filters.is_read !== undefined && notification.is_read !== filters.is_read) {
          return false
        }
        
        if (filters.category && notification.category !== filters.category) {
          return false
        }
        
        if (filters.date_from && new Date(notification.created_at) < new Date(filters.date_from)) {
          return false
        }
        
        if (filters.date_to && new Date(notification.created_at) > new Date(filters.date_to)) {
          return false
        }
        
        return true
      })
    },

    getUnreadCount: () => get().stats.unread,

    getNotificationsByCategory: (category) =>
      get().notifications.filter((n) => n.category === category),

    getNotificationsByPriority: (priority) =>
      get().notifications.filter((n) => n.metadata?.priority === priority),
  }))
)

// Subscribe to changes for persistence
useNotifications.subscribe(
  (state) => ({ notifications: state.notifications, preferences: state.preferences }),
  (state) => {
    // Persist to localStorage
    if (typeof window !== 'undefined') {
      localStorage.setItem('biolab-notifications', JSON.stringify(state.notifications))
      localStorage.setItem('biolab-notification-preferences', JSON.stringify(state.preferences))
    }
  }
)

// Initialize from localStorage
if (typeof window !== 'undefined') {
  try {
    const savedNotifications = localStorage.getItem('biolab-notifications')
    const savedPreferences = localStorage.getItem('biolab-notification-preferences')
    
    if (savedNotifications) {
      const notifications = JSON.parse(savedNotifications)
      useNotifications.setState({ notifications })
    }
    
    if (savedPreferences) {
      const preferences = JSON.parse(savedPreferences)
      useNotifications.setState({ preferences })
    }
  } catch (error) {
    console.error('Failed to load notifications from localStorage:', error)
  }
} 