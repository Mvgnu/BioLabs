# BioLabs Frontend

This is an early scaffold for the Next.js application. It was generated manually to avoid shipping node modules.

## Getting Started

```bash
npm install
npm run dev
```

The app now includes simple login and registration pages along with an inventory screen. Logged in users can create new items using a dynamically generated form based on field definitions returned by the backend. Tokens are stored in `localStorage` and used for authenticated API requests.
You can also manage custom field definitions through the **Fields** page. New fields can be created for any entity type and will immediately appear in the inventory creation form.
Items listed on the inventory page can now be edited or deleted. Selecting **Edit** fills the form with the item's current data so you can update it on the fly.
Additional features include item detail pages where you can upload files to an item and visualize its relationships. Files are stored via the backend API and listed alongside a simple D3-based graph of related items.
Real-time updates are streamed over WebSockets. When items are created, updated, or deleted, connected clients receive event messages automatically.
You can also browse and contribute to a knowledge base of troubleshooting articles via the **Troubleshooting** page.
General lab tips can be shared in the new **Knowledge Base** page which lists all community articles.
Templates for standard lab procedures can be created and executed through the **Protocols** page.
Notebook entries can be managed from the **Notebook** page.
Sequence annotation files (GenBank) can be uploaded on the **Sequence** page to
view parsed features in a table. Interact with the lab buddy AI assistant from
the **Assistant** page to get project and inventory summaries.
Navigate to `/dna-viewer/[assetId]` to explore the new DNA viewer surface which renders circular and linear feature overlays,
guardrail badge states, kinetics summaries, and version diffs using the backend viewer payload contract.
Launch the cloning planner wizard at `/planner` to create new sessions, then follow orchestration progress and guardrail
escalations at `/planner/{sessionId}` with live Redis-backed updates and QC artifact previews.
Launch guided experiment runs through the **Experiment Console**, which unifies protocol steps, live logging, inventory pulls,
and equipment bookings into a single execution workspace.
Use the **Search** page to quickly locate items by name.

Administrators can now access the **Governance** workspace to author narrative workflow templates. The console surfaces the
template library, version-aware editor, and a React Flow powered ladder builder for stage design. Persist drafts or publish new
versions directly against the backend governance APIs, then map templates to teams or protocol templates via the assignment
panel.

## Testing

Run the Vitest suite to execute unit coverage for client hooks and UI logic, including the staged approval ladder cache handlers:

```bash
npm run test
```
