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
daemon.response
~~~~~~~~~~~~~~~~~

This module provides a :class:`Response <Response>` object to manage and persist
response settings (cookies, auth, proxies), and to construct HTTP responses
based on incoming requests.

The current version supports MIME type detection, content loading and header formatting.
"""

import datetime
import os
import mimetypes
from .dictionary import CaseInsensitiveDict

BASE_DIR = ""

# HTTP status messages
STATUS_MESSAGES = {
    200: "OK",
    201: "Created",
    204: "No Content",
    301: "Moved Permanently",
    302: "Found",
    304: "Not Modified",
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    500: "Internal Server Error",
}


class Response():
    """The :class:`Response <Response>` object, which contains a
    server's response to an HTTP request.

    :attrs status_code (int): HTTP status code (e.g., 200, 404).
    :attrs headers (dict): Dictionary of response headers.
    :attrs url (str): URL of the response.
    :attrs encoding (str): Encoding used for decoding response content.
    :attrs history (list): List of previous Response objects (for redirects).
    :attrs reason (str): Textual reason for the status code.
    :attrs cookies (CaseInsensitiveDict): Response cookies.
    :attrs elapsed (datetime.timedelta): Time taken to complete the request.
    :attrs request: The original request object.

    Usage::

      >>> resp = Response()
      >>> data = resp.build_response(req)
      >>> conn.sendall(data)
    """

    __attrs__ = [
        "_content",
        "_header",
        "status_code",
        "method",
        "headers",
        "url",
        "history",
        "encoding",
        "reason",
        "cookies",
        "elapsed",
        "request",
        "body",
    ]

    def __init__(self, request=None):
        """Initializes a new :class:`Response <Response>` object.

        :param request: The originating request object.
        """
        self._content = b""
        self._header = b""
        self._content_consumed = False
        self._next = None

        #: HTTP status code
        self.status_code = 200

        #: Response headers dict
        self.headers = {}

        #: URL of the response
        self.url = None

        #: Encoding
        self.encoding = "utf-8"

        #: History of redirects
        self.history = []

        #: Reason phrase
        self.reason = "OK"

        #: Cookies
        self.cookies = CaseInsensitiveDict()

        #: Elapsed time
        self.elapsed = datetime.timedelta(0)

        #: Originating request
        self.request = request

        #: Body bytes
        self.body = b""

    # ------------------------------------------------------------------
    # MIME helpers
    # ------------------------------------------------------------------

    def get_mime_type(self, path):
        """Determine the MIME type of a file based on its path.

        :param path (str): Path to the file.
        :rtype str: MIME type string (e.g., 'text/html', 'image/png').
        """
        try:
            mime_type, _ = mimetypes.guess_type(path)
        except Exception:
            return 'application/octet-stream'
        return mime_type or 'application/octet-stream'

    def prepare_content_type(self, mime_type='text/html'):
        """Prepare the Content-Type header and determine the base directory
        for serving the file based on its MIME type.

        :param mime_type (str): MIME type of the requested resource.
        :rtype str: Base directory path for locating the resource.
        :raises ValueError: If the MIME type is unsupported.
        """
        base_dir = ""

        if not hasattr(self, "headers") or self.headers is None:
            self.headers = {}

        main_type, sub_type = mime_type.split('/', 1)
        print("[Response] Processing main_type={} sub_type={}".format(main_type, sub_type))

        if main_type == 'text':
            self.headers['Content-Type'] = 'text/{}'.format(sub_type)
            if sub_type in ('plain', 'css', 'javascript', 'csv', 'xml'):
                base_dir = BASE_DIR + "static/"
            elif sub_type == 'html':
                base_dir = BASE_DIR + "www/"
            else:
                base_dir = BASE_DIR + "static/"

        elif main_type == 'image':
            base_dir = BASE_DIR + "static/"
            self.headers['Content-Type'] = 'image/{}'.format(sub_type)

        elif main_type == 'application':
            if sub_type in ('json', 'octet-stream'):
                base_dir = BASE_DIR + "apps/"
                self.headers['Content-Type'] = 'application/json'
            elif sub_type in ('xml', 'zip'):
                base_dir = BASE_DIR + "static/"
                self.headers['Content-Type'] = 'application/{}'.format(sub_type)
            else:
                base_dir = BASE_DIR + "static/"
                self.headers['Content-Type'] = 'application/{}'.format(sub_type)

        elif main_type == 'video':
            base_dir = BASE_DIR + "static/"
            self.headers['Content-Type'] = 'video/{}'.format(sub_type)

        elif main_type == 'audio':
            base_dir = BASE_DIR + "static/"
            self.headers['Content-Type'] = 'audio/{}'.format(sub_type)

        else:
            raise ValueError("Unsupported MIME type: main_type={} sub_type={}".format(main_type, sub_type))

        return base_dir

    # ------------------------------------------------------------------
    # Content loading
    # ------------------------------------------------------------------

    def build_content(self, path, base_dir):
        """Load a file from storage and return its length and bytes.

        :param path (str): Relative path to the file.
        :param base_dir (str): Base directory where the file is located.
        :rtype tuple: (int content_length, bytes content_data)
        """
        filepath = os.path.join(base_dir, path.lstrip('/'))
        print("[Response] Serving object at {}".format(filepath))
        try:
            with open(filepath, "rb") as f:
                content = f.read()
        except FileNotFoundError:
            print("[Response] File not found: {}".format(filepath))
            return -1, b""
        except Exception as e:
            print("[Response] build_content exception: {}".format(e))
            return -1, b""
        return len(content), content

    # ------------------------------------------------------------------
    # Header construction
    # ------------------------------------------------------------------

    def build_response_header(self, request):
        """Construct the HTTP response header bytes.

        :param request: Incoming :class:`Request <Request>` object.
        :rtype bytes: Encoded HTTP response header block.
        """
        reqhdr = request.headers if (request and request.headers) else {}
        status_msg = STATUS_MESSAGES.get(self.status_code, "Unknown")
        content_type = self.headers.get('Content-Type', 'text/html')
        content_len = len(self._content)

        header_lines = [
            "HTTP/1.1 {} {}".format(self.status_code, status_msg),
            "Date: {}".format(datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")),
            "Server: AsynapRous/1.0",
            "Content-Type: {}".format(content_type),
            "Content-Length: {}".format(content_len),
            "Cache-Control: no-cache",
            "Connection: close",
        ]

        # Append Set-Cookie headers if any
        for key, value in self.cookies.items():
            header_lines.append("Set-Cookie: {}={}; Path=/; HttpOnly".format(key, value))

        # WWW-Authenticate for 401 responses
        if self.status_code == 401:
            header_lines.append('WWW-Authenticate: Basic realm="AsynapRous"')

        header_text = "\r\n".join(header_lines) + "\r\n\r\n"
        return header_text.encode('utf-8')

    # ------------------------------------------------------------------
    # Error responses
    # ------------------------------------------------------------------

    def build_notfound(self):
        """Construct a standard 404 Not Found HTTP response.

        :rtype bytes: Encoded 404 response.
        """
        body = b"404 Not Found"
        return (
            "HTTP/1.1 404 Not Found\r\n"
            "Content-Type: text/html\r\n"
            "Content-Length: {}\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).format(len(body)).encode('utf-8') + body

    def build_unauthorized(self):
        """Construct a 401 Unauthorized response requesting Basic auth.

        :rtype bytes: Encoded 401 response.
        """
        body = b"401 Unauthorized - Authentication Required"
        return (
            "HTTP/1.1 401 Unauthorized\r\n"
            'WWW-Authenticate: Basic realm="AsynapRous"\r\n'
            "Content-Type: text/plain\r\n"
            "Content-Length: {}\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).format(len(body)).encode('utf-8') + body

    def build_json_ok(self, json_bytes):
        """Construct a 200 OK JSON response.

        :param json_bytes (bytes): JSON-encoded response body.
        :rtype bytes: Encoded HTTP response.
        """
        return (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: application/json\r\n"
            "Content-Length: {}\r\n"
            "Cache-Control: no-cache\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).format(len(json_bytes)).encode('utf-8') + json_bytes

    def build_set_cookie_response(self, body_bytes, cookies):
        """Construct a 200 OK response with Set-Cookie headers.

        :param body_bytes (bytes): Response body.
        :param cookies (dict): Dict of cookie name -> value pairs.
        :rtype bytes: Full encoded HTTP response.
        """
        cookie_lines = ""
        for k, v in cookies.items():
            cookie_lines += "Set-Cookie: {}={}; Path=/; HttpOnly\r\n".format(k, v)

        return (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: application/json\r\n"
            "Content-Length: {}\r\n"
            "{}Cache-Control: no-cache\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).format(len(body_bytes), cookie_lines).encode('utf-8') + body_bytes

    # ------------------------------------------------------------------
    # Main response builder
    # ------------------------------------------------------------------

    def build_response(self, request, envelop_content=None):
        """Build a full HTTP response including headers and content.

        :param request: Incoming :class:`Request <Request>` object.
        :param envelop_content (bytes): Optional pre-built body to send.
        :rtype bytes: Complete HTTP response.
        """
        print("[Response] build_response path={}".format(request.path if request else "None"))

        # If a pre-built body is provided (e.g. from a route handler), wrap it
        if envelop_content is not None:
            if isinstance(envelop_content, str):
                envelop_content = envelop_content.encode('utf-8')
            self._content = envelop_content
            self._header = self.build_response_header(request)
            return self._header + self._content

        path = request.path
        if not path:
            return self.build_notfound()

        mime_type = self.get_mime_type(path)
        print("[Response] {} path={} mime={}".format(request.method, path, mime_type))

        try:
            if path.endswith('.html') or mime_type == 'text/html':
                base_dir = self.prepare_content_type(mime_type='text/html')
            elif mime_type == 'text/css':
                base_dir = self.prepare_content_type(mime_type='text/css')
            elif mime_type and mime_type.startswith('image/'):
                base_dir = self.prepare_content_type(mime_type=mime_type)
            elif mime_type == 'application/javascript' or path.endswith('.js'):
                self.headers['Content-Type'] = 'application/javascript'
                base_dir = BASE_DIR + "static/"
            elif mime_type in ('application/json', 'application/octet-stream'):
                base_dir = self.prepare_content_type(mime_type='application/json')
                if envelop_content is None:
                    envelop_content = b""
            else:
                # Try to serve as static
                base_dir = BASE_DIR + "static/"
                self.headers['Content-Type'] = mime_type or 'application/octet-stream'
        except ValueError:
            return self.build_notfound()

        content_len, content = self.build_content(path, base_dir)
        if content_len < 0:
            return self.build_notfound()

        self._content = content
        self._header = self.build_response_header(request)
        return self._header + self._content