# Biolab

A comprehensive laboratory management system.

## Overview

Biolab is a modern laboratory management platform that provides comprehensive tools for inventory management, protocol execution, data analysis, and team collaboration. Built with FastAPI and Next.js, it offers a robust API and intuitive web interface for managing laboratory workflows.

## Features

### Core Functionality
- **Dynamic Inventory Management**: Flexible inventory system with custom fields and hierarchical locations
- **Protocol Templates**: Reusable protocol templates with variable support and execution tracking
- **Lab Notebook**: Digital lab notebook with structured entries and versioning
- **Team Collaboration**: Role-based access control and team management
- **File Management**: Integrated file storage with MinIO for documents and data files

### Advanced Features
- **Sequence Analysis**: BLAST search, chromatogram parsing, and sequence alignment tools
- **Analytics Dashboard**: Comprehensive analytics and trending data visualization
- **Knowledge Base**: Collaborative knowledge sharing with articles and comments
- **Community Features**: Forum, social feed, and lab networking capabilities
- **Marketplace**: Resource sharing and service exchange between labs
- **Workflow Engine**: Automated workflows combining tools and protocols

### Technical Features
- **Real-time Updates**: WebSocket support for live data synchronization
- **Search**: Full-text search across inventory, protocols, and knowledge base
- **API Integration**: RESTful API with comprehensive documentation
- **Security**: JWT authentication, two-factor auth, and audit logging
- **Scalability**: Docker containerization and microservices architecture

## Database Schema

