'use client'
import { useState, useCallback, useMemo, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Button, Card, CardBody, LoadingState, EmptyState, Alert } from '../components/ui'
import InventoryTable from '../components/inventory/InventoryTable'
import AdvancedSearch from '../components/inventory/AdvancedSearch'
import BulkOperations from '../components/inventory/BulkOperations'
import {
  useInventoryItems,
  useInventoryFacets,
  useCreateItem,
  useUpdateItem,
  useDeleteItem,
  useInventorySearch,
  useInventoryImport
} from '../hooks/useInventory'
import type { InventoryItem } from '../types'
import CreateInventoryItem from './create/page'
import { Dialog } from '../components/ui/Dialog'
import { useSearchParams, usePathname, useRouter as useNextRouter } from 'next/navigation'

interface SearchFilters {
  name?: string
  status?: string
  item_type?: string
  team_id?: string
  barcode?: string
  created_from?: string
  created_to?: string
  custom?: Record<string, any>
}

export default function InventoryPage() {
  const router = useRouter()
  const nextRouter = useNextRouter()
  const searchParams = useSearchParams()
  const pathname = usePathname()
  const [filters, setFilters] = useState<SearchFilters>({})
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedItems, setSelectedItems] = useState<InventoryItem[]>([])
  const [sortBy, setSortBy] = useState<string>('created_at')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [showImportDialog, setShowImportDialog] = useState(false)

  // Sync dialog state with URL
  useEffect(() => {
    const action = searchParams.get('action')
    setShowCreateDialog(action === 'create')
    setShowImportDialog(action === 'import')
  }, [searchParams])

  // Data fetching
  const { data: items = [], isLoading, error, refetch } = useInventoryItems(filters)
  const { data: facets } = useInventoryFacets()
  const searchMutation = useInventorySearch()
  
  // Mutations
  const createItem = useCreateItem()
  const updateItem = useUpdateItem()
  const deleteItem = useDeleteItem()
  const importMutation = useInventoryImport()

  // Computed values
  const filteredItems = useMemo(() => {
    let result = items

    // Apply search results if available
    if (searchMutation.data && searchQuery.trim()) {
      result = searchMutation.data
    }

    // Apply sorting
    result = [...result].sort((a, b) => {
      let aValue: any = a[sortBy as keyof InventoryItem]
      let bValue: any = b[sortBy as keyof InventoryItem]

      // Handle nested properties
      if (sortBy === 'team_id' && facets?.teams) {
        const teamA = facets.teams.find(t => t.value === a.team_id)
        const teamB = facets.teams.find(t => t.value === b.team_id)
        aValue = teamA?.name || ''
        bValue = teamB?.name || ''
      }

      // Handle dates
      if (aValue instanceof Date) aValue = aValue.getTime()
      if (bValue instanceof Date) bValue = bValue.getTime()
      if (typeof aValue === 'string' && aValue.match(/^\d{4}-\d{2}-\d{2}/)) {
        aValue = new Date(aValue).getTime()
        bValue = new Date(bValue).getTime()
      }

      // Handle null/undefined values
      if (aValue == null) aValue = ''
      if (bValue == null) bValue = ''

      // String comparison
      if (typeof aValue === 'string' && typeof bValue === 'string') {
        return sortOrder === 'asc' 
          ? aValue.localeCompare(bValue)
          : bValue.localeCompare(aValue)
      }

      // Numeric comparison
      if (sortOrder === 'asc') {
        return aValue < bValue ? -1 : aValue > bValue ? 1 : 0
      } else {
        return aValue > bValue ? -1 : aValue < bValue ? 1 : 0
      }
    })

    return result
  }, [items, searchMutation.data, searchQuery, sortBy, sortOrder, facets])

  // Event handlers
  const handleFiltersChange = useCallback((newFilters: SearchFilters) => {
    setFilters(newFilters)
    setSearchQuery('') // Clear search when filters change
  }, [])

  const handleSearch = useCallback((query: string) => {
    setSearchQuery(query)
    if (query.trim()) {
      searchMutation.mutate(query.trim())
    }
  }, [searchMutation])

  const handleSort = useCallback((field: string) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(field)
      setSortOrder('asc')
    }
  }, [sortBy, sortOrder])

  const handleSelectionChange = useCallback((items: InventoryItem[]) => {
    setSelectedItems(items)
  }, [])

  const handleItemUpdate = useCallback((item: InventoryItem) => {
    router.push(`/inventory/${item.id}?action=edit`)
  }, [router])

  const handleItemDelete = useCallback(async (itemId: string) => {
    if (confirm('Are you sure you want to delete this item? This action cannot be undone.')) {
      try {
        await deleteItem.mutateAsync(itemId)
        // Remove from selection if it was selected
        setSelectedItems(prev => prev.filter(item => item.id !== itemId))
      } catch (error) {
        console.error('Failed to delete item:', error)
      }
    }
  }, [deleteItem])

  const handleItemsUpdated = useCallback(() => {
    refetch()
    setSelectedItems([]) // Clear selection after bulk operations
  }, [refetch])

  const handleSelectionClear = useCallback(() => {
    setSelectedItems([])
  }, [])

  // Loading and error states
  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <LoadingState description="Loading inventory..." />
      </div>
    )
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-8">
        <EmptyState
          title="Failed to load inventory"
          description="There was an error loading your inventory items. Please try again."
          action={
            <Button onClick={() => refetch()}>
              Try Again
            </Button>
          }
        />
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-neutral-900">Inventory Management</h1>
          <p className="text-neutral-600 mt-1">
            Manage your laboratory inventory, track items, and perform bulk operations
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <Button
            variant="ghost"
            onClick={() => nextRouter.push(pathname + '?action=create')}
          >
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
            Create Item
          </Button>
          <Button
            onClick={() => nextRouter.push(pathname + '?action=import')}
          >
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10" />
            </svg>
            Import
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardBody className="p-4">
            <div className="flex items-center">
              <div className="p-2 bg-primary-100 rounded-lg">
                <svg className="w-6 h-6 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                </svg>
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-neutral-600">Total Items</p>
                <p className="text-2xl font-bold text-neutral-900">{items.length}</p>
              </div>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardBody className="p-4">
            <div className="flex items-center">
              <div className="p-2 bg-success-100 rounded-lg">
                <svg className="w-6 h-6 text-success-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-neutral-600">Available</p>
                <p className="text-2xl font-bold text-neutral-900">
                  {items.filter(item => item.status === 'available').length}
                </p>
              </div>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardBody className="p-4">
            <div className="flex items-center">
              <div className="p-2 bg-warning-100 rounded-lg">
                <svg className="w-6 h-6 text-warning-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-neutral-600">In Use</p>
                <p className="text-2xl font-bold text-neutral-900">
                  {items.filter(item => item.status === 'used').length}
                </p>
              </div>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardBody className="p-4">
            <div className="flex items-center">
              <div className="p-2 bg-error-100 rounded-lg">
                <svg className="w-6 h-6 text-error-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-neutral-600">Expired</p>
                <p className="text-2xl font-bold text-neutral-900">
                  {items.filter(item => item.status === 'expired').length}
                </p>
              </div>
            </div>
          </CardBody>
        </Card>
      </div>

      {/* Advanced Search */}
      <AdvancedSearch
        onFiltersChange={handleFiltersChange}
        onSearch={handleSearch}
        currentFilters={filters}
      />

      {/* Bulk Operations */}
      {selectedItems.length > 0 && (
        <BulkOperations
          selectedItems={selectedItems}
          onSelectionClear={handleSelectionClear}
          onItemsUpdated={handleItemsUpdated}
          currentFilters={filters}
        />
      )}

      {/* Results Summary */}
      {filteredItems.length > 0 && (
        <div className="flex items-center justify-between text-sm text-neutral-600">
          <span>
            Showing {filteredItems.length} of {items.length} items
            {searchQuery && ` matching "${searchQuery}"`}
            {Object.keys(filters).length > 0 && ' with filters applied'}
          </span>
          <div className="flex items-center space-x-2">
            <span>Sort by:</span>
            <select
              value={`${sortBy}-${sortOrder}`}
              onChange={(e) => {
                const [field, order] = e.target.value.split('-')
                setSortBy(field)
                setSortOrder(order as 'asc' | 'desc')
              }}
              className="text-sm border border-neutral-300 rounded px-2 py-1"
            >
              <option value="created_at-desc">Newest First</option>
              <option value="created_at-asc">Oldest First</option>
              <option value="name-asc">Name A-Z</option>
              <option value="name-desc">Name Z-A</option>
              <option value="status-asc">Status A-Z</option>
              <option value="status-desc">Status Z-A</option>
              <option value="item_type-asc">Type A-Z</option>
              <option value="item_type-desc">Type Z-A</option>
            </select>
          </div>
        </div>
      )}

      {/* Inventory Table */}
      <InventoryTable
        items={filteredItems}
        loading={isLoading}
        error={error ? String(error) : undefined}
        selectedItems={selectedItems}
        onSelectionChange={handleSelectionChange}
        onItemUpdate={handleItemUpdate}
        onItemDelete={handleItemDelete}
        sortBy={sortBy}
        sortOrder={sortOrder}
        onSort={handleSort}
      />

      {/* Search Results Alert */}
      {searchMutation.data && searchQuery.trim() && (
        <Alert variant="info">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="font-medium">Search Results</h4>
              <p className="text-sm">
                Found {searchMutation.data.length} items matching "{searchQuery}"
              </p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setSearchQuery('')
                searchMutation.reset()
              }}
            >
              Clear Search
            </Button>
          </div>
        </Alert>
      )}

      {/* Create Dialog */}
      <Dialog open={showCreateDialog} onClose={() => nextRouter.push(pathname)} title="Create New Item">
        <div className="max-w-2xl">
          <CreateInventoryItem />
        </div>
      </Dialog>
      {/* Import Dialog */}
      <Dialog open={showImportDialog} onClose={() => nextRouter.push(pathname)} title="Import Inventory">
        <ImportInventoryDialog onClose={() => nextRouter.push(pathname)} />
      </Dialog>
    </div>
  )
}

// Simple import dialog component
function ImportInventoryDialog({ onClose }: { onClose: () => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)
  const importMutation = useInventoryImport()

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFile(e.target.files?.[0] || null)
    setError('')
    setSuccess('')
  }

  const handleImport = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    if (!file) {
      setError('Please select a file to import.')
      return
    }
    setLoading(true)
    try {
      await importMutation.mutateAsync(file)
      setSuccess('Inventory imported successfully!')
      setFile(null)
      setTimeout(onClose, 1500)
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to import inventory.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleImport} className="space-y-4">
      <input type="file" accept=".csv,.xlsx" onChange={handleFileChange} />
      {error && <div className="text-error-600 text-sm">{error}</div>}
      {success && <div className="text-success-600 text-sm">{success}</div>}
      <div className="flex justify-end space-x-2">
        <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
        <Button type="submit" loading={loading} disabled={!file}>Import</Button>
      </div>
    </form>
  )
}
