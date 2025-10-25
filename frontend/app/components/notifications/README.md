# Notification Components

## Overview
- purpose: Provide a unified real-time notification experience across the BioLab frontend.
- status: active
- owner: notifications team
- related_docs: ../../store/useNotifications.ts, ../../hooks/useNotificationAPI.ts, NotificationProvider.tsx

## Key Pieces
1. **NotificationProvider**
   - Hydrates the notification Zustand store from REST endpoints (`/api/notifications`, `/api/notifications/stats`, `/api/notifications/preferences`).
   - Subscribes to all team-scoped WebSocket channels for the current user, deduplicating lifecycle events before forwarding them to the store.
   - Reacts to team membership churn and tab/connection resume events by resetting the dedupe window and replaying data from REST sources so late-joining or returning sessions do not miss historical activity.
   - Renders toast notifications for `notification_created` events while updating global loading/error state directly on the store.
2. **NotificationCenter**
   - Reads exclusively from the shared store for list rendering, filtering, and statistics (no duplicate React Query fetch loops).
   - Provides bulk actions (mark-all-read, clear filters) and detail views per notification.
3. **NotificationBell / ToastContainer**
   - Exposes global entry points for the center and surfaces lightweight real-time alerts.
4. **NotificationSettingsPanel**
   - Provides digest cadence controls, quiet hour scheduling, and per-category channel routing backed by `/api/notifications/settings` and `/api/notifications/preferences`.

## Integration Notes
- Ensure `NotificationProvider` is mounted once inside `layout.tsx` after the `QueryClientProvider` so React Query hooks have access to the shared client.
- WebSocket connections require the current user's team memberships; the provider fetches `/api/teams/` and subscribes to each membership while suppressing duplicate lifecycle events.
- Membership changes trigger a full replay cycle (refreshing notifications, stats, preferences) to backfill any gaps introduced while the user joined/left teams mid-session.
- When extending notification payloads, update both `backend/app/schemas.py::NotificationOut` and `frontend/app/types/notifications.ts` to keep the event contract synchronized.

## Testing
- Backend coverage: `backend/app/tests/test_notifications.py::{test_notification_events_published,test_notification_events_multiteam_stream}` asserts Redis/WebSocket propagation across all teams.
- Frontend store behavior is validated with unit tests under `frontend/app/store/__tests__/useNotifications.test.ts`.
