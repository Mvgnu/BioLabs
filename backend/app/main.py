from fastapi import FastAPI, WebSocket, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import json
import os
import time
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from . import pubsub
from .database import Base, engine
from .routes import (
    auth,
    users,
    inventory,
    fields,
    locations,
    teams,
    files,
    protocols,
    troubleshooting,
    notebook,
    comments,
    notifications,
    schedule,
    sequence,
    projects,
    assistant,
    calendar,
    tools,
    analytics,
    governance_analytics,
    governance_baselines,
    search,
    audit,
    labs,
    resource_shares,
    marketplace,
    services,
    forum,
    community,
    compliance,
    governance,
    equipment,
    experiment_console,
    external,
    data_analysis,
    knowledge,
    workflows,
)


dsn = os.getenv("SENTRY_DSN")
if dsn:
    sentry_sdk.init(dsn=dsn, integrations=[FastApiIntegration()])

REQUEST_COUNT = Counter("request_count", "Total requests", ["method", "endpoint"])
REQUEST_LATENCY = Histogram(
    "request_latency_seconds", "Request latency", ["endpoint"]
)

app = FastAPI(title="BioLabs API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda r, e: Response("Too Many Requests", status_code=429))
if os.getenv("TESTING") != "1":
    app.add_middleware(SlowAPIMiddleware)


@app.middleware("http")
async def record_metrics(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    endpoint = request.url.path
    REQUEST_COUNT.labels(request.method, endpoint).inc()
    REQUEST_LATENCY.labels(endpoint).observe(time.time() - start)
    return response

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(inventory.router)
app.include_router(fields.router)
app.include_router(locations.router)
app.include_router(teams.router)
app.include_router(files.router)
app.include_router(protocols.router)
app.include_router(troubleshooting.router)
app.include_router(notebook.router)
app.include_router(comments.router)
app.include_router(notifications.router)
app.include_router(schedule.router)
app.include_router(sequence.router)
app.include_router(projects.router)
app.include_router(assistant.router)
app.include_router(calendar.router)
app.include_router(tools.router)
app.include_router(analytics.router)
app.include_router(governance_analytics.router)
app.include_router(governance_baselines.router)
app.include_router(search.router)
app.include_router(audit.router)
app.include_router(labs.router)
app.include_router(resource_shares.router)
app.include_router(marketplace.router)
app.include_router(services.router)
app.include_router(forum.router)
app.include_router(community.router)
app.include_router(compliance.router)
app.include_router(governance.router)
app.include_router(equipment.router)
app.include_router(experiment_console.router)
app.include_router(experiment_console.preview_router)
app.include_router(external.router)
app.include_router(data_analysis.router)
app.include_router(knowledge.router)
app.include_router(workflows.router)


def audit_routes():
    from fastapi.routing import APIRoute
    from .auth import get_current_user

    public_paths = {
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/request-password-reset",
        "/api/auth/reset-password",
        "/metrics",
        "/api/marketplace/listings",
        "/api/services/listings",
        "/api/protocols/public",
    }
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api") and route.path not in public_paths:
            calls = [dep.call for dep in route.dependant.dependencies]
            if get_current_user not in calls:
                raise RuntimeError(f"Route {route.path} missing authentication")


audit_routes()


@app.websocket("/ws/{team_id}")
async def websocket_endpoint(websocket: WebSocket, team_id: str):
    await websocket.accept()
    r = await pubsub.get_redis()
    pub = r.pubsub()
    await pub.subscribe(f"team:{team_id}")
    try:
        async for message in pub.listen():
            if message["type"] == "message":
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode()
                await websocket.send_text(data)
    finally:
        await pub.unsubscribe(f"team:{team_id}")
