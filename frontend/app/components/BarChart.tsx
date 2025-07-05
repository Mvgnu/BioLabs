'use client'
import { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import type { ItemTypeCount } from '../types'

export default function BarChart({ data }: { data: ItemTypeCount[] }) {
  const ref = useRef<SVGSVGElement | null>(null)
  useEffect(() => {
    if (!ref.current) return
    const svg = d3.select(ref.current)
    svg.selectAll('*').remove()
    const width = 400
    const height = 300
    const margin = { top: 20, right: 20, bottom: 30, left: 40 }
    const x = d3
      .scaleBand()
      .domain(data.map((d) => d.item_type))
      .range([margin.left, width - margin.right])
      .padding(0.1)
    const y = d3
      .scaleLinear()
      .domain([0, d3.max(data, (d) => d.count)!])
      .range([height - margin.bottom, margin.top])
    svg
      .append('g')
      .selectAll('rect')
      .data(data)
      .enter()
      .append('rect')
      .attr('x', (d) => x(d.item_type)!)
      .attr('y', (d) => y(d.count))
      .attr('height', (d) => y(0) - y(d.count))
      .attr('width', x.bandwidth())
      .attr('fill', '#3182bd')
    svg
      .append('g')
      .attr('transform', `translate(0,${height - margin.bottom})`)
      .call(d3.axisBottom(x))
    svg
      .append('g')
      .attr('transform', `translate(${margin.left},0)`)
      .call(d3.axisLeft(y))
  }, [data])
  return <svg ref={ref} width={400} height={300} />
}
