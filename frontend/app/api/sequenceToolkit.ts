// purpose: expose REST helpers for sequence toolkit catalog endpoints
// status: experimental

import api from './client'
import type { SequenceToolkitPresetCatalog } from '../types'

export const getSequenceToolkitPresets = async (): Promise<SequenceToolkitPresetCatalog> => {
  const response = await api.get('/api/sequence-toolkit/presets')
  return response.data as SequenceToolkitPresetCatalog
}
