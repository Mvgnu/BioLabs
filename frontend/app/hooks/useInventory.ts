'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import type { InventoryItem } from '../types'

interface InventoryFilters {
  name?: string
  status?: string
  item_type?: string
  team_id?: string
  barcode?: string
  created_from?: string
  created_to?: string
  custom?: Record<string, any>
}

interface InventoryFacets {
  item_types: Array<{ value: string; count: number }>
  statuses: Array<{ value: string; count: number }>
  teams: Array<{ value: string; count: number; name: string }>
  fields: Array<{ field_key: string; field_label: string; field_type: string }>
}

// Core inventory operations
export const useInventoryItems = (filters?: InventoryFilters) => {
  return useQuery({
    queryKey: ['inventory', filters],
    queryFn: async () => {
      try {
        const resp = await api.get('/api/inventory/items', { params: filters })
        return resp.data as InventoryItem[]
      } catch (error) {
        console.error('Failed to fetch inventory items:', error)
        return []
      }
    },
    staleTime: 2 * 60 * 1000, // 2 minutes
  })
}

export const useInventoryItem = (id: string) => {
  return useQuery({
    queryKey: ['inventory', 'item', id],
    queryFn: async () => {
      const resp = await api.get(`/api/inventory/items/${id}`)
      return resp.data as InventoryItem
    },
    enabled: !!id,
  })
}

export const useCreateItem = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: Partial<InventoryItem>) => {
      const resp = await api.post('/api/inventory/items', data)
      return resp.data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['inventory'] })
      qc.invalidateQueries({ queryKey: ['inventory-facets'] })
    },
  })
}

export const useUpdateItem = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: { id: string; data: Partial<InventoryItem> }) => {
      const resp = await api.put(`/api/inventory/items/${vars.id}`, vars.data)
      return resp.data
    },
    onSuccess: (data, vars) => {
      qc.invalidateQueries({ queryKey: ['inventory'] })
      qc.invalidateQueries({ queryKey: ['inventory', 'item', vars.id] })
      qc.invalidateQueries({ queryKey: ['inventory-facets'] })
    },
  })
}

