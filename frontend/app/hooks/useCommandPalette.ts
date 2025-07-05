import { useState, useEffect, useCallback } from 'react'
import type { CommandItem } from '../components/ui/CommandPalette'

interface UseCommandPaletteReturn {
  isOpen: boolean
  open: () => void
  close: () => void
  toggle: () => void
  addRecentItem: (item: CommandItem) => void
  recentItems: CommandItem[]
}

const RECENT_ITEMS_KEY = 'biolab-recent-commands'
const MAX_RECENT_ITEMS = 5

export function useCommandPalette(): UseCommandPaletteReturn {
  const [isOpen, setIsOpen] = useState(false)
  const [recentItems, setRecentItems] = useState<CommandItem[]>([])

  // Load recent items from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem(RECENT_ITEMS_KEY)
    if (stored) {
      try {
        const parsed = JSON.parse(stored)
        setRecentItems(parsed)
      } catch (error) {
        console.warn('Failed to parse recent command items:', error)
      }
    }
  }, [])

  // Global keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Command+K or Ctrl+K to open command palette
      if ((event.metaKey || event.ctrlKey) && event.key === 'k') {
        event.preventDefault()
        setIsOpen(true)
        return
      }

      // Escape to close when open
      if (event.key === 'Escape' && isOpen) {
        event.preventDefault()
        setIsOpen(false)
        return
      }

      // Quick navigation shortcuts (only when palette is closed)
      if (!isOpen && (event.metaKey || event.ctrlKey)) {
        switch (event.key) {
          case 'd':
            event.preventDefault()
            window.location.href = '/'
            break
          case 'i':
            if (event.shiftKey) {
              event.preventDefault()
              window.location.href = '/inventory?action=create'
            } else {
              event.preventDefault()
              window.location.href = '/inventory'
            }
            break
          case 'p':
            if (event.shiftKey) {
              event.preventDefault()
              window.location.href = '/protocols?action=create'
            } else {
              event.preventDefault()
              window.location.href = '/protocols'
            }
            break
          case 'n':
            if (event.shiftKey) {
              event.preventDefault()
              window.location.href = '/notebook?action=create'
            } else {
              event.preventDefault()
              window.location.href = '/notebook'
            }
            break
          case 'f':
            if (event.shiftKey) {
              event.preventDefault()
              window.location.href = '/search'
            }
            break
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen])

  const open = useCallback(() => {
    setIsOpen(true)
  }, [])

  const close = useCallback(() => {
    setIsOpen(false)
  }, [])

  const toggle = useCallback(() => {
    setIsOpen(prev => !prev)
  }, [])

  const addRecentItem = useCallback((item: CommandItem) => {
    setRecentItems(prev => {
      // Remove item if it already exists
      const filtered = prev.filter(existing => existing.id !== item.id)
      
      // Add item to the beginning with 'recent' category
      const recentItem: CommandItem = {
        ...item,
        category: 'recent'
      }
      
      const newItems = [recentItem, ...filtered].slice(0, MAX_RECENT_ITEMS)
      
      // Save to localStorage
      try {
        localStorage.setItem(RECENT_ITEMS_KEY, JSON.stringify(newItems))
      } catch (error) {
        console.warn('Failed to save recent command items:', error)
      }
      
      return newItems
    })
  }, [])

  return {
    isOpen,
    open,
    close,
    toggle,
    addRecentItem,
    recentItems
  }
}