import { beforeEach, describe, expect, it } from 'vitest'

import { useNotifications } from '../useNotifications'
import type { NotificationEvent } from '../../types/notifications'

const baseNotification = {
  id: 'notif-1',
  user_id: 'user-1',
  message: 'Multi-team event payload',
  title: 'Lab update',
  category: 'system',
  priority: 'medium',
  is_read: false,
  meta: {},
  created_at: '2024-01-01T00:00:00.000Z',
}

const resetStore = () => {
  useNotifications.setState({
    notifications: [],
    realTimeNotifications: [],
    isOpen: false,
    isLoading: false,
    error: null,
    filters: {
      is_read: undefined,
      category: undefined,
      priority: undefined,
      date_from: undefined,
      date_to: undefined,
    },
    preferences: [],
    stats: {
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
    },
  })
}

describe('useNotifications store', () => {
  beforeEach(() => {
    resetStore()
  })

  it('adds new notifications once even when duplicate creation events arrive', () => {
    const createdEvent: NotificationEvent = {
      type: 'notification_created',
      data: baseNotification,
      timestamp: '2024-01-01T00:00:00.000Z',
    }

    const { handleNotificationEvent } = useNotifications.getState()
    handleNotificationEvent(createdEvent)
    handleNotificationEvent(createdEvent)

    const { notifications, stats } = useNotifications.getState()
    expect(notifications).toHaveLength(1)
    expect(stats.total).toBe(1)
    expect(stats.unread).toBe(1)
  })

  it('updates read status and unread counts from read events', () => {
    const createdEvent: NotificationEvent = {
      type: 'notification_created',
      data: baseNotification,
      timestamp: '2024-01-01T00:00:00.000Z',
    }

    const readEvent: NotificationEvent = {
      type: 'notification_read',
      data: { ...baseNotification, is_read: true },
      timestamp: '2024-01-01T01:00:00.000Z',
    }

    const { handleNotificationEvent } = useNotifications.getState()
    handleNotificationEvent(createdEvent)
    handleNotificationEvent(readEvent)

    const { notifications, stats } = useNotifications.getState()
    expect(notifications[0].is_read).toBe(true)
    expect(stats.unread).toBe(0)
  })

  it('removes notifications and stats when delete events arrive', () => {
    const createdEvent: NotificationEvent = {
      type: 'notification_created',
      data: baseNotification,
      timestamp: '2024-01-01T00:00:00.000Z',
    }

    const deleteEvent: NotificationEvent = {
      type: 'notification_deleted',
      data: baseNotification,
      timestamp: '2024-01-01T02:00:00.000Z',
    }

    const { handleNotificationEvent } = useNotifications.getState()
    handleNotificationEvent(createdEvent)
    handleNotificationEvent(deleteEvent)

    const { notifications, stats } = useNotifications.getState()
    expect(notifications).toHaveLength(0)
    expect(stats.total).toBe(0)
    expect(stats.unread).toBe(0)
  })
})
