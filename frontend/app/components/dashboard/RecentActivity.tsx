'use client'
import React from 'react'
import Link from 'next/link'
import { Card, CardHeader, CardBody, Skeleton } from '../ui'

export interface ActivityItem {
  id: string
  type: 'inventory' | 'protocol' | 'notebook' | 'project' | 'comment' | 'file' | 'compliance'
  title: string
  description: string
  user?: string
  timestamp: string
  href?: string
  status?: 'success' | 'warning' | 'error' | 'pending'
}

interface RecentActivityProps {
  activities?: ActivityItem[]
  loading?: boolean
  showAll?: boolean
  onShowAll?: () => void
  className?: string
}

const RecentActivity: React.FC<RecentActivityProps> = ({
  activities = [],
  loading = false,
  showAll = false,
  onShowAll,
  className
}) => {
  const getActivityIcon = (type: ActivityItem['type']) => {
    const iconClasses = "w-4 h-4"
    
    switch (type) {
      case 'inventory':
        return (
          <svg className={iconClasses} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
          </svg>
        )
      case 'protocol':
        return (
          <svg className={iconClasses} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
          </svg>
        )
      case 'notebook':
        return (
          <svg className={iconClasses} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L6.832 19.82a4.5 4.5 0 01-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 011.13-1.897L16.863 4.487zm0 0L19.5 7.125" />
          </svg>
        )
      case 'project':
        return (
          <svg className={iconClasses} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m6.75 18.75H8.25A2.25 2.25 0 016 18.75V3a.75.75 0 01.75-.75h7.5a.75.75 0 01.75.75v4.5c0 .414.336.75.75.75H18a.75.75 0 01.75.75v10.5z" />
          </svg>
        )
      case 'comment':
        return (
          <svg className={iconClasses} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
          </svg>
        )
      case 'file':
        return (
          <svg className={iconClasses} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m3.75 9v6m3-3l-3 3-3-3" />
          </svg>
        )
      case 'compliance':
        return (
          <svg className={iconClasses} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.623 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
          </svg>
        )
      default:
        return (
          <svg className={iconClasses} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
          </svg>
        )
    }
  }

  const getActivityColor = (type: ActivityItem['type']) => {
    switch (type) {
      case 'inventory': return 'text-primary-600 bg-primary-50'
      case 'protocol': return 'text-secondary-600 bg-secondary-50'
      case 'notebook': return 'text-info-600 bg-info-50'
      case 'project': return 'text-warning-600 bg-warning-50'
      case 'comment': return 'text-neutral-600 bg-neutral-50'
      case 'file': return 'text-success-600 bg-success-50'
      case 'compliance': return 'text-error-600 bg-error-50'
      default: return 'text-neutral-600 bg-neutral-50'
    }
  }

  const getStatusBadge = (status?: ActivityItem['status']) => {
    if (!status) return null

    const statusClasses = {
      success: 'bg-success-100 text-success-800',
      warning: 'bg-warning-100 text-warning-800',
      error: 'bg-error-100 text-error-800',
      pending: 'bg-neutral-100 text-neutral-800'
    }

    const statusLabels = {
      success: 'Completed',
      warning: 'Warning',
      error: 'Failed',
      pending: 'Pending'
    }

    return (
      <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${statusClasses[status]}`}>
        {statusLabels[status]}
      </span>
    )
  }

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diffInMinutes = Math.floor((now.getTime() - date.getTime()) / (1000 * 60))

    if (diffInMinutes < 1) return 'Just now'
    if (diffInMinutes < 60) return `${diffInMinutes}m ago`
    
    const diffInHours = Math.floor(diffInMinutes / 60)
    if (diffInHours < 24) return `${diffInHours}h ago`
    
    const diffInDays = Math.floor(diffInHours / 24)
    if (diffInDays < 7) return `${diffInDays}d ago`
    
    return date.toLocaleDateString()
  }

  const displayedActivities = showAll ? activities : activities.slice(0, 5)

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-neutral-900">Recent Activity</h3>
          <div className="flex items-center space-x-2">
            <div className="flex items-center space-x-1">
              <div className="w-2 h-2 bg-success-500 rounded-full animate-pulse"></div>
              <span className="text-xs text-neutral-500">Live</span>
            </div>
            {!showAll && activities.length > 5 && (
              <button
                onClick={onShowAll}
                className="text-sm text-primary-600 hover:text-primary-700 font-medium"
              >
                View all
              </button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardBody className="pt-0">
        <div className="space-y-4">
          {loading ? (
            // Loading skeleton
            Array.from({ length: 3 }).map((_, index) => (
              <div key={index} className="flex items-start space-x-3">
                <div className="w-8 h-8 bg-neutral-200 rounded-full animate-pulse"></div>
                <div className="flex-1 space-y-2">
                  <Skeleton lines={1} className="w-3/4" />
                  <Skeleton lines={1} className="w-1/2" />
                </div>
              </div>
            ))
          ) : displayedActivities.length === 0 ? (
            // Empty state
            <div className="text-center py-6">
              <svg className="w-12 h-12 text-neutral-400 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5m8.5 3v6.75" />
              </svg>
              <p className="text-neutral-500 text-sm">No recent activity</p>
              <p className="text-neutral-400 text-xs mt-1">Start working to see updates here</p>
            </div>
          ) : (
            // Activity list
            displayedActivities.map((activity) => {
              const ActivityContent = (
                <div className="flex items-start space-x-3 p-3 rounded-lg hover:bg-neutral-50 transition-colors">
                  <div className={`p-2 rounded-full ${getActivityColor(activity.type)}`}>
                    {getActivityIcon(activity.type)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-neutral-900 truncate">
                          {activity.title}
                        </p>
                        <p className="text-sm text-neutral-600 mt-1">
                          {activity.description}
                        </p>
                        {activity.user && (
                          <p className="text-xs text-neutral-500 mt-1">
                            by {activity.user}
                          </p>
                        )}
                      </div>
                      <div className="flex flex-col items-end space-y-1 ml-3">
                        {getStatusBadge(activity.status)}
                        <span className="text-xs text-neutral-400">
                          {formatTimestamp(activity.timestamp)}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              )

              if (activity.href) {
                return (
                  <Link key={activity.id} href={activity.href}>
                    {ActivityContent}
                  </Link>
                )
              }

              return <div key={activity.id}>{ActivityContent}</div>
            })
          )}
        </div>
      </CardBody>
    </Card>
  )
}

export default RecentActivity