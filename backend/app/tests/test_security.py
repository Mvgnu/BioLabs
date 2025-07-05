from app.main import app
from app.auth import get_current_user

PUBLIC_PATHS = {
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/request-password-reset",
    "/api/auth/reset-password",
    "/metrics",
    "/api/marketplace/listings",
    "/api/services/listings",
    "/api/protocols/public",
}


def test_all_routes_protected():
    for route in app.routes:
        path = getattr(route, 'path', '')
        if not path.startswith('/api'):
            continue
        if path in PUBLIC_PATHS:
            continue
        if not hasattr(route, 'dependant'):
            continue
        deps = [d.call for d in route.dependant.dependencies]
        assert get_current_user in deps, f"{path} missing authentication"
