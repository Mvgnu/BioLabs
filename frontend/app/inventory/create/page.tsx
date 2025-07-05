'use client'
import { useState, useCallback, useEffect, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Button, Card, CardBody, LoadingState, EmptyState, Alert, Input } from '../../components/ui'
import { useCreateItem, useUpdateItem, useInventoryItem, useInventoryFacets } from '../../hooks/useInventory'
import type { InventoryItem } from '../../types'
import { Dialog } from '../../components/ui/Dialog'
import axios from 'axios'

function CreateInventoryItemContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const itemId = searchParams.get('id') || ''
  const isEditing = !!itemId
  
  const [formData, setFormData] = useState({
    name: '',
    item_type: '',
    status: 'available',
    barcode: '',
    custom_data: {} as Record<string, any>
  })
  const [customFields, setCustomFields] = useState<Array<{ key: string; value: string }>>([])
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [itemTypes, setItemTypes] = useState<{ id: string; name: string; description?: string }[]>([])
  const [typeDialogOpen, setTypeDialogOpen] = useState(false)
  const [newTypeName, setNewTypeName] = useState('')
  const [newTypeDesc, setNewTypeDesc] = useState('')
  const [typeError, setTypeError] = useState('')
  const [typeLoading, setTypeLoading] = useState(false)

  // Data fetching
  const { data: item, isLoading: itemLoading } = useInventoryItem(isEditing ? itemId : '')
  const { data: facets, isLoading: facetsLoading } = useInventoryFacets()
  
  // Mutations
  const createItem = useCreateItem()
  const updateItem = useUpdateItem()

  // Initialize form data when editing
  useEffect(() => {
    if (item && isEditing) {
      setFormData({
        name: item.name,
        item_type: item.item_type,
        status: item.status || 'available',
        barcode: item.barcode || '',
        custom_data: item.custom_data || {}
      })
      
      // Convert custom data to array for form
      const customArray = Object.entries(item.custom_data || {}).map(([key, value]) => ({
        key,
        value: String(value)
      }))
      setCustomFields(customArray)
    }
  }, [item, isEditing])

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

  // Add new type
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
      setFormData(prev => ({ ...prev, item_type: newTypeName }))
    } catch (err: any) {
      setTypeError(err?.response?.data?.detail || 'Failed to add type')
    } finally {
      setTypeLoading(false)
    }
  }

  // Validation
  const validateForm = useCallback(() => {
    const newErrors: Record<string, string> = {}
    
    if (!formData.name.trim()) {
      newErrors.name = 'Name is required'
    }
    
    if (!formData.item_type) {
      newErrors.item_type = 'Item type is required'
    }
    
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }, [formData])

  // Event handlers
  const handleFieldChange = useCallback((field: string, value: any) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }))
    
    // Clear error when user starts typing
    if (errors[field]) {
      setErrors(prev => ({
        ...prev,
        [field]: ''
      }))
    }
  }, [errors])

  const handleCustomFieldChange = useCallback((index: number, field: 'key' | 'value', value: string) => {
    setCustomFields(prev => {
      const newFields = [...prev]
      newFields[index] = { ...newFields[index], [field]: value }
      return newFields
    })
  }, [])

  const addCustomField = useCallback(() => {
    setCustomFields(prev => [...prev, { key: '', value: '' }])
  }, [])

  const removeCustomField = useCallback((index: number) => {
    setCustomFields(prev => prev.filter((_, i) => i !== index))
  }, [])

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!validateForm()) {
      return
    }
    
    setIsSubmitting(true)
    
    try {
      // Convert custom fields array to object
      const customData = customFields.reduce((acc, field) => {
        if (field.key.trim()) {
          acc[field.key.trim()] = field.value
        }
        return acc
      }, {} as Record<string, any>)
      
      const submitData = {
        ...formData,
        custom_data: customData
      }
      
      if (isEditing && item) {
        await updateItem.mutateAsync({
          id: item.id,
          data: submitData
        })
      } else {
        await createItem.mutateAsync(submitData)
      }
      
      router.push('/inventory')
    } catch (error) {
      console.error('Failed to save item:', error)
      setErrors({ submit: 'Failed to save item. Please try again.' })
    } finally {
      setIsSubmitting(false)
    }
  }, [validateForm, customFields, formData, isEditing, item, updateItem, createItem, router])

  const handleCancel = useCallback(() => {
    router.push('/inventory')
  }, [router])

  // Loading states
  if (itemLoading || facetsLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <LoadingState description="Loading..." />
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-neutral-900">
              {isEditing ? 'Edit Item' : 'Create New Item'}
            </h1>
            <p className="text-neutral-600 mt-1">
              {isEditing ? 'Update inventory item details' : 'Add a new item to your inventory'}
            </p>
          </div>
          <Button
            variant="ghost"
            onClick={handleCancel}
          >
            Cancel
          </Button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-6">
          <Card>
            <CardBody className="p-6">
              <h2 className="text-xl font-semibold text-neutral-900 mb-4">
                Basic Information
              </h2>
              
              <div className="space-y-4">
                {/* Name */}
                <div>
                  <label className="block text-sm font-medium text-neutral-700 mb-1">
                    Name *
                  </label>
                  <Input
                    value={formData.name}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleFieldChange('name', e.target.value)}
                    placeholder="Enter item name"
                    error={errors.name}
                  />
                </div>
                
                {/* Item Type */}
                <div>
                  <label className="block text-sm font-medium text-neutral-700 mb-1">
                    Item Type *
                  </label>
                  <div className="flex items-center space-x-2">
                    <select
                      value={formData.item_type}
                      onChange={(e: React.ChangeEvent<HTMLSelectElement>) => handleFieldChange('item_type', e.target.value)}
                      className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 ${errors.item_type ? 'border-error-300' : 'border-neutral-300'}`}
                    >
                      <option value="">Select type</option>
                      {itemTypes.map(type => (
                        <option key={type.id} value={type.name}>{type.name}</option>
                      ))}
                    </select>
                    <Button type="button" variant="ghost" onClick={() => setTypeDialogOpen(true)}>
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                      </svg>
                      Add Type
                    </Button>
                  </div>
                  {errors.item_type && (
                    <p className="text-sm text-error-600 mt-1">{errors.item_type}</p>
                  )}
                </div>
                
                {/* Status */}
                <div>
                  <label className="block text-sm font-medium text-neutral-700 mb-1">
                    Status
                  </label>
                  <select
                    value={formData.status}
                    onChange={(e: React.ChangeEvent<HTMLSelectElement>) => handleFieldChange('status', e.target.value)}
                    className="w-full px-3 py-2 border border-neutral-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  >
                    <option value="available">Available</option>
                    <option value="used">In Use</option>
                    <option value="expired">Expired</option>
                    <option value="disposed">Disposed</option>
                    <option value="reserved">Reserved</option>
                    <option value="maintenance">Under Maintenance</option>
                  </select>
                </div>
                
                {/* Barcode */}
                <div>
                  <label className="block text-sm font-medium text-neutral-700 mb-1">
                    Barcode
                  </label>
                  <Input
                    value={formData.barcode}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleFieldChange('barcode', e.target.value)}
                    placeholder="Enter barcode (optional)"
                  />
                </div>
              </div>
            </CardBody>
          </Card>

          {/* Custom Fields */}
          <Card>
            <CardBody className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-neutral-900">
                  Custom Fields
                </h2>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={addCustomField}
                >
                  <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                  </svg>
                  Add Field
                </Button>
              </div>
              
              {customFields.length === 0 ? (
                <p className="text-neutral-500 text-center py-8">
                  No custom fields added. Click "Add Field" to add custom properties.
                </p>
              ) : (
                <div className="space-y-4">
                  {customFields.map((field, index) => (
                    <div key={index} className="flex items-center space-x-3">
                      <div className="flex-1">
                        <Input
                          value={field.key}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleCustomFieldChange(index, 'key', e.target.value)}
                          placeholder="Field name"
                        />
                      </div>
                      <div className="flex-1">
                        <Input
                          value={field.value}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleCustomFieldChange(index, 'value', e.target.value)}
                          placeholder="Field value"
                        />
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => removeCustomField(index)}
                        className="text-error-600 hover:text-error-800"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </CardBody>
          </Card>

          {/* Error Alert */}
          {errors.submit && (
            <Alert variant="error">
              {errors.submit}
            </Alert>
          )}

          {/* Submit Buttons */}
          <div className="flex items-center justify-end space-x-3">
            <Button
              type="button"
              variant="ghost"
              onClick={handleCancel}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              loading={isSubmitting}
              disabled={isSubmitting}
            >
              {isEditing ? 'Update Item' : 'Create Item'}
            </Button>
          </div>
        </form>
        {/* Dialog for adding new type */}
        <Dialog open={typeDialogOpen} onClose={() => setTypeDialogOpen(false)} title="Add Item Type">
          <form onSubmit={handleAddType} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">Type Name</label>
              <Input value={newTypeName} onChange={e => setNewTypeName(e.target.value)} required autoFocus />
            </div>
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">Description</label>
              <Input value={newTypeDesc} onChange={e => setNewTypeDesc(e.target.value)} />
            </div>
            {typeError && <p className="text-error-600 text-sm">{typeError}</p>}
            <div className="flex justify-end space-x-2">
              <Button type="button" variant="ghost" onClick={() => setTypeDialogOpen(false)}>Cancel</Button>
              <Button type="submit" loading={typeLoading} disabled={!newTypeName.trim()}>Add</Button>
            </div>
          </form>
        </Dialog>
      </div>
    </div>
  )
}

export default function CreateInventoryItem() {
  return (
    <Suspense fallback={<LoadingState description="Loading..." />}>
      <CreateInventoryItemContent />
    </Suspense>
  )
} 