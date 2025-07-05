'use client'
import { useState, useCallback, useEffect, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Button, Card, CardBody, LoadingState, EmptyState, Alert, Input } from '../../components/ui'
import { useInventoryItem, useUpdateItem, useDeleteItem, useItemRelationships, useItemGraph } from '../../hooks/useInventory'
import type { InventoryItem } from '../../types'
import { Dialog } from '../../components/ui/Dialog'
import axios from 'axios'

interface InventoryItemDetailProps {
  params: { id: string }
}

function InventoryItemDetailContent({ params }: InventoryItemDetailProps) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const action = searchParams.get('action')
  
  const [isEditing, setIsEditing] = useState(action === 'edit')
  const [editData, setEditData] = useState<Partial<InventoryItem>>({})
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [itemTypes, setItemTypes] = useState<{ id: string; name: string; description?: string }[]>([])
  const [typeDialogOpen, setTypeDialogOpen] = useState(false)
  const [newTypeName, setNewTypeName] = useState('')
  const [newTypeDesc, setNewTypeDesc] = useState('')
  const [typeError, setTypeError] = useState('')
  const [typeLoading, setTypeLoading] = useState(false)

  // Data fetching
  const { data: item, isLoading, error } = useInventoryItem(params.id)
  const { data: relationships } = useItemRelationships(params.id)
  const { data: graph } = useItemGraph(params.id, 2)
  
  // Mutations
  const updateItem = useUpdateItem()
  const deleteItem = useDeleteItem()

  // Fetch item types from API
  const fetchItemTypes = useCallback(async () => {
    try {
      const resp = await axios.get('/api/inventory/item-types')
      setItemTypes(resp.data)
    } catch (e) {
      setItemTypes([])
    }
  }, [])

  useEffect(() => {
    fetchItemTypes()
  }, [fetchItemTypes])

  // Initialize edit data when item loads
  useEffect(() => {
    if (item && isEditing) {
      setEditData({
        name: item.name,
        item_type: item.item_type,
        status: item.status,
        barcode: item.barcode,
        custom_data: item.custom_data || {}
      })
    }
  }, [item, isEditing])

  // Event handlers
  const handleEdit = useCallback(() => {
    setIsEditing(true)
    if (item) {
      setEditData({
        name: item.name,
        item_type: item.item_type,
        status: item.status,
        barcode: item.barcode,
        custom_data: item.custom_data || {}
      })
    }
  }, [item])

  const handleSave = useCallback(async () => {
    if (!item) return
    
    try {
      await updateItem.mutateAsync({
        id: item.id,
        data: editData
      })
      setIsEditing(false)
    } catch (error) {
      console.error('Failed to update item:', error)
    }
  }, [item, editData, updateItem])

  const handleCancel = useCallback(() => {
    setIsEditing(false)
    setEditData({})
  }, [])

  const handleDelete = useCallback(async () => {
    if (!item) return
    
    try {
      await deleteItem.mutateAsync(item.id)
      router.push('/inventory')
    } catch (error) {
      console.error('Failed to delete item:', error)
      setShowDeleteConfirm(false)
    }
  }, [item, deleteItem, router])

  const handleFieldChange = useCallback((field: string, value: any) => {
    setEditData(prev => ({
      ...prev,
      [field]: value
    }))
  }, [])

  const handleCustomFieldChange = useCallback((key: string, value: any) => {
    setEditData(prev => ({
      ...prev,
      custom_data: {
        ...prev.custom_data,
        [key]: value
      }
    }))
  }, [])

  // Add new item type
  const handleAddType = async (e: React.FormEvent) => {
    e.preventDefault()
    setTypeError('')
    setTypeLoading(true)
    try {
      await axios.post('/api/inventory/item-types', { name: newTypeName, description: newTypeDesc })
      setTypeDialogOpen(false)
      setNewTypeName('')
      setNewTypeDesc('')
      fetchItemTypes()
      setEditData(prev => ({ ...prev, item_type: newTypeName }))
    } catch (err: any) {
      setTypeError(err?.response?.data?.detail || 'Failed to add type')
    } finally {
      setTypeLoading(false)
    }
  }

  // Loading and error states
  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <LoadingState description="Loading inventory item..." />
      </div>
    )
  }

  if (error || !item) {
    return (
      <div className="container mx-auto px-4 py-8">
        <EmptyState
          title="Item not found"
          description="The inventory item you're looking for doesn't exist or you don't have permission to view it."
          action={
            <Button onClick={() => router.push('/inventory')}>
              Back to Inventory
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
          <div className="flex items-center space-x-3">
            <Button
              variant="ghost"
              onClick={() => router.push('/inventory')}
            >
              <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              Back
            </Button>
            <h1 className="text-3xl font-bold text-neutral-900">
              {isEditing ? 'Edit Item' : item.name}
            </h1>
          </div>
          <p className="text-neutral-600 mt-1">
            {isEditing ? 'Update item details and custom fields' : `Item ID: ${item.id}`}
          </p>
        </div>
        
        {!isEditing && (
          <div className="flex items-center space-x-3">
            <Button
              variant="ghost"
              onClick={handleEdit}
            >
              <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
              Edit
            </Button>
            <Button
              variant="danger"
              onClick={() => setShowDeleteConfirm(true)}
            >
              <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              Delete
            </Button>
          </div>
        )}
      </div>

      {/* Delete Confirmation */}
      {showDeleteConfirm && (
        <Alert variant="error">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="font-medium">Confirm Deletion</h4>
              <p className="text-sm">
                Are you sure you want to delete "{item.name}"? This action cannot be undone.
              </p>
            </div>
            <div className="flex items-center space-x-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowDeleteConfirm(false)}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={handleDelete}
                loading={deleteItem.isPending}
              >
                Delete
              </Button>
            </div>
          </div>
        </Alert>
      )}

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Item Details */}
        <div className="lg:col-span-2 space-y-6">
          {/* Basic Information */}
          <Card>
            <CardBody className="p-6">
              <h2 className="text-xl font-semibold text-neutral-900 mb-4">
                Basic Information
              </h2>
              
              {isEditing ? (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 mb-1">
                      Name *
                    </label>
                    <Input
                      value={editData.name || ''}
                      onChange={(e) => handleFieldChange('name', e.target.value)}
                      placeholder="Enter item name"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 mb-1">
                      Item Type *
                    </label>
                    <div className="flex space-x-2">
                      <select
                        value={editData.item_type || ''}
                        onChange={(e) => handleFieldChange('item_type', e.target.value)}
                        className="flex-1 px-3 py-2 border border-neutral-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                      >
                        <option value="">Select type</option>
                        {itemTypes.map(type => (
                          <option key={type.id} value={type.name}>
                            {type.name}
                          </option>
                        ))}
                      </select>
                      <Button
                        type="button"
                        variant="ghost"
                        onClick={() => setTypeDialogOpen(true)}
                        className="px-3 py-2"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                        </svg>
                      </Button>
                    </div>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 mb-1">
                      Status
                    </label>
                    <select
                      value={editData.status || ''}
                      onChange={(e) => handleFieldChange('status', e.target.value)}
                      className="w-full px-3 py-2 border border-neutral-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                    >
                      <option value="">Select status</option>
                      <option value="available">Available</option>
                      <option value="used">In Use</option>
                      <option value="expired">Expired</option>
                      <option value="disposed">Disposed</option>
                    </select>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 mb-1">
                      Barcode
                    </label>
                    <Input
                      value={editData.barcode || ''}
                      onChange={(e) => handleFieldChange('barcode', e.target.value)}
                      placeholder="Enter barcode"
                    />
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 mb-1">
                      Name
                    </label>
                    <p className="text-neutral-900">{item.name}</p>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 mb-1">
                      Item Type
                    </label>
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-neutral-100 text-neutral-800">
                      {item.item_type}
                    </span>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 mb-1">
                      Status
                    </label>
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      item.status === 'available' ? 'bg-success-100 text-success-800' :
                      item.status === 'used' ? 'bg-warning-100 text-warning-800' :
                      item.status === 'expired' ? 'bg-error-100 text-error-800' :
                      'bg-neutral-100 text-neutral-800'
                    }`}>
                      {item.status}
                    </span>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 mb-1">
                      Barcode
                    </label>
                    <p className="text-neutral-900 font-mono">
                      {item.barcode || 'Not assigned'}
                    </p>
                  </div>
                </div>
              )}
            </CardBody>
          </Card>

          {/* Custom Fields */}
          <Card>
            <CardBody className="p-6">
              <h2 className="text-xl font-semibold text-neutral-900 mb-4">
                Custom Fields
              </h2>
              
              {isEditing ? (
                <div className="space-y-4">
                  {Object.keys(editData.custom_data || {}).map(key => (
                    <div key={key}>
                      <label className="block text-sm font-medium text-neutral-700 mb-1">
                        {key}
                      </label>
                      <Input
                        value={editData.custom_data?.[key] || ''}
                        onChange={(e) => handleCustomFieldChange(key, e.target.value)}
                        placeholder={`Enter ${key}`}
                      />
                    </div>
                  ))}
                  
                  <Button
                    variant="ghost"
                    onClick={() => {
                      const newKey = prompt('Enter field name:')
                      if (newKey && newKey.trim()) {
                        handleCustomFieldChange(newKey.trim(), '')
                      }
                    }}
                  >
                    <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                    </svg>
                    Add Custom Field
                  </Button>
                </div>
              ) : (
                <div>
                  {Object.keys(item.custom_data || {}).length > 0 ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {Object.entries(item.custom_data || {}).map(([key, value]) => (
                        <div key={key}>
                          <label className="block text-sm font-medium text-neutral-700 mb-1">
                            {key}
                          </label>
                          <p className="text-neutral-900">
                            {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                          </p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-neutral-500">No custom fields defined</p>
                  )}
                </div>
              )}
            </CardBody>
          </Card>

          {/* Relationships */}
          {relationships && relationships.length > 0 && (
            <Card>
              <CardBody className="p-6">
                <h2 className="text-xl font-semibold text-neutral-900 mb-4">
                  Relationships ({relationships.length})
                </h2>
                <div className="space-y-3">
                  {relationships.map(rel => (
                    <div key={rel.id} className="flex items-center justify-between p-3 border border-neutral-200 rounded-lg">
                      <div>
                        <p className="text-sm font-medium text-neutral-900">
                          {rel.relationship_type}
                        </p>
                        <p className="text-xs text-neutral-500">
                          Related to item {rel.from_item === item.id ? rel.to_item : rel.from_item}
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => router.push(`/inventory/${rel.from_item === item.id ? rel.to_item : rel.from_item}`)}
                      >
                        View
                      </Button>
                    </div>
                  ))}
                </div>
              </CardBody>
            </Card>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Metadata */}
          <Card>
            <CardBody className="p-6">
              <h3 className="text-lg font-semibold text-neutral-900 mb-4">
                Metadata
              </h3>
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-neutral-500 mb-1">
                    Created
                  </label>
                  <p className="text-sm text-neutral-900">
                    {new Date(item.created_at).toLocaleDateString()}
                  </p>
                </div>
                
                <div>
                  <label className="block text-xs font-medium text-neutral-500 mb-1">
                    Last Updated
                  </label>
                  <p className="text-sm text-neutral-900">
                    {new Date(item.updated_at).toLocaleDateString()}
                  </p>
                </div>
                
                {item.team_id && (
                  <div>
                    <label className="block text-xs font-medium text-neutral-500 mb-1">
                      Team
                    </label>
                    <p className="text-sm text-neutral-900">
                      {item.team_id}
                    </p>
        </div>
      )}
                
                {item.owner_id && (
        <div>
                    <label className="block text-xs font-medium text-neutral-500 mb-1">
                      Owner
                    </label>
                    <p className="text-sm text-neutral-900">
                      {item.owner_id}
                    </p>
                  </div>
                )}
              </div>
            </CardBody>
          </Card>

          {/* Actions */}
          {isEditing && (
            <Card>
              <CardBody className="p-6">
                <h3 className="text-lg font-semibold text-neutral-900 mb-4">
                  Actions
                </h3>
                <div className="space-y-3">
                  <Button
                    onClick={handleSave}
                    loading={updateItem.isPending}
                    disabled={!editData.name || !editData.item_type}
                    className="w-full"
                  >
                    Save Changes
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={handleCancel}
                    className="w-full"
                  >
                    Cancel
                  </Button>
                </div>
              </CardBody>
            </Card>
          )}

          {/* Quick Actions */}
          {!isEditing && (
            <Card>
              <CardBody className="p-6">
                <h3 className="text-lg font-semibold text-neutral-900 mb-4">
                  Quick Actions
                </h3>
                <div className="space-y-3">
                  <Button
                    variant="ghost"
                    onClick={() => router.push(`/inventory/${item.id}?action=edit`)}
                    className="w-full justify-start"
                  >
                    <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                    Edit Item
                  </Button>
                  
                  <Button
                    variant="ghost"
                    onClick={() => router.push(`/notebook?item_id=${item.id}`)}
                    className="w-full justify-start"
                  >
                    <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    Add to Notebook
                  </Button>
                  
                  <Button
                    variant="ghost"
                    onClick={() => router.push(`/protocols?item_id=${item.id}`)}
                    className="w-full justify-start"
                  >
                    <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                    </svg>
                    View Protocols
                  </Button>
                </div>
              </CardBody>
            </Card>
          )}
        </div>
      </div>

      {/* Add Item Type Dialog */}
      <Dialog
        open={typeDialogOpen}
        onClose={() => {
          setTypeDialogOpen(false)
          setNewTypeName('')
          setNewTypeDesc('')
          setTypeError('')
        }}
        title="Add New Item Type"
      >
        <form onSubmit={handleAddType} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-1">
              Type Name *
            </label>
            <Input
              value={newTypeName}
              onChange={(e) => setNewTypeName(e.target.value)}
              placeholder="Enter type name"
              required
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-1">
              Description
            </label>
            <textarea
              value={newTypeDesc}
              onChange={(e) => setNewTypeDesc(e.target.value)}
              placeholder="Enter description (optional)"
              className="w-full px-3 py-2 border border-neutral-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              rows={3}
            />
          </div>
          
          {typeError && (
            <div className="text-sm text-red-600">
              {typeError}
            </div>
          )}
          
          <div className="flex justify-end space-x-3">
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setTypeDialogOpen(false)
                setNewTypeName('')
                setNewTypeDesc('')
                setTypeError('')
              }}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              loading={typeLoading}
              disabled={!newTypeName.trim()}
            >
              Add Type
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  )
}

export default function InventoryItemDetail({ params }: InventoryItemDetailProps) {
  return (
    <Suspense fallback={<LoadingState description="Loading..." />}>
      <InventoryItemDetailContent params={params} />
    </Suspense>
  )
}
