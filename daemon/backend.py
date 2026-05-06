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
daemon.backend
~~~~~~~~~~~~~~~~~

This module provides a backend object to manage and persist backend daemon.
It implements a basic backend server using Python's socket and threading libraries.
It supports handling multiple client connections concurrently and routing requests using a
custom HTTP adapter.

Non-blocking mode is selected via the ASYNC_MODE environment variable or
the module-level mode_async variable:
  - "threading"  : default; one daemon thread per connection
  - "callback"   : event-driven via selectors.DefaultSelector (non-blocking)
  - "coroutine"  : asyncio async/await via asyncio.start_server

Merged from:
- repo5 (Cminh11): ASYNC_MODE env var, clean selector callback, proper coroutine teardown
- repo1 (dangthai011205): multi-threading default
"""

import socket
import threading
import os
import asyncio
import inspect
import selectors

from .response import Response
from .httpadapter import HttpAdapter
from .dictionary import CaseInsensitiveDict

sel = selectors.DefaultSelector()

mode_async = "threading"
VALID_ASYNC_MODES = {"threading", "callback", "coroutine"}


def handle_client(ip, port, conn, addr, routes):
    """Initializes an HttpAdapter instance and delegates the client handling logic to it.

    :param ip (str): IP address of the server.
    :param port (int): Port number the server is listening on.
    :param conn (socket.socket): Client connection socket.
    :param addr (tuple): client address (IP, port).
    :param routes (dict): Dictionary of route handlers.
    """
    print("[Backend] Invoke handle_client accepted connection from {}".format(addr))
    daemon = HttpAdapter(ip, port, conn, addr, routes)
    daemon.handle_client(conn, addr, routes)


def handle_client_callback(server, ip, port, routes):
    """Event-driven callback: accept one connection and handle it.

    Called by the selector event loop when the server socket is readable.

    :param server (socket.socket): The listening server socket.
    :param ip (str): IP address of the server.
    :param port (int): Port number the server is listening on.
    :param routes (dict): Dictionary of route handlers.
    """
    try:
        conn, addr = server.accept()
    except BlockingIOError:
        return

    print("[Backend] Invoke handle_client_callback accepted connection from {}".format(addr))
    daemon = HttpAdapter(ip, port, conn, addr, routes)
    daemon.handle_client(conn, addr, routes)


async def handle_client_coroutine(reader, writer):
    """Coroutine: initialize HttpAdapter and delegate async handling.

    :param reader (asyncio.StreamReader): Stream reader wrapper.
    :param writer (asyncio.StreamWriter): Stream writer wrapper.
    """
    addr = writer.get_extra_info("peername")
    print("[Backend] Invoke handle_client_coroutine accepted connection from {}".format(addr))

    daemon = HttpAdapter(None, None, None, addr, {})
    await daemon.handle_client_coroutine(reader, writer)
    writer.close()
    await writer.wait_closed()


async def async_server(ip="0.0.0.0", port=7000, routes={}):
    """Run the asyncio-based server.

    :param ip (str): IP address to bind.
    :param port (int): Port to listen on.
    :param routes (dict): Route handler mapping.
    """
    print("[Backend] async_server **ASYNC** listening on port {}".format(port))
    if routes:
        print("[Backend] route settings")
        for key, value in routes.items():
            isCoFunc = "**ASYNC** " if inspect.iscoroutinefunction(value) else ""
            print("   + ('{}', '{}'): {}{}".format(key[0], key[1], isCoFunc, str(value)))

    async def connection_handler(reader, writer):
        addr = writer.get_extra_info("peername")
        print("[Backend] Coroutine connection from {}".format(addr))
        daemon = HttpAdapter(ip, port, None, addr, routes)
        await daemon.handle_client_coroutine(reader, writer)
        writer.close()
        await writer.wait_closed()

    srv = await asyncio.start_server(connection_handler, ip, port)
    async with srv:
        await srv.serve_forever()


def run_backend(ip, port, routes):
    """Start the backend server.

    Reads ASYNC_MODE environment variable to select the concurrency mode:
      - "threading"  (default): spawns a daemon thread per connection
      - "callback"   : selector-based event loop
      - "coroutine"  : asyncio

    :param ip (str): IP address to bind the server.
    :param port (int): Port number to listen on.
    :param routes (dict): Dictionary of route handlers.
    """
    global mode_async

    mode_async = os.getenv("ASYNC_MODE", mode_async).strip().lower()
    if mode_async not in VALID_ASYNC_MODES:
        print("[Backend] Invalid ASYNC_MODE='{}', fallback to 'threading'".format(mode_async))
        mode_async = "threading"

    print("[Backend] run_backend mode={} routes={}".format(mode_async, list(routes.keys()) if routes else []))

    if mode_async == "coroutine":
        asyncio.run(async_server(ip, port, routes))
        return

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server.bind((ip, port))
        server.listen(50)
        print("[Backend] Listening on port {}".format(port))

        if routes:
            print("[Backend] route settings")
            for key, value in routes.items():
                isCoFunc = "**ASYNC** " if inspect.iscoroutinefunction(value) else ""
                print("   + ('{}', '{}'): {}{}".format(key[0], key[1], isCoFunc, str(value)))

        if mode_async == "callback":
            server.setblocking(False)
            sel.register(
                server,
                selectors.EVENT_READ,
                (handle_client_callback, ip, port, routes),
            )

        while True:
            if mode_async == "callback":
                events = sel.select(timeout=None)
                for key, _ in events:
                    callback, event_ip, event_port, event_routes = key.data
                    callback(key.fileobj, event_ip, event_port, event_routes)
            else:
                # Default: multi-threading
                conn, addr = server.accept()
                client_thread = threading.Thread(
                    target=handle_client,
                    args=(ip, port, conn, addr, routes),
                    daemon=True,
                )
                client_thread.start()

    except KeyboardInterrupt:
        print("[Backend] Shutdown requested")
    except socket.error as e:
        print("[Backend] Socket error: {}".format(e))
    finally:
        try:
            if mode_async == "callback":
                sel.unregister(server)
        except Exception:
            pass
        server.close()
        print("[Backend] Server socket closed")


def create_backend(ip, port, routes={}):
    """Entry point for creating and running the backend server.

    :param ip (str): IP address to bind the server.
    :param port (int): Port number to listen on.
    :param routes (dict, optional): Dictionary of route handlers. Defaults to empty dict.
    """
    run_backend(ip, port, routes)
