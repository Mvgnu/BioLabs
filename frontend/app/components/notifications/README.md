# Notification Components

## Overview
- purpose: Provide a unified real-time notification experience across the BioLab frontend.
- status: active
- owner: notifications team
- related_docs: ../../store/useNotifications.ts, ../../hooks/useNotificationAPI.ts, NotificationProvider.tsx

## Key Pieces
1. **NotificationProvider**
   - Hydrates the notification Zustand store from REST endpoints (`/api/notifications`, `/api/notifications/stats`, `/api/notifications/preferences`).
   - Subscribes to the team-scoped WebSocket channel and dispatches lifecycle events to the store.
   - Renders toast notifications for `notification_created` events.
2. **NotificationCenter**
   - Reads from the shared store for list rendering, filtering, and statistics.
   - Provides bulk actions (mark-all-read, clear filters) and detail views per notification.
3. **NotificationBell / ToastContainer**
   - Exposes global entry points for the center and surfaces lightweight real-time alerts.

## Integration Notes
- Ensure `NotificationProvider` is mounted once inside `layout.tsx` after the `QueryClientProvider` so React Query hooks have access to the shared client.
- WebSocket connections require the current user's primary team; the provider fetches `/api/teams/` and selects the first result.
- When extending notification payloads, update both `backend/app/schemas.py::NotificationOut` and `frontend/app/types/notifications.ts` to keep the event contract synchronized.

## Testing
- Backend coverage: `backend/app/tests/test_notifications.py::test_notification_events_published` asserts Redis/WebSocket propagation.
- Frontend store behavior can be validated with targeted unit tests under `frontend/app/store/__tests__/` (to be added).
