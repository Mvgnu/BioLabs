import { useEffect } from 'react'

export function useWebSocket(teamId: string, onMessage: (data: any) => void) {
  useEffect(() => {
    if (!teamId) return
    const ws = new WebSocket(`ws://localhost:8000/ws/${teamId}`)
    ws.onmessage = (ev) => {
      try {
        onMessage(JSON.parse(ev.data))
      } catch {
        onMessage(ev.data)
      }
    }
    return () => ws.close()
  }, [teamId, onMessage])
}
