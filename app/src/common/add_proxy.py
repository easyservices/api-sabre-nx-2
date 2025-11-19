from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from src import logger

class CustomProxyHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        x_forwarded_for = request.headers.get("x-forwarded-for")
        x_forwarded_proto = request.headers.get("x-forwarded-proto")

        if x_forwarded_for:
            # Met à jour le client avec la première IP dans la liste
            request.scope["client"] = (x_forwarded_for.split(",")[0].strip(), 0)
        if x_forwarded_proto:
            # Met à jour le scheme http/https
            request.scope["scheme"] = x_forwarded_proto

        response = await call_next(request)
        return response
