import time
import uuid
import hmac
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.logger import logger
from app.config import settings

class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        # In-memory rate limiting state
        self.rate_limits = {}

    def _apply_response_headers(self, response: Response, request_id: str) -> Response:
        response.headers["X-Request-ID"] = request_id
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    def _json_error(self, status_code: int, content: dict, request_id: str) -> JSONResponse:
        return self._apply_response_headers(
            JSONResponse(status_code=status_code, content=content),
            request_id,
        )
        
    async def dispatch(self, request: Request, call_next) -> Response:
        # 1. Request ID & Structured Logging
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        client_ip = request.client.host if request.client else "unknown"
        
        logger.info(f"[Req={request_id}] Incoming {request.method} {request.url.path} from {client_ip}")

        # 2. Request Size Limit (1MB)
        content_length = request.headers.get("content-length")
        try:
            payload_size = int(content_length) if content_length else 0
        except ValueError:
            return self._json_error(400, {"error": "Invalid Content-Length"}, request_id)
        if payload_size > settings.request_body_limit_bytes:
            logger.warning(f"[Req={request_id}] Payload too large: {content_length} bytes")
            return self._json_error(413, {"error": "Payload too large"}, request_id)

        rate_limit_exceeded = False

        # API authentication is mandatory in production and optional for local development.
        if request.url.path.startswith("/api/"):
            api_key = request.headers.get("x-api-key")
            if settings.is_production:
                if not settings.api_key:
                    logger.error("Production API key is not configured")
                    return self._json_error(503, {"error": "Service misconfigured"}, request_id)
                if not api_key or not hmac.compare_digest(api_key, settings.api_key):
                    return self._json_error(401, {"error": "Unauthorized"}, request_id)
            
            # Redis Rate Limiting with In-memory Fallback
            try:
                import redis.asyncio as redis
                if not hasattr(self, "redis_pool"):
                    self.redis_pool = redis.from_url(
                        settings.redis_url, 
                        decode_responses=True,
                        socket_connect_timeout=0.1,
                        socket_timeout=0.1
                    )
                
                # Simple token bucket in Redis via Lua script.
                lua_script = """
                local key = KEYS[1]
                local rate = tonumber(ARGV[1])
                local capacity = tonumber(ARGV[2])
                local ttl = tonumber(ARGV[4])
                local now = tonumber(ARGV[3])
                local requested = 1
                
                local last_tokens = tonumber(redis.call("hget", key, "tokens"))
                if last_tokens == nil then
                    last_tokens = capacity
                end
                
                local last_refreshed = tonumber(redis.call("hget", key, "timestamp"))
                if last_refreshed == nil then
                    last_refreshed = 0
                end
                
                local delta = math.max(0, now - last_refreshed)
                local filled_tokens = math.min(capacity, last_tokens + (delta * rate))
                if filled_tokens >= requested then
                    local new_tokens = filled_tokens - requested
                    redis.call("hset", key, "tokens", new_tokens)
                    redis.call("hset", key, "timestamp", now)
                    redis.call("expire", key, ttl)
                    return 1
                end
                return 0
                """
                now = time.time()
                script = self.redis_pool.register_script(lua_script)
                allowed = await script(
                    keys=[f"rate_limit:{client_ip}"],
                    args=[
                        settings.rate_limit_refill_per_second,
                        settings.rate_limit_capacity,
                        now,
                        settings.rate_limit_ttl_seconds,
                    ],
                )
                if not allowed:
                    rate_limit_exceeded = True
            except Exception as e:
                logger.warning(f"[Req={request_id}] Redis rate limiting failed, falling back to in-memory: {e}")
                # In-memory fallback
                now = time.time()
                capacity = settings.rate_limit_capacity
                refill = settings.rate_limit_refill_per_second
                limit_state = self.rate_limits.get(client_ip, {"tokens": capacity, "last_updated": now})
                elapsed = now - limit_state["last_updated"]
                limit_state["tokens"] = min(capacity, limit_state["tokens"] + elapsed * refill)
                limit_state["last_updated"] = now
                
                if limit_state["tokens"] < 1.0:
                    rate_limit_exceeded = True
                else:
                    limit_state["tokens"] -= 1.0
                    self.rate_limits[client_ip] = limit_state
                
                if len(self.rate_limits) > 10_000:
                    cutoff = now - settings.rate_limit_ttl_seconds
                    self.rate_limits = {
                        ip: state for ip, state in self.rate_limits.items()
                        if state["last_updated"] >= cutoff
                    }

        if rate_limit_exceeded:
            logger.warning(f"[Req={request_id}] Rate limit exceeded for IP: {client_ip}")
            return self._json_error(429, {"error": "Too many requests"}, request_id)

        try:
            t0 = time.time()
            response = await call_next(request)
            duration = time.time() - t0
            self._apply_response_headers(response, request_id)
            logger.info(f"[Req={request_id}] Completed {response.status_code} in {duration:.3f}s")
            return response
            
        except Exception as e:
            logger.exception(f"[Req={request_id}] Unhandled server error")
            return self._json_error(
                500,
                {
                    "error": "Internal Server Error",
                    "request_id": request_id,
                    "code": "ERR_INTERNAL",
                },
                request_id,
            )
