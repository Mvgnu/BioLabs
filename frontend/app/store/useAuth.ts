'use client'
import { create } from 'zustand'

interface AuthState {
  token: string | null
  setToken: (token: string | null) => void
}

// Get initial token from localStorage (only on client side)
const getInitialToken = (): string | null => {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('token')
  }
  return null
}

export const useAuth = create<AuthState>((set) => ({
  token: getInitialToken(),
  setToken: (token) => {
    if (typeof window !== 'undefined') {
      if (token) {
        localStorage.setItem('token', token)
      } else {
        localStorage.removeItem('token')
      }
    }
    set({ token })
  }
}))

export const useAuthStore = useAuth;
