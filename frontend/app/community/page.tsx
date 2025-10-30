'use client'

import React, { useMemo, useState } from 'react'
import { useAuthStore } from '../store/useAuth'
import {
  useCommunityFeed,
  useCommunityPortfolios,
  useTrendingPortfolios,
  useCreatePortfolio,
  useRecordPortfolioEngagement,
} from '../hooks/useCommunity'
import type { CommunityPortfolio, CommunityPortfolioAsset } from '../types'

const guardrailBadge = (flags: string[]) => {
  if (!flags.length) return <span className="rounded bg-emerald-100 px-2 py-1 text-xs text-emerald-700">guardrails cleared</span>
  return (
    <span className="rounded bg-amber-100 px-2 py-1 text-xs text-amber-700">
      guardrail flags: {flags.join(', ')}
    </span>
  )
}

const AssetPanel = ({ asset }: { asset: CommunityPortfolioAsset }) => {
  const metadata = (asset.meta ?? {}) as Record<string, unknown>
  const diffValue = metadata['diff']
  const diff = typeof diffValue === 'string' ? diffValue : undefined
  return (
    <div className="rounded border p-3" data-asset-type={asset.asset_type}>
      <div className="flex items-center justify-between text-sm font-semibold">
        <span>{asset.asset_type.replace('_', ' ')}</span>
        <span className="text-xs text-slate-500">linked {new Date(asset.created_at).toLocaleString()}</span>
      </div>
      <dl className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-600">
        <div>
          <dt className="font-semibold">Asset ID</dt>
          <dd className="break-all">{asset.asset_id}</dd>
        </div>
        {asset.asset_version_id && (
          <div>
            <dt className="font-semibold">Version</dt>
            <dd>{asset.asset_version_id}</dd>
          </div>
        )}
        {asset.planner_session_id && (
          <div>
            <dt className="font-semibold">Planner session</dt>
            <dd>{asset.planner_session_id}</dd>
          </div>
        )}
      </dl>
      <div className="mt-3 space-y-2 text-xs">
        <div className="text-slate-600">
          <span className="font-semibold">Guardrail snapshot:</span>{' '}
          <code className="break-all text-slate-500">{JSON.stringify(asset.guardrail_snapshot)}</code>
        </div>
        {diff && (
          <div className="rounded bg-slate-900 p-2 font-mono text-[11px] text-emerald-200" aria-label="inline diff preview">
            {diff}
          </div>
        )}
      </div>
    </div>
  )
}

const PortfolioCard = ({ portfolio }: { portfolio: CommunityPortfolio }) => {
  const engagement = useRecordPortfolioEngagement(portfolio.id)
  const emitEngagement = (interaction: 'view' | 'star' | 'bookmark' | 'review', weight?: number) => () => {
    engagement.mutate({ interaction, weight })
  }
  return (
    <article className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm" data-portfolio-id={portfolio.id}>
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">{portfolio.title}</h3>
          <p className="text-sm text-slate-600">{portfolio.summary || 'No summary provided yet.'}</p>
        </div>
        {guardrailBadge(portfolio.guardrail_flags)}
      </header>
      <div className="mt-3 flex flex-wrap gap-2 text-xs uppercase tracking-wide text-slate-500">
        <span className="rounded bg-slate-100 px-2 py-1">{portfolio.license}</span>
        <span className="rounded bg-slate-100 px-2 py-1">status: {portfolio.status}</span>
        <span className="rounded bg-slate-100 px-2 py-1">score: {portfolio.engagement_score.toFixed(2)}</span>
        {portfolio.tags.map(tag => (
          <span key={tag} className="rounded bg-indigo-100 px-2 py-1 text-indigo-700">
            #{tag}
          </span>
        ))}
      </div>
      <section className="mt-4 grid gap-3 md:grid-cols-2" aria-label="linked assets">
        {portfolio.assets.map(asset => (
          <AssetPanel key={asset.id} asset={asset} />
        ))}
        {!portfolio.assets.length && <p className="text-sm text-slate-500">No assets have been linked yet.</p>}
      </section>
      <footer className="mt-4 flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <button
          className="rounded bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-100"
          onClick={emitEngagement('star')}
        >
          Star for curation
        </button>
        <button
          className="rounded bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-100"
          onClick={emitEngagement('bookmark', 0.7)}
        >
          Bookmark for replay
        </button>
        <button
          className="rounded bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100"
          onClick={emitEngagement('view', 0.2)}
        >
          Record review session
        </button>
        <span className="ml-auto text-right">Updated {new Date(portfolio.updated_at).toLocaleString()}</span>
      </footer>
    </article>
  )
}

