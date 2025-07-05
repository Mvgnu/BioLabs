'use client'
import { Card, CardBody } from '../ui'
import { ReactNode } from 'react'

interface MetricCardProps {
  title: string
  value: string | number
  change?: number
  changeLabel?: string
  icon?: ReactNode
  trend?: 'up' | 'down' | 'neutral'
  loading?: boolean
  className?: string
  onClick?: () => void
}

export default function MetricCard({
  title,
  value,
  change,
  changeLabel,
  icon,
  trend,
  loading,
  className,
  onClick
}: MetricCardProps) {
  const getTrendColor = () => {
    switch (trend) {
      case 'up':
        return 'text-success-600'
      case 'down':
        return 'text-error-600'
      default:
        return 'text-neutral-600'
    }
  }

  const getTrendIcon = () => {
    switch (trend) {
      case 'up':
        return (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
          </svg>
        )
      case 'down':
        return (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6" />
          </svg>
        )
      default:
        return null
    }
  }

  return (
    <Card 
      className={`${className} ${onClick ? 'cursor-pointer hover:shadow-md transition-shadow' : ''}`}
      onClick={onClick}
    >
      <CardBody className="p-6">
        {loading ? (
          <div className="animate-pulse">
            <div className="flex items-center justify-between mb-4">
              <div className="h-4 bg-neutral-200 rounded w-24"></div>
              <div className="h-8 w-8 bg-neutral-200 rounded-full"></div>
            </div>
            <div className="h-8 bg-neutral-200 rounded w-32 mb-2"></div>
            <div className="h-3 bg-neutral-200 rounded w-20"></div>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-medium text-neutral-600">{title}</h3>
              {icon && (
                <div className="p-2 bg-primary-50 rounded-lg">
                  <div className="w-5 h-5 text-primary-600">{icon}</div>
                </div>
              )}
            </div>
            
            <div className="mb-2">
              <p className="text-2xl font-bold text-neutral-900">
                {typeof value === 'number' ? value.toLocaleString() : value}
              </p>
            </div>
            
            {(change !== undefined || changeLabel) && (
              <div className="flex items-center space-x-2">
                {change !== undefined && (
                  <div className={`flex items-center space-x-1 ${getTrendColor()}`}>
                    {getTrendIcon()}
                    <span className="text-sm font-medium">
                      {change > 0 ? '+' : ''}{change}%
                    </span>
                  </div>
                )}
                {changeLabel && (
                  <span className="text-sm text-neutral-500">{changeLabel}</span>
                )}
              </div>
            )}
          </>
        )}
      </CardBody>
    </Card>
  )
}