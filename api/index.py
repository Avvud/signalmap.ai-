"""
ASGI Path-Preserving Shim for Vercel Serverless Deployment.

Why this exists:
Vercel's modern serverless rewrites (e.g. '/api/:path*' -> '/api/index?__p=/api/:path*')
replace the path received by the serverless function with '/api/index', passing the original
route in the '__p' query parameter. Without this shim, FastAPI receives scope['path'] = '/api/index'
for every request, matching no route and returning 404 Not Found.

This ASGI callable intercepts incoming HTTP scopes, extracts the original path from the '__p'
query parameter, restores scope['path'] and scope['raw_path'] (ensuring a leading '/'),
strips '__p' from scope['query_string'], and forwards the modified scope to FastAPI (fastapi_app).
"""

import urllib.parse
from backend.main import app as fastapi_app


async def app(scope, receive, send):
    if scope.get("type") == "http":
        raw_query = scope.get("query_string", b"").decode("utf-8", errors="replace")
        parsed_params = urllib.parse.parse_qsl(raw_query, keep_blank_values=True)

        original_path = None
        remaining_params = []

        for key, val in parsed_params:
            if key == "__p" and original_path is None:
                original_path = val
            else:
                remaining_params.append((key, val))

        if original_path is not None:
            if not original_path.startswith("/"):
                original_path = "/" + original_path

            new_scope = dict(scope)
            new_scope["path"] = original_path
            new_scope["raw_path"] = original_path.encode("utf-8")
            new_scope["query_string"] = urllib.parse.urlencode(remaining_params).encode("utf-8")
            await fastapi_app(new_scope, receive, send)
            return

    await fastapi_app(scope, receive, send)
