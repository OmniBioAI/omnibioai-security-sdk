import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class ServiceAuthMiddleware(BaseHTTPMiddleware):

    def __init__(self, app, secret: str, service_name: str):
        super().__init__(app)
        self.secret = secret
        self.service_name = service_name

    async def dispatch(self, request, call_next):

        token = request.headers.get("X-Service-Token")

        if not token:
            return JSONResponse({"error": "missing service token"}, 401)

        try:
            # verify_aud=False: audience is checked manually below so PyJWT
            # doesn't reject tokens before we can return the correct 403 status.
            payload = jwt.decode(
                token, self.secret, algorithms=["HS256"],
                options={"verify_aud": False},
            )
        except Exception:
            return JSONResponse({"error": "invalid service token"}, 401)

        if self.service_name not in payload.get("aud", []):
            return JSONResponse({"error": "service not allowed"}, 403)

        request.state.service = payload["service"]

        return await call_next(request)