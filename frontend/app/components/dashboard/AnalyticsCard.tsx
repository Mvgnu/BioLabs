'use client'
import React from 'react'
import { Card, CardBody } from '../ui'
import { cn } from '../../utils/cn'

export interface AnalyticsCardProps {
  title: string
  value: string | number
  change?: {
    value: number
    period: string
    trend: 'up' | 'down' | 'neutral'
  }
  icon?: React.ReactNode
  color?: 'primary' | 'secondary' | 'success' | 'warning' | 'error' | 'info'
  loading?: boolean
  onClick?: () => void
  className?: string
}

const AnalyticsCard: React.FC<AnalyticsCardProps> = ({
  title,
  value,
  change,
  icon,
  color = 'primary',
  loading = false,
  onClick,
  className
}) => {
  const colorClasses = {
    primary: 'from-primary-500 to-primary-600',
    secondary: 'from-secondary-500 to-secondary-600',
    success: 'from-success-500 to-success-600',
    warning: 'from-warning-500 to-warning-600',
    error: 'from-error-500 to-error-600',
    info: 'from-info-500 to-info-600'
  }

  const changeColorClasses = {
    up: 'text-success-600 bg-success-50',
    down: 'text-error-600 bg-error-50',
    neutral: 'text-neutral-600 bg-neutral-50'
  }

  if (loading) {
    return (
      <Card className={cn('overflow-hidden', onClick && 'cursor-pointer hover:shadow-md transition-shadow', className)}>
        <CardBody className="p-6">
          <div className="animate-pulse">
            <div className="flex items-center justify-between mb-4">
              <div className="h-4 bg-neutral-200 rounded w-24"></div>
              <div className="h-8 w-8 bg-neutral-200 rounded-lg"></div>
            </div>
            <div className="h-8 bg-neutral-200 rounded w-20 mb-2"></div>
            <div className="h-3 bg-neutral-200 rounded w-32"></div>
          </div>
        </CardBody>
      </Card>
    )
  }

  return (
    <Card 
      className={cn(
        'overflow-hidden relative group',
        onClick && 'cursor-pointer hover:shadow-lg hover:-translate-y-1 transition-all duration-200',
        className
      )}
      onClick={onClick}
    >
      {/* Gradient accent */}
      <div className={cn('absolute top-0 left-0 right-0 h-1 bg-gradient-to-r', colorClasses[color])} />
      
      <CardBody className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium text-neutral-600 group-hover:text-neutral-900 transition-colors">
            {title}
          </h3>
          {icon && (
            <div className={cn(
              'p-2 rounded-lg bg-gradient-to-br text-white transition-transform group-hover:scale-110',
              colorClasses[color]
            )}>
              {icon}
            </div>
          )}
        </div>

        <div className="space-y-2">
          <p className="text-3xl font-bold text-neutral-900">
            {typeof value === 'number' ? value.toLocaleString() : value}
          </p>
          
          {change && (
            <div className="flex items-center space-x-2">
              <span className={cn(
                'inline-flex items-center px-2 py-1 rounded-full text-xs font-medium',
                changeColorClasses[change.trend]
              )}>
                {change.trend === 'up' && (
                  <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 17l9.2-9.2M17 17V7H7" />
                  </svg>
                )}
                {change.trend === 'down' && (
                  <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 7l-9.2 9.2M7 7v10h10" />
                  </svg>
                )}
                {Math.abs(change.value)}%
              </span>
              <span className="text-xs text-neutral-500">vs {change.period}</span>
            </div>
          )}
        </div>
      </CardBody>
    </Card>
  )
}

export default AnalyticsCard