The system uses PostgreSQL with the following key tables:

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    hashed_password VARCHAR NOT NULL,
    full_name VARCHAR,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE teams (
    id UUID PRIMARY KEY,
    name VARCHAR NOT NULL,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE inventory_items (
    id UUID PRIMARY KEY,
    name VARCHAR NOT NULL,
    item_type VARCHAR NOT NULL,
    team_id UUID REFERENCES teams(id),
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE item_relationships (
    id UUID PRIMARY KEY,
    source_item_id UUID REFERENCES inventory_items(id),
    target_item_id UUID REFERENCES inventory_items(id),
    relationship_type VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Phase 1: Core Foundation (Months 1-3)

### Sprint 1-2: Authentication & User Management

**Goals:** Establish secure user authentication and team management

**Implementation:**

1. **User Authentication System**
- JWT-based auth with refresh tokens
- OAuth2 integration (Google, ORCID)
- Two-factor authentication
- Password policies and recovery
1. **Team & Permission Management**
- Hierarchical team structure
- Role-based permissions (Admin, Manager, Researcher, Viewer)
- Custom permission sets
- Audit logging system
1. **User Profile System**
- Professional profiles with ORCID integration
- Expertise tags
- Publication links
- Availability calendar

### Authorization

The API enforces role-based access control. Users belong to teams with a role of
`owner`, `manager`, or `member`. Owners can manage team membership, while
managers may edit team resources. Members have read/write access only to items
they own. Global administrators (`is_admin` flag) bypass these checks. Helpers in
`rbac.py` verify the current user has the required role before mutating data.
Every API route is audited at startup to ensure it requires authentication unless
explicitly listed as public (login, registration, metrics). A test verifies this
policy so new endpoints cannot accidentally bypass the RBAC layer.

**Deliverables:**

- Complete auth API endpoints
- User dashboard with profile management
- Team invitation and management system
- Permission matrix configuration UI

### Sprint 3-4: Dynamic Inventory System Foundation

**Goals:** Build flexible inventory management with custom fields

**Implementation:**

1. **Dynamic Field System**
- Field definition API
- UI for creating custom fields per inventory type
- Field types: text, number, date, select, multi-select, file, relation
- Validation rules engine
- Inheritance system for field definitions
1. **Core Inventory Management**
- CRUD operations for all inventory types
- Barcode/QR code generation and scanning
- Location management with hierarchical storage
- Batch operations support
- Import/Export functionality (CSV, Excel)

## Phase 2: Enhanced Features (Months 4-6)

### Sprint 5-6: Protocol Management

**Goals:** Implement protocol template system and execution tracking

**Implementation:**

1. **Protocol Templates**
- Template creation and management
- Variable system for dynamic protocols
- Version control and branching
- Public sharing and collaboration
1. **Execution Tracking**
- Protocol execution workflow
- Progress tracking and notifications
- Result recording and analysis
- Integration with inventory items

### Sprint 7-8: Data Analysis & Integration

**Goals:** Add sequence analysis tools and external integrations

**Implementation:**

1. **Sequence Analysis**
- BLAST search integration
- Chromatogram parsing and visualization
- Sequence alignment tools
- Primer design and restriction mapping
1. **External Services**
- NCBI database integration
- PubMed article linking
- Vendor catalog integration
- Equipment API connections

## Phase 3: Collaboration & Community (Months 7-9)

### Sprint 9-10: Knowledge Management

**Goals:** Build collaborative knowledge base and community features

**Implementation:**

1. **Knowledge Base**
- Article creation and management
- Tagging and categorization
- Comment system and ratings
- Search and discovery
1. **Community Features**
- Forum for discussions
- Social feed and following
- Lab networking and connections
- Resource sharing marketplace

### Sprint 11-12: Advanced Analytics

**Goals:** Implement comprehensive analytics and reporting

**Implementation:**

1. **Analytics Engine**
- Usage statistics and trends
- Performance metrics
- Predictive analytics
- Custom report generation
1. **Data Visualization**
- Interactive dashboards
- Chart and graph components
- Real-time data updates
- Export capabilities

## Phase 4: Advanced Features (Months 10-12)

### Sprint 13-14: Workflow Automation

**Goals:** Implement workflow engine and automation features

**Implementation:**

1. **Workflow Engine**
- Visual workflow builder
- Conditional logic and branching
- Integration with protocols and tools
- Execution monitoring
1. **Automation Features**
- Scheduled tasks and reminders
- Inventory alerts and forecasting
- Automated data collection
- Integration with lab equipment

### Sprint 15-16: Enterprise Features

**Goals:** Add enterprise-grade features and compliance tools

**Implementation:**

1. **Compliance & Security**
- Audit logging and reporting
- Data retention policies
- Security hardening
- Compliance frameworks
1. **Enterprise Integration**
- Single sign-on (SSO)
- LDAP/Active Directory integration
- API rate limiting
- Advanced monitoring

## Implementation Guidelines

### Development Best Practices

1. **Code Quality**
- Comprehensive test coverage
- Code review process
- Documentation standards
- Performance optimization
1. **Security**
- Input validation and sanitization
- SQL injection prevention
- XSS protection
- CSRF protection
1. **Scalability**
- Database optimization
- Caching strategies
- Load balancing
- Microservices architecture

### Technology Stack

**Backend:**
- FastAPI (Python web framework)
- SQLAlchemy (ORM)
- PostgreSQL (Database)
- Redis (Caching)
- Celery (Task queue)
- MinIO (Object storage)

**Frontend:**
- Next.js (React framework)
- TypeScript
- Tailwind CSS
- shadcn/ui components
- React Query (Data fetching)

**DevOps:**
- Docker (Containerization)
- GitHub Actions (CI/CD)
- Prometheus (Monitoring)
- Grafana (Visualization)

### Deployment Architecture

The system is designed for containerized deployment with the following components:

- **Web Application**: FastAPI backend + Next.js frontend
- **Database**: PostgreSQL with connection pooling
- **Cache**: Redis for session storage and caching
- **Storage**: MinIO for file storage
- **Queue**: Celery for background tasks
- **Monitoring**: Prometheus + Grafana

### Security Considerations

- All API endpoints require authentication except public routes
- JWT tokens with configurable expiration
- Password hashing with bcrypt
- Rate limiting on API endpoints
- Input validation and sanitization
- Audit logging for all data modifications
- Regular security updates and patches

### Performance Optimization

- Database query optimization with indexes
- Redis caching for frequently accessed data
- CDN for static assets
- Image optimization and compression
- Lazy loading for large datasets
- Background processing for heavy operations

## Budget Considerations

- Development team: 8-12 engineers
- Infrastructure: $5-15k/month
- Third-party services: $2-5k/month
- Security audits: $20-30k/year
- Marketing: $50-100k/year

## Timeline Summary

- Phase 1: Months 1-4 (Core Foundation)
- Phase 2: Months 5-7 (Enhanced Features)
- Phase 3: Months 8-10 (Collaboration)
- Phase 4: Months 11-12 (Advanced Features)
- Total MVP to Full Platform: 12 months

## Next Steps

1. Finalize technical architecture
1. Hire core development team
1. Set up development environment
1. Begin Phase 1 Sprint 1
1. Establish user advisory board

## Development with Docker

Run `docker-compose up --build` to start all services including Postgres, Redis, MinIO, the FastAPI backend, and Next.js frontend.

### Environment variables

Copy `.env.example` to `.env` and adjust values for your deployment. `SECRET_KEY` **must** be set to a random value or the server will refuse to start. Other variables configure database access, file storage, and Celery broker settings. `INVENTORY_WARNING_DAYS` controls when inventory alerts are sent based on forecasted depletion (default `7`).

### Database migrations

The project uses Alembic for managing database schema changes. After modifying
models, create a new migration and apply it:

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

Make sure `DATABASE_URL` is set to your database before running these commands.

## End-to-end tests

The frontend uses Playwright for E2E tests. From the `frontend` directory run:

```bash
npm install
npm run test:e2e
```

This starts the Next.js dev server and executes the tests.

## Performance benchmarking

Basic load tests are provided using [Locust](https://locust.io). From the `backend` directory run:

```bash
pip install -r requirements.txt
locust -f benchmarks/locustfile.py --host http://localhost:8000
```

Then open http://localhost:8089 in your browser to start the test.

## Data analysis tools

The backend includes a simple Pandas-based endpoint for summarizing CSV files. Upload a CSV to `/api/data/summary` to receive descriptive statistics for numeric columns.

## Analytics

Use `/api/analytics/summary` to see counts of inventory items by type. The
`/api/analytics/trending-protocols` endpoint lists the most frequently executed
protocol templates and weights results by how recently each template was run.
`/api/analytics/trending-protocol-stars` ranks public templates by how many users have starred them, weighted by how recent the stars are.
`/api/analytics/trending-articles` returns the most viewed knowledge articles,
also weighting recent views more heavily, while `/api/analytics/trending-article-stars` ranks articles by star count with a similar recency weighting. `/api/analytics/trending-article-comments` lists articles with the most comment activity. `/api/analytics/trending-items` shows
which inventory items appear most often in notebook entries with a similar
recency weighting. `/api/analytics/trending-threads` lists forum threads by a
weighted score of post count and recent activity, and
`/api/analytics/trending-posts` ranks community posts using likes adjusted for
how recently the post was created. Each trending endpoint accepts an optional
`days` query parameter (default `30`) to control how far back the data should be
aggregated.

The frontend Analytics page visualizes these trends, displaying item counts and
lists of top protocols, knowledge articles, inventory items, and forum threads.

## Knowledge base

Users can contribute articles to a collaborative knowledge base. Use the `/api/knowledge/articles` endpoints to create, list, update, and delete articles tagged by topic.
Set `is_public` to make an article visible to all users. Articles can be commented on via `/api/comments` using the `knowledge_article_id` field.
Readers may star helpful articles with `POST /api/knowledge/articles/{id}/star` and remove their star via `DELETE` to the same path. Retrieve the current count from `/api/knowledge/articles/{id}/stars`.

## Forum

Use `/api/forum/threads` to start discussion threads and `/api/forum/threads/{thread_id}/posts` to reply. The forum allows labs to collaborate and troubleshoot together.

## Protocol diffs

Compare two protocol templates using `/api/protocols/diff?old_id=...&new_id=...` to see a unified diff of their contents.
The frontend exposes a diff viewer at `/protocols/diff` where you can select two templates and view the differences.

## Calendar events

Schedule meetings or equipment usage with the `/api/calendar` endpoints. The frontend Calendar page allows creating events and viewing them in a list.

## Project management

Create and organize projects using `/api/projects`. Each project can have multiple tasks managed via `/api/projects/{project_id}/tasks`. The Projects page allows creating projects and tracking task status.

## Lab network

Labs can create public profiles and connect with other labs to collaborate. Use `/api/labs` to create and list lab profiles. Request connections with `/api/labs/{lab_id}/connections` and accept them via `/api/labs/connections/{connection_id}/accept`.

## Locations

Manage hierarchical storage locations via the `/api/locations` endpoints. Locations can be nested (e.g. `Building > Room > Freezer > Shelf`). When creating or updating an inventory item, set `location_id` to link it to a specific location.

## Faceted inventory search

The `/api/inventory/facets` endpoint returns counts of items grouped by type, status and team, along with available custom fields. The `/api/inventory/items` list API accepts `status`, `team_id`, `created_from`, and `created_to` query parameters to filter results. The frontend inventory page uses these facets to provide sidebar filters and shareable URLs.

## Resource sharing

Connected labs can share equipment with each other. Submit a request to `/api/resource-shares` with a resource ID and the target lab. Lab owners view requests at `/api/resource-shares` and may accept or reject them via `/api/resource-shares/{share_id}/accept` or `/reject`.

## Marketplace

Labs may list inventory items for exchange or sale. Create a listing via `/api/marketplace/listings` with the item ID and optional price. Anyone can view open listings at `/api/marketplace/listings`. Interested labs submit a request to `/api/marketplace/listings/{listing_id}/requests` and the listing owner may accept or reject it using `/api/marketplace/requests/{request_id}/accept` or `/reject`.
The frontend includes a Marketplace page where labs can browse listings, create their own, and manage incoming requests.

Labs may also offer **services** such as sequencing runs. Create a service listing via `/api/services/listings` and request it with `/api/services/listings/{listing_id}/requests`. Providers respond using `/api/services/requests/{request_id}/accept` or `/reject`.
After completing a request, providers upload result files with `/api/services/requests/{request_id}/deliver`. Requesters confirm payment via `/api/services/requests/{request_id}/confirm-payment` which marks the request as paid.

## Workflows and enhanced notebook

Workflows combine analysis tools and protocol templates into reusable pipelines. Create workflows via `/api/workflows` with a list of steps referencing tool or protocol IDs. Run a workflow on an inventory item by calling `/api/workflows/run`.

Protocol templates may define **variables** that must be provided when executing. Include a `variables` array when creating a template. When starting an execution, all required parameters must be supplied in the `params` object.
Templates can be shared with the community by setting `is_public` to `true`. Public templates are listed at `/api/protocols/public`. Use `/api/protocols/templates/{id}/fork` to copy a public template into your own team for customization.
Anyone may propose improvements via **merge requests** using `/api/protocols/merge-requests`. Template authors can review requests, accept them to update their template, or reject them.
Users may also **star** interesting public templates. Add a star with `POST /api/protocols/templates/{id}/star` and remove it with `DELETE` to the same path. Retrieve the current star count via `/api/protocols/templates/{id}/stars`.

Workflow steps accept an optional `condition` expression. If the expression evaluates to false using the current `item` and accumulated `results`, the step is skipped. This allows simple branching logic without a full workflow engine.

Notebook entries now support linking to projects, multiple items, protocols, and uploaded images. Include `project_id`, `items`, `protocols`, and `images` fields when creating or updating entries.

Entries may include **structured blocks** representing rich text, tables, images, and materials used. The API accepts a `blocks` array when creating or updating entries, storing each block as JSON so the frontend's TipTap editor can reconstruct the content.

Entries can be **signed** by their author and subsequently **witnessed** by another user. Signing locks the entry from further edits. Every save automatically records a new version in `notebook_entry_versions`, which can be retrieved via `/api/notebook/entries/{entry_id}/versions`.
Use `/api/notebook/entries/{entry_id}/sign` to sign an entry and `/witness` to witness it.

## Lab buddy assistant

The `/api/assistant` endpoints provide a lightweight chat assistant. Ask
questions with `/api/assistant/ask` and view history via `/api/assistant`.
The assistant can forecast inventory depletion based on recent notebook
usage with `/api/assistant/forecast`.
It can also suggest relevant protocols and matching materials from your
inventory using `/api/assistant/suggest?goal=...`.
The design helper at `/api/assistant/design?goal=...` returns a suggested
protocol, matching materials, and relevant knowledge articles to kick start
an experiment.
Each day a background task reviews the forecast and sends an in-app or
email notification if any item is projected to run out within
`INVENTORY_WARNING_DAYS`.

## Community feed

Users can follow other researchers and share short posts. Create posts with `/api/community/posts` and follow a user via `/api/community/follow/{user_id}`. Your feed of followed users is available at `/api/community/feed`. The frontend provides a simple feed page to browse recent posts.
Posts can be liked using `/api/community/posts/{post_id}/like` and unliked via `DELETE` to the same path. Retrieve the like count with `/api/community/posts/{post_id}/likes`. Posts can also be reported for moderation using `/api/community/posts/{post_id}/report`. Reports are listed at `/api/community/reports` and may be resolved via `/api/community/reports/{report_id}/resolve`.

## UI/UX improvements

Recent frontend updates focus on accessibility and usability:

- Responsive navigation menu with mobile toggle
- Skip link for keyboard users
- Loading and error states on inventory pages
- Simple onboarding tour displayed on first visit

## Monitoring

The backend exposes Prometheus metrics at `/metrics`. Running `docker-compose up`
also starts Prometheus and Grafana. Visit `http://localhost:3001` to view
metrics dashboards. Set `SENTRY_DSN` in the backend environment to enable
Sentry error reporting. 