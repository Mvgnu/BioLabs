import { useEffect } from 'react'

type MessageHandler = (data: any, context: { teamId: string }) => void

const normalizeTeamIds = (teamIds: string | string[]): string[] => {
  const rawIds = Array.isArray(teamIds) ? teamIds : [teamIds]
  const filtered = rawIds.filter(
    (value): value is string => typeof value === 'string' && value.trim().length > 0
  )
  return Array.from(new Set(filtered))
}

export function useWebSocket(teamIds: string | string[], onMessage: MessageHandler) {
  const subscriptionKey = Array.isArray(teamIds)
    ? [...teamIds].sort().join(',')
    : teamIds ?? ''

  useEffect(() => {
    const normalized = normalizeTeamIds(teamIds)
    if (normalized.length === 0) {
      return
    }

    const sockets = normalized.map((teamId) => {
      const ws = new WebSocket(`ws://localhost:8000/ws/${teamId}`)
      ws.onmessage = (ev) => {
        try {
          onMessage(JSON.parse(ev.data), { teamId })
        } catch {
          onMessage(ev.data, { teamId })
        }
      }
      return ws
    })

    return () => {
      for (const ws of sockets) {
        ws.close()
      }
    }
  }, [subscriptionKey, onMessage])
}
