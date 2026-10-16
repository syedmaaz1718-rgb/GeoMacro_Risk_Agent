"""Single admin password gate (ADMIN_PASSWORD). Disabled when the variable is empty.
Session = HMAC-signed expiry in an HttpOnly cookie. POST routes also accept X-Admin-Token."""
import hashlib
import hmac
import time

from fastapi import HTTPException, Request, Response

from .config import env

COOKIE = "gm_session"
TTL = 7 * 24 * 3600
OPEN_PREFIXES = ("/static", "/auth", "/health", "/risk", "/favicon")


def enabled() -> bool:
    return bool(env("ADMIN_PASSWORD"))


def _key() -> bytes:
    return hashlib.sha256(("gm|" + env("ADMIN_PASSWORD") + "|" + env("SESSION_SECRET")).encode()).digest()


def make_token() -> str:
    exp = str(int(time.time()) + TTL)
    return exp + "." + hmac.new(_key(), exp.encode(), hashlib.sha256).hexdigest()


def valid_token(tok: str | None) -> bool:
    try:
        exp, sig = (tok or "").split(".", 1)
        return int(exp) > time.time() and hmac.compare_digest(sig, hmac.new(_key(), exp.encode(), hashlib.sha256).hexdigest())
    except ValueError:
        return False


def check_password(pw: str) -> bool:
    return enabled() and hmac.compare_digest(pw.encode(), env("ADMIN_PASSWORD").encode())


def authed(request: Request) -> bool:
    if not enabled():
        return True
    if valid_token(request.cookies.get(COOKIE)):
        return True
    t = env("ADMIN_TOKEN") or env("ADMIN_PASSWORD")
    return bool(request.headers.get("x-admin-token")) and hmac.compare_digest(request.headers["x-admin-token"], t)


async def gate(request: Request, call_next):
    p = request.url.path
    if p == "/" or p.startswith(OPEN_PREFIXES) or authed(request):
        return await call_next(request)
    from fastapi.responses import JSONResponse
    return JSONResponse({"detail": "login required"}, status_code=401)


_fails: dict = {}


def login(request: Request, response: Response, pw: str):
    ip = request.client.host if request.client else "?"
    n, t0 = _fails.get(ip, (0, time.time()))
    if time.time() - t0 > 600:
        n, t0 = 0, time.time()
    if n >= 8:
        raise HTTPException(429, "too many attempts, try again in a few minutes")
    if not check_password(pw):
        _fails[ip] = (n + 1, t0)
        raise HTTPException(401, "wrong password")
    _fails.pop(ip, None)
    response.set_cookie(COOKIE, make_token(), max_age=TTL, httponly=True, samesite="lax", secure=request.url.scheme == "https")
