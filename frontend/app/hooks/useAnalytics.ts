'use client'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import type {
  ItemTypeCount,
  TrendingProtocol,
  TrendingArticle,
  TrendingItem,
  TrendingThread,
} from '../types'

export const useAnalytics = () => {
  return useQuery({
    queryKey: ['analytics'],
    queryFn: async () => {
      try {
        const resp = await api.get('/api/analytics/summary')
        return resp.data as ItemTypeCount[]
      } catch (error) {
        console.error('Analytics query failed:', error)
        return []
      }
    },
    retry: 1,
    staleTime: 5 * 60 * 1000,
  })
}

export const useTrendingProtocols = () => {
  return useQuery({
    queryKey: ['trending-protocols'],
    queryFn: async () => {
      try {
        const resp = await api.get('/api/analytics/trending-protocols')
        return resp.data as TrendingProtocol[]
      } catch (error) {
        console.error('Trending protocols query failed:', error)
        return []
      }
    },
    retry: 1,
    staleTime: 5 * 60 * 1000,
  })
}

export const useTrendingArticles = () => {
  return useQuery({
    queryKey: ['trending-articles'],
    queryFn: async () => {
      try {
        const resp = await api.get('/api/analytics/trending-articles')
        return resp.data as TrendingArticle[]
      } catch (error) {
        console.error('Trending articles query failed:', error)
        return []
      }
    },
    retry: 1,
    staleTime: 5 * 60 * 1000,
  })
}

export const useTrendingItems = () => {
  return useQuery({
    queryKey: ['trending-items'],
    queryFn: async () => {
      try {
        const resp = await api.get('/api/analytics/trending-items')
        return resp.data as TrendingItem[]
      } catch (error) {
        console.error('Trending items query failed:', error)
        return []
      }
    },
    retry: 1,
    staleTime: 5 * 60 * 1000,
  })
}

export const useTrendingThreads = () => {
  return useQuery({
    queryKey: ['trending-threads'],
    queryFn: async () => {
      try {
        const resp = await api.get('/api/analytics/trending-threads')
        return resp.data as TrendingThread[]
      } catch (error) {
        console.error('Trending threads query failed:', error)
        return []
      }
    },
    retry: 1,
    staleTime: 5 * 60 * 1000,
  })
}

export const useAdvancedAnalytics = () => {
  return useQuery({
    queryKey: ['advanced-analytics'],
    queryFn: async () => {
      try {
        const [summary, protocols, articles, items, threads] = await Promise.all([
          api.get('/api/analytics/summary'),
          api.get('/api/analytics/trending-protocols'),
          api.get('/api/analytics/trending-articles'),
          api.get('/api/analytics/trending-items'),
          api.get('/api/analytics/trending-threads')
        ])
        
        return {
          summary: summary.data as ItemTypeCount[],
          protocols: protocols.data as TrendingProtocol[],
          articles: articles.data as TrendingArticle[],
          items: items.data as TrendingItem[],
          threads: threads.data as TrendingThread[]
        }
      } catch (error) {
        console.error('Advanced analytics query failed:', error)
        return {
          summary: [],
          protocols: [],
          articles: [],
          items: [],
          threads: []
        }
      }
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

export const useLabMetrics = () => {
  return useQuery({
    queryKey: ['lab-metrics'],
    queryFn: async () => {
      try {
        // Use existing analytics endpoints to build comprehensive metrics
        const [
          inventoryResp,
          protocolsResp,
          projectsResp,
          notebookResp,
          auditResp
        ] = await Promise.all([
          api.get('/api/inventory/items'),
          api.get('/api/protocols/templates'),
          api.get('/api/projects'),
          api.get('/api/notebook/entries'),
          api.get('/api/audit/logs')
        ])

        const inventory = inventoryResp.data
        const protocols = protocolsResp.data
        const projects = projectsResp.data
        const notebook = notebookResp.data
        const auditLogs = auditResp.data

        // Calculate metrics from actual data
        const totalItems = inventory.length
        const activeProjects = projects.filter((p: any) => p.status === 'active').length
        const completedProtocols = protocols.filter((p: any) => p.status === 'completed').length
        
        // Calculate recent activity from audit logs
        const recent = auditLogs.slice(0, 50) // Get recent 50 activities
        
        return {
          totalItems,
          activeProjects,
          completedProtocols,
          recentActivity: recent,
          inventory,
          protocols,
          projects,
          notebook
        }
      } catch (error) {
        console.error('Lab metrics query failed:', error)
        return {
          totalItems: 0,
          activeProjects: 0,
          completedProtocols: 0,
          recentActivity: [],
          inventory: [],
          protocols: [],
          projects: [],
          notebook: []
        }
      }
    },
    staleTime: 2 * 60 * 1000, // 2 minutes
  })
}
