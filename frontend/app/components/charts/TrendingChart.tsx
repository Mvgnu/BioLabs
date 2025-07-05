'use client'
import { useEffect, useRef, useMemo } from 'react'
import * as d3 from 'd3'

interface TrendingItem {
  id: string
  name: string
  count: number
  trend?: number // percentage change
  category?: string
}

interface TrendingChartProps {
  data: TrendingItem[]
  height?: number
  maxItems?: number
  showTrend?: boolean
  onClick?: (item: TrendingItem) => void
}

export default function TrendingChart({
  data,
  height = 400,
  maxItems = 10,
  showTrend = true,
  onClick
}: TrendingChartProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  
  const processedData = useMemo(() => {
    return data.slice(0, maxItems).sort((a, b) => b.count - a.count)
  }, [data, maxItems])

  useEffect(() => {
    if (!svgRef.current || !processedData.length) return

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const margin = { top: 20, right: 100, bottom: 40, left: 200 }
    const width = 700
    const chartHeight = height - margin.top - margin.bottom
    const chartWidth = width - margin.left - margin.right

    // Create scales
    const xScale = d3
      .scaleLinear()
      .domain([0, d3.max(processedData, d => d.count) || 0])
      .range([0, chartWidth])
      .nice()

    const yScale = d3
      .scaleBand()
      .domain(processedData.map(d => d.id))
      .range([0, chartHeight])
      .padding(0.15)

    // Create main group
    const g = svg
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`)

    // Add gradient definition
    const defs = svg.append('defs')
    const gradient = defs
      .append('linearGradient')
      .attr('id', 'trending-gradient')
      .attr('x1', '0%')
      .attr('y1', '0%')
      .attr('x2', '100%')
      .attr('y2', '0%')
    
    gradient
      .append('stop')
      .attr('offset', '0%')
      .attr('style', 'stop-color:#3B82F6;stop-opacity:0.3')
    
    gradient
      .append('stop')
      .attr('offset', '100%')
      .attr('style', 'stop-color:#3B82F6;stop-opacity:0.8')

    // Create bars
    const bars = g
      .selectAll('.trending-bar')
      .data(processedData)
      .enter()
      .append('g')
      .attr('class', 'trending-bar')

    // Add background bars
    bars
      .append('rect')
      .attr('x', 0)
      .attr('y', d => yScale(d.id)!)
      .attr('width', chartWidth)
      .attr('height', yScale.bandwidth())
      .attr('fill', '#F8FAFC')
      .attr('rx', 4)

    // Add main bars
    const mainBars = bars
      .append('rect')
      .attr('x', 0)
      .attr('y', d => yScale(d.id)!)
      .attr('width', 0)
      .attr('height', yScale.bandwidth())
      .attr('fill', 'url(#trending-gradient)')
      .attr('rx', 4)
      .style('cursor', onClick ? 'pointer' : 'default')

        // Add click handler conditionally
    if (onClick) {
      mainBars.on('click', function(this: SVGRectElement, event: any, d: TrendingItem) {
        onClick(d)
      })
    }

    // Add mouseover and mouseout handlers
    mainBars
        .on('mouseover', function(event, d) {
        d3.select(this)
          .transition()
          .duration(200)
          .style('filter', 'drop-shadow(0 2px 4px rgba(59, 130, 246, 0.3))')
      })
      .on('mouseout', function() {
        d3.select(this)
          .transition()
          .duration(200)
          .style('filter', 'none')
      })
      .transition()
      .duration(800)
      .delay((d, i) => i * 100)
      .attr('width', d => xScale(d.count))

    // Add item labels
    bars
      .append('text')
      .attr('x', -10)
      .attr('y', d => yScale(d.id)! + yScale.bandwidth() / 2)
      .attr('dy', '0.35em')
      .attr('text-anchor', 'end')
      .attr('font-size', '14px')
      .attr('font-weight', '500')
      .attr('fill', '#374151')
      .text(d => d.name.length > 25 ? d.name.slice(0, 25) + '...' : d.name)
      .style('opacity', 0)
      .transition()
      .duration(800)
      .delay((d, i) => i * 100 + 400)
      .style('opacity', 1)

    // Add count labels
    bars
      .append('text')
      .attr('x', d => xScale(d.count) + 8)
      .attr('y', d => yScale(d.id)! + yScale.bandwidth() / 2)
      .attr('dy', '0.35em')
      .attr('font-size', '12px')
      .attr('font-weight', '600')
      .attr('fill', '#1F2937')
      .text(d => d.count.toLocaleString())
      .style('opacity', 0)
      .transition()
      .duration(800)
      .delay((d, i) => i * 100 + 600)
      .style('opacity', 1)

    // Add trend indicators if enabled
    if (showTrend) {
      bars
        .filter(d => d.trend !== undefined)
        .append('text')
        .attr('x', d => xScale(d.count) + 50)
        .attr('y', d => yScale(d.id)! + yScale.bandwidth() / 2)
        .attr('dy', '0.35em')
        .attr('font-size', '11px')
        .attr('font-weight', '500')
        .attr('fill', d => (d.trend || 0) >= 0 ? '#10B981' : '#EF4444')
        .text(d => {
          const trend = d.trend || 0
          const sign = trend >= 0 ? '+' : ''
          return `${sign}${trend.toFixed(1)}%`
        })
        .style('opacity', 0)
        .transition()
        .duration(800)
        .delay((d, i) => i * 100 + 800)
        .style('opacity', 1)
    }

    // Add X axis
    g.append('g')
      .attr('transform', `translate(0,${chartHeight})`)
      .call(d3.axisBottom(xScale).ticks(5))
      .selectAll('text')
      .style('font-size', '12px')
      .style('fill', '#6B7280')

    // Style axis
    g.selectAll('.domain')
      .style('stroke', '#E5E7EB')

    g.selectAll('.tick line')
      .style('stroke', '#F3F4F6')

  }, [processedData, height, showTrend, onClick])

  return (
    <div className="w-full overflow-x-auto">
      <svg
        ref={svgRef}
        width={700}
        height={height}
        className="w-full max-w-full"
        style={{ minWidth: '600px' }}
      />
    </div>
  )
}