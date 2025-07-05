'use client'
import React from 'react'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'
import { Bar, Line, Doughnut } from 'react-chartjs-2'

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

// Chart.js configuration
const chartConfig = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'bottom' as const,
      labels: {
        usePointStyle: true,
        padding: 20,
        font: {
          size: 12,
        },
      },
    },
    tooltip: {
      backgroundColor: 'rgba(0, 0, 0, 0.8)',
      titleColor: 'white',
      bodyColor: 'white',
      borderColor: 'rgba(255, 255, 255, 0.1)',
      borderWidth: 1,
      cornerRadius: 8,
      displayColors: true,
    },
  },
}

// Color schemes
const colorSchemes = {
  primary: ['#3B82F6', '#1D4ED8', '#1E40AF', '#1E3A8A', '#172554'],
  success: ['#10B981', '#059669', '#047857', '#065F46', '#064E3B'],
  warning: ['#F59E0B', '#D97706', '#B45309', '#92400E', '#78350F'],
  error: ['#EF4444', '#DC2626', '#B91C1C', '#991B1B', '#7F1D1D'],
  neutral: ['#6B7280', '#4B5563', '#374151', '#1F2937', '#111827'],
  rainbow: ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8'],
}

interface BarChartProps {
  data: Array<{ item_type: string; count: number }>
  title?: string
  colorScheme?: keyof typeof colorSchemes
  height?: number
  onClick?: (item: { item_type: string; count: number }) => void
}

export const BarChart: React.FC<BarChartProps> = ({
  data,
  title,
  colorScheme = 'primary',
  height = 300,
  onClick,
}) => {
  const colors = colorSchemes[colorScheme]
  
  const chartData = {
    labels: data.map(item => item.item_type),
    datasets: [
      {
        label: 'Count',
        data: data.map(item => item.count),
        backgroundColor: data.map((_, index) => colors[index % colors.length]),
        borderColor: data.map((_, index) => colors[index % colors.length]),
        borderWidth: 1,
        borderRadius: 6,
        borderSkipped: false,
      },
    ],
  }

  const options = {
    ...chartConfig,
    plugins: {
      ...chartConfig.plugins,
      title: title ? {
        display: true,
        text: title,
        font: { size: 16, weight: 'bold' as const },
        padding: { bottom: 20 },
      } : undefined,
    },
    scales: {
      y: {
        beginAtZero: true,
        grid: {
          color: 'rgba(0, 0, 0, 0.1)',
        },
        ticks: {
          font: { size: 12 },
        },
      },
      x: {
        grid: {
          display: false,
        },
        ticks: {
          font: { size: 12 },
          maxRotation: 45,
        },
      },
    },
    onClick: (event: any, elements: any) => {
      if (onClick && elements.length > 0) {
        const index = elements[0].index
        onClick(data[index])
      }
    },
  }

  return (
    <div style={{ height }}>
      <Bar data={chartData} options={options} />
    </div>
  )
}

interface LineChartProps {
  data: Array<{ date: string; value: number }>
  title?: string
  color?: string
  height?: number
}

export const LineChart: React.FC<LineChartProps> = ({
  data,
  title,
  color = '#3B82F6',
  height = 300,
}) => {
  const chartData = {
    labels: data.map(item => item.date),
    datasets: [
      {
        label: 'Value',
        data: data.map(item => item.value),
        borderColor: color,
        backgroundColor: `${color}20`,
        borderWidth: 2,
        fill: true,
        tension: 0.4,
        pointBackgroundColor: color,
        pointBorderColor: '#fff',
        pointBorderWidth: 2,
        pointRadius: 4,
        pointHoverRadius: 6,
      },
    ],
  }

  const options = {
    ...chartConfig,
    plugins: {
      ...chartConfig.plugins,
      title: title ? {
        display: true,
        text: title,
        font: { size: 16, weight: 'bold' as const },
        padding: { bottom: 20 },
      } : undefined,
    },
    scales: {
      y: {
        beginAtZero: true,
        grid: {
          color: 'rgba(0, 0, 0, 0.1)',
        },
        ticks: {
          font: { size: 12 },
        },
      },
      x: {
        grid: {
          color: 'rgba(0, 0, 0, 0.1)',
        },
        ticks: {
          font: { size: 12 },
        },
      },
    },
  }

  return (
    <div style={{ height }}>
      <Line data={chartData} options={options} />
    </div>
  )
}