export const useDeleteItem = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/api/inventory/items/${id}`)
      return id
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['inventory'] })
      qc.invalidateQueries({ queryKey: ['inventory-facets'] })
    },
  })
}

// Advanced search and filtering
export const useInventoryFacets = () => {
  return useQuery({
    queryKey: ['inventory-facets'],
    queryFn: async () => {
      try {
        const resp = await api.get('/api/inventory/facets')
        return resp.data as InventoryFacets
      } catch (error) {
        console.error('Failed to fetch inventory facets:', error)
        return {
          item_types: [],
          statuses: [],
          teams: [],
          fields: []
        }
      }
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

// Bulk operations
export const useInventoryExport = () => {
  return useMutation({
    mutationFn: async (filters?: InventoryFilters) => {
      const resp = await api.get('/api/inventory/export', {
        params: filters,
        responseType: 'blob'
      })
      
      // Create download link
      const url = window.URL.createObjectURL(new Blob([resp.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `inventory-${new Date().toISOString().split('T')[0]}.csv`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      
      return resp.data
    },
  })
}

export const useInventoryImport = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      
      const resp = await api.post('/api/inventory/import', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })
      return resp.data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['inventory'] })
      qc.invalidateQueries({ queryKey: ['inventory-facets'] })
    },
  })
}

// Barcode operations
export const useGenerateBarcode = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (itemId: string) => {
      const resp = await api.post(`/api/inventory/items/${itemId}/barcode`, {}, {
        responseType: 'blob'
      })
      
      // Create download link for barcode image
      const url = window.URL.createObjectURL(new Blob([resp.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `barcode-${itemId}.png`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      
      return resp.data
    },
    onSuccess: (data, itemId) => {
      qc.invalidateQueries({ queryKey: ['inventory', 'item', itemId] })
    },
  })
}

// Relationship management
export const useItemRelationships = (itemId: string) => {
  return useQuery({
    queryKey: ['inventory', 'relationships', itemId],
    queryFn: async () => {
      try {
        const resp = await api.get(`/api/inventory/items/${itemId}/relationships`)
        return resp.data as Array<{
          id: string
          from_item: string
          to_item: string
          relationship_type: string
          meta: Record<string, any>
        }>
      } catch (error) {
        console.error('Failed to fetch item relationships:', error)
        return []
      }
    },
    enabled: !!itemId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

export const useItemGraph = (itemId: string, depth: number = 2) => {
  return useQuery({
    queryKey: ['inventory', 'graph', itemId, depth],
    queryFn: async () => {
      try {
        const resp = await api.get(`/api/inventory/items/${itemId}/graph`, {
          params: { depth }
        })
        return resp.data as {
          nodes: InventoryItem[]
          edges: Array<{
            id: string
            from_item: string
            to_item: string
            relationship_type: string
            meta: Record<string, any>
          }>
        }
      } catch (error) {
        console.error('Failed to fetch item graph:', error)
        return { nodes: [], edges: [] }
      }
    },
    enabled: !!itemId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

export const useCreateRelationship = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      from_item: string
      to_item: string
      relationship_type: string
      meta?: Record<string, any>
    }) => {
      try {
        const resp = await api.post('/api/inventory/relationships', data)
        return resp.data as {
          id: string
          from_item: string
          to_item: string
          relationship_type: string
          meta: Record<string, any>
        }
      } catch (error) {
        console.error('Failed to create relationship:', error)
        throw error
      }
    },
    onSuccess: (data, vars) => {
      qc.invalidateQueries({ queryKey: ['inventory', 'relationships', vars.from_item] })
      qc.invalidateQueries({ queryKey: ['inventory', 'relationships', vars.to_item] })
      qc.invalidateQueries({ queryKey: ['inventory', 'graph'] })
    },
  })
}

// Search operations
export const useInventorySearch = () => {
  return useMutation({
    mutationFn: async (query: string) => {
      const resp = await api.get('/api/search/items', {
        params: { q: query }
      })
      return resp.data as InventoryItem[]
    },
  })
}

// Bulk operations for multiple items
export const useBulkUpdateItems = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (updates: Array<{ id: string; data: Partial<InventoryItem> }>) => {
      try {
        const response = await api.post('/api/inventory/bulk/update', {
          items: updates.map(update => ({
            id: update.id,
            data: update.data
          }))
        })
        
        return {
          successful: response.data.results.filter((r: any) => r.success).map((r: any) => r.item_id),
          failed: response.data.results.filter((r: any) => !r.success).map((r: any) => ({ 
            id: r.item_id, 
            error: r.error 
          })),
          total: response.data.total,
          successfulCount: response.data.successful,
          failedCount: response.data.failed
        }
      } catch (error) {
        console.error('Bulk update failed:', error)
        throw error
      }
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['inventory'] })
      qc.invalidateQueries({ queryKey: ['inventory-facets'] })
      
      // Log failed updates for debugging
      if (data.failed.length > 0) {
        console.warn('Some bulk updates failed:', data.failed)
      }
    },
  })
}

export const useBulkDeleteItems = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (ids: string[]) => {
      try {
        const response = await api.post('/api/inventory/bulk/delete', {
          item_ids: ids
        })
        
        return {
          successful: response.data.results.filter((r: any) => r.success).map((r: any) => r.item_id),
          failed: response.data.results.filter((r: any) => !r.success).map((r: any) => ({ 
            id: r.item_id, 
            error: r.error 
          })),
          total: response.data.total,
          successfulCount: response.data.successful,
          failedCount: response.data.failed
        }
      } catch (error) {
        console.error('Bulk delete failed:', error)
        throw error
      }
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['inventory'] })
      qc.invalidateQueries({ queryKey: ['inventory-facets'] })
      
      // Log failed deletions for debugging
      if (data.failed.length > 0) {
        console.warn('Some bulk deletions failed:', data.failed)
      }
    },
  })
}

// Location management
export const useLocations = () => {
  return useQuery({
    queryKey: ['locations'],
    queryFn: async () => {
      try {
        const resp = await api.get('/api/locations')
        return resp.data as Array<{
          id: string
          name: string
          parent_id?: string
          team_id?: string
          created_at: string
        }>
      } catch (error) {
        console.error('Failed to fetch locations:', error)
        return []
      }
    },
    staleTime: 10 * 60 * 1000, // 10 minutes
  })
}