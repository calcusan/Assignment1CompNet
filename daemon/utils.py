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

import base64
from urllib.parse import urlparse, unquote


def get_auth_from_url(url):
    """Given a url with authentication components, extract them into a tuple of
    username, password.

    :rtype: (str, str)
    """
    parsed = urlparse(url)
    try:
        auth = (unquote(parsed.username or ""), unquote(parsed.password or ""))
    except (AttributeError, TypeError):
        auth = ("", "")
    return auth


def encode_basic_auth(username, password):
    """Encode username:password as a Base64 Basic auth string.

    :param username (str): The username.
    :param password (str): The password.
    :rtype: str  -- the encoded credentials string.
    """
    credentials = "{}:{}".format(username, password)
    encoded = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
    return "Basic {}".format(encoded)


def decode_basic_auth(auth_header):
    """Decode a Basic auth header value into (username, password).

    :param auth_header (str): Value of the Authorization header.
    :rtype: (str, str) or (None, None) if decoding fails.
    """
    try:
        scheme, encoded = auth_header.strip().split(" ", 1)
        if scheme.lower() != "basic":
            return None, None
        decoded = base64.b64decode(encoded).decode("utf-8")
        username, password = decoded.split(":", 1)
        return username, password
    except Exception:
        return None, None


def generate_session_token(username):
    """Generate a simple session token for a user.

    :param username (str): The logged-in username.
    :rtype: str
    """
    import hashlib, time
    raw = "{}:{}".format(username, time.time())
    return hashlib.sha256(raw.encode()).hexdigest()