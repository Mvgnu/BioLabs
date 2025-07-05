'use client'
import { useState } from 'react'
import {
  useMarketplaceListings,
  useCreateListing,
  useMarketplaceRequests,
  useCreateRequest,
  useAcceptRequest,
  useRejectRequest,
} from '../hooks/useMarketplace'

export default function MarketplacePage() {
  const { data: listings } = useMarketplaceListings()
  const create = useCreateListing()
  const [itemId, setItemId] = useState('')
  const [price, setPrice] = useState('')
  const [selected, setSelected] = useState<string | null>(null)
  const { data: requests } = useMarketplaceRequests(selected ?? '')
  const makeRequest = useCreateRequest(selected ?? '')
  const accept = useAcceptRequest()
  const reject = useRejectRequest()

  const handleCreate = () => {
    create.mutate({ item_id: itemId, price: price ? Number(price) : null })
    setItemId('')
    setPrice('')
  }

  const handleRequest = (listingId: string) => {
    makeRequest.mutate({ message: 'Interested' })
  }

  return (
    <div>
      <h1 className="text-xl mb-4">Marketplace</h1>
      <div className="mb-4 space-x-2">
        <input
          className="border p-1"
          placeholder="Item ID"
          value={itemId}
          onChange={(e) => setItemId(e.target.value)}
        />
        <input
          className="border p-1"
          placeholder="Price"
          type="number"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
        />
        <button onClick={handleCreate}>List Item</button>
      </div>
      <h2 className="text-lg mb-2">Open Listings</h2>
      <ul className="space-y-2 mb-6">
        {listings?.map((l) => (
          <li
            key={l.id}
            className="border p-2 flex justify-between"
            onClick={() => setSelected(l.id)}
          >
            <span>
              {l.item_id} - {l.price ?? 'N/A'} - {l.status}
            </span>
            <button onClick={() => handleRequest(l.id)}>Request</button>
          </li>
        ))}
      </ul>
      {selected && (
        <div>
          <h2 className="text-lg mb-2">Requests for {selected}</h2>
          <ul className="space-y-2">
            {requests?.map((r) => (
              <li key={r.id} className="border p-2 flex justify-between">
                <span>
                  {r.buyer_id} - {r.status}
                </span>
                {r.status === 'pending' && (
                  <span className="space-x-2 text-sm">
                    <button onClick={() => accept.mutate(r.id)}>Accept</button>
                    <button onClick={() => reject.mutate(r.id)}>Reject</button>
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
