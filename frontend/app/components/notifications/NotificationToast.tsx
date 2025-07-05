'use client'
import React, { useEffect, useState } from 'react'
import { 
  X, 
  CheckCircle, 
  AlertCircle, 
  Info, 
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
import { cn } from '../../utils/cn'
import type { RealTimeNotification, NotificationCategory } from '../../types/notifications'

interface NotificationToastProps {
  notification: RealTimeNotification
  onDismiss: (id: string) => void
  onAction?: (notification: RealTimeNotification) => void
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

const priorityColors: Record<string, string> = {
  low: 'border-green-200 bg-green-50 text-green-800',
  medium: 'border-yellow-200 bg-yellow-50 text-yellow-800',
  high: 'border-orange-200 bg-orange-50 text-orange-800',
  urgent: 'border-red-200 bg-red-50 text-red-800',
}

const typeIcons: Record<string, React.ComponentType<any>> = {
  notification: Info,
  alert: AlertCircle,
  update: CheckCircle,
}

export const NotificationToast: React.FC<NotificationToastProps> = ({
  notification,
  onDismiss,
  onAction,
  className
}) => {
  const [isVisible, setIsVisible] = useState(false)
  const [isDismissing, setIsDismissing] = useState(false)

  const IconComponent = categoryIcons[notification.category]
  const TypeIcon = typeIcons[notification.type]
  const priorityColor = priorityColors[notification.priority] || priorityColors.medium

  useEffect(() => {
    // Animate in
    const timer = setTimeout(() => setIsVisible(true), 100)
    
    // Auto dismiss after 5 seconds (unless urgent)
    const dismissTimer = setTimeout(() => {
      if (notification.priority !== 'urgent') {
        handleDismiss()
      }
    }, 5000)

    return () => {
      clearTimeout(timer)
      clearTimeout(dismissTimer)
    }
  }, [notification.priority])

  const handleDismiss = () => {
    setIsDismissing(true)
    setTimeout(() => onDismiss(notification.id), 300)
  }

  const handleAction = () => {
    if (onAction) {
      onAction(notification)
    } else if (notification.action_url) {
      window.open(notification.action_url, '_blank')
    }
    handleDismiss()
  }

  return (
    <div
      className={cn(
        'relative w-96 max-w-sm bg-white rounded-lg shadow-lg border border-neutral-200 transform transition-all duration-300 ease-in-out',
        isVisible && !isDismissing ? 'translate-x-0 opacity-100' : 'translate-x-full opacity-0',
        priorityColor,
        className
      )}
    >
      {/* Progress bar for auto-dismiss */}
      {notification.priority !== 'urgent' && (
        <div className="absolute top-0 left-0 right-0 h-1 bg-neutral-200 rounded-t-lg overflow-hidden">
          <div 
            className="h-full bg-current transition-all duration-5000 ease-linear"
            style={{ width: isDismissing ? '0%' : '100%' }}
          />
        </div>
      )}

      <div className="p-4">
        <div className="flex items-start space-x-3">
          {/* Icon */}
          <div className="flex-shrink-0">
            <div className="relative">
              <IconComponent className="w-5 h-5" />
              <TypeIcon className="absolute -bottom-1 -right-1 w-3 h-3 bg-white rounded-full" />
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <h4 className="text-sm font-medium text-current mb-1">
                  {notification.title}
                </h4>
                <p className="text-sm text-current/80">
                  {notification.message}
                </p>
                
                {/* Metadata */}
                <div className="mt-2 flex items-center space-x-2 text-xs text-current/60">
                  <span className="capitalize">{notification.category}</span>
                  <span>•</span>
                  <span className="capitalize">{notification.priority}</span>
                </div>
              </div>

              {/* Dismiss button */}
              <button
                onClick={handleDismiss}
                className="flex-shrink-0 p-1 rounded-md hover:bg-current/10 transition-colors"
                title="Dismiss"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Action buttons */}
            {(onAction || notification.action_url) && (
              <div className="mt-3 flex items-center space-x-2">
                <button
                  onClick={handleAction}
                  className="flex items-center space-x-1 px-3 py-1.5 text-xs font-medium bg-current/10 hover:bg-current/20 rounded-md transition-colors"
                >
                  <ExternalLink className="w-3 h-3" />
                  <span>View Details</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// Toast container for managing multiple toasts
interface ToastContainerProps {
  notifications: RealTimeNotification[]
  onDismiss: (id: string) => void
  onAction?: (notification: RealTimeNotification) => void
  className?: string
}

export const ToastContainer: React.FC<ToastContainerProps> = ({
  notifications,
  onDismiss,
  onAction,
  className
}) => {
  return (
    <div className={cn(
      'fixed top-4 right-4 z-50 space-y-2',
      className
    )}>
      {notifications.map((notification) => (
        <NotificationToast
          key={notification.id}
          notification={notification}
          onDismiss={onDismiss}
          onAction={onAction}
        />
      ))}
    </div>
  )
} 