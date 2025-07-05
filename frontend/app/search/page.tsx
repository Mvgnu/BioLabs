'use client'
import { useState } from 'react'
import { useSearchItems } from '../hooks/useSearch'
import Link from 'next/link'

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const { data } = useSearchItems(query)

  return (
    <div>
      <h1 className="text-xl font-bold mb-2">Search Inventory</h1>
      <input
        className="border p-2 mr-2"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search by name"
      />
      <ul className="mt-4 space-y-2">
        {data?.map((item) => (
          <li key={item.id} className="border p-2">
            <Link href={`/inventory/${item.id}`}>{item.name}</Link>
          </li>
        ))}
      </ul>
    </div>
  )
}

