'use client'
import React from 'react'
import { Bell } from 'lucide-react'
import { useNotifications } from '../../store/useNotifications'
import { cn } from '../../utils/cn'

interface NotificationBellProps {
  className?: string
  size?: 'sm' | 'md' | 'lg'
}

export const NotificationBell: React.FC<NotificationBellProps> = ({
  className,
  size = 'md'
}) => {
  const { isOpen, setOpen, getUnreadCount } = useNotifications()
  const unreadCount = getUnreadCount()

  const sizeClasses = {
    sm: 'w-5 h-5',
    md: 'w-6 h-6',
    lg: 'w-8 h-8'
  }

  const badgeSizeClasses = {
    sm: 'w-4 h-4 text-xs',
    md: 'w-5 h-5 text-xs',
    lg: 'w-6 h-6 text-sm'
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!isOpen)}
        className={cn(
          'relative p-2 rounded-lg hover:bg-neutral-100 transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2',
          className
        )}
        aria-label={`Notifications (${unreadCount} unread)`}
      >
        <Bell
          className={cn(
            'text-neutral-600 transition-colors',
            sizeClasses[size]
          )}
        />

        {/* Unread count badge */}
        {unreadCount > 0 && (
          <div
            className={cn(
              'absolute -top-1 -right-1 bg-error-500 text-white rounded-full flex items-center justify-center font-medium',
              badgeSizeClasses[size]
            )}
          >
            {unreadCount > 99 ? '99+' : unreadCount}
          </div>
        )}

        {/* Pulse animation for urgent notifications */}
        {unreadCount > 0 && (
          <div className="absolute -top-1 -right-1 w-2 h-2 bg-error-500 rounded-full animate-ping opacity-75" />
        )}
      </button>
    </div>
  )
} 