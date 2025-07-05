# Refinement Roadmap

This tracker outlines advanced enhancements planned after the MVP. Each section lists concrete tasks that build on the existing infrastructure to deliver a polished, production-ready experience.

## Completed
- **Notebook signing & versioning** (2025-07-14)
  - Entries can be signed and locked by the author
  - Witnesses may countersign locked entries
  - Every save creates a `NotebookEntryVersion` record
  - API endpoints support signing, witnessing and version retrieval
- **Hierarchical locations** (2025-07-13)
  - Added `Location` model and CRUD endpoints
  - Inventory items reference `location_id`
- **Equipment operations module** (2025-07-15)
  - Schedule calibration and maintenance tasks for devices
  - Maintain an SOP repository with version history
  - Record user training linked to SOPs and equipment
- **Inventory faceted search** (2025-07-16)
  - Added sidebar filters and facets endpoint for inventory listing
- **Protocol variables & conditional workflows** (2025-07-17)
  - Templates define variables filled at execution time
  - Workflow steps can be conditionally skipped
- **Structured notebook blocks** (2025-07-18)
  - Notebook entries store an array of rich content blocks
  - API and schemas accept a `blocks` array
- **Service marketplace for CRO offerings** (2025-07-19)
  - Added service listing and request APIs
  - Providers can accept or reject service requests
- **Public protocol sharing** (2025-07-20)
  - Templates include `is_public` flag and optional `forked_from` reference
  - `/api/protocols/public` lists shared templates
  - `/api/protocols/templates/{id}/fork` creates a copy for your team

- **Protocol merge requests** (2025-07-21)
  - Users can propose changes to public templates
  - Authors review requests and accept or reject them
- **Assistant protocol suggestions** (2025-07-23)
  - `/api/assistant/suggest` recommends protocols matching a goal
  - Returns suggested inventory items for required variables
- **Predictive inventory alerts** (2025-07-25)
  - Daily task checks forecasted stock levels
  - Sends notifications or emails when items may run low
- **Service result delivery & payment tracking** (2025-07-26)
  - CRO providers upload results for service requests
  - Requesters confirm payment once results are received
- **Trending protocol analytics** (2025-07-27)
  - `/api/analytics/trending-protocols` lists most-run templates in the last 30 days
- **Trending article analytics** (2025-07-28)
  - `/api/analytics/trending-articles` shows the most viewed knowledge articles in the last 30 days
- **Trending item analytics** (2025-07-29)
  - `/api/analytics/trending-items` lists inventory items appearing most often in notebook entries
- **Trending thread analytics** (2025-08-02)
  - `/api/analytics/trending-threads` lists forum threads with the most posts
- **Protocol diff viewer** (2025-08-04)
  - View unified diffs between protocol templates
- **Post like analytics** (2025-08-05)
  - Users can like posts and `/api/analytics/trending-posts` ranks them
- **Advanced trending ranking** (2025-08-06)
  - Trending posts and threads weighted by recency
- **Weighted protocol, article and item analytics** (2025-08-07)
  - Trending protocols, articles and items now factor in how recent the
    executions, views and notebook entries occurred
- **Protocol stars and trending by stars** (2025-08-08)
  - Users can star templates and `/api/analytics/trending-protocol-stars`
    lists the most starred templates weighted by recency
- **Article stars and trending by stars** (2025-08-09)
  - Knowledge articles can be starred and `/api/analytics/trending-article-stars`
    lists the most starred articles weighted by recency
- **Article comment analytics** (2025-08-10)
  - `/api/analytics/trending-article-comments` ranks articles by recent comment activity

## Next Steps

## Future Opportunities
- **Service marketplace for CRO offerings**
  - Support service listings and request workflows
  - Handle file delivery and payment tracking
- **Forkable public protocols**
  - Users may publish protocols and accept merge requests
  - Version history shows provenance of community contributions
- **Intelligent assistant**
  - Analyze inventory usage to forecast shortages
  - Suggest protocols and assemble materials lists automatically
