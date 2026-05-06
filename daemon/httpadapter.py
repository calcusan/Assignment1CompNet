#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# AsynapRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#

"""
daemon.httpadapter
~~~~~~~~~~~~~~~~~

This module provides an HttpAdapter object to manage client connections,
parse HTTP requests, invoke route handlers, and send HTTP responses.
It supports both synchronous (blocking/threaded) and asynchronous (coroutine)
operation modes, with full HTTP Basic authentication and cookie-based
session management.

Merged from:
- repo3 (phutranphu1109-del): RFC 2617/7235 Basic auth, RFC 6265 cookie sessions,
  build_unauthorized, build_set_cookie_response
- repo5 (Cminh11): cleaner async coroutine handler with writer.wait_closed()
"""

import json
import inspect
import asyncio

from .request import Request
from .response import Response
from .dictionary import CaseInsensitiveDict

# In-memory session store: token -> username
_SESSION_STORE = {}

# Simple user database (username -> password)
# In production this should be replaced with a proper database / hashed passwords
_USER_DB = {
    "admin": "admin123",
    "user1": "password1",
    "user2": "password2",
}


class HttpAdapter:
    """A mutable :class:`HttpAdapter <HttpAdapter>` for managing client connections
    and routing requests.

    The HttpAdapter class encapsulates the logic for receiving HTTP requests,
    dispatching them to appropriate route handlers, building responses, and
    implementing HTTP Basic authentication and cookie-based session management.

    Attributes:
        ip (str): IP address of the server.
        port (int): Port number of the server.
        conn (socket): Active socket connection.
        connaddr (tuple): Address of the connected client.
        routes (dict): Mapping of (METHOD, path) to handler functions.
        request (Request): Request object for parsing incoming data.
        response (Response): Response object for building and sending replies.
    """

    __attrs__ = ["ip", "port", "conn", "connaddr", "routes", "request", "response"]

    def __init__(self, ip, port, conn, connaddr, routes):
        """Initialize a new HttpAdapter instance.

        :param ip (str): IP address of the server.
        :param port (int): Port number of the server.
        :param conn (socket): Active socket connection.
        :param connaddr (tuple): Address of the connected client.
        :param routes (dict): Mapping of route paths to handler functions.
        """
        self.ip = ip
        self.port = port
        self.conn = conn
        self.connaddr = connaddr
        self.routes = routes or {}
        self.request = Request()
        self.response = Response()

    # ------------------------------------------------------------------
    # Authentication helpers (RFC 2617 / RFC 7235 / RFC 6265)
    # ------------------------------------------------------------------

    def _authenticate_basic(self, req):
        """Validate Basic authentication credentials from the request.

        Implements RFC 2617 / RFC 7235 Basic authentication.

        :param req (Request): The parsed request.
        :rtype: str or None -- the authenticated username, or None if failed.
        """
        auth_header = req.headers.get('authorization', '')
        if not auth_header:
            return None
        username, password = req.auth if req.auth else (None, None)
        if not username:
            return None
        expected = _USER_DB.get(username)
        if expected and expected == password:
            print("[HttpAdapter] Basic auth OK for user: {}".format(username))
            return username
        print("[HttpAdapter] Basic auth FAILED for user: {}".format(username))
        return None

    def _authenticate_cookie(self, req):
        """Validate session token from Cookie header.

        Implements RFC 6265 cookie-based session management.

        :param req (Request): The parsed request.
        :rtype: str or None -- the authenticated username, or None if failed.
        """
        token = req.cookies.get('session_token')
        if token and token in _SESSION_STORE:
            username = _SESSION_STORE[token]
            print("[HttpAdapter] Cookie auth OK for user: {}".format(username))
            return username
        return None

    def _create_session(self, username):
        """Create a new session token for a user.

        :param username (str): Authenticated username.
        :rtype: str -- the generated session token.
        """
        from .utils import generate_session_token
        token = generate_session_token(username)
        _SESSION_STORE[token] = username
        print("[HttpAdapter] Created session token for user: {}".format(username))
        return token

    def _is_authenticated(self, req):
        """Check if the request is authenticated via Basic auth or cookie session.

        :param req (Request): The parsed request.
        :rtype: (bool, str or None) -- (is_auth, username)
        """
        # Try cookie first (RFC 6265)
        username = self._authenticate_cookie(req)
        if username:
            return True, username
        # Try Basic auth (RFC 2617)
        username = self._authenticate_basic(req)
        if username:
            return True, username
        return False, None

    # ------------------------------------------------------------------
    # Response construction helpers
    # ------------------------------------------------------------------

    def _is_public(self, req):
        """Return True if the path requires no authentication.

        API routes (those with a registered hook) and P2P endpoints are always
        public so the chat app and peer-to-peer messaging work without login.
        Static assets and the login page are also public.

        :param req (Request): Parsed request.
        :rtype bool
        """
        # Registered route hooks (AsynapRous apps) are always public
        if req.hook:
            return True
        # Explicit public HTML pages
        public_pages = ['/index.html', '/login.html', '/form.html', '/favicon.ico', '/chat.html']
        if req.path in public_pages:
            return True
        # Static asset directories
        public_prefixes = ['/css/', '/images/', '/static/']
        if any(req.path.startswith(p) for p in public_prefixes):
            return True
        return False

    def _build_hook_response(self, req, resp, hook_result):
        """Wrap the handler return value into a proper HTTP response bytes.

        :param req (Request): Parsed request.
        :param resp (Response): Response object.
        :param hook_result: The return value from the route handler.
        :rtype bytes: Encoded HTTP response.
        """
        if hook_result is None:
            hook_result = b""
        
        # If the result is already a complete HTTP response (starts with HTTP/), return it as-is
        if isinstance(hook_result, bytes) and hook_result.startswith(b'HTTP/'):
            return hook_result
        
        if isinstance(hook_result, dict):
            hook_result = json.dumps(hook_result).encode('utf-8')
        elif isinstance(hook_result, str):
            hook_result = hook_result.encode('utf-8')
        return resp.build_json_ok(hook_result)

    # ------------------------------------------------------------------
    # Main client handler (synchronous / threaded)
    # ------------------------------------------------------------------

    def handle_client(self, conn, addr, routes):
        """Handle an incoming client connection synchronously.

        Reads the request, authenticates if needed, dispatches to the
        appropriate route handler, builds and sends the response.

        :param conn (socket): The client socket connection.
        :param addr (tuple): The client's address.
        :param routes (dict): The route mapping for dispatching requests.
        """
        self.conn = conn
        self.connaddr = addr
        req = self.request
        resp = self.response

        try:
            # Receive full request (headers + body)
            raw = b""
            conn.settimeout(5.0)
            while True:
                try:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    raw += chunk
                    if b"\r\n\r\n" in raw:
                        header_part, body_part = raw.split(b"\r\n\r\n", 1)
                        content_length = 0
                        for line in header_part.decode('utf-8', errors='replace').split('\r\n'):
                            if line.lower().startswith('content-length:'):
                                content_length = int(line.split(':', 1)[1].strip())
                                break
                        if len(body_part) >= content_length:
                            break
                except Exception:
                    break

            msg = raw.decode('utf-8', errors='replace')
            if not msg.strip():
                conn.close()
                return

            req.prepare(msg, routes)
            print("[HttpAdapter] handle_client from {} {} {}".format(addr, req.method, req.path))

            if req.hook:
                print("[HttpAdapter] Invoking hook for {} {}".format(req.method, req.path))
                # Special handling for /login: validate credentials + set cookie
                if req.path == '/login' and req.method in ('POST', 'PUT'):
                    response = self._handle_login(req, resp)
                else:
                    response = self._invoke_hook(req, resp)
            else:
                # Static file serving with auth protection
                if self._is_public(req):
                    response = resp.build_response(req)
                else:
                    authenticated, username = self._is_authenticated(req)
                    if not authenticated:
                        response = resp.build_unauthorized()
                    else:
                        response = resp.build_response(req)

        except Exception as e:
            print("[HttpAdapter] handle_client exception: {}".format(e))
            response = resp.build_notfound()

        try:
            conn.sendall(response)
        except Exception as e:
            print("[HttpAdapter] sendall error: {}".format(e))
        finally:
            conn.close()

    def _handle_login(self, req, resp):
        """Handle a login request: verify credentials and return a session cookie.

        Supports JSON body credentials and HTTP Basic auth header.

        :param req (Request): Parsed request.
        :param resp (Response): Response object.
        :rtype bytes: HTTP response with Set-Cookie on success, or 401 on failure.
        """
        import json as _json
        username, password = None, None

        # Try JSON body first
        try:
            body_json = _json.loads(req.body)
            username = body_json.get('username') or body_json.get('user')
            password = body_json.get('password') or body_json.get('pass')
        except Exception:
            pass

        # Fall back to Basic auth header
        if not username and req.auth:
            username, password = req.auth

        # Also invoke the registered hook for additional processing
        if req.hook:
            try:
                if inspect.iscoroutinefunction(req.hook):
                    loop = asyncio.new_event_loop()
                    loop.run_until_complete(req.hook(headers=dict(req.headers), body=req.body))
                    loop.close()
                else:
                    req.hook(headers=dict(req.headers), body=req.body)
            except Exception as e:
                print("[HttpAdapter] login hook error: {}".format(e))

        # Validate credentials against user database
        if username and _USER_DB.get(username) == password:
            token = self._create_session(username)
            body_data = _json.dumps({
                "message": "Login successful",
                "username": username
            }).encode('utf-8')
            return resp.build_set_cookie_response(body_data, {"session_token": token})
        else:
            return resp.build_unauthorized()

    def _invoke_hook(self, req, resp):
        """Invoke the matched route handler and return the HTTP response bytes.

        Handles both sync and async handlers.

        :param req (Request): Parsed request.
        :param resp (Response): Response object.
        :rtype bytes: HTTP response.
        """
        try:
            if inspect.iscoroutinefunction(req.hook):
                loop = asyncio.new_event_loop()
                result = loop.run_until_complete(
                    req.hook(headers=dict(req.headers), body=req.body))
                loop.close()
            else:
                result = req.hook(headers=dict(req.headers), body=req.body)
            return self._build_hook_response(req, resp, result)
        except Exception as e:
            print("[HttpAdapter] hook invocation error: {}".format(e))
            error_body = json.dumps({"error": str(e)}).encode('utf-8')
            return resp.build_json_ok(error_body)

    # ------------------------------------------------------------------
    # Async coroutine client handler (repo5 improved version)
    # ------------------------------------------------------------------

    async def handle_client_coroutine(self, reader, writer):
        """Handle an incoming client connection asynchronously (coroutine mode).

        :param reader (asyncio.StreamReader): Async stream reader.
        :param writer (asyncio.StreamWriter): Async stream writer.
        """
        addr = writer.get_extra_info("peername")
        req = Request()
        resp = Response()

        try:
            raw = await reader.read(65536)
            msg = raw.decode('utf-8', errors='replace')
            if not msg.strip():
                writer.close()
                await writer.wait_closed()
                return

            req.prepare(msg, self.routes)
            print("[HttpAdapter] async handle_client from {} {} {}".format(
                addr, req.method, req.path))

            if req.hook:
                if req.path == '/login' and req.method in ('POST', 'PUT'):
                    response = self._handle_login(req, resp)
                else:
                    if inspect.iscoroutinefunction(req.hook):
                        result = await req.hook(headers=dict(req.headers), body=req.body)
                    else:
                        result = req.hook(headers=dict(req.headers), body=req.body)
                    response = self._build_hook_response(req, resp, result)
            else:
                # Static file serving with auth protection (mirrors sync handler)
                if self._is_public(req):
                    response = resp.build_response(req)
                else:
                    authenticated, username = self._is_authenticated(req)
                    if not authenticated:
                        response = resp.build_unauthorized()
                    else:
                        response = resp.build_response(req)

        except Exception as e:
            print("[HttpAdapter] async exception: {}".format(e))
            response = resp.build_notfound()

        try:
            writer.write(response)
            await writer.drain()
        except Exception as e:
            print("[HttpAdapter] async write error: {}".format(e))
        finally:
            writer.close()
            await writer.wait_closed()

    # ------------------------------------------------------------------
    # Header / proxy helpers
    # ------------------------------------------------------------------

    @property
    def extract_cookies(self):
        """Extract cookies from the current request headers.

        :rtype dict: Cookie key-value pairs.
        """
        return self.request.cookies if self.request else {}

    def add_headers(self, request):
        """Add headers to the request. Override in subclasses for custom headers.

        :param request (Request): Request to add headers to.
        """
        pass

    def build_proxy_headers(self, proxy):
        """Return a dictionary of headers to add to requests forwarded via proxy.

        :param proxy (str): The proxy URL being used.
        :rtype dict: Headers to add.
        """
        headers = {}
        username = "proxy_user"
        password = "proxy_pass"
        if username:
            import base64
            credentials = base64.b64encode(
                "{}:{}".format(username, password).encode()).decode()
            headers["Proxy-Authorization"] = "Basic {}".format(credentials)
        return headers

    def build_response(self, req, resp):
        """Build a Response object from a raw response.

        :param req (Request): The originating request.
        :param resp: The raw response data.
        :rtype Response: Populated response object.
        """
        response = Response(req)
        response.raw = resp
        if isinstance(req.url, bytes):
            response.url = req.url.decode("utf-8")
        else:
            response.url = req.url
        response.request = req
        response.connection = self
        return response

    def build_json_response(self, req, resp):
        """Build a Response object from JSON data.

        :param req (Request): The originating request.
        :param resp: The raw JSON response data.
        :rtype Response: Populated response object.
        """
        response = Response(req)
        response.raw = resp
        if isinstance(req.url, bytes):
            response.url = req.url.decode("utf-8")
        else:
            response.url = req.url
        response.request = req
        response.connection = self
        return response