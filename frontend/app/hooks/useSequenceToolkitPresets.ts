'use client'

import { useQuery } from '@tanstack/react-query'

import { getSequenceToolkitPresets } from '../api/sequenceToolkit'

// purpose: load toolkit preset catalog for planner and DNA viewer clients
// status: experimental

const QUERY_KEY = ['sequence-toolkit', 'presets'] as const

export const useSequenceToolkitPresets = () => {
  return useQuery({
    queryKey: QUERY_KEY,
    queryFn: getSequenceToolkitPresets,
  })
}
