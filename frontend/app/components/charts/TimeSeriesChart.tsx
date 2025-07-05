'use client'
import { useEffect, useRef, useMemo } from 'react'
import * as d3 from 'd3'

interface TimeSeriesDataPoint {
  date: string
  value: number
  category?: string
}

interface TimeSeriesChartProps {
  data: TimeSeriesDataPoint[]
  height?: number
  showDots?: boolean
  showArea?: boolean
  color?: string
  onClick?: (point: TimeSeriesDataPoint) => void
}

export default function TimeSeriesChart({
  data,
  height = 300,
  showDots = true,
  showArea = true,
  color = '#3B82F6',
  onClick
}: TimeSeriesChartProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  
  const processedData = useMemo(() => {
    return data.map(d => ({
      ...d,
      parsedDate: new Date(d.date)
    })).sort((a, b) => a.parsedDate.getTime() - b.parsedDate.getTime())
  }, [data])

  useEffect(() => {
    if (!svgRef.current || !processedData.length) return

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const margin = { top: 20, right: 30, bottom: 40, left: 50 }
    const width = 600
    const chartHeight = height - margin.top - margin.bottom
    const chartWidth = width - margin.left - margin.right

    // Create scales
    const xScale = d3
      .scaleTime()
      .domain(d3.extent(processedData, d => d.parsedDate) as [Date, Date])
      .range([0, chartWidth])

    const yScale = d3
      .scaleLinear()
      .domain([0, d3.max(processedData, d => d.value) || 0])
      .range([chartHeight, 0])
      .nice()

    // Create main group
    const g = svg
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`)

    // Add gradient definition
    const defs = svg.append('defs')
    const gradient = defs
      .append('linearGradient')
      .attr('id', 'area-gradient')
      .attr('x1', '0%')
      .attr('y1', '0%')
      .attr('x2', '0%')
      .attr('y2', '100%')
    
    gradient
      .append('stop')
      .attr('offset', '0%')
      .attr('style', `stop-color:${color};stop-opacity:0.3`)
    
    gradient
      .append('stop')
      .attr('offset', '100%')
      .attr('style', `stop-color:${color};stop-opacity:0.05`)

    // Create line generator
    const line = d3
      .line<typeof processedData[0]>()
      .x(d => xScale(d.parsedDate))
      .y(d => yScale(d.value))
      .curve(d3.curveMonotoneX)

    // Create area generator
    const area = d3
      .area<typeof processedData[0]>()
      .x(d => xScale(d.parsedDate))
      .y0(chartHeight)
      .y1(d => yScale(d.value))
      .curve(d3.curveMonotoneX)

    // Add grid lines
    g.selectAll('.grid-line-x')
      .data(xScale.ticks(6))
      .enter()
      .append('line')
      .attr('class', 'grid-line-x')
      .attr('x1', d => xScale(d))
      .attr('x2', d => xScale(d))
      .attr('y1', 0)
      .attr('y2', chartHeight)
      .style('stroke', '#F3F4F6')
      .style('stroke-width', '1px')

    g.selectAll('.grid-line-y')
      .data(yScale.ticks(5))
      .enter()
      .append('line')
      .attr('class', 'grid-line-y')
      .attr('x1', 0)
      .attr('x2', chartWidth)
      .attr('y1', d => yScale(d))
      .attr('y2', d => yScale(d))
      .style('stroke', '#F3F4F6')
      .style('stroke-width', '1px')

    // Add area if enabled
    if (showArea) {
      g.append('path')
        .datum(processedData)
        .attr('fill', 'url(#area-gradient)')
        .attr('d', area)
        .style('opacity', 0)
        .transition()
        .duration(1000)
        .style('opacity', 1)
    }

    // Add line
    const path = g
      .append('path')
      .datum(processedData)
      .attr('fill', 'none')
      .attr('stroke', color)
      .attr('stroke-width', 2.5)
      .attr('stroke-linejoin', 'round')
      .attr('stroke-linecap', 'round')
      .attr('d', line)

    // Animate line drawing
    const totalLength = path.node()?.getTotalLength() || 0
    path
      .attr('stroke-dasharray', totalLength + ' ' + totalLength)
      .attr('stroke-dashoffset', totalLength)
      .transition()
      .duration(1500)
      .ease(d3.easeLinear)
      .attr('stroke-dashoffset', 0)

    // Add dots if enabled
    if (showDots) {
      const dots = g.selectAll('.dot')
        .data(processedData)
        .enter()
        .append('circle')
        .attr('class', 'dot')
        .attr('cx', d => xScale(d.parsedDate))
        .attr('cy', d => yScale(d.value))
        .attr('r', 0)
        .attr('fill', color)
        .style('cursor', onClick ? 'pointer' : 'default')

      // Add click handler conditionally
      if (onClick) {
        dots.on('click', function(this: SVGCircleElement, event: any, d: any) {
          onClick(d)
        })
      }

      // Add mouseover and mouseout handlers
      dots
        .on('mouseover', function(event, d) {
          // Show tooltip
          const tooltip = d3.select('body')
            .append('div')
            .attr('class', 'tooltip')
            .style('position', 'absolute')
            .style('background', 'rgba(0, 0, 0, 0.8)')
            .style('color', 'white')
            .style('padding', '8px 12px')
            .style('border-radius', '4px')
            .style('font-size', '12px')
            .style('pointer-events', 'none')
            .style('opacity', 0)
            .html(`
              <div>Date: ${d.date}</div>
              <div>Value: ${d.value.toLocaleString()}</div>
            `)

          tooltip
            .transition()
            .duration(200)
            .style('opacity', 1)
            .style('left', (event.pageX + 10) + 'px')
            .style('top', (event.pageY - 30) + 'px')

          d3.select(this)
            .transition()
            .duration(200)
            .attr('r', 6)
        })
        .on('mouseout', function() {
          d3.selectAll('.tooltip').remove()
          d3.select(this)
            .transition()
            .duration(200)
            .attr('r', 4)
        })
        .transition()
        .duration(800)
        .delay((d, i) => i * 100 + 800)
        .attr('r', 4)
    }

    // Add X axis
    g.append('g')
      .attr('transform', `translate(0,${chartHeight})`)
      .call(d3.axisBottom(xScale).ticks(6))
      .selectAll('text')
      .style('font-size', '12px')
      .style('fill', '#6B7280')

    // Add Y axis
    g.append('g')
      .call(d3.axisLeft(yScale).ticks(5))
      .selectAll('text')
      .style('font-size', '12px')
      .style('fill', '#6B7280')

    // Style axes
    g.selectAll('.domain')
      .style('stroke', '#E5E7EB')

    g.selectAll('.tick line')
      .style('stroke', '#E5E7EB')

    return () => {
      // Cleanup tooltips on unmount
      d3.selectAll('.tooltip').remove()
    }
  }, [processedData, height, showDots, showArea, color, onClick])

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