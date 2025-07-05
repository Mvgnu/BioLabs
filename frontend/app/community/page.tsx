'use client'
import { useFeed, useCreatePost } from '../hooks/useCommunity'
import { useState } from 'react'
import { useAuthStore } from '../store/useAuth'

export default function CommunityPage() {
  const { data } = useFeed()
  const create = useCreatePost()
  const [text, setText] = useState('')
  const { token } = useAuthStore()
  if (!token) return <div>Please login</div>
  return (
    <div className="p-4 space-y-4">
      <h1 className="text-xl font-bold">Community Feed</h1>
      <form
        onSubmit={e => {
          e.preventDefault()
          create.mutate({ content: text })
          setText('')
        }}
        className="space-x-2"
      >
        <input value={text} onChange={e => setText(e.target.value)} className="border px-2" />
        <button type="submit" className="bg-blue-500 text-white px-3 py-1 rounded">Post</button>
      </form>
      <ul className="space-y-2">
        {data?.map(p => (
          <li key={p.id} className="border p-2">
            <span className="text-gray-600 text-sm">{new Date(p.created_at).toLocaleString()}</span>
            <div>{p.content}</div>
          </li>
        ))}
      </ul>
    </div>
  )
}
