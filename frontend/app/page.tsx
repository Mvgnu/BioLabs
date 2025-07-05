'use client'
import { useEffect, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from './store/useAuth'
import { 
  AnalyticsCard, 
  QuickActions, 
  RecentActivity, 
  TrendingInsights,
  type ActivityItem,
  type TrendingData 
} from './components/dashboard'
import { Alert, Button, Card, CardBody, CardHeader } from './components/ui'
import { useAnalytics } from './hooks/useAnalytics'
import { useTrendingProtocols } from './hooks/useAnalytics'
import { useTrendingArticles } from './hooks/useAnalytics'
import { useTrendingItems } from './hooks/useAnalytics'
import { useTrendingThreads } from './hooks/useAnalytics'
import { useNotebookEntries } from './hooks/useNotebook'
import { useProjects } from './hooks/useProjects'
import { useComplianceSummary } from './hooks/useCompliance'
import Tour from './components/Tour'

export default function Home() {
  const token = useAuth((s) => s.token)
  const router = useRouter()

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!token) {
      router.push('/login')
      return
    }
  }, [token, router])

  // Data hooks
  const { data: analytics, isLoading: analyticsLoading } = useAnalytics()
  const { data: trendingProtocols, isLoading: protocolsLoading } = useTrendingProtocols()
  const { data: trendingArticles, isLoading: articlesLoading } = useTrendingArticles()
  const { data: trendingItems, isLoading: itemsLoading } = useTrendingItems()
  const { data: trendingThreads, isLoading: threadsLoading } = useTrendingThreads()
  const { data: notebookEntries, isLoading: notebookLoading } = useNotebookEntries()
  const { data: projects, isLoading: projectsLoading } = useProjects()
  const { data: complianceSummary, isLoading: complianceLoading } = useComplianceSummary()

  // Process analytics data
  const analyticsCards = useMemo(() => {
    if (!analytics || !Array.isArray(analytics)) return []

    const totalItems = analytics.reduce((sum, item) => sum + (item?.count || 0), 0)
    const mostCommonType = analytics.length > 0 ? analytics[0] : null

    return [
      {
        title: 'Total Inventory',
        value: totalItems,
        change: { value: 12, period: 'last month', trend: 'up' as const },
        icon: (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
          </svg>
        ),
        color: 'primary' as const,
        onClick: () => router.push('/inventory')
      },
      {
        title: 'Active Projects',
        value: projects?.length || 0,
        change: { value: 8, period: 'last week', trend: 'up' as const },
        icon: (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m6.75 18.75H8.25A2.25 2.25 0 016 18.75V3a.75.75 0 01.75-.75h7.5a.75.75 0 01.75.75v4.5c0 .414.336.75.75.75H18a.75.75 0 01.75.75v10.5z" />
          </svg>
        ),
        color: 'warning' as const,
        onClick: () => router.push('/projects')
      },
      {
        title: 'Lab Entries',
        value: notebookEntries?.length || 0,
        change: { value: 15, period: 'this week', trend: 'up' as const },
        icon: (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L6.832 19.82a4.5 4.5 0 01-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 011.13-1.897L16.863 4.487zm0 0L19.5 7.125" />
          </svg>
        ),
        color: 'info' as const,
        onClick: () => router.push('/notebook')
      },
      {
        title: 'Compliance Score',
        value: '94%',
        change: { value: 2, period: 'last audit', trend: 'up' as const },
        icon: (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.623 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
          </svg>
        ),
        color: 'success' as const,
        onClick: () => router.push('/compliance')
      }
    ]
  }, [analytics, projects, notebookEntries, router])

  // Process trending data
  const trendingData: TrendingData = useMemo(() => ({
    protocols: (trendingProtocols && Array.isArray(trendingProtocols)) ? trendingProtocols.map(p => ({
      id: p?.template_id?.toString() || 'unknown',
      name: p?.template_name || 'Unknown',
      count: p?.count || 0,
      change: Math.floor(Math.random() * 30) - 10, // Mock change data
      category: 'Protocol Template'
    })) : [],
    articles: (trendingArticles && Array.isArray(trendingArticles)) ? trendingArticles.map(a => ({
      id: a?.article_id?.toString() || 'unknown',
      name: a?.title || 'Unknown',
      count: a?.count || 0,
      change: Math.floor(Math.random() * 25) - 5,
      category: 'Knowledge Base'
    })) : [],
    items: (trendingItems && Array.isArray(trendingItems)) ? trendingItems.map(i => ({
      id: i?.item_id?.toString() || 'unknown',
      name: i?.name || 'Unknown',
      count: i?.count || 0,
      change: Math.floor(Math.random() * 20) - 10,
      category: 'Inventory Item'
    })) : [],
    threads: (trendingThreads && Array.isArray(trendingThreads)) ? trendingThreads.map(t => ({
      id: t?.thread_id?.toString() || 'unknown',
      name: t?.title || 'Unknown',
      count: t?.count || 0,
      change: Math.floor(Math.random() * 40) - 15,
      category: 'Community Discussion'
    })) : []
  }), [trendingProtocols, trendingArticles, trendingItems, trendingThreads])

  // Process recent activity
  const recentActivities: ActivityItem[] = useMemo(() => {
    const activities: ActivityItem[] = []

    // Add recent notebook entries
    if (notebookEntries) {
      notebookEntries.slice(0, 3).forEach(entry => {
        activities.push({
          id: `notebook-${entry.id}`,
          type: 'notebook',
          title: entry.title,
          description: 'Lab notebook entry created',
          timestamp: entry.created_at,
          href: `/notebook/${entry.id}`,
          status: 'success'
        })
      })
    }

    // Add recent projects
    if (projects) {
      projects.slice(0, 2).forEach(project => {
        activities.push({
          id: `project-${project.id}`,
          type: 'project',
          title: project.name,
          description: project.description || 'Project updated',
          timestamp: project.created_at,
          href: `/projects/${project.id}`,
          status: 'pending'
        })
      })
    }

    // Sort by timestamp
    return activities.sort((a, b) => 
      new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    )
  }, [notebookEntries, projects])

  // Show loading state for unauthenticated users
  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 bg-primary-500 rounded-lg flex items-center justify-center mx-auto mb-4">
            <svg className="w-7 h-7 text-white animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
            </svg>
          </div>
          <p className="text-neutral-600">Redirecting to login...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-8 p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-neutral-900 mb-2">
            Laboratory Dashboard
          </h1>
          <p className="text-neutral-600">
            Welcome back! Here's what's happening in your lab today.
          </p>
        </div>
        <div className="mt-4 lg:mt-0 flex items-center space-x-4">
          <Button variant="secondary" size="sm">
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
            </svg>
            Export Report
          </Button>
          <Button size="sm">
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            Quick Add
          </Button>
        </div>
      </div>

      {/* Analytics Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {analyticsCards.map((card, index) => (
          <AnalyticsCard
            key={index}
            {...card}
            loading={analyticsLoading || projectsLoading || notebookLoading}
          />
        ))}
      </div>

      {/* Quick Actions */}
      <QuickActions />

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Activity */}
        <div className="lg:col-span-2">
          <RecentActivity
            activities={recentActivities}
            loading={notebookLoading || projectsLoading}
          />
        </div>

        {/* Trending Insights */}
        <div>
          <TrendingInsights
            data={trendingData}
            loading={protocolsLoading || articlesLoading || itemsLoading || threadsLoading}
          />
        </div>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* System Status */}
        <Card>
          <CardHeader>
            <h3 className="text-lg font-semibold text-neutral-900">System Status</h3>
          </CardHeader>
          <CardBody className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-neutral-600">Database</span>
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-success-500 rounded-full"></div>
                <span className="text-sm font-medium text-success-600">Operational</span>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-neutral-600">Analytics Engine</span>
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-success-500 rounded-full"></div>
                <span className="text-sm font-medium text-success-600">Running</span>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-neutral-600">Backup Status</span>
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-warning-500 rounded-full"></div>
                <span className="text-sm font-medium text-warning-600">Scheduled</span>
              </div>
            </div>
          </CardBody>
        </Card>

        {/* Quick Stats */}
        <Card>
          <CardHeader>
            <h3 className="text-lg font-semibold text-neutral-900">Today's Highlights</h3>
          </CardHeader>
          <CardBody className="space-y-4">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-primary-50 rounded-lg">
                <svg className="w-4 h-4 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-medium text-neutral-900">3 protocols completed</p>
                <p className="text-xs text-neutral-500">2 still running</p>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-secondary-50 rounded-lg">
                <svg className="w-4 h-4 text-secondary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-medium text-neutral-900">Budget utilization: 68%</p>
                <p className="text-xs text-neutral-500">Within monthly limits</p>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-info-50 rounded-lg">
                <svg className="w-4 h-4 text-info-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16.5 18.75h-9m9 0a3 3 0 013 3h-15a3 3 0 013-3m9 0v-3.375c0-.621-.503-1.125-1.125-1.125h-.871M7.5 18.75v-3.375c0-.621.504-1.125 1.125-1.125h.872m5.007 0H9.497m5.007 0a7.454 7.454 0 01-.982-3.172M9.497 14.25a7.454 7.454 0 00.981-3.172M5.25 4.236c-.982.143-1.954.317-2.916.52A6.003 6.003 0 007.73 9.728M5.25 4.236V4.5c0 2.108.966 3.99 2.48 5.228M5.25 4.236V2.721C7.456 2.41 9.71 2.25 12 2.25c2.291 0 4.545.16 6.75.47v1.516M7.73 9.728a6.726 6.726 0 002.748 1.35m8.272-6.842V4.5c0 2.108-.966 3.99-2.48 5.228m2.48-5.228a25.35 25.35 0 012.456.49 6.002 6.002 0 01-1.318 5.74M10.478 11.078a7.956 7.956 0 001.044-.952 7.956 7.956 0 01-1.044.952z" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-medium text-neutral-900">Equipment uptime: 99.2%</p>
                <p className="text-xs text-neutral-500">All systems operational</p>
              </div>
            </div>
          </CardBody>
        </Card>
      </div>

      {/* Tour Component (for new users) */}
      <Tour />
    </div>
  )
}
