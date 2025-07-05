'use client'
import { useState } from 'react'
import { useAssistantHistory, useAskAssistant } from '../hooks/useAssistant'

export default function AssistantPage() {
  const { data: history } = useAssistantHistory()
  const ask = useAskAssistant()
  const [question, setQuestion] = useState('')

  const submit = () => {
    if (!question) return
    ask.mutate(question)
    setQuestion('')
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Lab Buddy Assistant</h1>
      <ul className="space-y-2 border p-2 max-h-80 overflow-y-auto">
        {history?.map((m) => (
          <li key={m.id} className={m.is_user ? 'text-right' : 'text-left'}>
            <span className={m.is_user ? 'text-blue-700' : 'text-green-700'}>
              {m.message}
            </span>
          </li>
        ))}
      </ul>
      <div className="flex gap-2">
        <input
          className="border px-2 py-1 flex-grow"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question"
        />
        <button onClick={submit} className="bg-blue-600 text-white px-3">
          Send
        </button>
      </div>
    </div>
  )
}
