'use client'

import { useCallback, useEffect, useMemo, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'

import api from '../../api/client'
import { ToastContainer } from './NotificationToast'
import { useNotifications as useNotificationStore } from '../../store/useNotifications'
import {
  useNotifications as useNotificationsQuery,
  useNotificationStats,
  useNotificationPreferences,
  useNotificationSettings,
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
// inputs: React Query notification datasets, WebSocket messages scoped by teams
// outputs: Zustand store hydration, Notification toast rendering, deduplicated lifecycle events
// status: active
// depends_on: frontend/app/store/useNotifications.ts, frontend/app/hooks/useNotificationAPI.ts, frontend/app/hooks/useWebSocket.ts
// related_docs: frontend/app/components/notifications/README.md

type TeamSummary = {
  id: string
  name: string
}

const MAX_PROCESSED_EVENTS = 200
const PROCESSED_EVENT_TTL_MS = 5 * 60 * 1000

export const NotificationProvider: React.FC = () => {
  const {
    realTimeNotifications,
    addRealTimeNotification,
    removeRealTimeNotification,
    setNotifications,
    updateStats,
    setPreferences,
    setSettings,
    handleNotificationEvent,
    setLoading,
    setError,
  } = useNotificationStore((state) => ({
    realTimeNotifications: state.realTimeNotifications,
    addRealTimeNotification: state.addRealTimeNotification,
    removeRealTimeNotification: state.removeRealTimeNotification,
    setNotifications: state.setNotifications,
    updateStats: state.updateStats,
    setPreferences: state.setPreferences,
    setSettings: state.setSettings,
    handleNotificationEvent: state.handleNotificationEvent,
    setLoading: state.setLoading,
    setError: state.setError,
  }))

  const {
    data: notificationsData,
    isFetching: notificationsFetching,
    error: notificationsError,
    refetch: refetchNotifications,
  } = useNotificationsQuery()
  const { data: statsData, refetch: refetchStats } = useNotificationStats()
  const {
    data: preferencesData,
    refetch: refetchPreferences,
  } = useNotificationPreferences()
  const { data: settingsData, refetch: refetchSettings } = useNotificationSettings()

  useEffect(() => {
    if (notificationsData) {
      setNotifications(notificationsData)
    }
  }, [notificationsData, setNotifications])

  useEffect(() => {
    setLoading(Boolean(notificationsFetching))
  }, [notificationsFetching, setLoading])

  useEffect(() => {
    if (!notificationsError) {
      setError(null)
      return
    }

    if (notificationsError instanceof Error) {
      setError(notificationsError.message)
    } else {
      setError('Failed to load notifications')
    }
  }, [notificationsError, setError])

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

  useEffect(() => {
    if (settingsData) {
      setSettings({
        ...settingsData,
        quiet_hours_start: settingsData.quiet_hours_start
          ? settingsData.quiet_hours_start.slice(0, 5)
          : null,
        quiet_hours_end: settingsData.quiet_hours_end
          ? settingsData.quiet_hours_end.slice(0, 5)
          : null,
      })
    }
  }, [settingsData, setSettings])

  const { data: teamsData } = useQuery({
    queryKey: ['teams'],
    queryFn: async () => {
      const response = await api.get('/api/teams/')
      return response.data as TeamSummary[]
    },
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: true,
    refetchOnReconnect: true,
  })

  const teamIds = useMemo(
    () => (teamsData ?? []).map((team) => team.id).filter((id): id is string => Boolean(id)),
    [teamsData]
  )

  const processedEventKeys = useRef<Map<string, number>>(new Map())
  const previousTeamIdsRef = useRef<string[]>([])

  const resetProcessedEvents = useCallback(() => {
    processedEventKeys.current.clear()
  }, [])

  const pruneProcessedEvents = useCallback(() => {
    const store = processedEventKeys.current
    const expiryThreshold = Date.now() - PROCESSED_EVENT_TTL_MS
    for (const [key, recordedAt] of store.entries()) {
      if (recordedAt < expiryThreshold) {
        store.delete(key)
      }
    }
  }, [])

  const shouldProcessEvent = useCallback(
    (key: string, occurredAt?: string) => {
      const store = processedEventKeys.current
      pruneProcessedEvents()
      if (store.has(key)) {
        return false
      }

      const recordedAt = occurredAt ? new Date(occurredAt).getTime() || Date.now() : Date.now()
      store.set(key, recordedAt)

      if (store.size > MAX_PROCESSED_EVENTS) {
        let oldestKey: string | undefined
        let oldestTimestamp = Number.POSITIVE_INFINITY
        for (const [existingKey, timestamp] of store.entries()) {
          if (timestamp < oldestTimestamp) {
            oldestTimestamp = timestamp
            oldestKey = existingKey
          }
        }
        if (oldestKey) {
          store.delete(oldestKey)
        }
      }
      return true
    },
    [pruneProcessedEvents]
  )

  const handleSocketMessage = useCallback(
    (message: WebSocketMessage, _context: { teamId: string }) => {
      if (!message || typeof message !== 'object' || !message.type) {
        return
      }

      if (message.type.startsWith('notification_') && message.data) {
        const event: NotificationEvent = {
          type: message.type as NotificationEvent['type'],
          data: message.data as Notification,
          timestamp: message.timestamp ?? new Date().toISOString(),
        }

        const eventKey = `${event.type}:${event.data?.id ?? ''}:${event.timestamp}`
        if (!shouldProcessEvent(eventKey, event.timestamp)) {
          return
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
    [addRealTimeNotification, handleNotificationEvent, shouldProcessEvent]
  )

  useWebSocket(teamIds, handleSocketMessage)

  const replayFromSource = useCallback(() => {
    resetProcessedEvents()
    void refetchNotifications()
    void refetchStats()
    void refetchSettings()
  }, [refetchNotifications, refetchSettings, refetchStats, resetProcessedEvents])

  useEffect(() => {
    const previousTeamIds = previousTeamIdsRef.current
    const membershipChanged =
      previousTeamIds.length > 0 &&
      (teamIds.some((id) => !previousTeamIds.includes(id)) ||
        previousTeamIds.some((id) => !teamIds.includes(id)))

    if (membershipChanged) {
      replayFromSource()
      void refetchPreferences()
      void refetchSettings()
    }

    previousTeamIdsRef.current = teamIds
  }, [teamIds, replayFromSource, refetchPreferences, refetchSettings])

  useEffect(() => {
    if (typeof window === 'undefined' || typeof document === 'undefined') {
      return undefined
    }

    const handleResume = () => {
      replayFromSource()
      void refetchPreferences()
      void refetchSettings()
    }

    const handleVisibility = () => {
      if (document.visibilityState === 'visible') {
        handleResume()
      }
    }

    window.addEventListener('focus', handleResume)
    window.addEventListener('online', handleResume)
    document.addEventListener('visibilitychange', handleVisibility)

    return () => {
      window.removeEventListener('focus', handleResume)
      window.removeEventListener('online', handleResume)
      document.removeEventListener('visibilitychange', handleVisibility)
    }
  }, [replayFromSource, refetchPreferences, refetchSettings])


  return (
    <ToastContainer
      notifications={realTimeNotifications}
      onDismiss={removeRealTimeNotification}
    />
  )
}
