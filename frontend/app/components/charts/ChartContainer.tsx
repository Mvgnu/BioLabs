'use client'
import { Card, CardHeader, CardBody } from '../ui'
import { ReactNode } from 'react'

interface ChartContainerProps {
  title: string
  subtitle?: string
  children: ReactNode
  loading?: boolean
  error?: string
  className?: string
  action?: ReactNode
}

export default function ChartContainer({
  title,
  subtitle,
  children,
  loading,
  error,
  className,
  action
}: ChartContainerProps) {
  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-neutral-900">{title}</h3>
            {subtitle && <p className="text-sm text-neutral-600 mt-1">{subtitle}</p>}
          </div>
          {action && <div className="flex items-center">{action}</div>}
        </div>
      </CardHeader>
      <CardBody>
        {loading && (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
          </div>
        )}
        {error && (
          <div className="flex items-center justify-center h-64 text-error-600">
            <div className="text-center">
              <svg className="w-8 h-8 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-sm font-medium">Failed to load chart</p>
              <p className="text-xs text-neutral-500 mt-1">{error}</p>
            </div>
          </div>
        )}
        {!loading && !error && children}
      </CardBody>
    </Card>
  )
}