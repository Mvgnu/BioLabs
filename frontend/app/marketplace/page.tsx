'use client'

import React, { useEffect, useMemo, useState } from 'react'
import {
  useMarketplaceListings,
  useCreateListing,
  useMarketplaceRequests,
  useCreateRequest,
  useAcceptRequest,
  useRejectRequest,
  useMarketplacePlans,
  useCreateSubscription,
  useOrganizationSubscription,
  useOrganizationUsage,
  useSubscriptionInvoices,
  useCreateInvoiceDraft,
  useAdjustCredits,
  useCreditLedger,
} from '../hooks/useMarketplace'
import { useComplianceOrganizations } from '../hooks/useCompliance'

function centsToCurrency(cents: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
  }).format(cents / 100)
}

export default function MarketplacePage() {
  const { data: plans } = useMarketplacePlans()
  const { data: organizations } = useComplianceOrganizations()
  const [selectedOrg, setSelectedOrg] = useState<string>('')
  const [period, setPeriod] = useState(() => ({
    start: new Date(Date.now() - 1000 * 60 * 60 * 24 * 30).toISOString(),
    end: new Date().toISOString(),
  }))
  const [creditAdjustment, setCreditAdjustment] = useState({
    subscription_id: '',
    delta_credits: 0,
    reason: 'manual_adjustment',
  })

  useEffect(() => {
    if (!selectedOrg && organizations && organizations.length > 0) {
      setSelectedOrg(organizations[0].id)
    }
  }, [organizations, selectedOrg])

  const subscriptionQuery = useOrganizationSubscription(selectedOrg)
  const subscription = subscriptionQuery.data ?? null
  const usageQuery = useOrganizationUsage(selectedOrg)
  const invoicesQuery = useSubscriptionInvoices(subscription?.id ?? '')
  const ledgerQuery = useCreditLedger(subscription?.id ?? '')
  const createSubscription = useCreateSubscription(selectedOrg)
  const createInvoiceDraft = useCreateInvoiceDraft(subscription?.id ?? '')
  const adjustCredits = useAdjustCredits()

  const { data: listings } = useMarketplaceListings()
  const createListing = useCreateListing()
  const [listingItemId, setListingItemId] = useState('')
  const [listingPrice, setListingPrice] = useState('')
  const [selectedListing, setSelectedListing] = useState<string | null>(null)
  const requestsQuery = useMarketplaceRequests(selectedListing ?? '')
  const createRequest = useCreateRequest(selectedListing ?? '')
  const acceptRequest = useAcceptRequest()
  const rejectRequest = useRejectRequest()

  const activePlanIds = useMemo(() => plans?.map((plan) => plan.id) ?? [], [plans])

  const handleSubscribe = (planId: string) => {
    if (!selectedOrg) return
    createSubscription.mutate({
      plan_id: planId,
      billing_email: organizations?.find((org) => org.id === selectedOrg)?.slug
        ? `${organizations?.find((org) => org.id === selectedOrg)?.slug}@billing.invalid`
        : undefined,
      sla_acceptance: {
        accepted_at: new Date().toISOString(),
        plan_id: planId,
      },
    })
  }

  const handleDraftInvoice = () => {
    if (!subscription) return
    createInvoiceDraft.mutate({
      period_start: period.start,
      period_end: period.end,
    })
  }

  const handleAdjustCredits = () => {
    if (!subscription) return
    adjustCredits.mutate({
      ...creditAdjustment,
      subscription_id: subscription.id,
    })
    setCreditAdjustment((current) => ({ ...current, delta_credits: 0 }))
  }

  const handleCreateListing = () => {
    createListing.mutate({
      item_id: listingItemId,
      price: listingPrice ? Number(listingPrice) : null,
    })
    setListingItemId('')
    setListingPrice('')
  }

  const handleCreateRequest = () => {
    createRequest.mutate({ message: 'Interested in bundle' })
  }

  return (
    <div className="space-y-10">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Marketplace & Billing</h1>
        <p className="text-sm text-slate-600">
          Explore BioLabs tool bundles, manage enterprise subscriptions, and review usage
          insights backed by guardrail-aware billing telemetry.
        </p>
      </header>

      <section>
        <h2 className="text-xl font-semibold mb-4">Marketplace Bundles</h2>
        <div className="grid gap-4 md:grid-cols-2">
          {plans?.map((plan) => (
            <article key={plan.id} className="border rounded-lg p-4 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-medium">{plan.title}</h3>
                  <p className="text-sm text-slate-600">{plan.description}</p>
                </div>
                <span className="text-lg font-semibold">
                  {centsToCurrency(plan.base_price_cents)}/
                  {plan.billing_cadence === 'monthly' ? 'mo' : plan.billing_cadence}
                </span>
              </div>
              <ul className="mt-3 space-y-1 text-sm">
                <li className="font-medium">Credits: {plan.credit_allowance.toLocaleString()}</li>
                <li className="font-medium">SLA Tier: {plan.sla_tier}</li>
                {plan.features.map((feature) => (
                  <li key={feature.id} className="flex items-start gap-2">
                    <span className="mt-1 h-1.5 w-1.5 rounded-full bg-emerald-500" />
                    <div>
                      <p className="font-semibold text-sm">{feature.label}</p>
                      {feature.details && (
                        <p className="text-xs text-slate-600">{feature.details}</p>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
              <button
                className="mt-4 inline-flex items-center rounded bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white"
                onClick={() => handleSubscribe(plan.id)}
                disabled={!selectedOrg || createSubscription.isPending}
              >
                {createSubscription.isPending ? 'Subscribing…' : 'Subscribe'}
              </button>
            </article>
          ))}
        </div>
      </section>

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">Organization Billing Overview</h2>
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium" htmlFor="org-select">
              Organization
            </label>
            <select
              id="org-select"
              className="border rounded px-2 py-1 text-sm"
              value={selectedOrg}
              onChange={(event) => setSelectedOrg(event.target.value)}
            >
              <option value="" disabled>
                Select an organization
              </option>
              {organizations?.map((org) => (
                <option key={org.id} value={org.id}>
                  {org.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {subscription ? (
          <div className="grid gap-6 md:grid-cols-2">
            <div className="rounded-lg border p-4 shadow-sm">
              <h3 className="text-lg font-semibold">Subscription Status</h3>
              <dl className="mt-3 space-y-2 text-sm">
                <div className="flex justify-between">
                  <dt className="font-medium">Plan</dt>
                  <dd>{subscription.plan.title}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="font-medium">Credits Remaining</dt>
                  <dd>{subscription.current_credits.toLocaleString()}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="font-medium">Renews</dt>
                  <dd>{subscription.renews_at ? new Date(subscription.renews_at).toLocaleDateString() : 'N/A'}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="font-medium">Billing Email</dt>
                  <dd>{subscription.billing_email ?? 'Not set'}</dd>
                </div>
              </dl>
            </div>

            <div className="rounded-lg border p-4 shadow-sm space-y-3">
              <h3 className="text-lg font-semibold">Invoice Actions</h3>
              <div className="flex flex-col gap-2 text-sm">
                <label className="font-medium" htmlFor="period-start">
                  Billing period
                </label>
                <div className="flex gap-2">
                  <input
                    id="period-start"
                    type="datetime-local"
                    className="w-full rounded border px-2 py-1"
                    value={period.start.slice(0, 16)}
                    onChange={(event) =>
                      setPeriod((current) => ({ ...current, start: new Date(event.target.value).toISOString() }))
                    }
                  />
                  <input
                    type="datetime-local"
                    className="w-full rounded border px-2 py-1"
                    value={period.end.slice(0, 16)}
                    onChange={(event) =>
                      setPeriod((current) => ({ ...current, end: new Date(event.target.value).toISOString() }))
                    }
                  />
                </div>
                <button
                  className="inline-flex w-full justify-center rounded bg-sky-600 px-3 py-1.5 text-sm font-medium text-white"
                  onClick={handleDraftInvoice}
                  disabled={createInvoiceDraft.isPending}
                >
                  {createInvoiceDraft.isPending ? 'Generating…' : 'Generate Draft Invoice'}
                </button>
              </div>

              <div className="border-t pt-3">
                <h4 className="text-sm font-semibold">Credit Adjustment</h4>
                <div className="mt-2 flex gap-2">
                  <input
                    type="number"
                    className="w-24 rounded border px-2 py-1 text-sm"
                    aria-label="Credit delta"
                    value={creditAdjustment.delta_credits}
                    onChange={(event) =>
                      setCreditAdjustment((current) => ({
                        ...current,
                        delta_credits: Number(event.target.value),
                      }))
                    }
                  />
                  <input
                    className="flex-1 rounded border px-2 py-1 text-sm"
                    placeholder="Reason"
                    aria-label="Adjustment reason"
                    value={creditAdjustment.reason}
                    onChange={(event) =>
                      setCreditAdjustment((current) => ({
                        ...current,
                        reason: event.target.value,
                      }))
                    }
                  />
                </div>
                <button
                  className="mt-2 inline-flex w-full justify-center rounded border border-emerald-600 px-3 py-1.5 text-sm font-medium text-emerald-700"
                  onClick={handleAdjustCredits}
                  disabled={adjustCredits.isPending}
                >
                  {adjustCredits.isPending ? 'Adjusting…' : 'Apply Credit Adjustment'}
                </button>
              </div>
            </div>
          </div>
        ) : (
          <p className="rounded border border-dashed p-4 text-sm text-slate-600">
            Select an organization to subscribe and begin tracking monetized usage.
          </p>
        )}

        <div className="grid gap-6 md:grid-cols-2">
          <div>
            <h3 className="text-lg font-semibold mb-2">Recent Usage Events</h3>
            <div className="max-h-64 overflow-y-auto rounded border">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-slate-100 text-xs uppercase text-slate-600">
                  <tr>
                    <th className="px-3 py-2">Service</th>
                    <th className="px-3 py-2">Operation</th>
                    <th className="px-3 py-2">Credits</th>
                    <th className="px-3 py-2">Timestamp</th>
                  </tr>
                </thead>
                <tbody>
                  {usageQuery.data?.map((event) => (
                    <tr key={event.id} className="odd:bg-white even:bg-slate-50">
                      <td className="px-3 py-2 font-medium">{event.service}</td>
                      <td className="px-3 py-2">{event.operation}</td>
                      <td className="px-3 py-2">{event.credits_consumed}</td>
                      <td className="px-3 py-2">
                        {new Date(event.occurred_at).toLocaleString()}
                      </td>
                    </tr>
                  )) || (
                    <tr>
                      <td className="px-3 py-4 text-slate-500" colSpan={4}>
                        No usage recorded yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <h3 className="text-lg font-semibold mb-2">Invoices</h3>
            <div className="max-h-64 overflow-y-auto rounded border">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-slate-100 text-xs uppercase text-slate-600">
                  <tr>
                    <th className="px-3 py-2">Invoice</th>
                    <th className="px-3 py-2">Period</th>
                    <th className="px-3 py-2">Credits</th>
                    <th className="px-3 py-2">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {invoicesQuery.data?.map((invoice) => (
                    <tr key={invoice.id} className="odd:bg-white even:bg-slate-50">
                      <td className="px-3 py-2 font-medium">{invoice.invoice_number}</td>
                      <td className="px-3 py-2">
                        {new Date(invoice.period_start).toLocaleDateString()} –{' '}
                        {new Date(invoice.period_end).toLocaleDateString()}
                      </td>
                      <td className="px-3 py-2">{invoice.credit_usage}</td>
                      <td className="px-3 py-2">{centsToCurrency(invoice.amount_due_cents)}</td>
                    </tr>
                  )) || (
                    <tr>
                      <td className="px-3 py-4 text-slate-500" colSpan={4}>
                        No invoices generated yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div>
          <h3 className="text-lg font-semibold mb-2">Credit Ledger</h3>
          <div className="max-h-48 overflow-y-auto rounded border">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-100 text-xs uppercase text-slate-600">
                <tr>
                  <th className="px-3 py-2">Timestamp</th>
                  <th className="px-3 py-2">Delta</th>
                  <th className="px-3 py-2">Balance</th>
                  <th className="px-3 py-2">Reason</th>
                </tr>
              </thead>
              <tbody>
                {ledgerQuery.data?.map((entry) => (
                  <tr key={entry.id} className="odd:bg-white even:bg-slate-50">
                    <td className="px-3 py-2">
                      {new Date(entry.created_at).toLocaleString()}
                    </td>
                    <td className={`px-3 py-2 ${entry.delta_credits >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                      {entry.delta_credits > 0 ? '+' : ''}
                      {entry.delta_credits}
                    </td>
                    <td className="px-3 py-2">{entry.running_balance}</td>
                    <td className="px-3 py-2">{entry.reason}</td>
                  </tr>
                )) || (
                  <tr>
                    <td className="px-3 py-4 text-slate-500" colSpan={4}>
                      Credit ledger is empty.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold">Partner Listings</h2>
        <p className="text-sm text-slate-600">
          Directly exchange specialized services with partner labs while orchestrating guardrail-aware
          review workflows.
        </p>
        <div className="flex flex-wrap gap-2">
          <input
            className="w-48 rounded border px-2 py-1 text-sm"
            placeholder="Inventory item ID"
            value={listingItemId}
            onChange={(event) => setListingItemId(event.target.value)}
          />
          <input
            className="w-32 rounded border px-2 py-1 text-sm"
            placeholder="Price"
            type="number"
            value={listingPrice}
            onChange={(event) => setListingPrice(event.target.value)}
          />
          <button
            className="inline-flex items-center rounded bg-slate-800 px-3 py-1.5 text-sm font-medium text-white"
            onClick={handleCreateListing}
          >
            Publish Listing
          </button>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          {listings?.map((listing) => (
            <article
              key={listing.id}
              className={`rounded border p-3 shadow-sm ${
                listing.id === selectedListing ? 'ring-2 ring-emerald-500' : ''
              }`}
              onClick={() => setSelectedListing(listing.id)}
            >
              <div className="flex items-center justify-between text-sm">
                <span className="font-semibold">Item {listing.item_id}</span>
                <span>{listing.price ? centsToCurrency(listing.price * 100) : 'Contact'}</span>
              </div>
              <p className="text-xs text-slate-600">Status: {listing.status}</p>
              <button
                className="mt-2 rounded border border-slate-400 px-2 py-1 text-xs"
                onClick={(event) => {
                  event.stopPropagation()
                  setSelectedListing(listing.id)
                  handleCreateRequest()
                }}
              >
                Request Collaboration
              </button>
            </article>
          ))}
        </div>
        {selectedListing && (
          <div className="rounded border p-3">
            <h3 className="text-lg font-semibold">Requests for listing {selectedListing}</h3>
            <ul className="mt-3 space-y-2 text-sm">
              {requestsQuery.data?.map((request) => (
                <li key={request.id} className="flex items-center justify-between rounded border px-3 py-2">
                  <div>
                    <p className="font-medium">Buyer: {request.buyer_id}</p>
                    <p className="text-xs text-slate-600">Status: {request.status}</p>
                  </div>
                  {request.status === 'pending' && (
                    <span className="space-x-2">
                      <button
                        className="rounded border border-emerald-600 px-2 py-1 text-xs text-emerald-700"
                        onClick={() => acceptRequest.mutate(request.id)}
                      >
                        Accept
                      </button>
                      <button
                        className="rounded border border-rose-600 px-2 py-1 text-xs text-rose-700"
                        onClick={() => rejectRequest.mutate(request.id)}
                      >
                        Reject
                      </button>
                    </span>
                  )}
                </li>
              )) || (
                <li className="rounded border border-dashed px-3 py-2 text-slate-500">
                  No requests yet.
                </li>
              )}
            </ul>
          </div>
        )}
      </section>
    </div>
  )
}
