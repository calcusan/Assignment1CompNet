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
daemon.request
~~~~~~~~~~~~~~~~~

This module provides a Request object to manage and persist
request settings (cookies, auth, proxies).

Merged from:
- repo3 (phutranphu1109-del): full auth parsing (RFC 2617 Basic), cookie parsing, CaseInsensitiveDict headers
- repo1 (dangthai011205): request line normalisation
"""

from .dictionary import CaseInsensitiveDict


class Request():
    """The fully mutable :class:`Request <Request>` object,
    containing the parsed HTTP request received from the client.

    Usage::

      >>> req = Request()
      >>> req.prepare(raw_http_string, routes)
      >>> req.method   # 'GET', 'POST', etc.
      >>> req.path     # '/index.html'
    """

    __attrs__ = [
        "method",
        "url",
        "headers",
        "body",
        "_raw_headers",
        "_raw_body",
        "reason",
        "cookies",
        "routes",
        "hook",
        "auth",
    ]

    def __init__(self):
        #: HTTP verb (GET, POST, PUT, DELETE, ...)
        self.method = None
        #: Full request URL/path
        self.url = None
        #: Path portion of the URL
        self.path = None
        #: HTTP version string
        self.version = None
        #: Parsed headers dict (case-insensitive)
        self.headers = CaseInsensitiveDict()
        #: Parsed cookies dict
        self.cookies = {}
        #: Request body string
        self.body = ""
        #: Raw header section
        self._raw_headers = ""
        #: Raw body section
        self._raw_body = ""
        #: Route mapping
        self.routes = {}
        #: Matched route handler function (or None)
        self.hook = None
        #: Auth tuple (username, password) if Basic auth present
        self.auth = None

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def extract_request_line(self, request):
        """Parse the first line of the HTTP request.

        :param request (str): Raw HTTP request string.
        :rtype: tuple (method, path, version) or (None, None, None) on error.
        """
        try:
            lines = request.splitlines()
            first_line = lines[0]
            parts = first_line.split()
            if len(parts) < 3:
                return None, None, None
            method, path, version = parts[0], parts[1], parts[2]
            if path == '/':
                path = '/index.html'
        except Exception:
            return None, None, None
        return method, path, version

    def prepare_headers(self, raw_header_section):
        """Parse HTTP headers from the raw header section.

        :param raw_header_section (str): The header block (lines after the request line).
        :rtype: CaseInsensitiveDict
        """
        headers = CaseInsensitiveDict()
        lines = raw_header_section.split('\r\n')
        for line in lines[1:]:   # skip request line
            if ': ' in line:
                key, val = line.split(': ', 1)
                headers[key] = val
        return headers

    def fetch_headers_body(self, request):
        """Split the raw request into header section and body section.

        :param request (str): Raw HTTP request string.
        :rtype: tuple (_headers_str, _body_str)
        """
        parts = request.split("\r\n\r\n", 1)
        _headers = parts[0]
        _body = parts[1] if len(parts) > 1 else ""
        return _headers, _body

    # ------------------------------------------------------------------
    # Cookie parsing (RFC 6265)
    # ------------------------------------------------------------------

    def parse_cookies(self, cookie_header):
        """Parse a Cookie header string into a dict.

        :param cookie_header (str): Value of the Cookie header.
        :rtype: dict
        """
        cookies = {}
        if not cookie_header:
            return cookies
        for pair in cookie_header.split(';'):
            pair = pair.strip()
            if '=' in pair:
                key, value = pair.split('=', 1)
                cookies[key.strip()] = value.strip()
        return cookies

    # ------------------------------------------------------------------
    # Auth parsing (RFC 2617 / RFC 7235 Basic auth)
    # ------------------------------------------------------------------

    def prepare_auth(self, auth_header, url=""):
        """Parse the Authorization header and store credentials.

        Supports Basic authentication per RFC 2617.

        :param auth_header (str): Value of the Authorization header.
        :param url (str): Optional URL (unused currently).
        """
        if not auth_header:
            return
        try:
            import base64
            scheme, encoded = auth_header.strip().split(" ", 1)
            if scheme.lower() == "basic":
                decoded = base64.b64decode(encoded).decode("utf-8")
                username, password = decoded.split(":", 1)
                self.auth = (username, password)
        except Exception as e:
            print("[Request] prepare_auth error: {}".format(e))
            self.auth = None

    # ------------------------------------------------------------------
    # Body helpers
    # ------------------------------------------------------------------

    def prepare_body(self, data, files=None, json=None):
        """Store the request body.

        :param data: Body data (str or bytes).
        :param files: (unused) file attachments.
        :param json: (unused) JSON payload.
        """
        if isinstance(data, bytes):
            self.body = data.decode('utf-8', errors='replace')
        else:
            self.body = data or ""
        self.prepare_content_length(self.body)

    def prepare_content_length(self, body):
        """Set the Content-Length header based on body length.

        :param body (str): The request body.
        """
        self.headers["Content-Length"] = str(len(body.encode('utf-8')) if body else 0)

    def prepare_cookies(self, cookies):
        """Attach a Cookie header value.

        :param cookies (str): Raw Cookie header value.
        """
        self.headers["Cookie"] = cookies

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def prepare(self, request, routes=None):
        """Parse the complete HTTP request.

        :param request (str): Raw HTTP request string received from the socket.
        :param routes (dict): Route mapping {(METHOD, path): handler_func}.
        """
        if not request:
            return

        print("[Request] prepare raw message len={}".format(len(request)))

        # Split headers and body
        self._raw_headers, self._raw_body = self.fetch_headers_body(request)

        # Parse request line
        self.method, self.path, self.version = self.extract_request_line(request)
        print("[Request] {} path={} version={}".format(self.method, self.path, self.version))

        # Parse headers
        self.headers = self.prepare_headers(self._raw_headers)

        # Parse body
        self.body = self._raw_body

        # Parse cookies from Cookie header (RFC 6265)
        cookie_header = self.headers.get('cookie', '')
        self.cookies = self.parse_cookies(cookie_header)

        # Parse auth from Authorization header (RFC 2617)
        auth_header = self.headers.get('authorization', '')
        self.prepare_auth(auth_header)

        # Route lookup
        if routes:
            self.routes = routes
            key = (self.method, self.path)
            self.hook = routes.get(key)
            if self.hook:
                print("[Request] Matched route {} -> {}".format(key, self.hook))
            else:
                print("[Request] No route for {}".format(key))

        return
