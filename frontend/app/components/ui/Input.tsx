import React from 'react'
import { cn } from '../../utils/cn'

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  helperText?: string
  variant?: 'default' | 'search'
  leftIcon?: React.ReactNode
  rightIcon?: React.ReactNode
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, helperText, variant = 'default', leftIcon, rightIcon, id, ...props }, ref) => {
    const inputId = id || `input-${Math.random().toString(36).substr(2, 9)}`
    
    const baseStyles = 'w-full px-4 py-3 text-sm bg-white border rounded-md transition-all duration-200 ease-in-out placeholder-neutral-400 focus:outline-none focus:ring-2 focus:ring-offset-0 disabled:bg-neutral-50 disabled:text-neutral-500 disabled:cursor-not-allowed'
    
    const variants = {
      default: error 
        ? 'border-error-500 focus:border-error-500 focus:ring-error-500/10' 
        : 'border-neutral-300 focus:border-primary-500 focus:ring-primary-500/10',
      search: 'border-neutral-300 focus:border-primary-500 focus:ring-primary-500/10 pl-10'
    }
    
    const iconStyles = 'absolute top-1/2 transform -translate-y-1/2 text-neutral-400'
    
    return (
      <div className="w-full">
        {label && (
          <label htmlFor={inputId} className="block text-sm font-medium text-neutral-700 mb-2">
            {label}
          </label>
        )}
        <div className="relative">
          {leftIcon && (
            <div className={cn(iconStyles, 'left-3')}>
              {leftIcon}
            </div>
          )}
          <input
            ref={ref}
            id={inputId}
            className={cn(
              baseStyles,
              variants[variant],
              leftIcon && 'pl-10',
              rightIcon && 'pr-10',
              className
            )}
            {...props}
          />
          {rightIcon && (
            <div className={cn(iconStyles, 'right-3')}>
              {rightIcon}
            </div>
          )}
        </div>
        {error && (
          <p className="mt-1 text-xs text-error-600" role="alert">
            {error}
          </p>
        )}
        {helperText && !error && (
          <p className="mt-1 text-xs text-neutral-500">
            {helperText}
          </p>
        )}
      </div>
    )
  }
)

Input.displayName = 'Input'

export { Input }