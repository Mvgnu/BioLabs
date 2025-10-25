'use client'
import React from 'react'
import { 
  CheckCircle, 
  AlertCircle, 
  Info, 
  X, 
  Clock, 
  ExternalLink,
  Package,
  FlaskConical,
  FolderOpen,
  Calendar,
  Settings,
  Users,
  Shield,
  Wrench,
  Store
} from 'lucide-react'
import { useNotifications } from '../../store/useNotifications'
import { useMarkNotificationRead } from '../../hooks/useNotificationAPI'
import { cn } from '../../utils/cn'
import type { Notification, NotificationCategory } from '../../types/notifications'

interface NotificationItemProps {
  notification: Notification
  onAction?: (notification: Notification) => void
  className?: string
}

const categoryIcons: Record<NotificationCategory, React.ComponentType<any>> = {
  inventory: Package,
  protocols: FlaskConical,
  projects: FolderOpen,
  bookings: Calendar,
  system: Settings,
  collaboration: Users,
  compliance: Shield,
  equipment: Wrench,
  marketplace: Store,
}

const categoryColors: Record<NotificationCategory, string> = {
  inventory: 'text-blue-600 bg-blue-50',
  protocols: 'text-purple-600 bg-purple-50',
  projects: 'text-green-600 bg-green-50',
  bookings: 'text-orange-600 bg-orange-50',
  system: 'text-gray-600 bg-gray-50',
  collaboration: 'text-indigo-600 bg-indigo-50',
  compliance: 'text-red-600 bg-red-50',
  equipment: 'text-yellow-600 bg-yellow-50',
  marketplace: 'text-pink-600 bg-pink-50',
}

export const NotificationItem: React.FC<NotificationItemProps> = ({
  notification,
  onAction,
  className
}) => {
  const { markAsRead, deleteNotification } = useNotifications()
  const markAsReadMutation = useMarkNotificationRead()

  const IconComponent = categoryIcons[notification.category || 'system']
  const colorClasses = categoryColors[notification.category || 'system']

  const handleMarkAsRead = async () => {
    if (!notification.is_read) {
      try {
        await markAsReadMutation.mutateAsync(notification.id)
        markAsRead(notification.id)
      } catch (error) {
        console.error('Failed to mark notification as read:', error)
      }
    }
  }

  const handleDelete = () => {
    deleteNotification(notification.id)
  }

  const handleAction = () => {
    if (onAction) {
      onAction(notification)
    } else if (notification.action_url) {
      window.open(notification.action_url, '_blank')
    }
  }

  const formatTime = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffInMinutes = Math.floor((now.getTime() - date.getTime()) / (1000 * 60))

    if (diffInMinutes < 1) return 'Just now'
    if (diffInMinutes < 60) return `${diffInMinutes}m ago`
    if (diffInMinutes < 1440) return `${Math.floor(diffInMinutes / 60)}h ago`
    return `${Math.floor(diffInMinutes / 1440)}d ago`
  }

  return (
    <div
      className={cn(
        'group relative p-4 border-b border-neutral-100 hover:bg-neutral-50 transition-colors',
        !notification.is_read && 'bg-blue-50/50',
        className
      )}
    >
      <div className="flex items-start space-x-3">
        {/* Category Icon */}
        <div className={cn(
          'flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center',
          colorClasses
        )}>
          <IconComponent className="w-4 h-4" />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <p className={cn(
                'text-sm text-neutral-900',
                notification.is_read ? 'font-normal' : 'font-medium'
              )}>
                {notification.message}
              </p>
              
              {/* Metadata */}
              {notification.meta && (
                <div className="mt-1 flex items-center space-x-2 text-xs text-neutral-500">
                  {notification.meta.priority && (
                    <span className={cn(
                      'px-2 py-0.5 rounded-full text-xs font-medium',
                      {
                        'bg-green-100 text-green-800': notification.meta.priority === 'low',
                        'bg-yellow-100 text-yellow-800': notification.meta.priority === 'medium',
                        'bg-orange-100 text-orange-800': notification.meta.priority === 'high',
                        'bg-red-100 text-red-800': notification.meta.priority === 'urgent',
                      }
                    )}>
                      {notification.meta.priority}
                    </span>
                  )}
                  
                  <div className="flex items-center space-x-1">
                    <Clock className="w-3 h-3" />
                    <span>{formatTime(notification.created_at)}</span>
                  </div>
                </div>
              )}
            </div>

            {/* Actions */}
            <div className="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
              {!notification.is_read && (
                <button
                  onClick={handleMarkAsRead}
                  className="p-1 rounded-md hover:bg-neutral-200 transition-colors"
                  title="Mark as read"
                  disabled={markAsReadMutation.isPending}
                >
                  <CheckCircle className="w-4 h-4 text-green-600" />
                </button>
              )}
              
              {notification.action_url && (
                <button
                  onClick={handleAction}
                  className="p-1 rounded-md hover:bg-neutral-200 transition-colors"
                  title="View details"
                >
                  <ExternalLink className="w-4 h-4 text-blue-600" />
                </button>
              )}
              
              <button
                onClick={handleDelete}
                className="p-1 rounded-md hover:bg-neutral-200 transition-colors"
                title="Delete notification"
              >
                <X className="w-4 h-4 text-neutral-500" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Unread indicator */}
      {!notification.is_read && (
        <div className="absolute left-0 top-0 bottom-0 w-1 bg-blue-500 rounded-r-sm" />
      )}
    </div>
  )
} 