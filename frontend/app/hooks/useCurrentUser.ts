'use client'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import type { UserIdentity } from '../types'
import { useAuthStore } from '../store/useAuth'

// purpose: fetch authenticated user profile for RBAC gating
// inputs: auth token from zustand store
// outputs: react-query result containing UserIdentity
// status: experimental
export const useCurrentUser = () => {
  const token = useAuthStore((state) => state.token)

  return useQuery({
    queryKey: ['current-user', token],
    queryFn: async () => {
      const response = await api.get<UserIdentity>('/api/users/me')
      return response.data
    },
    enabled: Boolean(token),
    staleTime: 5 * 60 * 1000,
    retry: (failureCount, error) => {
      if (!token) return false
      return failureCount < 2
    },
  })
}

export type UseCurrentUserResult = ReturnType<typeof useCurrentUser>
