'use client'
import { useEffect, useRef, useMemo } from 'react'
import * as d3 from 'd3'
import type { ItemTypeCount } from '../../types'

interface ModernBarChartProps {
  data: ItemTypeCount[]
  height?: number
  colorScheme?: 'primary' | 'secondary' | 'rainbow'
  animated?: boolean
  onClick?: (item: ItemTypeCount) => void
}

export default function ModernBarChart({
  data,
  height = 320,
  colorScheme = 'primary',
  animated = true,
  onClick
}: ModernBarChartProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  
  const colors = useMemo(() => {
    switch (colorScheme) {
      case 'primary':
        return ['#3B82F6', '#1D4ED8', '#1E40AF', '#1E3A8A', '#172554']
      case 'secondary':
        return ['#10B981', '#059669', '#047857', '#065F46', '#064E3B']
      case 'rainbow':
        return ['#F59E0B', '#EF4444', '#8B5CF6', '#06B6D4', '#10B981']
      default:
        return ['#3B82F6']
    }
  }, [colorScheme])

  useEffect(() => {
    if (!svgRef.current || !data.length) return

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const margin = { top: 20, right: 20, bottom: 60, left: 80 }
    const width = 600
    const chartHeight = height - margin.top - margin.bottom
    const chartWidth = width - margin.left - margin.right

    // Create scales
    const xScale = d3
      .scaleBand()
      .domain(data.map(d => d.item_type))
      .range([0, chartWidth])
      .padding(0.2)

    const yScale = d3
      .scaleLinear()
      .domain([0, d3.max(data, d => d.count) || 0])
      .range([chartHeight, 0])
      .nice()

    const colorScale = d3
      .scaleOrdinal<string>()
      .domain(data.map(d => d.item_type))
      .range(colors)

    // Create main group
    const g = svg
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`)

    // Add gradient definitions
    const defs = svg.append('defs')
    data.forEach((d, i) => {
      const gradient = defs
        .append('linearGradient')
        .attr('id', `gradient-${i}`)
        .attr('x1', '0%')
        .attr('y1', '0%')
        .attr('x2', '0%')
        .attr('y2', '100%')
      
      gradient
        .append('stop')
        .attr('offset', '0%')
        .attr('style', `stop-color:${colorScale(d.item_type)};stop-opacity:0.9`)
      
      gradient
        .append('stop')
        .attr('offset', '100%')
        .attr('style', `stop-color:${colorScale(d.item_type)};stop-opacity:0.6`)
    })

    // Create bars
    const bars = g
      .selectAll('.bar')
      .data(data)
      .enter()
      .append('g')
      .attr('class', 'bar')

    // Add bar rectangles
    const barRects = bars
      .append('rect')
      .attr('x', d => xScale(d.item_type)!)
      .attr('y', chartHeight)
      .attr('width', xScale.bandwidth())
      .attr('height', 0)
      .attr('fill', (d, i) => `url(#gradient-${i})`)
      .attr('rx', 6)
      .attr('ry', 6)
      .style('cursor', onClick ? 'pointer' : 'default')

    // Add click handler conditionally
    if (onClick) {
      barRects.on('click', function(this: SVGRectElement, event: any, d: ItemTypeCount) {
        onClick(d)
      })
    }

    // Add mouseover and mouseout handlers
    barRects
      .on('mouseover', function(event, d) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('transform', 'scale(1.02)')
          .style('filter', 'drop-shadow(0 4px 8px rgba(0,0,0,0.1))')
      })
      .on('mouseout', function() {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('transform', 'scale(1)')
          .style('filter', 'none')
      })

    // Animate bars
    if (animated) {
      bars
        .select('rect')
        .transition()
        .duration(800)
        .delay((d, i) => i * 100)
        .attr('y', d => yScale(d.count))
        .attr('height', d => chartHeight - yScale(d.count))
    } else {
      bars
        .select('rect')
        .attr('y', d => yScale(d.count))
        .attr('height', d => chartHeight - yScale(d.count))
    }

    // Add value labels on bars
    bars
      .append('text')
      .attr('x', d => xScale(d.item_type)! + xScale.bandwidth() / 2)
      .attr('y', d => yScale(d.count) - 8)
      .attr('text-anchor', 'middle')
      .attr('font-size', '12px')
      .attr('font-weight', '600')
      .attr('fill', '#374151')
      .text(d => d.count)
      .style('opacity', 0)

    if (animated) {
      bars
        .select('text')
        .transition()
        .duration(800)
        .delay((d, i) => i * 100 + 400)
        .style('opacity', 1)
    } else {
      bars
        .select('text')
        .style('opacity', 1)
    }

    // Add X axis
    g.append('g')
      .attr('transform', `translate(0,${chartHeight})`)
      .call(d3.axisBottom(xScale))
      .selectAll('text')
      .style('text-anchor', 'end')
      .attr('dx', '-.8em')
      .attr('dy', '.15em')
      .attr('transform', 'rotate(-45)')
      .style('font-size', '12px')
      .style('fill', '#6B7280')

    // Add Y axis
    g.append('g')
      .call(d3.axisLeft(yScale).ticks(6))
      .selectAll('text')
      .style('font-size', '12px')
      .style('fill', '#6B7280')

    // Style axis lines
    g.selectAll('.domain')
      .style('stroke', '#E5E7EB')
      .style('stroke-width', '1px')

    g.selectAll('.tick line')
      .style('stroke', '#F3F4F6')
      .style('stroke-width', '1px')

    // Add grid lines
    g.selectAll('.grid-line')
      .data(yScale.ticks(6))
      .enter()
      .append('line')
      .attr('class', 'grid-line')
      .attr('x1', 0)
      .attr('x2', chartWidth)
      .attr('y1', d => yScale(d))
      .attr('y2', d => yScale(d))
      .style('stroke', '#F9FAFB')
      .style('stroke-width', '1px')

  }, [data, height, colors, animated, onClick])

  return (
    <div className="w-full overflow-x-auto">
      <svg
        ref={svgRef}
        width={600}
        height={height}
        className="w-full max-w-full"
        style={{ minWidth: '500px' }}
      />
    </div>
  )
}