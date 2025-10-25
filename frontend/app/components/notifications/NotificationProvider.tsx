'use client'

import { useCallback, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'

import api from '../../api/client'
import { ToastContainer } from './NotificationToast'
import { useNotifications as useNotificationStore } from '../../store/useNotifications'
import {
  useNotifications as useNotificationsQuery,
  useNotificationStats,
  useNotificationPreferences,
} from '../../hooks/useNotificationAPI'
import { useWebSocket } from '../../hooks/useWebSocket'
import type {
  Notification,
  NotificationEvent,
  RealTimeNotification,
  WebSocketMessage,
} from '../../types/notifications'

// biolab-meta:
// purpose: Bridge API data and WebSocket events into the notification store while rendering global toasts
// inputs: React Query notification datasets, WebSocket messages scoped by team
// outputs: Zustand store hydration, Notification toast rendering
// status: active
// depends_on: frontend/app/store/useNotifications.ts, frontend/app/hooks/useNotificationAPI.ts, frontend/app/hooks/useWebSocket.ts
// related_docs: frontend/app/components/notifications/README.md

type TeamSummary = {
  id: string
  name: string
}

export const NotificationProvider: React.FC = () => {
  const {
    realTimeNotifications,
    addRealTimeNotification,
    removeRealTimeNotification,
    setNotifications,
    updateStats,
    setPreferences,
    handleNotificationEvent,
  } = useNotificationStore((state) => ({
    realTimeNotifications: state.realTimeNotifications,
    addRealTimeNotification: state.addRealTimeNotification,
    removeRealTimeNotification: state.removeRealTimeNotification,
    setNotifications: state.setNotifications,
    updateStats: state.updateStats,
    setPreferences: state.setPreferences,
    handleNotificationEvent: state.handleNotificationEvent,
  }))

  const { data: notificationsData } = useNotificationsQuery()
  const { data: statsData } = useNotificationStats()
  const { data: preferencesData } = useNotificationPreferences()

  useEffect(() => {
    if (notificationsData) {
      setNotifications(notificationsData)
    }
  }, [notificationsData, setNotifications])

  useEffect(() => {
    if (statsData) {
      updateStats(statsData)
    }
  }, [statsData, updateStats])

  useEffect(() => {
    if (preferencesData) {
      setPreferences(preferencesData)
    }
  }, [preferencesData, setPreferences])

  const { data: teamsData } = useQuery({
    queryKey: ['teams'],
    queryFn: async () => {
      const response = await api.get('/api/teams/')
      return response.data as TeamSummary[]
    },
    staleTime: 5 * 60 * 1000,
  })

  const primaryTeamId = teamsData?.[0]?.id ?? ''

  const handleSocketMessage = useCallback(
    (message: WebSocketMessage) => {
      if (!message || typeof message !== 'object' || !message.type) {
        return
      }

      if (message.type.startsWith('notification_') && message.data) {
        const event: NotificationEvent = {
          type: message.type as NotificationEvent['type'],
          data: message.data as Notification,
          timestamp: message.timestamp ?? new Date().toISOString(),
        }
        handleNotificationEvent(event)

        if (message.type === 'notification_created') {
          const source = message.data as Notification
          if (source && source.id) {
            const toast: RealTimeNotification = {
              ...source,
              type: 'notification',
              timestamp: event.timestamp,
            }
            addRealTimeNotification(toast)
          }
        }
      }
    },
    [addRealTimeNotification, handleNotificationEvent]
  )

  useWebSocket(primaryTeamId, handleSocketMessage)

  return (
    <ToastContainer
      notifications={realTimeNotifications}
      onDismiss={removeRealTimeNotification}
    />
  )
}
