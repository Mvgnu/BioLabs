'use client'
import { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import type { GraphData } from '../types'

export default function Graph({ data }: { data: GraphData }) {
  const ref = useRef<SVGSVGElement | null>(null)
  useEffect(() => {
    if (!ref.current) return
    const svg = d3.select(ref.current)
    svg.selectAll('*').remove()
    const width = 400
    const height = 300
    const simulation = d3.forceSimulation(data.nodes as any)
      .force('link', d3.forceLink(data.edges as any).id((d: any) => d.id).distance(80))
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(width / 2, height / 2))

    const link = svg.append('g')
      .selectAll('line')
      .data(data.edges)
      .enter()
      .append('line')
      .attr('stroke', '#999')

    const node = svg.append('g')
      .selectAll('circle')
      .data(data.nodes)
      .enter()
      .append('circle')
      .attr('r', 8)
      .attr('fill', '#3182bd')
      .call(d3.drag<SVGCircleElement, any>()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended))

    const label = svg.append('g')
      .selectAll('text')
      .data(data.nodes)
      .enter()
      .append('text')
      .text((d: any) => d.name)
      .attr('font-size', 10)
      .attr('dx', 12)
      .attr('dy', '.35em')

    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => (d.source as any).x)
        .attr('y1', (d: any) => (d.source as any).y)
        .attr('x2', (d: any) => (d.target as any).x)
        .attr('y2', (d: any) => (d.target as any).y)
      node.attr('cx', (d: any) => d.x!).attr('cy', (d: any) => d.y!)
      label.attr('x', (d: any) => d.x!).attr('y', (d: any) => d.y!)
    })

    function dragstarted(event: any) {
      if (!event.active) simulation.alphaTarget(0.3).restart()
      event.subject.fx = event.subject.x
      event.subject.fy = event.subject.y
    }

    function dragged(event: any) {
      event.subject.fx = event.x
      event.subject.fy = event.y
    }

    function dragended(event: any) {
      if (!event.active) simulation.alphaTarget(0)
      event.subject.fx = null
      event.subject.fy = null
    }
  }, [data])

  return <svg ref={ref} width={400} height={300} />
}
