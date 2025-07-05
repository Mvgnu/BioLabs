'use client'
import { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import type { ChromatogramData } from '../types'

export default function ChromatogramPlot({ data, height=200 }: { data: ChromatogramData, height?: number }) {
  const ref = useRef<SVGSVGElement | null>(null)
  useEffect(() => {
    if (!ref.current) return
    const svg = d3.select(ref.current)
    svg.selectAll('*').remove()
    const bases = ['A','C','G','T'] as const
    const colors: Record<string,string> = {A:'green',C:'blue',G:'black',T:'red'}
    const maxLen = Math.max(...bases.map(b => data.traces[b].length))
    const maxVal = Math.max(...bases.flatMap(b => data.traces[b])) || 1
    const width = maxLen
    svg.attr('viewBox', `0 0 ${width} ${height}`)
    bases.forEach(b => {
      const line = d3.line<number>()
        .x((_, i) => i)
        .y(v => height - v / maxVal * height)
      svg.append('path')
        .datum(data.traces[b])
        .attr('fill','none')
        .attr('stroke', colors[b])
        .attr('stroke-width', 1)
        .attr('d', line as any)
    })
  }, [data, height])
  return <svg ref={ref} width="100%" height={height}></svg>
}
