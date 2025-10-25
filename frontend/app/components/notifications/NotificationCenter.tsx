'use client'
import React, { useState, useEffect } from 'react'
import { 
  X, 
  Search, 
  Filter, 
  CheckCircle, 
  Trash2, 
  Settings,
  Bell,
  Package,
  FlaskConical,
  FolderOpen,
  Calendar,
  Settings as SettingsIcon,
  Users,
  Shield,
  Wrench,
  Store,
  ChevronDown,
  ChevronUp,
  AlertCircle
} from 'lucide-react'
import { useNotifications } from '../../store/useNotifications'
import { useMarkAllNotificationsRead } from '../../hooks/useNotificationAPI'
import { NotificationItem } from './NotificationItem'
import { NotificationSettingsPanel } from './NotificationSettingsPanel'
import { cn } from '../../utils/cn'
import type { Notification, NotificationCategory } from '../../types/notifications'

interface NotificationCenterProps {
  className?: string
}

const categoryOptions: { value: NotificationCategory; label: string; icon: React.ComponentType<any> }[] = [
  { value: 'inventory', label: 'Inventory', icon: Package },
  { value: 'protocols', label: 'Protocols', icon: FlaskConical },
  { value: 'projects', label: 'Projects', icon: FolderOpen },
  { value: 'bookings', label: 'Bookings', icon: Calendar },
  { value: 'system', label: 'System', icon: SettingsIcon },
  { value: 'collaboration', label: 'Collaboration', icon: Users },
  { value: 'compliance', label: 'Compliance', icon: Shield },
  { value: 'equipment', label: 'Equipment', icon: Wrench },
  { value: 'marketplace', label: 'Marketplace', icon: Store },
]

