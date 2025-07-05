import React from 'react'
import { cn } from '../../utils/cn'

export interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'success' | 'warning' | 'error' | 'info'
  title?: string
  dismissible?: boolean
  onDismiss?: () => void
  children: React.ReactNode
}

const Alert = React.forwardRef<HTMLDivElement, AlertProps>(
  ({ className, variant = 'info', title, dismissible = false, onDismiss, children, ...props }, ref) => {
    const baseStyles = 'p-4 rounded-md border text-sm'
    
    const variants = {
      success: 'bg-success-50 border-success-200 text-success-800',
      warning: 'bg-warning-50 border-warning-200 text-warning-800',
      error: 'bg-error-50 border-error-200 text-error-800',
      info: 'bg-info-50 border-info-200 text-info-800'
    }
    
    const icons = {
      success: (
        <svg className="w-5 h-5 text-success-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
      warning: (
        <svg className="w-5 h-5 text-warning-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16c-.77.833.192 2.5 1.732 2.5z" />
        </svg>
      ),
      error: (
        <svg className="w-5 h-5 text-error-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
      info: (
        <svg className="w-5 h-5 text-info-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      )
    }
    
    return (
      <div
        ref={ref}
        className={cn(baseStyles, variants[variant], className)}
        role="alert"
        {...props}
      >
        <div className="flex items-start">
          <div className="flex-shrink-0 mr-3">
            {icons[variant]}
          </div>
          <div className="flex-grow">
            {title && (
              <h4 className="font-medium mb-1">
                {title}
              </h4>
            )}
            <div className={title ? 'text-sm' : ''}>
              {children}
            </div>
          </div>
          {dismissible && (
            <button
              onClick={onDismiss}
              className="ml-4 flex-shrink-0 p-1 rounded-md hover:bg-black/5 transition-colors"
              aria-label="Dismiss alert"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>
    )
  }
)

Alert.displayName = 'Alert'

export { Alert }