export default function CommunityDiscoveryPage() {
  const { token } = useAuthStore()
  const [licenseFilter, setLicenseFilter] = useState<string>('all')
  const [guardrailFilter, setGuardrailFilter] = useState<'all' | 'cleared' | 'flagged'>('all')
  const [timeframe, setTimeframe] = useState<'24h' | '7d' | '30d'>('7d')
  const [search, setSearch] = useState('')
  const createPortfolio = useCreatePortfolio()
  const { data: feed } = useCommunityFeed(6)
  const { data: trending } = useTrendingPortfolios(timeframe)
  const { data: portfolios } = useCommunityPortfolios({ visibility: 'public' })

  const filteredPortfolios = useMemo(() => {
    if (!portfolios) return []
    return portfolios.filter(portfolio => {
      const matchesLicense = licenseFilter === 'all' || portfolio.license === licenseFilter
      const matchesGuardrail =
        guardrailFilter === 'all' ||
        (guardrailFilter === 'cleared' && portfolio.guardrail_flags.length === 0) ||
        (guardrailFilter === 'flagged' && portfolio.guardrail_flags.length > 0)
      const matchesSearch =
        !search ||
        portfolio.title.toLowerCase().includes(search.toLowerCase()) ||
        portfolio.tags.some(tag => tag.toLowerCase().includes(search.toLowerCase()))
      return matchesLicense && matchesGuardrail && matchesSearch
    })
  }, [portfolios, licenseFilter, guardrailFilter, search])

  if (!token) {
    return <div className="p-6 text-center text-slate-600">Please sign in to explore collaborative community portfolios.</div>
  }

  return (
    <div className="space-y-10 p-6">
      <header className="space-y-3">
        <h1 className="text-2xl font-bold text-slate-900">Community discovery hub</h1>
        <p className="max-w-3xl text-sm text-slate-600">
          Explore federated DNA workspaces, review provenance-aware releases, and surface cloning templates ready for replay with guardrail context.
        </p>
      </header>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm" aria-label="portfolio controls">
        <form
          className="flex flex-wrap gap-3"
          onSubmit={event => {
            event.preventDefault()
            const form = event.currentTarget
            const data = new FormData(form)
            const slug = (data.get('slug') as string) || ''
            const title = (data.get('title') as string) || ''
            if (!slug || !title) return
            createPortfolio.mutate({
              slug,
              title,
              summary: (data.get('summary') as string) || undefined,
              license: (data.get('license') as string) || 'CC-BY-4.0',
              tags: ((data.get('tags') as string) || '')
                .split(',')
                .map(tag => tag.trim())
                .filter(Boolean),
              assets: [],
            })
            form.reset()
          }}
        >
          <div className="flex flex-1 flex-col gap-1">
            <label htmlFor="portfolio-search" className="text-xs font-semibold uppercase text-slate-500">
              Search & filters
            </label>
            <input
              id="portfolio-search"
              name="portfolio-search"
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              placeholder="Filter by tag, title, or license"
              value={search}
              onChange={event => setSearch(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold uppercase text-slate-500" htmlFor="license-filter">
              License
            </label>
            <select
              id="license-filter"
              className="rounded border border-slate-300 px-3 py-2 text-sm"
              value={licenseFilter}
              onChange={event => setLicenseFilter(event.target.value)}
            >
              <option value="all">All</option>
              <option value="CC-BY-4.0">CC-BY-4.0</option>
              <option value="CC0">CC0</option>
              <option value="restricted">Restricted</option>
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold uppercase text-slate-500" htmlFor="guardrail-filter">
              Guardrails
            </label>
            <select
              id="guardrail-filter"
              className="rounded border border-slate-300 px-3 py-2 text-sm"
              value={guardrailFilter}
              onChange={event => setGuardrailFilter(event.target.value as typeof guardrailFilter)}
            >
              <option value="all">All</option>
              <option value="cleared">Cleared</option>
              <option value="flagged">Flagged</option>
            </select>
          </div>
          <div className="flex flex-1 flex-col gap-1">
            <label className="text-xs font-semibold uppercase text-slate-500" htmlFor="slug">
              New portfolio slug
            </label>
            <input id="slug" name="slug" className="rounded border border-slate-300 px-3 py-2 text-sm" placeholder="synthetic-control-kit" />
          </div>
          <div className="flex flex-1 flex-col gap-1">
            <label className="text-xs font-semibold uppercase text-slate-500" htmlFor="title">
              Title
            </label>
            <input id="title" name="title" className="rounded border border-slate-300 px-3 py-2 text-sm" placeholder="Synthetic control kit" />
          </div>
          <div className="flex flex-1 flex-col gap-1">
            <label className="text-xs font-semibold uppercase text-slate-500" htmlFor="summary">
              Summary
            </label>
            <input id="summary" name="summary" className="rounded border border-slate-300 px-3 py-2 text-sm" placeholder="Share replay-ready plasmid templates" />
          </div>
          <div className="flex flex-1 flex-col gap-1">
            <label className="text-xs font-semibold uppercase text-slate-500" htmlFor="license">
              License
            </label>
            <select id="license" name="license" className="rounded border border-slate-300 px-3 py-2 text-sm" defaultValue="CC-BY-4.0">
              <option value="CC-BY-4.0">CC-BY-4.0</option>
              <option value="CC0">CC0</option>
              <option value="restricted">Restricted</option>
            </select>
          </div>
          <div className="flex flex-1 flex-col gap-1">
            <label className="text-xs font-semibold uppercase text-slate-500" htmlFor="tags">
              Tags (comma separated)
            </label>
            <input id="tags" name="tags" className="rounded border border-slate-300 px-3 py-2 text-sm" placeholder="plasmid, qpcr, guardrail" />
          </div>
          <button
            type="submit"
            className="self-end rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800"
            disabled={createPortfolio.isPending}
          >
            Publish discovery portfolio
          </button>
        </form>
      </section>

      <section className="grid gap-6 lg:grid-cols-3" aria-label="insights">
        <div className="space-y-3 rounded-lg border border-indigo-200 bg-indigo-50 p-4 text-sm text-indigo-900">
          <h2 className="text-base font-semibold">Personalized review queue</h2>
          <ul className="space-y-2">
            {feed?.map(entry => (
              <li key={entry.portfolio.id} className="rounded bg-white/70 p-3 shadow-sm">
                <div className="flex items-center justify-between text-xs uppercase tracking-wide text-indigo-500">
                  <span>{entry.reason}</span>
                  <span>score {entry.score.toFixed(2)}</span>
                </div>
                <p className="mt-1 text-sm font-medium text-slate-900">{entry.portfolio.title}</p>
                <p className="text-xs text-slate-600">{entry.portfolio.summary}</p>
              </li>
            )) || <li className="text-xs text-indigo-500">No personalized entries yet.</li>}
          </ul>
        </div>
        <div className="space-y-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold">Trending guardrail-ready releases</h2>
            <select
              className="rounded border border-emerald-300 bg-white px-2 py-1 text-xs"
              value={timeframe}
              onChange={event => setTimeframe(event.target.value as typeof timeframe)}
            >
              <option value="24h">24h</option>
              <option value="7d">7d</option>
              <option value="30d">30d</option>
            </select>
          </div>
          <ul className="space-y-2">
            {trending?.portfolios.map(entry => (
              <li key={entry.portfolio.id} className="rounded bg-white/70 p-3 shadow-sm">
                <div className="flex items-center justify-between text-xs uppercase tracking-wide text-emerald-500">
                  <span>engagement Δ {entry.engagement_delta.toFixed(2)}</span>
                  <span>{entry.guardrail_summary.length ? entry.guardrail_summary.join(', ') : 'cleared'}</span>
                </div>
                <p className="mt-1 text-sm font-medium text-slate-900">{entry.portfolio.title}</p>
                <p className="text-xs text-slate-600">{entry.portfolio.summary}</p>
              </li>
            )) || <li className="text-xs text-emerald-500">No trending releases detected.</li>}
          </ul>
        </div>
        <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-900">
          <h2 className="text-base font-semibold">Replay checkpoints</h2>
          <ul className="space-y-2 text-xs text-slate-600">
            {filteredPortfolios.flatMap(portfolio =>
              portfolio.replay_checkpoints.map(checkpoint => {
                const record = (checkpoint as Record<string, unknown>) ?? {}
                const checkpointLabel = typeof record['checkpoint'] === 'string' ? (record['checkpoint'] as string) : 'checkpoint pending'
                const guardrailMeta = JSON.stringify(record)
                return (
                  <li key={`${portfolio.id}-${checkpointLabel}`} className="rounded border border-slate-100 bg-slate-50 p-2">
                    <div className="flex items-center justify-between text-[11px] uppercase tracking-wide text-slate-500">
                      <span>{portfolio.title}</span>
                      <span>{checkpointLabel}</span>
                    </div>
                    <code className="mt-1 block break-all font-mono text-[11px] text-slate-700">{guardrailMeta}</code>
                  </li>
                )
              }),
            )}
            {!filteredPortfolios.some(p => p.replay_checkpoints.length) && (
              <li className="text-xs text-slate-500">Replay checkpoints will appear once portfolios link planner sessions.</li>
            )}
          </ul>
        </div>
      </section>

      <section className="space-y-4" aria-label="portfolio library">
        <h2 className="text-xl font-semibold text-slate-900">Federated portfolios</h2>
        <div className="grid gap-4 xl:grid-cols-2">
          {filteredPortfolios.map(portfolio => (
            <PortfolioCard key={portfolio.id} portfolio={portfolio} />
          ))}
          {!filteredPortfolios.length && (
            <p className="text-sm text-slate-500">No portfolios match the current filters. Adjust filters or publish a new discovery set.</p>
          )}
        </div>
      </section>
    </div>
  )
}
