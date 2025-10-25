'use client'
import './styles/globals.css'
import { ReactNode, useState, useEffect } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { usePathname } from 'next/navigation'
import Header from './components/layout/Header'
import Footer from './components/layout/Footer'
import { NotificationCenter, NotificationProvider } from './components/notifications'
import { CommandPalette, type CommandItem } from './components/ui'
import { useCommandPalette } from './hooks/useCommandPalette'

function AppContent({ children }: { children: ReactNode }) {
  const pathname = usePathname()
  const { isOpen, close, recentItems, addRecentItem } = useCommandPalette()

  // Custom commands based on current page context
  const [customCommands, setCustomCommands] = useState<CommandItem[]>([])

  useEffect(() => {
    // Add context-specific commands based on current route
    const commands: CommandItem[] = []

    if (pathname === '/inventory') {
      commands.push({
        id: 'inventory-export',
        title: 'Export Inventory',
        subtitle: 'Download current inventory as CSV',
        keywords: ['export', 'download', 'csv'],
        category: 'action',
        href: '/api/inventory/export',
        icon: (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
          </svg>
        )
      })
    }

    if (pathname === '/protocols') {
      commands.push({
        id: 'protocols-trending',
        title: 'View Trending Protocols',
        subtitle: 'See most popular protocol templates',
        keywords: ['trending', 'popular', 'analytics'],
        category: 'suggestion',
        href: '/analytics?tab=protocols',
        icon: (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.362 5.214A8.252 8.252 0 0112 21 8.25 8.25 0 016.038 7.048 8.287 8.287 0 009 9.6a8.983 8.983 0 003.361-6.867 8.21 8.21 0 003 2.48z" />
          </svg>
        )
      })
    }

    setCustomCommands(commands)
  }, [pathname])

  return (
    <>
      {/* App Layout */}
      <div className="min-h-full flex flex-col">
        <Header />
        <main id="main" className="flex-1">
          {children}
        </main>
        <Footer />
      </div>

      {/* Global Command Palette */}
      <CommandPalette
        isOpen={isOpen}
        onClose={close}
        recentItems={recentItems}
        customCommands={customCommands}
      />

      <NotificationCenter />
      <NotificationProvider />
    </>
  )
}

export default function RootLayout({ children }: { children: ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        retry: 1,
        refetchOnWindowFocus: false,
        staleTime: 5 * 60 * 1000, // 5 minutes
      },
    },
  }))

  return (
    <html lang="en" className="h-full">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet" />
      </head>
      <body className="h-full bg-neutral-50 text-neutral-900 font-sans antialiased">
        <QueryClientProvider client={queryClient}>
          {/* Skip Link for Accessibility */}
          <a 
            href="#main" 
            className="sr-only focus:not-sr-only focus:absolute focus:top-6 focus:left-6 bg-primary-500 text-white px-4 py-2 rounded-md z-50 transition-all"
          >
            Skip to content
          </a>
          
          <AppContent>{children}</AppContent>
        </QueryClientProvider>
      </body>
    </html>
  )
}
