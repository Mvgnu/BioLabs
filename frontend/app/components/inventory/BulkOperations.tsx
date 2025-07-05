'use client'
import { useState } from 'react'
import { Button, Input, Alert } from '../ui'
import { 
  useBulkUpdateItems, 
  useBulkDeleteItems, 
  useInventoryExport, 
  useInventoryImport,
  useInventoryFacets
} from '../../hooks/useInventory'
import type { InventoryItem } from '../../types'

interface BulkOperationsProps {
  selectedItems: InventoryItem[]
  onSelectionClear: () => void
  onItemsUpdated: () => void
  currentFilters?: Record<string, any>
}

export default function BulkOperations({
  selectedItems,
  onSelectionClear,
  onItemsUpdated,
  currentFilters
}: BulkOperationsProps) {
  const [operation, setOperation] = useState<'update' | 'delete' | 'export' | 'import' | null>(null)
  const [bulkUpdateData, setBulkUpdateData] = useState({
    status: '',
    item_type: '',
    custom_data: {}
  })
  const [importFile, setImportFile] = useState<File | null>(null)
  const [showConfirmation, setShowConfirmation] = useState(false)

  const bulkUpdate = useBulkUpdateItems()
  const bulkDelete = useBulkDeleteItems()
  const exportMutation = useInventoryExport()
  const importMutation = useInventoryImport()
  const { data: facets } = useInventoryFacets()

  const selectedCount = selectedItems.length

  const handleBulkUpdate = async () => {
    if (selectedCount === 0) return

    const updates = selectedItems.map(item => ({
      id: item.id,
      data: {
        ...(bulkUpdateData.status && { status: bulkUpdateData.status }),
        ...(bulkUpdateData.item_type && { item_type: bulkUpdateData.item_type }),
        ...(Object.keys(bulkUpdateData.custom_data).length > 0 && { 
          custom_data: { ...item.custom_data, ...bulkUpdateData.custom_data }
        })
      }
    }))

    try {
      await bulkUpdate.mutateAsync(updates)
      onItemsUpdated()
      onSelectionClear()
      setOperation(null)
      setBulkUpdateData({ status: '', item_type: '', custom_data: {} })
    } catch (error) {
      console.error('Bulk update failed:', error)
    }
  }

  const handleBulkDelete = async () => {
    if (selectedCount === 0) return

    try {
      await bulkDelete.mutateAsync(selectedItems.map(item => item.id))
      onItemsUpdated()
      onSelectionClear()
      setOperation(null)
      setShowConfirmation(false)
    } catch (error) {
      console.error('Bulk delete failed:', error)
    }
  }

  const handleExport = async () => {
    try {
      await exportMutation.mutateAsync(currentFilters)
      setOperation(null)
    } catch (error) {
      console.error('Export failed:', error)
    }
  }

  const handleImport = async () => {
    if (!importFile) return

    try {
      await importMutation.mutateAsync(importFile)
      onItemsUpdated()
      setOperation(null)
      setImportFile(null)
    } catch (error) {
      console.error('Import failed:', error)
    }
  }

  if (operation === 'delete' && showConfirmation) {
    return (
      <div className="bg-white border border-red-200 rounded-lg p-4">
        <Alert variant="error" className="mb-4">
          <div>
            <h3 className="font-medium">Confirm Deletion</h3>
            <p className="mt-1">
              Are you sure you want to delete {selectedCount} selected item{selectedCount !== 1 ? 's' : ''}? 
              This action cannot be undone.
            </p>
          </div>
        </Alert>
        
        <div className="flex justify-end space-x-3">
          <Button 
            variant="ghost" 
            onClick={() => {
              setShowConfirmation(false)
              setOperation(null)
            }}
          >
            Cancel
          </Button>
          <Button 
            variant="danger" 
            onClick={handleBulkDelete}
            loading={bulkDelete.isPending}
          >
            Delete {selectedCount} Item{selectedCount !== 1 ? 's' : ''}
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white border border-neutral-200 rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-3">
          <span className="text-sm font-medium text-neutral-700">
            {selectedCount > 0 ? (
              `${selectedCount} item${selectedCount !== 1 ? 's' : ''} selected`
            ) : (
              'Bulk Operations'
            )}
          </span>
          {selectedCount > 0 && (
            <button
              onClick={onSelectionClear}
              className="text-sm text-neutral-500 hover:text-neutral-700 transition-colors"
            >
              Clear selection
            </button>
          )}
        </div>

        {!operation && (
          <div className="flex items-center space-x-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setOperation('export')}
              disabled={exportMutation.isPending}
            >
              <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Export
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setOperation('import')}
            >
              <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10" />
              </svg>
              Import
            </Button>
            {selectedCount > 0 && (
              <>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => setOperation('update')}
                >
                  Update Selected
                </Button>
                <Button
                  variant="danger"
                  size="sm"
                  onClick={() => {
                    setOperation('delete')
                    setShowConfirmation(true)
                  }}
                >
                  Delete Selected
                </Button>
              </>
            )}
          </div>
        )}
      </div>

      {/* Bulk Update Form */}
      {operation === 'update' && (
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-neutral-900">
            Update {selectedCount} Selected Item{selectedCount !== 1 ? 's' : ''}
          </h3>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">
                Status
              </label>
              <select
                value={bulkUpdateData.status}
                onChange={(e) => setBulkUpdateData(prev => ({ ...prev, status: e.target.value }))}
                className="w-full px-3 py-2 border border-neutral-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              >
                <option value="">Keep current status</option>
                {facets?.statuses.map(status => (
                  <option key={status.value} value={status.value}>
                    {status.value}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">
                Item Type
              </label>
              <select
                value={bulkUpdateData.item_type}
                onChange={(e) => setBulkUpdateData(prev => ({ ...prev, item_type: e.target.value }))}
                className="w-full px-3 py-2 border border-neutral-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              >
                <option value="">Keep current type</option>
                {facets?.item_types.map(type => (
                  <option key={type.value} value={type.value}>
                    {type.value}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex justify-end space-x-3">
            <Button 
              variant="ghost" 
              onClick={() => {
                setOperation(null)
                setBulkUpdateData({ status: '', item_type: '', custom_data: {} })
              }}
            >
              Cancel
            </Button>
            <Button 
              variant="primary" 
              onClick={handleBulkUpdate}
              loading={bulkUpdate.isPending}
              disabled={!bulkUpdateData.status && !bulkUpdateData.item_type}
            >
              Update Items
            </Button>
          </div>
        </div>
      )}

      {/* Export Form */}
      {operation === 'export' && (
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-neutral-900">Export Inventory</h3>
          <p className="text-sm text-neutral-600">
            {currentFilters && Object.keys(currentFilters).length > 0
              ? 'Export filtered inventory items to CSV'
              : 'Export all inventory items to CSV'
            }
          </p>

          <div className="flex justify-end space-x-3">
            <Button 
              variant="ghost" 
              onClick={() => setOperation(null)}
            >
              Cancel
            </Button>
            <Button 
              variant="primary" 
              onClick={handleExport}
              loading={exportMutation.isPending}
            >
              <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Download CSV
            </Button>
          </div>
        </div>
      )}

      {/* Import Form */}
      {operation === 'import' && (
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-neutral-900">Import Inventory</h3>
          <p className="text-sm text-neutral-600">
            Upload a CSV file to import inventory items. The file should include columns: 
            item_type, name, barcode, status, and any custom field data.
          </p>

          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-2">
              Select CSV File
            </label>
            <input
              type="file"
              accept=".csv"
              onChange={(e) => setImportFile(e.target.files?.[0] || null)}
              className="block w-full text-sm text-neutral-500
                file:mr-4 file:py-2 file:px-4
                file:rounded-md file:border-0
                file:text-sm file:font-medium
                file:bg-primary-50 file:text-primary-700
                hover:file:bg-primary-100"
            />
          </div>

          {importMutation.error && (
            <Alert variant="error">
              Import failed. Please check your CSV format and try again.
            </Alert>
          )}

          <div className="flex justify-end space-x-3">
            <Button 
              variant="ghost" 
              onClick={() => {
                setOperation(null)
                setImportFile(null)
              }}
            >
              Cancel
            </Button>
            <Button 
              variant="primary" 
              onClick={handleImport}
              loading={importMutation.isPending}
              disabled={!importFile}
            >
              <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10" />
              </svg>
              Import CSV
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}