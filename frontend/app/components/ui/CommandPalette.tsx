'use client'
import React, { useState, useEffect, useMemo, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { Card, Input } from './'
import { cn } from '../../utils/cn'

export interface CommandItem {
  id: string
  title: string
  subtitle?: string
  keywords?: string[]
  category: 'navigation' | 'action' | 'search' | 'recent' | 'suggestion'
  icon: React.ReactNode
  href?: string
  action?: () => void
  shortcut?: string
  badge?: string
}

interface CommandPaletteProps {
  isOpen: boolean
  onClose: () => void
  recentItems?: CommandItem[]
  customCommands?: CommandItem[]
}

const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  recentItems = [],
  customCommands = []
}) => {
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const router = useRouter()

  // Base commands - navigation and actions
  const baseCommands: CommandItem[] = useMemo(() => [
    // Navigation Commands
    {
      id: 'nav-dashboard',
      title: 'Dashboard',
      subtitle: 'Laboratory overview and metrics',
      keywords: ['home', 'overview', 'metrics', 'analytics'],
      category: 'navigation',
      href: '/',
      shortcut: '⌘D',
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
        </svg>
      )
    },
    {
      id: 'nav-inventory',
      title: 'Inventory',
      subtitle: 'Manage laboratory items and materials',
      keywords: ['items', 'materials', 'reagents', 'equipment'],
      category: 'navigation',
      href: '/inventory',
      shortcut: '⌘I',
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
        </svg>
      )
    },
    {
      id: 'nav-protocols',
      title: 'Protocols',
      subtitle: 'Protocol templates and executions',
      keywords: ['procedures', 'methods', 'experiments', 'sop'],
      category: 'navigation',
      href: '/protocols',
      shortcut: '⌘P',
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
        </svg>
      )
    },
    {
      id: 'nav-notebook',
      title: 'Lab Notebook',
      subtitle: 'Digital notebook and documentation',
      keywords: ['notes', 'documentation', 'entries', 'journal'],
      category: 'navigation',
      href: '/notebook',
      shortcut: '⌘N',
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L6.832 19.82a4.5 4.5 0 01-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 011.13-1.897L16.863 4.487zm0 0L19.5 7.125" />
        </svg>
      )
    },
    {
      id: 'nav-projects',
      title: 'Projects',
      subtitle: 'Research project management',
      keywords: ['research', 'tasks', 'collaboration', 'planning'],
      category: 'navigation',
      href: '/projects',
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
        </svg>
      )
    },
    {
      id: 'nav-analytics',
      title: 'Analytics',
      subtitle: 'Lab metrics and insights',
      keywords: ['reports', 'charts', 'data', 'trends'],
      category: 'navigation',
      href: '/analytics',
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
        </svg>
      )
    },

    // Quick Actions
    {
      id: 'action-add-item',
      title: 'Add Inventory Item',
      subtitle: 'Create new inventory entry',
      keywords: ['create', 'new', 'add', 'item'],
      category: 'action',
      href: '/inventory?action=create',
      shortcut: '⌘⇧I',
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4.5v15m7.5-7.5h-15" />
        </svg>
      )
    },
    {
      id: 'action-new-protocol',
      title: 'Create Protocol',
      subtitle: 'New protocol template',
      keywords: ['create', 'protocol', 'template'],
      category: 'action',
      href: '/protocols?action=create',
      shortcut: '⌘⇧P',
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4.5v15m7.5-7.5h-15" />
        </svg>
      )
    },
    {
      id: 'action-new-entry',
      title: 'New Lab Entry',
      subtitle: 'Create notebook entry',
      keywords: ['create', 'note', 'entry', 'documentation'],
      category: 'action',
      href: '/notebook?action=create',
      shortcut: '⌘⇧N',
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4.5v15m7.5-7.5h-15" />
        </svg>
      )
    },
    {
      id: 'action-search',
      title: 'Search Everything',
      subtitle: 'Global search across all data',
      keywords: ['find', 'search', 'look'],
      category: 'search',
      href: '/search',
      shortcut: '⌘⇧F',
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="m21 21-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
        </svg>
      )
    },
    {
      id: 'action-assistant',
      title: 'Ask Lab Assistant',
      subtitle: 'AI-powered laboratory help',
      keywords: ['ai', 'help', 'assistant', 'support'],
      category: 'action',
      href: '/assistant',
      badge: 'AI',
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
        </svg>
      )
    }
  ], [])

  // Combine all commands
  const allCommands = useMemo(() => [
    ...baseCommands,
    ...customCommands,
    ...recentItems
  ], [baseCommands, customCommands, recentItems])

  // Filter commands based on query
  const filteredCommands = useMemo(() => {
    if (!query.trim()) {
      // Show recent items and suggestions when no query
      const recent = allCommands.filter(cmd => cmd.category === 'recent').slice(0, 3)
      const navigation = allCommands.filter(cmd => cmd.category === 'navigation').slice(0, 6)
      const actions = allCommands.filter(cmd => cmd.category === 'action').slice(0, 4)
      return [...recent, ...navigation, ...actions]
    }

    const queryLower = query.toLowerCase()
    return allCommands.filter(cmd => {
      const titleMatch = cmd.title.toLowerCase().includes(queryLower)
      const subtitleMatch = cmd.subtitle?.toLowerCase().includes(queryLower)
      const keywordMatch = cmd.keywords?.some(keyword => 
        keyword.toLowerCase().includes(queryLower)
      )
      return titleMatch || subtitleMatch || keywordMatch
    }).slice(0, 8)
  }, [query, allCommands])

  // Handle command execution
  const executeCommand = useCallback((command: CommandItem) => {
    if (command.action) {
      command.action()
    } else if (command.href) {
      router.push(command.href)
    }
    onClose()
  }, [router, onClose])

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (!isOpen) return

      switch (event.key) {
        case 'ArrowDown':
          event.preventDefault()
          setSelectedIndex(prev => 
            prev < filteredCommands.length - 1 ? prev + 1 : prev
          )
          break
        case 'ArrowUp':
          event.preventDefault()
          setSelectedIndex(prev => prev > 0 ? prev - 1 : prev)
          break
        case 'Enter':
          event.preventDefault()
          if (filteredCommands[selectedIndex]) {
            executeCommand(filteredCommands[selectedIndex])
          }
          break
        case 'Escape':
          event.preventDefault()
          onClose()
          break
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, selectedIndex, filteredCommands, executeCommand, onClose])

  // Reset selection when commands change
  useEffect(() => {
    setSelectedIndex(0)
  }, [filteredCommands])

  // Reset state when opening/closing
  useEffect(() => {
    if (isOpen) {
      setQuery('')
      setSelectedIndex(0)
    }
  }, [isOpen])

  if (!isOpen) return null

  const getCategoryLabel = (category: CommandItem['category']) => {
    switch (category) {
      case 'navigation': return 'Navigate'
      case 'action': return 'Actions'
      case 'search': return 'Search'
      case 'recent': return 'Recent'
      case 'suggestion': return 'Suggestions'
      default: return ''
    }
  }

  const getCategoryIcon = (category: CommandItem['category']) => {
    switch (category) {
      case 'navigation':
        return (
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
          </svg>
        )
      case 'action':
        return (
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
          </svg>
        )
      case 'search':
        return (
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="m21 21-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
        )
      default:
        return null
    }
  }

  // Group commands by category
  const groupedCommands = useMemo(() => {
    const groups: Record<string, CommandItem[]> = {}
    filteredCommands.forEach(cmd => {
      if (!groups[cmd.category]) {
        groups[cmd.category] = []
      }
      groups[cmd.category].push(cmd)
    })
    return groups
  }, [filteredCommands])

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/50 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />
      
      {/* Command Palette */}
      <div className="flex min-h-full items-start justify-center p-4 pt-[10vh]">
        <Card className="w-full max-w-2xl bg-white/95 backdrop-blur-sm border-0 shadow-2xl overflow-hidden">
          {/* Search Input */}
          <div className="p-4 border-b border-neutral-200">
            <div className="flex items-center space-x-3">
              <svg className="w-5 h-5 text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="m21 21-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
              </svg>
              <input
                type="text"
                placeholder="Search commands, navigate, or take actions..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="flex-1 bg-transparent border-0 text-lg placeholder-neutral-400 focus:outline-none"
                autoFocus
              />
              <div className="flex items-center space-x-2 text-xs text-neutral-500">
                <kbd className="px-2 py-1 bg-neutral-100 rounded border">↑↓</kbd>
                <span>navigate</span>
                <kbd className="px-2 py-1 bg-neutral-100 rounded border">↵</kbd>
                <span>select</span>
                <kbd className="px-2 py-1 bg-neutral-100 rounded border">esc</kbd>
                <span>close</span>
              </div>
            </div>
          </div>

          {/* Results */}
          <div className="max-h-96 overflow-y-auto">
            {filteredCommands.length === 0 ? (
              <div className="p-8 text-center text-neutral-500">
                <svg className="w-12 h-12 mx-auto mb-3 text-neutral-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="m21 21-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
                </svg>
                <p className="text-sm">No commands found</p>
                <p className="text-xs mt-1">Try a different search term</p>
              </div>
            ) : (
              <div className="py-2">
                {Object.entries(groupedCommands).map(([category, commands]) => (
                  <div key={category}>
                    {/* Category Header */}
                    <div className="flex items-center space-x-2 px-4 py-2 text-xs font-medium text-neutral-500 bg-neutral-50">
                      {getCategoryIcon(category as CommandItem['category'])}
                      <span>{getCategoryLabel(category as CommandItem['category'])}</span>
                    </div>
                    
                    {/* Commands */}
                    {commands.map((command, index) => {
                      const globalIndex = filteredCommands.indexOf(command)
                      return (
                        <button
                          key={command.id}
                          onClick={() => executeCommand(command)}
                          className={cn(
                            'w-full flex items-center space-x-3 px-4 py-3 text-left hover:bg-neutral-50 transition-colors',
                            globalIndex === selectedIndex && 'bg-primary-50 border-r-2 border-primary-500'
                          )}
                        >
                          <div className={cn(
                            'flex items-center justify-center w-8 h-8 rounded-lg',
                            globalIndex === selectedIndex 
                              ? 'bg-primary-500 text-white' 
                              : 'bg-neutral-100 text-neutral-600'
                          )}>
                            {command.icon}
                          </div>
                          
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center space-x-2">
                              <p className="text-sm font-medium text-neutral-900 truncate">
                                {command.title}
                              </p>
                              {command.badge && (
                                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-primary-100 text-primary-800">
                                  {command.badge}
                                </span>
                              )}
                            </div>
                            {command.subtitle && (
                              <p className="text-xs text-neutral-500 truncate">
                                {command.subtitle}
                              </p>
                            )}
                          </div>
                          
                          {command.shortcut && (
                            <div className="flex items-center space-x-1 text-xs text-neutral-400">
                              {command.shortcut.split('').map((key, idx) => (
                                <kbd key={idx} className="px-1.5 py-0.5 bg-neutral-100 rounded border text-xs">
                                  {key}
                                </kbd>
                              ))}
                            </div>
                          )}
                        </button>
                      )
                    })}
                  </div>
                ))}
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  )
}

export default CommandPalette