'use client'
import { useState, useRef } from 'react'
import { Button, Input, Card, CardBody } from '../ui'
import { useInventoryFacets, useInventorySearch } from '../../hooks/useInventory'

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

interface AdvancedSearchProps {
  onFiltersChange: (filters: SearchFilters) => void
  onSearch: (query: string) => void
  currentFilters: SearchFilters
  className?: string
}

export default function AdvancedSearch({
  onFiltersChange,
  onSearch,
  currentFilters,
  className
}: AdvancedSearchProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [localFilters, setLocalFilters] = useState<SearchFilters>(currentFilters)
  const searchInputRef = useRef<HTMLInputElement>(null)
  
  const { data: facets, isLoading: facetsLoading } = useInventoryFacets()
  const searchMutation = useInventorySearch()

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (searchQuery.trim()) {
      onSearch(searchQuery.trim())
      searchMutation.mutate(searchQuery.trim())
    }
  }

  const handleFilterChange = (key: keyof SearchFilters, value: any) => {
    const newFilters = { ...localFilters, [key]: value }
    setLocalFilters(newFilters)
    onFiltersChange(newFilters)
  }

  const clearFilters = () => {
    const emptyFilters = {}
    setLocalFilters(emptyFilters)
    setSearchQuery('')
    onFiltersChange(emptyFilters)
  }

  const activeFilterCount = Object.keys(currentFilters).filter(
    key => currentFilters[key as keyof SearchFilters] !== undefined && 
          currentFilters[key as keyof SearchFilters] !== ''
  ).length

  return (
    <Card className={className}>
      <CardBody className="p-4">
        {/* Search Bar */}
        <form onSubmit={handleSearchSubmit} className="mb-4">
          <div className="flex space-x-2">
            <div className="flex-1 relative">
              <Input
                ref={searchInputRef}
                placeholder="Search inventory by name, type, or barcode..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pr-10"
              />
              <div className="absolute inset-y-0 right-0 flex items-center pr-3">
                <svg className="w-4 h-4 text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="m21 21-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
                </svg>
              </div>
            </div>
            <Button 
              type="submit" 
              loading={searchMutation.isPending}
              disabled={!searchQuery.trim()}
            >
              Search
            </Button>
          </div>
        </form>

        {/* Filter Toggle */}
        <div className="flex items-center justify-between mb-4">
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center space-x-2 text-sm font-medium text-neutral-700 hover:text-primary-600 transition-colors"
          >
            <svg 
              className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`} 
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
            <span>Advanced Filters</span>
            {activeFilterCount > 0 && (
              <span className="bg-primary-100 text-primary-600 px-2 py-0.5 rounded-full text-xs font-medium">
                {activeFilterCount}
              </span>
            )}
          </button>
          
          {activeFilterCount > 0 && (
            <button
              onClick={clearFilters}
              className="text-sm text-neutral-500 hover:text-neutral-700 transition-colors"
            >
              Clear all
            </button>
          )}
        </div>

        {/* Advanced Filters */}
        {isExpanded && (
          <div className="space-y-4 pt-4 border-t border-neutral-200">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {/* Item Type Filter */}
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  Item Type
                </label>
                <select
                  value={localFilters.item_type || ''}
                  onChange={(e) => handleFilterChange('item_type', e.target.value || undefined)}
                  className="w-full px-3 py-2 border border-neutral-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  disabled={facetsLoading}
                >
                  <option value="">All types</option>
                  {facets?.item_types.map(type => (
                    <option key={type.value} value={type.value}>
                      {type.value} ({type.count})
                    </option>
                  ))}
                </select>
              </div>

              {/* Status Filter */}
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  Status
                </label>
                <select
                  value={localFilters.status || ''}
                  onChange={(e) => handleFilterChange('status', e.target.value || undefined)}
                  className="w-full px-3 py-2 border border-neutral-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  disabled={facetsLoading}
                >
                  <option value="">All statuses</option>
                  {facets?.statuses.map(status => (
                    <option key={status.value} value={status.value}>
                      {status.value} ({status.count})
                    </option>
                  ))}
                </select>
              </div>

              {/* Team Filter */}
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  Team
                </label>
                <select
                  value={localFilters.team_id || ''}
                  onChange={(e) => handleFilterChange('team_id', e.target.value || undefined)}
                  className="w-full px-3 py-2 border border-neutral-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  disabled={facetsLoading}
                >
                  <option value="">All teams</option>
                  {facets?.teams.map(team => (
                    <option key={team.value} value={team.value}>
                      {team.name} ({team.count})
                    </option>
                  ))}
                </select>
              </div>

              {/* Barcode Search */}
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  Barcode
                </label>
                <Input
                  placeholder="Search by barcode..."
                  value={localFilters.barcode || ''}
                  onChange={(e) => handleFilterChange('barcode', e.target.value || undefined)}
                />
              </div>

              {/* Date Range */}
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  Created From
                </label>
                <Input
                  type="date"
                  value={localFilters.created_from || ''}
                  onChange={(e) => handleFilterChange('created_from', e.target.value || undefined)}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  Created To
                </label>
                <Input
                  type="date"
                  value={localFilters.created_to || ''}
                  onChange={(e) => handleFilterChange('created_to', e.target.value || undefined)}
                />
              </div>
            </div>

            {/* Active Filters Summary */}
            {activeFilterCount > 0 && (
              <div className="flex flex-wrap gap-2 pt-2">
                {Object.entries(currentFilters).map(([key, value]) => {
                  if (!value) return null
                  
                  let displayValue = value as string
                  if (key === 'team_id') {
                    const team = facets?.teams.find(t => t.value === value)
                    displayValue = team?.name || value as string
                  }
                  
                  return (
                    <span
                      key={key}
                      className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-primary-100 text-primary-800"
                    >
                      {key.replace('_', ' ')}: {displayValue}
                      <button
                        onClick={() => handleFilterChange(key as keyof SearchFilters, undefined)}
                        className="ml-1.5 text-primary-600 hover:text-primary-800"
                      >
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </span>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {/* Search Results Preview */}
        {searchMutation.data && searchMutation.data.length > 0 && (
          <div className="mt-4 pt-4 border-t border-neutral-200">
            <h4 className="text-sm font-medium text-neutral-700 mb-2">
              Search Results ({searchMutation.data.length})
            </h4>
            <div className="space-y-1 max-h-32 overflow-y-auto">
              {searchMutation.data.slice(0, 5).map(item => (
                <div key={item.id} className="text-sm text-neutral-600 hover:text-neutral-900 cursor-pointer">
                  {item.name} ({item.item_type})
                </div>
              ))}
              {searchMutation.data.length > 5 && (
                <div className="text-xs text-neutral-500">
                  +{searchMutation.data.length - 5} more results
                </div>
              )}
            </div>
          </div>
        )}
      </CardBody>
    </Card>
  )
}