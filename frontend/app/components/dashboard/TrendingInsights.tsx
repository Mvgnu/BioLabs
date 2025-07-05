'use client'
import React, { useState } from 'react'
import { Card, CardHeader, CardBody, Button, Skeleton } from '../ui'

export interface TrendingItem {
  id: string
  name: string
  count: number
  change?: number
  category?: string
  href?: string
}

export interface TrendingData {
  protocols: TrendingItem[]
  articles: TrendingItem[]
  items: TrendingItem[]
  threads: TrendingItem[]
}

interface TrendingInsightsProps {
  data?: TrendingData
  loading?: boolean
  className?: string
}

type TrendingCategory = keyof TrendingData

const TrendingInsights: React.FC<TrendingInsightsProps> = ({
  data,
  loading = false,
  className
}) => {
  const [activeTab, setActiveTab] = useState<TrendingCategory>('protocols')

  const tabs: { key: TrendingCategory; label: string; icon: React.ReactNode }[] = [
    {
      key: 'protocols',
      label: 'Protocols',
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
        </svg>
      )
    },
    {
      key: 'articles',
      label: 'Articles',
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
        </svg>
      )
    },
    {
      key: 'items',
      label: 'Items',
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
        </svg>
      )
    },
    {
      key: 'threads',
      label: 'Discussions',
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
        </svg>
      )
    }
  ]

  const activeData = data?.[activeTab] || []

  const getTrendingIcon = (change?: number) => {
    if (change === undefined) return null
    
    if (change > 0) {
      return (
        <div className="flex items-center text-success-600">
          <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 17l9.2-9.2M17 17V7H7" />
          </svg>
          <span className="text-xs font-medium">+{change}%</span>
        </div>
      )
    } else if (change < 0) {
      return (
        <div className="flex items-center text-error-600">
          <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 7l-9.2 9.2M7 7v10h10" />
          </svg>
          <span className="text-xs font-medium">{change}%</span>
        </div>
      )
    }
    
    return (
      <div className="flex items-center text-neutral-500">
        <span className="text-xs">—</span>
      </div>
    )
  }

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-neutral-900">Trending</h3>
          <div className="flex items-center space-x-1">
            <svg className="w-4 h-4 text-warning-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.362 5.214A8.252 8.252 0 0112 21 8.25 8.25 0 016.038 7.048 8.287 8.287 0 009 9.6a8.983 8.983 0 013.361-6.867 8.21 8.21 0 003 2.48z" />
            </svg>
            <span className="text-xs text-neutral-500">Last 7 days</span>
          </div>
        </div>
      </CardHeader>
      <CardBody className="pt-0">
        {/* Tab Navigation */}
        <div className="flex space-x-1 mb-4 bg-neutral-100 rounded-lg p-1">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`
                flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium transition-all
                ${activeTab === tab.key
                  ? 'bg-white text-primary-600 shadow-sm'
                  : 'text-neutral-600 hover:text-neutral-900'
                }
              `}
            >
              {tab.icon}
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="space-y-3">
          {loading ? (
            // Loading skeleton
            Array.from({ length: 5 }).map((_, index) => (
              <div key={index} className="flex items-center justify-between p-3 rounded-lg border border-neutral-100">
                <div className="flex items-center space-x-3 flex-1">
                  <div className="flex items-center space-x-3 flex-1">
                    <Skeleton className="w-6 h-6 rounded" />
                    <Skeleton lines={1} className="w-3/4" />
                  </div>
                </div>
                <Skeleton className="w-12 h-4" />
              </div>
            ))
          ) : activeData.length === 0 ? (
            // Empty state
            <div className="text-center py-6">
              <svg className="w-12 h-12 text-neutral-400 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.362 5.214A8.252 8.252 0 0112 21 8.25 8.25 0 016.038 7.048 8.287 8.287 0 009 9.6a8.983 8.983 0 003.361-6.867 8.21 8.21 0 003 2.48z" />
              </svg>
              <p className="text-neutral-500 text-sm">No trending {tabs.find(t => t.key === activeTab)?.label.toLowerCase()}</p>
              <p className="text-neutral-400 text-xs mt-1">Start using the platform to see trends</p>
            </div>
          ) : (
            // Trending list
            activeData.slice(0, 5).map((item, index) => (
              <div
                key={item.id}
                className="flex items-center justify-between p-3 rounded-lg border border-neutral-100 hover:border-neutral-200 hover:bg-neutral-50 transition-colors"
              >
                <div className="flex items-center space-x-3 flex-1 min-w-0">
                  <div className="flex items-center justify-center w-6 h-6 rounded bg-gradient-to-br from-primary-500 to-primary-600 text-white text-xs font-bold">
                    {index + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-neutral-900 truncate">
                      {item.name}
                    </p>
                    {item.category && (
                      <p className="text-xs text-neutral-500 truncate">
                        {item.category}
                      </p>
                    )}
                  </div>
                </div>
                <div className="flex items-center space-x-3">
                  <div className="text-right">
                    <p className="text-sm font-medium text-neutral-900">
                      {item.count.toLocaleString()}
                    </p>
                    {getTrendingIcon(item.change)}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* View More */}
        {!loading && activeData.length > 5 && (
          <div className="mt-4 pt-4 border-t border-neutral-100">
            <Button variant="ghost" size="sm" className="w-full">
              View all {tabs.find(t => t.key === activeTab)?.label.toLowerCase()}
              <svg className="w-4 h-4 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
              </svg>
            </Button>
          </div>
        )}
      </CardBody>
    </Card>
  )
}

export default TrendingInsights