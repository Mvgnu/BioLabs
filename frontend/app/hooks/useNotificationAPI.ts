'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import type {
  Notification,
  NotificationPreference,
  NotificationStats,
  NotificationFilters
} from '../types/notifications'

// Fetch notifications
export const useNotifications = (filters?: NotificationFilters) => {
  return useQuery({
    queryKey: ['notifications', filters],
    queryFn: async () => {
      const params = new URLSearchParams()
      
      if (filters?.is_read !== undefined) {
        params.append('is_read', filters.is_read.toString())
      }
      if (filters?.category) {
        params.append('category', filters.category)
      }
      if (filters?.date_from) {
        params.append('date_from', filters.date_from)
      }
      if (filters?.date_to) {
        params.append('date_to', filters.date_to)
      }
      
      const response = await api.get(`/api/notifications/?${params.toString()}`)
      return response.data as Notification[]
    },
    staleTime: 30 * 1000, // 30 seconds
  })
}

// Mark notification as read
export const useMarkNotificationRead = () => {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (notificationId: string) => {
      const response = await api.post(`/api/notifications/${notificationId}/read`)
      return response.data as Notification
    },
    onSuccess: (updatedNotification) => {
      // Update the notification in the cache
      queryClient.setQueryData(['notifications'], (oldData: Notification[] | undefined) => {
        if (!oldData) return [updatedNotification]
        return oldData.map(n => n.id === updatedNotification.id ? updatedNotification : n)
      })
      
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
      queryClient.invalidateQueries({ queryKey: ['notification-stats'] })
    },
  })
}

// Fetch notification preferences
export const useNotificationPreferences = () => {
  return useQuery({
    queryKey: ['notification-preferences'],
    queryFn: async () => {
      const response = await api.get('/api/notifications/preferences')
      return response.data as NotificationPreference[]
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

// Update notification preference
export const useUpdateNotificationPreference = () => {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({
      prefType,
      channel,
      enabled
    }: {
      prefType: string
      channel: string
      enabled: boolean
    }) => {
      const response = await api.put(`/api/notifications/preferences/${prefType}/${channel}`, {
        enabled
      })
      return response.data as NotificationPreference
    },
    onSuccess: (updatedPreference) => {
      // Update the preference in the cache
      queryClient.setQueryData(['notification-preferences'], (oldData: NotificationPreference[] | undefined) => {
        if (!oldData) return [updatedPreference]
        
        const exists = oldData.some(p => p.pref_type === updatedPreference.pref_type && p.channel === updatedPreference.channel)
        
        if (exists) {
          return oldData.map(p => 
            p.pref_type === updatedPreference.pref_type && p.channel === updatedPreference.channel
              ? updatedPreference
              : p
          )
        } else {
          return [...oldData, updatedPreference]
        }
      })
    },
  })
}

// Fetch notification statistics
export const useNotificationStats = () => {
  return useQuery({
    queryKey: ['notification-stats'],
    queryFn: async () => {
      const response = await api.get('/api/notifications/stats')
      return response.data as NotificationStats
    },
    staleTime: 60 * 1000, // 1 minute
  })
}

// Bulk operations
export const useMarkAllNotificationsRead = () => {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async () => {
      const response = await api.post('/api/notifications/mark-all-read')
      return response.data
    },
    onSuccess: () => {
      // Invalidate all notification-related queries
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
      queryClient.invalidateQueries({ queryKey: ['notification-stats'] })
    },
  })
}

// Delete notification
export const useDeleteNotification = () => {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (notificationId: string) => {
      const response = await api.delete(`/api/notifications/${notificationId}`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
      queryClient.invalidateQueries({ queryKey: ['notification-stats'] })
    },
  })
}

// Real-time notification polling (fallback for WebSocket)
export const useNotificationPolling = (enabled: boolean = true, interval: number = 30000) => {
  return useQuery({
    queryKey: ['notifications-polling'],
    queryFn: async () => {
      const response = await api.get('/api/notifications/')
      return response.data as Notification[]
    },
    enabled,
    refetchInterval: interval,
    refetchIntervalInBackground: true,
    staleTime: 0, // Always consider data stale for polling
  })
}

// Create notification (for testing or system use)
export const useCreateNotification = () => {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (notification: {
      user_id: string
      message: string
      title?: string
      category?: string
      priority?: string
      meta?: Record<string, any>
    }) => {
      const response = await api.post('/api/notifications/create', notification)
      return response.data as Notification
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
      queryClient.invalidateQueries({ queryKey: ['notification-stats'] })
    },
  })
} 