'use client'
import React, { useState, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { Button, Card, CardBody, LoadingState, EmptyState } from '../ui'
import { useGenerateBarcode } from '../../hooks/useInventory'
import type { InventoryItem } from '../../types'

interface InventoryTableProps {
  items: InventoryItem[]
  loading: boolean
  error?: string
  selectedItems: InventoryItem[]
  onSelectionChange: (items: InventoryItem[]) => void
  onItemUpdate: (item: InventoryItem) => void
  onItemDelete: (itemId: string) => void
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
  onSort?: (field: string) => void
}

export default function InventoryTable({
  items,
  loading,
  error,
  selectedItems,
  onSelectionChange,
  onItemUpdate,
  onItemDelete,
  sortBy,
  sortOrder = 'asc',
  onSort
}: InventoryTableProps) {
  const router = useRouter()
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())
  const generateBarcode = useGenerateBarcode()

  const selectedIds = useMemo(() => 
    new Set(selectedItems.map(item => item.id)), 
    [selectedItems]
  )

  const isAllSelected = items.length > 0 && selectedIds.size === items.length
  const isPartiallySelected = selectedIds.size > 0 && selectedIds.size < items.length

  const handleSelectAll = () => {
    if (isAllSelected) {
      onSelectionChange([])
    } else {
      onSelectionChange(items)
    }
  }

  const handleSelectItem = (item: InventoryItem) => {
    if (selectedIds.has(item.id)) {
      onSelectionChange(selectedItems.filter(selected => selected.id !== item.id))
    } else {
      onSelectionChange([...selectedItems, item])
    }
  }

  const toggleRowExpansion = (itemId: string) => {
    const newExpanded = new Set(expandedRows)
    if (newExpanded.has(itemId)) {
      newExpanded.delete(itemId)
    } else {
      newExpanded.add(itemId)
    }
    setExpandedRows(newExpanded)
  }

  const handleSort = (field: string) => {
    if (onSort) {
      onSort(field)
    }
  }

  const SortableHeader = ({ field, children }: { field: string, children: React.ReactNode }) => (
    <th 
      className="px-6 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider cursor-pointer hover:bg-neutral-50 transition-colors"
      onClick={() => handleSort(field)}
    >
      <div className="flex items-center space-x-1">
        <span>{children}</span>
        {sortBy === field && (
          <svg 
            className={`w-3 h-3 ${sortOrder === 'desc' ? 'rotate-180' : ''}`} 
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
          </svg>
        )}
      </div>
    </th>
  )

  if (loading) {
    return (
      <Card>
        <CardBody>
          <LoadingState description="Loading inventory items..." />
        </CardBody>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <CardBody>
          <EmptyState
            title="Failed to load inventory"
            description={error}
            action={
              <Button onClick={() => window.location.reload()}>
                Try Again
              </Button>
            }
          />
        </CardBody>
      </Card>
    )
  }

  if (items.length === 0) {
    return (
      <Card>
        <CardBody>
          <EmptyState
            title="No inventory items found"
            description="Start by creating your first inventory item or adjust your search filters."
            action={
              <Button onClick={() => router.push('/inventory?action=create')}>
                Create Item
              </Button>
            }
          />
        </CardBody>
      </Card>
    )
  }

  return (
    <Card>
      <CardBody className="p-0">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-neutral-200">
            <thead className="bg-neutral-50">
              <tr>
                <th className="px-6 py-3 text-left">
                  <input
                    type="checkbox"
                    checked={isAllSelected}
                    ref={input => {
                      if (input) input.indeterminate = isPartiallySelected
                    }}
                    onChange={handleSelectAll}
                    className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-neutral-300 rounded"
                  />
                </th>
                <SortableHeader field="name">Name</SortableHeader>
                <SortableHeader field="item_type">Type</SortableHeader>
                <SortableHeader field="status">Status</SortableHeader>
                <SortableHeader field="barcode">Barcode</SortableHeader>
                <SortableHeader field="created_at">Created</SortableHeader>
                <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-neutral-200">
              {items.map((item) => (
                <React.Fragment key={item.id}>
                  <tr className={`hover:bg-neutral-50 transition-colors ${selectedIds.has(item.id) ? 'bg-primary-50' : ''}`}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <input
                        type="checkbox"
                        checked={selectedIds.has(item.id)}
                        onChange={() => handleSelectItem(item)}
                        className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-neutral-300 rounded"
                      />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <button
                          onClick={() => router.push(`/inventory/${item.id}`)}
                          className="text-sm font-medium text-primary-600 hover:text-primary-800 transition-colors"
                        >
                          {item.name}
                        </button>
                        {Object.keys(item.custom_data || {}).length > 0 && (
                          <button
                            onClick={() => toggleRowExpansion(item.id)}
                            className="ml-2 text-neutral-400 hover:text-neutral-600"
                            title="Show custom fields"
                          >
                            <svg 
                              className={`w-4 h-4 transition-transform ${expandedRows.has(item.id) ? 'rotate-180' : ''}`}
                              fill="none" 
                              stroke="currentColor" 
                              viewBox="0 0 24 24"
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                          </button>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-neutral-100 text-neutral-800">
                        {item.item_type}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        item.status === 'available' ? 'bg-success-100 text-success-800' :
                        item.status === 'used' ? 'bg-warning-100 text-warning-800' :
                        item.status === 'expired' ? 'bg-error-100 text-error-800' :
                        'bg-neutral-100 text-neutral-800'
                      }`}>
                        {item.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        {item.barcode ? (
                          <span className="text-sm font-mono text-neutral-900">{item.barcode}</span>
                        ) : (
                          <button
                            onClick={() => generateBarcode.mutate(item.id)}
                            disabled={generateBarcode.isPending}
                            className="text-sm text-primary-600 hover:text-primary-800 transition-colors"
                          >
                            Generate
                          </button>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-neutral-500">
                      {new Date(item.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => onItemUpdate(item)}
                          className="text-primary-600 hover:text-primary-800 transition-colors"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => onItemDelete(item.id)}
                          className="text-error-600 hover:text-error-800 transition-colors"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                  
                  {/* Expanded Row for Custom Fields */}
                  {expandedRows.has(item.id) && item.custom_data && Object.keys(item.custom_data).length > 0 && (
                    <tr className="bg-neutral-25">
                      <td colSpan={7} className="px-6 py-4">
                        <div className="text-sm">
                          <h4 className="font-medium text-neutral-700 mb-2">Custom Fields</h4>
                          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                            {Object.entries(item.custom_data).map(([key, value]) => (
                              <div key={key}>
                                <span className="text-neutral-500">{key}:</span>
                                <span className="ml-2 text-neutral-900">
                                  {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </CardBody>
    </Card>
  )
}