export const NotificationCenter: React.FC<NotificationCenterProps> = ({
  className
}) => {
  const {
    isOpen,
    setOpen,
    filters,
    setFilters,
    clearFilters,
    markAllAsRead,
    clearAll,
    getFilteredNotifications,
    getUnreadCount,
    stats,
    isLoading,
    error
  } = useNotifications()
  const markAllAsReadMutation = useMarkAllNotificationsRead()

  const [searchTerm, setSearchTerm] = useState('')
  const [showFilters, setShowFilters] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState<NotificationCategory | undefined>(filters.category)
  const [showSettings, setShowSettings] = useState(false)

  const unreadCount = getUnreadCount()
  const filteredNotifications = getFilteredNotifications()

  // Filter notifications by search term
  const searchFilteredNotifications = filteredNotifications.filter(notification =>
    notification.message.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const handleCategoryChange = (category: NotificationCategory | undefined) => {
    setSelectedCategory(category)
    setFilters({ category })
  }

  const handleMarkAllAsRead = async () => {
    try {
      await markAllAsReadMutation.mutateAsync()
      markAllAsRead()
    } catch (error) {
      console.error('Failed to mark all notifications as read:', error)
    }
  }

  const handleNotificationAction = (notification: Notification) => {
    // Handle notification action (e.g., navigate to related page)
    if (notification.action_url) {
      window.open(notification.action_url, '_blank')
    }
  }

  // Close notification center when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Element
      if (isOpen && !target.closest('.notification-center')) {
        setOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen, setOpen])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/20" />
      
      {/* Notification Center */}
      <div className={cn(
        'absolute right-4 top-16 w-96 max-h-[calc(100vh-6rem)] bg-white rounded-lg shadow-xl border border-neutral-200 flex flex-col notification-center relative overflow-hidden',
        className
      )}>
        {showSettings && (
          <NotificationSettingsPanel onClose={() => setShowSettings(false)} />
        )}
        <div className={cn('flex h-full flex-col', showSettings ? 'hidden' : '')}>
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-neutral-200">
          <div className="flex items-center space-x-2">
            <Bell className="w-5 h-5 text-neutral-600" />
            <h3 className="text-lg font-semibold text-neutral-900">Notifications</h3>
            {unreadCount > 0 && (
              <span className="px-2 py-0.5 bg-blue-100 text-blue-800 text-xs font-medium rounded-full">
                {unreadCount}
              </span>
            )}
          </div>
          
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="p-1 rounded-md hover:bg-neutral-100 transition-colors"
              title="Toggle filters"
            >
              <Filter className="w-4 h-4 text-neutral-600" />
            </button>
            
            <button
              onClick={() => setOpen(false)}
              className="p-1 rounded-md hover:bg-neutral-100 transition-colors"
              title="Close"
            >
              <X className="w-4 h-4 text-neutral-600" />
            </button>
          </div>
        </div>

        {/* Search */}
        <div className="p-4 border-b border-neutral-200">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-neutral-400" />
            <input
              type="text"
              placeholder="Search notifications..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-neutral-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>
        </div>

        {/* Filters */}
        {showFilters && (
          <div className="p-4 border-b border-neutral-200 bg-neutral-50">
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-2">
                  Category
                </label>
                <div className="grid grid-cols-3 gap-2">
                  <button
                    onClick={() => handleCategoryChange(undefined)}
                    className={cn(
                      'flex items-center space-x-2 px-3 py-2 text-sm rounded-md border transition-colors',
                      !selectedCategory
                        ? 'bg-primary-50 border-primary-200 text-primary-700'
                        : 'bg-white border-neutral-300 text-neutral-700 hover:bg-neutral-50'
                    )}
                  >
                    <span>All</span>
                  </button>
                  
                  {categoryOptions.map(({ value, label, icon: Icon }) => (
                    <button
                      key={value}
                      onClick={() => handleCategoryChange(value)}
                      className={cn(
                        'flex items-center space-x-2 px-3 py-2 text-sm rounded-md border transition-colors',
                        selectedCategory === value
                          ? 'bg-primary-50 border-primary-200 text-primary-700'
                          : 'bg-white border-neutral-300 text-neutral-700 hover:bg-neutral-50'
                      )}
                    >
                      <Icon className="w-4 h-4" />
                      <span>{label}</span>
                    </button>
                  ))}
                </div>
              </div>
              
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setFilters({ is_read: false })}
                  className={cn(
                    'px-3 py-1 text-sm rounded-md border transition-colors',
                    filters.is_read === false
                      ? 'bg-blue-50 border-blue-200 text-blue-700'
                      : 'bg-white border-neutral-300 text-neutral-700 hover:bg-neutral-50'
                  )}
                >
                  Unread only
                </button>
                
                <button
                  onClick={clearFilters}
                  className="px-3 py-1 text-sm text-neutral-600 hover:text-neutral-800 transition-colors"
                >
                  Clear filters
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Actions */}
        {filteredNotifications.length > 0 && (
          <div className="flex items-center justify-between p-4 border-b border-neutral-200 bg-neutral-50">
            <div className="text-sm text-neutral-600">
              {searchFilteredNotifications.length} of {filteredNotifications.length} notifications
            </div>
            
            <div className="flex items-center space-x-2">
              {unreadCount > 0 && (
                <button
                  onClick={handleMarkAllAsRead}
                  disabled={markAllAsReadMutation.isPending}
                  className="flex items-center space-x-1 px-3 py-1 text-sm text-green-700 hover:bg-green-50 rounded-md transition-colors disabled:opacity-50"
                >
                  <CheckCircle className="w-4 h-4" />
                  <span>Mark all read</span>
                </button>
              )}
              
              <button
                onClick={clearAll}
                className="flex items-center space-x-1 px-3 py-1 text-sm text-red-700 hover:bg-red-50 rounded-md transition-colors"
              >
                <Trash2 className="w-4 h-4" />
                <span>Clear all</span>
              </button>
            </div>
          </div>
        )}

        {/* Notifications List */}
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="p-8 text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500 mx-auto"></div>
              <p className="mt-2 text-sm text-neutral-600">Loading notifications...</p>
            </div>
          ) : error ? (
            <div className="p-8 text-center">
              <AlertCircle className="w-8 h-8 text-red-500 mx-auto" />
              <p className="mt-2 text-sm text-red-600">Failed to load notifications</p>
            </div>
          ) : searchFilteredNotifications.length === 0 ? (
            <div className="p-8 text-center">
              <Bell className="w-8 h-8 text-neutral-400 mx-auto" />
              <p className="mt-2 text-sm text-neutral-600">
                {searchTerm ? 'No notifications match your search' : 'No notifications yet'}
              </p>
            </div>
          ) : (
            <div className="divide-y divide-neutral-100">
              {searchFilteredNotifications.map((notification) => (
                <NotificationItem
                  key={notification.id}
                  notification={notification}
                  onAction={handleNotificationAction}
                />
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-neutral-200 bg-neutral-50">
          <div className="flex items-center justify-between text-sm text-neutral-600">
            <div className="flex items-center space-x-4">
              <span>Total: {stats.total}</span>
              <span>Unread: {stats.unread}</span>
            </div>
            
            <button
              onClick={() => setShowSettings(true)}
              className="flex items-center space-x-1 text-neutral-600 hover:text-neutral-800 transition-colors"
            >
              <Settings className="w-4 h-4" />
              <span>Settings</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
} 