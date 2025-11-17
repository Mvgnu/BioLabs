import { fireEvent, render, screen, within } from '@testing-library/react'
import React from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import MarketplacePage from '../page'

const marketplaceMocks = vi.hoisted(() => ({
  useMarketplaceListings: vi.fn(),
  useCreateListing: vi.fn(),
  useMarketplaceRequests: vi.fn(),
  useCreateRequest: vi.fn(),
  useAcceptRequest: vi.fn(),
  useRejectRequest: vi.fn(),
  useMarketplacePlans: vi.fn(),
  useCreateSubscription: vi.fn(),
  useOrganizationSubscription: vi.fn(),
  useOrganizationUsage: vi.fn(),
  useSubscriptionInvoices: vi.fn(),
  useCreateInvoiceDraft: vi.fn(),
  useAdjustCredits: vi.fn(),
  useCreditLedger: vi.fn(),
}))

const complianceMocks = vi.hoisted(() => ({
  useComplianceOrganizations: vi.fn(),
}))

vi.mock('../../hooks/useMarketplace', () => marketplaceMocks)
vi.mock('../../hooks/useCompliance', () => complianceMocks)

describe('MarketplacePage', () => {
  const createListingMutate = vi.fn()
  const createRequestMutate = vi.fn()
  const acceptRequestMutate = vi.fn()
  const rejectRequestMutate = vi.fn()
  const createSubscriptionMutate = vi.fn()
  const createInvoiceMutate = vi.fn()
  const adjustCreditsMutate = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()

    complianceMocks.useComplianceOrganizations.mockReturnValue({
      data: [
        {
          id: 'org-1',
          name: 'Helix Labs',
          slug: 'helix',
          primary_region: 'us-east-1',
          allowed_regions: ['us-east-1'],
        },
      ],
    })

    marketplaceMocks.useMarketplacePlans.mockReturnValue({
      data: [
        {
          id: 'plan-1',
          slug: 'lab-standard',
          title: 'Lab Standard',
          description: 'Core bundle',
          billing_cadence: 'monthly',
          base_price_cents: 12500,
          credit_allowance: 500,
          sla_tier: 'standard',
          metadata: { overage_rate_cents: 25 },
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          features: [
            {
              id: 'feature-1',
              feature_key: 'planner.finalize',
              label: 'Planner finalization',
              details: 'Guardrail aware finalize',
              created_at: new Date().toISOString(),
            },
          ],
        },
      ],
    })

    marketplaceMocks.useOrganizationSubscription.mockReturnValue({
      data: {
        id: 'sub-1',
        organization_id: 'org-1',
        plan: {
          id: 'plan-1',
          slug: 'lab-standard',
          title: 'Lab Standard',
          description: 'Core bundle',
          billing_cadence: 'monthly',
          base_price_cents: 12500,
          credit_allowance: 500,
          sla_tier: 'standard',
          metadata: {},
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          features: [],
        },
        status: 'active',
        billing_email: 'billing@helix.test',
        started_at: new Date('2024-01-01T00:00:00Z').toISOString(),
        renews_at: new Date('2024-02-01T00:00:00Z').toISOString(),
        cancelled_at: null,
        sla_acceptance: {},
        current_credits: 420,
        metadata: {},
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    })

    marketplaceMocks.useOrganizationUsage.mockReturnValue({
      data: [
        {
          id: 'usage-1',
          subscription_id: 'sub-1',
          organization_id: 'org-1',
          team_id: 'team-1',
          user_id: 'user-1',
          service: 'instrumentation',
          operation: 'run_completed',
          unit_quantity: 1,
          credits_consumed: 5,
          guardrail_flags: [],
          metadata: {},
          occurred_at: new Date('2024-01-15T12:00:00Z').toISOString(),
          created_at: new Date('2024-01-15T12:00:01Z').toISOString(),
        },
      ],
    })

    marketplaceMocks.useSubscriptionInvoices.mockReturnValue({
      data: [
        {
          id: 'inv-1',
          subscription_id: 'sub-1',
          organization_id: 'org-1',
          invoice_number: 'INV-001',
          period_start: new Date('2024-01-01T00:00:00Z').toISOString(),
          period_end: new Date('2024-01-31T23:59:59Z').toISOString(),
          amount_due_cents: 12500,
          credit_usage: 500,
          status: 'draft',
          issued_at: null,
          paid_at: null,
          line_items: [],
          created_at: new Date().toISOString(),
        },
      ],
    })

    marketplaceMocks.useCreditLedger.mockReturnValue({
      data: [
        {
          id: 'ledger-1',
          subscription_id: 'sub-1',
          organization_id: 'org-1',
          usage_event_id: 'usage-1',
          delta_credits: -5,
          reason: 'usage:instrumentation:run_completed',
          running_balance: 420,
          metadata: {},
          created_at: new Date('2024-01-15T12:00:01Z').toISOString(),
        },
      ],
    })

    marketplaceMocks.useMarketplaceListings.mockReturnValue({
      data: [
        {
          id: 'list-1',
          item_id: 'sample-1',
          seller_id: 'seller-1',
          price: 55,
          description: 'Sequence analytics bundle',
          status: 'open',
          created_at: new Date().toISOString(),
        },
      ],
    })

    marketplaceMocks.useMarketplaceRequests.mockReturnValue({
      data: [
        {
          id: 'req-1',
          listing_id: 'list-1',
          buyer_id: 'buyer-1',
          message: 'Interested in bundle',
          status: 'pending',
          created_at: new Date().toISOString(),
        },
      ],
    })

    marketplaceMocks.useCreateListing.mockReturnValue({ mutate: createListingMutate })
    marketplaceMocks.useCreateRequest.mockReturnValue({ mutate: createRequestMutate })
    marketplaceMocks.useAcceptRequest.mockReturnValue({ mutate: acceptRequestMutate })
    marketplaceMocks.useRejectRequest.mockReturnValue({ mutate: rejectRequestMutate })
    marketplaceMocks.useCreateSubscription.mockReturnValue({
      mutate: createSubscriptionMutate,
      isPending: false,
    })
    marketplaceMocks.useCreateInvoiceDraft.mockReturnValue({
      mutate: createInvoiceMutate,
      isPending: false,
    })
    marketplaceMocks.useAdjustCredits.mockReturnValue({
      mutate: adjustCreditsMutate,
      isPending: false,
    })
  })

  it('renders bundles and subscription insights', () => {
    render(<MarketplacePage />)

    expect(screen.getByRole('heading', { name: 'Marketplace & Billing' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Marketplace Bundles' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Lab Standard' })).toBeTruthy()
    expect(screen.getByText(/Planner finalization/i)).toBeTruthy()
    expect(screen.getByText(/Credits Remaining/)).toBeTruthy()
    expect(screen.getByText('Billing Email')).toBeTruthy()
    expect(screen.getByText('INV-001')).toBeTruthy()
    expect(screen.getByText('usage:instrumentation:run_completed')).toBeTruthy()
  })

  it('subscribes, drafts invoice, and adjusts credits', () => {
    render(<MarketplacePage />)

    fireEvent.click(screen.getAllByText('Subscribe')[0])
    expect(createSubscriptionMutate).toHaveBeenCalled()

    const generateButton = screen.getAllByRole('button', { name: 'Generate Draft Invoice' })[0]
    fireEvent.click(generateButton)
    expect(createInvoiceMutate).toHaveBeenCalled()

    const deltaInput = screen.getAllByLabelText('Credit delta')[0]
    fireEvent.change(deltaInput, { target: { value: '25' } })
    fireEvent.click(screen.getAllByText('Apply Credit Adjustment')[0])
    expect(adjustCreditsMutate).toHaveBeenCalledWith(
      expect.objectContaining({ delta_credits: 25, subscription_id: 'sub-1' }),
    )
  })

  it('manages partner listings and collaboration requests', () => {
    render(<MarketplacePage />)

    fireEvent.change(screen.getAllByPlaceholderText('Inventory item ID')[0], {
      target: { value: 'sample-2' },
    })
    fireEvent.change(screen.getAllByPlaceholderText('Price')[0], { target: { value: '75' } })
    fireEvent.click(screen.getAllByText('Publish Listing')[0])
    expect(createListingMutate).toHaveBeenCalled()

    fireEvent.click(screen.getAllByText('Request Collaboration')[0])
    expect(createRequestMutate).toHaveBeenCalled()

    const requestRow = screen.getByText('Buyer: buyer-1').closest('li')
    expect(requestRow).toBeTruthy()
    if (!requestRow) throw new Error('Missing request row')
    const { getByText } = within(requestRow)
    fireEvent.click(getByText('Accept'))
    expect(acceptRequestMutate).toHaveBeenCalled()
    fireEvent.click(getByText('Reject'))
    expect(rejectRequestMutate).toHaveBeenCalled()
  })
})
