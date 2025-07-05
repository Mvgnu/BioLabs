'use client'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { useAuth } from '../../store/useAuth'
import { Button } from '../ui'
import { NotificationBell } from '../notifications'

export default function Header() {
  const token = useAuth((s) => s.token)
  const setToken = useAuth((s) => s.setToken)
  const router = useRouter()
  const [menuOpen, setMenuOpen] = useState(false)

  const logout = () => {
    setToken(null)
    router.push('/login')
  }

  if (!token) return null

  return (
    <header className="bg-white border-b border-neutral-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo */}
          <Link href="/" className="flex items-center space-x-3">
            <div className="w-8 h-8 bg-primary-500 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
              </svg>
            </div>
            <span className="text-xl font-bold text-neutral-900">BioLab</span>
          </Link>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center space-x-1">
            <Link href="/inventory" className="px-3 py-2 text-sm font-medium text-neutral-700 hover:text-primary-600 hover:bg-primary-50 rounded-md transition-colors">
              Inventory
            </Link>
            <Link href="/protocols" className="px-3 py-2 text-sm font-medium text-neutral-700 hover:text-primary-600 hover:bg-primary-50 rounded-md transition-colors">
              Protocols
            </Link>
            <Link href="/notebook" className="px-3 py-2 text-sm font-medium text-neutral-700 hover:text-primary-600 hover:bg-primary-50 rounded-md transition-colors">
              Notebook
            </Link>
            <Link href="/projects" className="px-3 py-2 text-sm font-medium text-neutral-700 hover:text-primary-600 hover:bg-primary-50 rounded-md transition-colors">
              Projects
            </Link>
            <Link href="/analytics" className="px-3 py-2 text-sm font-medium text-neutral-700 hover:text-primary-600 hover:bg-primary-50 rounded-md transition-colors">
              Analytics
            </Link>
          </nav>

          {/* User Menu */}
          <div className="flex items-center space-x-3">
            {/* Notification Bell */}
            <NotificationBell />

            {/* Command Palette Trigger */}
            <button
              onClick={() => {
                // Trigger command palette via keyboard event
                window.dispatchEvent(new KeyboardEvent('keydown', {
                  key: 'k',
                  metaKey: true,
                  bubbles: true
                }))
              }}
              className="hidden lg:flex items-center space-x-2 px-3 py-2 text-sm text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100 rounded-md transition-colors group"
              title="Open command palette"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="m21 21-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
              </svg>
              <span className="hidden xl:inline">Search</span>
              <div className="hidden xl:flex items-center space-x-1">
                <kbd className="px-1.5 py-0.5 text-xs bg-neutral-200 border border-neutral-300 rounded group-hover:bg-white transition-colors">⌘</kbd>
                <kbd className="px-1.5 py-0.5 text-xs bg-neutral-200 border border-neutral-300 rounded group-hover:bg-white transition-colors">K</kbd>
              </div>
            </button>

            <Button variant="ghost" size="sm" onClick={logout}>
              Sign out
            </Button>
            
            {/* Mobile menu button */}
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="md:hidden p-2 rounded-md text-neutral-400 hover:text-neutral-500 hover:bg-neutral-100 transition-colors"
              aria-label="Toggle menu"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                {menuOpen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>
          </div>
        </div>

        {/* Mobile Navigation */}
        {menuOpen && (
          <div className="md:hidden border-t border-neutral-200 py-3">
            <nav className="flex flex-col space-y-1">
              <Link href="/inventory" className="px-3 py-2 text-sm font-medium text-neutral-700 hover:text-primary-600 hover:bg-primary-50 rounded-md transition-colors">
                Inventory
              </Link>
              <Link href="/protocols" className="px-3 py-2 text-sm font-medium text-neutral-700 hover:text-primary-600 hover:bg-primary-50 rounded-md transition-colors">
                Protocols
              </Link>
              <Link href="/notebook" className="px-3 py-2 text-sm font-medium text-neutral-700 hover:text-primary-600 hover:bg-primary-50 rounded-md transition-colors">
                Notebook
              </Link>
              <Link href="/projects" className="px-3 py-2 text-sm font-medium text-neutral-700 hover:text-primary-600 hover:bg-primary-50 rounded-md transition-colors">
                Projects
              </Link>
              <Link href="/analytics" className="px-3 py-2 text-sm font-medium text-neutral-700 hover:text-primary-600 hover:bg-primary-50 rounded-md transition-colors">
                Analytics
              </Link>
            </nav>
          </div>
        )}
      </div>
    </header>
  )
}