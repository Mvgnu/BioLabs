import React from 'react'
import { cn } from '../../utils/cn'

export interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const Spinner: React.FC<SpinnerProps> = ({ size = 'md', className }) => {
  const sizes = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-8 h-8'
  }
  
  return (
    <div className={cn('animate-spin', sizes[size], className)}>
      <svg className="w-full h-full" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle
          className="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
        />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        />
      </svg>
    </div>
  )
}

export interface SkeletonProps {
  className?: string
  lines?: number
}

const Skeleton: React.FC<SkeletonProps> = ({ className, lines = 1 }) => {
  const baseStyles = 'bg-gradient-to-r from-neutral-200 via-neutral-100 to-neutral-200 bg-[length:200%_100%] animate-pulse rounded'
  
  if (lines === 1) {
    return <div className={cn(baseStyles, 'h-4 w-full', className)} />
  }
  
  return (
    <div className={cn('space-y-2', className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className={cn(
            baseStyles,
            'h-4',
            i === lines - 1 ? 'w-3/4' : 'w-full'
          )}
        />
      ))}
    </div>
  )
}

export interface LoadingStateProps {
  title?: string
  description?: string
  className?: string
}

const LoadingState: React.FC<LoadingStateProps> = ({ title, description, className }) => {
  return (
    <div className={cn('flex flex-col items-center justify-center p-8 text-center', className)}>
      <Spinner size="lg" className="text-primary-500 mb-4" />
      {title && <h3 className="text-lg font-medium text-neutral-900 mb-2">{title}</h3>}
      {description && <p className="text-sm text-neutral-600">{description}</p>}
    </div>
  )
}

export interface EmptyStateProps {
  title: string
  description?: string
  icon?: React.ReactNode
  action?: React.ReactNode
  className?: string
}

const EmptyState: React.FC<EmptyStateProps> = ({ title, description, icon, action, className }) => {
  return (
    <div className={cn('flex flex-col items-center justify-center p-8 text-center', className)}>
      {icon && (
        <div className="mb-4 text-neutral-400">
          {icon}
        </div>
      )}
      <h3 className="text-lg font-medium text-neutral-900 mb-2">{title}</h3>
      {description && <p className="text-sm text-neutral-600 mb-4">{description}</p>}
      {action && action}
    </div>
  )
}

export { Spinner, Skeleton, LoadingState, EmptyState }