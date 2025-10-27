'use client'
import React, { useState } from 'react'
import { useAnalytics, useTrendingItems } from '../hooks/useAnalytics'
import { useReviewerCadence } from './hooks/useReviewerCadence'
import {
  ReviewerCadenceAlerts,
  ReviewerCadenceTable,
} from './components'
import { 
  BarChart, 
  LineChart, 
  DoughnutChart, 
  HorizontalBarChart, 
  MetricCard 
} from '../components/charts/ChartComponents'
import { LoadingState } from '../components/ui'

export default function AnalyticsPage() {
  const [timeRange, setTimeRange] = useState('7d')
  const { data: inventoryDistribution, isLoading, error } = useAnalytics()
  const { data: trendingItems } = useTrendingItems()
  const reviewerCadenceQuery = useReviewerCadence()
  const reviewerCadence = reviewerCadenceQuery.reviewers

  if (error) {
    return (
      <div className="min-h-screen bg-neutral-50 p-6">
        <div className="max-w-7xl mx-auto">
          <div className="bg-error-50 border border-error-200 rounded-lg p-4">
            <h3 className="text-error-800 font-medium">Error loading analytics</h3>
            <p className="text-error-600 mt-1">{error.message}</p>
          </div>
        </div>
      </div>
    )
  }

  // Calculate summary metrics
  const totalItems = inventoryDistribution?.reduce((sum, item) => sum + item.count, 0) || 0
  const activeItems = Math.floor(totalItems * 0.85) // Mock active items calculation
  const trendingCount = trendingItems?.length || 0
  const avgTrendingScore = trendingItems && trendingItems.length > 0 
    ? trendingItems.reduce((sum, item) => sum + item.count, 0) / trendingItems.length 
    : 0

  // Mock data for charts that don't have endpoints yet
  const statusDistribution = [
    { label: 'Active', value: activeItems },
    { label: 'Inactive', value: totalItems - activeItems },
    { label: 'Maintenance', value: Math.floor(totalItems * 0.1) },
  ]

  const trendingData = [
    { date: 'Jan', value: 120 },
    { date: 'Feb', value: 135 },
    { date: 'Mar', value: 142 },
    { date: 'Apr', value: 158 },
    { date: 'May', value: 165 },
    { date: 'Jun', value: 172 },
  ]

  return (
    <div className="min-h-screen bg-neutral-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-neutral-900">Analytics Dashboard</h1>
          <p className="text-neutral-600 mt-2">
            Track your inventory performance and trends
          </p>
        </div>

        {/* Time Range Selector */}
        <div className="mb-6">
          <div className="flex items-center space-x-4">
            <label className="text-sm font-medium text-neutral-700">Time Range:</label>
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
              className="border border-neutral-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            >
              <option value="7d">Last 7 days</option>
              <option value="30d">Last 30 days</option>
              <option value="90d">Last 90 days</option>
              <option value="1y">Last year</option>
            </select>
          </div>
        </div>

        {isLoading ? (
          <LoadingState description="Loading analytics..." />
        ) : (
          <>
            {/* Summary Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
              <MetricCard
                title="Total Items"
                value={totalItems.toLocaleString()}
                icon={
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                  </svg>
                }
                trend={{ value: 12, isPositive: true }}
              />
              <MetricCard
                title="Active Items"
                value={activeItems.toLocaleString()}
                icon={
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                }
                trend={{ value: 8, isPositive: true }}
              />
              <MetricCard
                title="Trending Items"
                value={trendingCount}
                icon={
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                  </svg>
                }
                trend={{ value: 15, isPositive: true }}
              />
              <MetricCard
                title="Avg Trending Score"
                value={avgTrendingScore.toFixed(1)}
                icon={
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" />
                  </svg>
                }
                trend={{ value: 5, isPositive: false }}
              />
            </div>

            {/* Charts Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* Inventory Distribution */}
              <div className="bg-white rounded-lg shadow-sm border border-neutral-200 p-6">
                <h3 className="text-lg font-semibold text-neutral-900 mb-4">
                  Inventory Distribution by Type
                </h3>
                {inventoryDistribution && inventoryDistribution.length > 0 ? (
                  <BarChart
                    data={inventoryDistribution}
                    height={300}
                    colorScheme="primary"
                    onClick={(item) => {
                      console.log('Clicked on:', item.item_type)
                      // Could navigate to filtered inventory view
                    }}
                  />
                ) : (
                  <div className="flex items-center justify-center h-64 text-neutral-500">
                    No inventory data available
                  </div>
                )}
              </div>

              {/* Status Distribution */}
              <div className="bg-white rounded-lg shadow-sm border border-neutral-200 p-6">
                <h3 className="text-lg font-semibold text-neutral-900 mb-4">
                  Item Status Distribution
                </h3>
                {statusDistribution && statusDistribution.length > 0 ? (
                  <DoughnutChart
                    data={statusDistribution}
                    height={300}
                    onClick={(item) => {
                      console.log('Clicked on status:', item.label)
                      // Could navigate to filtered inventory view
                    }}
                  />
                ) : (
                  <div className="flex items-center justify-center h-64 text-neutral-500">
                    No status data available
                  </div>
                )}
              </div>

              {/* Trending Items */}
              <div className="bg-white rounded-lg shadow-sm border border-neutral-200 p-6">
                <h3 className="text-lg font-semibold text-neutral-900 mb-4">
                  Top Trending Items
                </h3>
                {trendingItems && trendingItems.length > 0 ? (
                  <HorizontalBarChart
                    data={trendingItems}
                    height={300}
                    maxItems={8}
                    colorScheme="success"
                    onClick={(item) => {
                      console.log('Clicked on trending item:', item.name)
                      // Could navigate to item detail
                    }}
                  />
                ) : (
                  <div className="flex items-center justify-center h-64 text-neutral-500">
                    No trending data available
                  </div>
                )}
              </div>

              {/* Trends Over Time */}
              <div className="bg-white rounded-lg shadow-sm border border-neutral-200 p-6">
                <h3 className="text-lg font-semibold text-neutral-900 mb-4">
                  Inventory Growth Trend
                </h3>
                {trendingData && trendingData.length > 0 ? (
                  <LineChart
                    data={trendingData}
                    height={300}
                    color="#10B981"
                  />
                ) : (
                  <div className="flex items-center justify-center h-64 text-neutral-500">
                    No trend data available
                  </div>
                )}
              </div>
            </div>

            {/* Additional Insights */}
            <div className="mt-8 bg-white rounded-lg shadow-sm border border-neutral-200 p-6">
              <h3 className="text-lg font-semibold text-neutral-900 mb-4">
                Key Insights
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                <div className="p-4 bg-primary-50 rounded-lg">
                  <h4 className="font-medium text-primary-900 mb-2">Most Popular Type</h4>
                  <p className="text-primary-700">
                    {inventoryDistribution?.[0]?.item_type || 'N/A'} 
                    ({inventoryDistribution?.[0]?.count || 0} items)
                  </p>
                </div>
                <div className="p-4 bg-success-50 rounded-lg">
                  <h4 className="font-medium text-success-900 mb-2">Health Score</h4>
                  <p className="text-success-700">
                    {((activeItems / totalItems) * 100).toFixed(1)}% of items are active
                  </p>
                </div>
                <div className="p-4 bg-warning-50 rounded-lg">
                  <h4 className="font-medium text-warning-900 mb-2">Growth Rate</h4>
                  <p className="text-warning-700">
                    {trendingData && trendingData.length > 1 
                      ? `${((trendingData[trendingData.length - 1].value - trendingData[0].value) / trendingData[0].value * 100).toFixed(1)}%`
                      : 'N/A'
                    } over selected period
                  </p>
                </div>
              </div>
            </div>

            {/* Reviewer Cadence */}
            <div className="mt-8 grid grid-cols-1 lg:grid-cols-3 gap-8">
              <div className="lg:col-span-2 bg-white rounded-lg shadow-sm border border-neutral-200 p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-neutral-900">Reviewer Cadence</h3>
                  <span className="text-xs text-neutral-500">Load bands, latency, churn</span>
                </div>
                {reviewerCadenceQuery.isLoading ? (
                  <LoadingState description="Loading reviewer cadence..." />
                ) : reviewerCadenceQuery.isError ? (
                  <p className="text-sm text-rose-600">
                    Unable to load reviewer cadence analytics at this time.
                  </p>
                ) : (
                  <ReviewerCadenceTable reviewers={reviewerCadence} />
                )}
              </div>
              <div className="bg-white rounded-lg shadow-sm border border-neutral-200 p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-neutral-900">Cadence Alerts</h3>
                  <span className="text-xs text-neutral-500">Publish streak guardrails</span>
                </div>
                {reviewerCadenceQuery.isLoading ? (
                  <LoadingState description="Checking streak alerts..." />
                ) : reviewerCadenceQuery.isError ? (
                  <p className="text-sm text-rose-600">
                    Unable to load reviewer cadence alerts.
                  </p>
                ) : (
                  <ReviewerCadenceAlerts
                    reviewers={reviewerCadence}
                    renderEmptyState={() => (
                      <p className="text-sm text-neutral-500">
                        No reviewer publish streak alerts detected for this period.
                      </p>
                    )}
                  />
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}