interface DoughnutChartProps {
  data: Array<{ label: string; value: number }>
  title?: string
  height?: number
  onClick?: (item: { label: string; value: number }) => void
}

export const DoughnutChart: React.FC<DoughnutChartProps> = ({
  data,
  title,
  height = 300,
  onClick,
}) => {
  const colors = colorSchemes.rainbow
  
  const chartData = {
    labels: data.map(item => item.label),
    datasets: [
      {
        data: data.map(item => item.value),
        backgroundColor: data.map((_, index) => colors[index % colors.length]),
        borderColor: '#fff',
        borderWidth: 2,
        hoverOffset: 4,
      },
    ],
  }

  const options = {
    ...chartConfig,
    plugins: {
      ...chartConfig.plugins,
      title: title ? {
        display: true,
        text: title,
        font: { size: 16, weight: 'bold' as const },
        padding: { bottom: 20 },
      } : undefined,
    },
    onClick: (event: any, elements: any) => {
      if (onClick && elements.length > 0) {
        const index = elements[0].index
        onClick(data[index])
      }
    },
  }

  return (
    <div style={{ height }}>
      <Doughnut data={chartData} options={options} />
    </div>
  )
}

interface HorizontalBarChartProps {
  data: Array<{ name: string; count: number }>
  title?: string
  colorScheme?: keyof typeof colorSchemes
  height?: number
  maxItems?: number
  onClick?: (item: { name: string; count: number }) => void
}

export const HorizontalBarChart: React.FC<HorizontalBarChartProps> = ({
  data,
  title,
  colorScheme = 'primary',
  height = 300,
  maxItems = 10,
  onClick,
}) => {
  const colors = colorSchemes[colorScheme]
  const limitedData = data.slice(0, maxItems)
  
  const chartData = {
    labels: limitedData.map(item => item.name),
    datasets: [
      {
        label: 'Count',
        data: limitedData.map(item => item.count),
        backgroundColor: limitedData.map((_, index) => colors[index % colors.length]),
        borderColor: limitedData.map((_, index) => colors[index % colors.length]),
        borderWidth: 1,
        borderRadius: 4,
      },
    ],
  }

  const options = {
    ...chartConfig,
    indexAxis: 'y' as const,
    plugins: {
      ...chartConfig.plugins,
      title: title ? {
        display: true,
        text: title,
        font: { size: 16, weight: 'bold' as const },
        padding: { bottom: 20 },
      } : undefined,
    },
    scales: {
      x: {
        beginAtZero: true,
        grid: {
          color: 'rgba(0, 0, 0, 0.1)',
        },
        ticks: {
          font: { size: 12 },
        },
      },
      y: {
        grid: {
          display: false,
        },
        ticks: {
          font: { size: 12 },
        },
      },
    },
    onClick: (event: any, elements: any) => {
      if (onClick && elements.length > 0) {
        const index = elements[0].index
        onClick(limitedData[index])
      }
    },
  }

  return (
    <div style={{ height }}>
      <Bar data={chartData} options={options} />
    </div>
  )
}

// Metric Card Component
interface MetricCardProps {
  title: string
  value: number | string
  icon?: React.ReactNode
  trend?: {
    value: number
    isPositive: boolean
  }
  onClick?: () => void
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  icon,
  trend,
  onClick,
}) => {
  return (
    <div
      className={`bg-white rounded-lg shadow-sm border border-neutral-200 p-6 hover:shadow-md transition-shadow ${
        onClick ? 'cursor-pointer' : ''
      }`}
      onClick={onClick}
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-neutral-600">{title}</p>
          <p className="text-2xl font-bold text-neutral-900 mt-1">{value}</p>
          {trend && (
            <div className="flex items-center mt-2">
              <span
                className={`text-sm font-medium ${
                  trend.isPositive ? 'text-success-600' : 'text-error-600'
                }`}
              >
                {trend.isPositive ? '+' : ''}{trend.value}%
              </span>
              <svg
                className={`w-4 h-4 ml-1 ${
                  trend.isPositive ? 'text-success-600' : 'text-error-600'
                }`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d={
                    trend.isPositive
                      ? 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6'
                      : 'M13 17h8m0 0v-8m0 8l-8-8-4 4-6-6'
                  }
                />
              </svg>
            </div>
          )}
        </div>
        {icon && (
          <div className="flex-shrink-0">
            <div className="w-8 h-8 bg-primary-100 rounded-lg flex items-center justify-center text-primary-600">
              {icon}
            </div>
          </div>
        )}
      </div>
    </div>
  )
} 