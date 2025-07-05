'use client'
import React from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardHeader, CardBody, Button } from '../ui'

export interface QuickAction {
  id: string
  title: string
  description: string
  icon: React.ReactNode
  href?: string
  onClick?: () => void
  color?: 'primary' | 'secondary' | 'success' | 'warning' | 'error' | 'info'
  badge?: string
}

interface QuickActionsProps {
  actions?: QuickAction[]
  className?: string
}

const defaultActions: QuickAction[] = [
  {
    id: 'add-inventory',
    title: 'Add Item',
    description: 'Add new inventory item',
    href: '/inventory?action=create',
    color: 'primary',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4.5v15m7.5-7.5h-15" />
      </svg>
    )
  },
  {
    id: 'start-protocol',
    title: 'Run Protocol',
    description: 'Execute protocol template',
    href: '/protocols',
    color: 'secondary',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
      </svg>
    )
  },
  {
    id: 'create-entry',
    title: 'Lab Entry',
    description: 'New notebook entry',
    href: '/notebook?action=create',
    color: 'info',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L6.832 19.82a4.5 4.5 0 01-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 011.13-1.897L16.863 4.487zm0 0L19.5 7.125" />
      </svg>
    )
  },
  {
    id: 'create-project',
    title: 'New Project',
    description: 'Start research project',
    href: '/projects?action=create',
    color: 'warning',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
      </svg>
    )
  },
  {
    id: 'search-items',
    title: 'Search',
    description: 'Find items & protocols',
    href: '/search',
    color: 'success',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="m21 21-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
      </svg>
    )
  },
  {
    id: 'ask-assistant',
    title: 'Ask AI',
    description: 'Lab assistant help',
    href: '/assistant',
    color: 'error',
    badge: 'AI',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
      </svg>
    )
  }
]

const QuickActions: React.FC<QuickActionsProps> = ({
  actions = defaultActions,
  className
}) => {
  const router = useRouter()

  const handleAction = (action: QuickAction) => {
    if (action.onClick) {
      action.onClick()
    } else if (action.href) {
      router.push(action.href)
    }
  }

  const colorClasses = {
    primary: 'from-primary-500 to-primary-600 hover:from-primary-600 hover:to-primary-700',
    secondary: 'from-secondary-500 to-secondary-600 hover:from-secondary-600 hover:to-secondary-700',
    success: 'from-success-500 to-success-600 hover:from-success-600 hover:to-success-700',
    warning: 'from-warning-500 to-warning-600 hover:from-warning-600 hover:to-warning-700',
    error: 'from-error-500 to-error-600 hover:from-error-600 hover:to-error-700',
    info: 'from-info-500 to-info-600 hover:from-info-600 hover:to-info-700'
  }

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-neutral-900">Quick Actions</h3>
          <svg className="w-5 h-5 text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
          </svg>
        </div>
      </CardHeader>
      <CardBody className="pt-0">
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
          {actions.map((action) => (
            <button
              key={action.id}
              onClick={() => handleAction(action)}
              className={`
                relative p-4 rounded-xl bg-gradient-to-br text-white text-left
                transform transition-all duration-200 hover:scale-105 hover:shadow-lg
                focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500
                ${colorClasses[action.color || 'primary']}
              `}
            >
              {action.badge && (
                <span className="absolute -top-1 -right-1 px-2 py-0.5 text-xs font-bold bg-white/20 backdrop-blur-sm rounded-full">
                  {action.badge}
                </span>
              )}
              
              <div className="flex items-center space-x-3">
                <div className="flex-shrink-0">
                  {action.icon}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-sm truncate">{action.title}</p>
                  <p className="text-xs opacity-90 truncate">{action.description}</p>
                </div>
              </div>
            </button>
          ))}
        </div>
      </CardBody>
    </Card>
  )
}

export default QuickActions