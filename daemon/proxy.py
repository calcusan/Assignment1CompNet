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
daemon.proxy
~~~~~~~~~~~~~~~~~

This module implements a simple proxy server using Python's socket and threading libraries.
It routes incoming HTTP requests to backend services based on hostname mappings and returns
the corresponding responses to clients.

Requirement:
-----------------
- socket: provides socket networking interface.
- threading: enables concurrent client handling via threads.
- response: customized :class: `Response <Response>` utilities.
- httpadapter: :class: `HttpAdapter <HttpAdapter >` adapter for HTTP request processing.
- dictionary: :class: `CaseInsensitiveDict <CaseInsensitiveDict>` for managing headers and cookies.

"""
import socket
import threading
from .response import *
from .httpadapter import HttpAdapter
from .dictionary import CaseInsensitiveDict
from .channel import get_channel_pool

#: A dictionary mapping hostnames to backend IP and port tuples.
#: Used to determine routing targets for incoming requests.
PROXY_PASS = {
    "192.168.56.103:8080": ('192.168.56.103', 9000),
    "app1.local": ('192.168.56.103', 9001),
    "app2.local": ('192.168.56.103', 9002),
}


def forward_request(host, port, request, channel_pool=None):
    """
    Forwards an HTTP request to a backend server and retrieves the response.
    Uses connection pooling for improved performance and resource utilization.

    :params host (str): IP address of the backend server.
    :params port (int): port number of the backend server.
    :params request (str): incoming HTTP request.
    :params channel_pool (ChannelPool): Optional channel pool for connection reuse.

    :rtype bytes: Raw HTTP response from the backend server. If the connection
                  fails, returns a 404 Not Found response.
    """

    if channel_pool is None:
        channel_pool = get_channel_pool()
    
    # Get a channel from the pool (reuse or create)
    channel = channel_pool.get_channel(host, port)
    
    if not channel:
        print("[Proxy] Failed to get channel to {}:{}".format(host, port))
        return (
            "HTTP/1.1 503 Service Unavailable\r\n"
            "Content-Type: text/plain\r\n"
            "Content-Length: 19\r\n"
            "Connection: close\r\n"
            "\r\n"
            "503 Service Unavailable"
        ).encode('utf-8')
    
    print("[Proxy] Got channel to {}:{}, is_connected = {}".format(host, port, channel.is_connected))
    
    try:
        response = channel.send_request(request)
        if response is None:
            response = (
                "HTTP/1.1 502 Bad Gateway\r\n"
                "Content-Type: text/plain\r\n"
                "Content-Length: 13\r\n"
                "Connection: close\r\n"
                "\r\n"
                "502 Bad Gateway"
            ).encode('utf-8')
        return response
    except Exception as e:
        print("[Proxy] Error forwarding request: {}".format(e))
        return (
            "HTTP/1.1 502 Bad Gateway\r\n"
            "Content-Type: text/plain\r\n"
            "Content-Length: 13\r\n"
            "Connection: close\r\n"
            "\r\n"
            "502 Bad Gateway"
        ).encode('utf-8')
    finally:
        # Release the channel back to the pool
        if channel:
            channel_pool.release_channel(channel)


# Load balancing counter for round-robin
_lb_counter = {}
_lb_lock = threading.Lock()

def apply_load_balancing(proxy_list, hostname, policy='round-robin'):
    """
    Apply load balancing policy to select a backend from multiple options.
    
    Supports:
    - round-robin: Distributes requests evenly across backends
    - least-connections: Selects backend with few active connections
    - random: Random selection (default fallback)
    
    :params proxy_list (list): List of 'host:port' backend servers.
    :params hostname (str): Hostname for tracking round-robin state.
    :params policy (str): Load balancing policy to apply.
    :rtype: str - Selected 'host:port' backend.
    """
    if not proxy_list or len(proxy_list) == 0:
        return None
    
    if len(proxy_list) == 1:
        return proxy_list[0]
    
    if policy == 'round-robin':
        with _lb_lock:
            if hostname not in _lb_counter:
                _lb_counter[hostname] = 0
            index = _lb_counter[hostname] % len(proxy_list)
            _lb_counter[hostname] += 1
            selected = proxy_list[index]
            print("[Proxy] Round-robin: Selected {} from {} (index {})".format(
                selected, len(proxy_list), index))
            return selected
    elif policy == 'random':
        import random
        selected = random.choice(proxy_list)
        print("[Proxy] Random: Selected {} from {}".format(selected, len(proxy_list)))
        return selected
    else:
        # Default to round-robin
        return apply_load_balancing(proxy_list, hostname, 'round-robin')

def resolve_routing_policy(hostname, routes):
    """
    Handles a routing policy to return the matching proxy_pass and any proxy headers.
    It determines the target backend to forward the request to, supporting multiple
    backends with load balancing.

    :params hostname (str): The hostname to resolve.
    :params routes (dict): Dictionary mapping hostnames to route metadata.
    :rtype: tuple - (proxy_host, proxy_port, proxy_headers).
    """

    normalized_hostname = hostname.strip().lower()
    print("[Proxy] Resolving hostname: {}".format(normalized_hostname))

    route = routes.get(normalized_hostname)
    if route is None:
        # Try fallback without port if exact match is not found
        hostname_no_port = normalized_hostname.split(':', 1)[0]
        route = routes.get(hostname_no_port)
        if route is not None:
            print("[Proxy] Fallback matched hostname without port: {}".format(hostname_no_port))

    if route is None:
        print("[Proxy] No route found for hostname {}".format(normalized_hostname))
        return '127.0.0.1', '9000', {}

    proxy_map = route.get('proxy_pass', ['127.0.0.1:9000'])
    policy = route.get('dist_policy', 'round-robin')
    proxy_headers = route.get('proxy_set_header', {}) or {}
    print("[Proxy] Policy: {}, Proxy map: {}".format(policy, proxy_map))

    # Handle proxy_map as a list of backends
    if isinstance(proxy_map, list):
        if len(proxy_map) == 0:
            print("[Proxy] Empty resolved routing of hostname {}".format(hostname))
            return '127.0.0.1', '9000', proxy_headers
        
        # Apply load balancing to select one backend
        selected_proxy = apply_load_balancing(proxy_map, hostname, policy)
        if selected_proxy:
            try:
                proxy_host, proxy_port = selected_proxy.split(":", 1)
                return proxy_host, proxy_port, proxy_headers
            except ValueError:
                print("[Proxy] Invalid proxy format: {}".format(selected_proxy))
                return '127.0.0.1', '9000', proxy_headers
    else:
        # proxy_map is a single string 'host:port'
        print("[Proxy] Single backend for hostname: {}".format(hostname))
        try:
            proxy_host, proxy_port = proxy_map.split(":", 1)
            return proxy_host, proxy_port, proxy_headers
        except ValueError:
            print("[Proxy] Invalid proxy format: {}".format(proxy_map))
            return '127.0.0.1', '9000', proxy_headers
    
    return None, None, proxy_headers

def _apply_proxy_set_headers(request, headers, original_hostname, backend_host):
    """
    Apply proxy_set_header overrides to the raw HTTP request.

    :param request (str): Original HTTP request string.
    :param headers (dict): Header name -> header value mappings.
    :param original_hostname (str): The original Host header value.
    :param backend_host (str): The backend host:port.
    :rtype: str: Modified request string.
    """
    if not headers:
        return request

    lines = request.split('\r\n')
    header_lines = []
    body_lines = []
    found_blank = False
    for line in lines:
        if not found_blank and line == '':
            found_blank = True
            body_lines.append(line)
            continue
        if found_blank:
            body_lines.append(line)
        else:
            header_lines.append(line)

    normalized_headers = {h.split(':', 1)[0].strip().lower(): i for i, h in enumerate(header_lines) if ':' in h}
    for name, value in headers.items():
        rewritten_value = value.replace('$host', backend_host)
        header_name = name.strip()
        normalized_name = header_name.lower()
        new_line = f"{header_name}: {rewritten_value}"
        if normalized_name in normalized_headers:
            header_lines[normalized_headers[normalized_name]] = new_line
        else:
            # Insert before blank line separator
            header_lines.append(new_line)

    return '\r\n'.join(header_lines + body_lines)


def handle_client(ip, port, conn, addr, routes, channel_pool=None):
    """
    Handles an individual client connection by parsing the request,
    determining the target backend, and forwarding the request.

    The handler extracts the Host header from the request to
    match the hostname against known routes. If a match is found,
    it forwards the request to the appropriate backend using
    the channel pool for connection reuse.

    The handler sends the backend response back to the client or
    returns 404 if the hostname is unreachable or is not recognized.

    :params ip (str): IP address of the proxy server.
    :params port (int): Port number of the proxy server.
    :params conn (socket.socket): Client connection socket.
    :params addr (tuple): Client address (IP, port).
    :params routes (dict): Dictionary mapping hostnames to location tuples (proxy_list, policy).
    :params channel_pool (ChannelPool): Optional channel pool for backend connections.
    """

    if channel_pool is None:
        channel_pool = get_channel_pool()
    
    print("[Proxy] Handling client from {}".format(addr))
    
    try:
        request = conn.recv(4096).decode(errors='ignore')
        print("[Proxy] Received request: {}".format(request.replace('\r\n', '\\r\\n')[:200]))
        
        if not request:
            print("[Proxy] Empty request from {}".format(addr))
            return

        # Extract hostname from Host header
        hostname = None
        for line in request.splitlines():
            if line.lower().startswith('host:'):
                hostname = line.split(':', 1)[1].strip()
                break
        if hostname:
            hostname = hostname.lower()
        
        if not hostname:
            print("[Proxy] No Host header found in request from {}".format(addr))
            response = (
                "HTTP/1.1 400 Bad Request\r\n"
                "Content-Type: text/plain\r\n"
                "Content-Length: 11\r\n"
                "Connection: close\r\n"
                "\r\n"
                "Bad Request"
            ).encode('utf-8')
            conn.sendall(response)
            return

        print("[Proxy] {} connecting to Host: {}".format(addr, hostname))

        # Resolve the matching destination in routes
        resolved_host, resolved_port, proxy_headers = resolve_routing_policy(hostname, routes)
        
        if not resolved_host:
            print("[Proxy] Could not resolve host: {}".format(hostname))
            response = (
                "HTTP/1.1 404 Not Found\r\n"
                "Content-Type: text/plain\r\n"
                "Content-Length: 13\r\n"
                "Connection: close\r\n"
                "\r\n"
                "404 Not Found"
            ).encode('utf-8')
            conn.sendall(response)
            return
        
        try:
            resolved_port = int(resolved_port)
        except ValueError:
            print("[Proxy] Invalid port number: {}".format(resolved_port))
            response = (
                "HTTP/1.1 500 Internal Server Error\r\n"
                "Content-Type: text/plain\r\n"
                "Content-Length: 21\r\n"
                "Connection: close\r\n"
                "\r\n"
                "Internal Server Error"
            ).encode('utf-8')
            conn.sendall(response)
            return

        if proxy_headers:
            backend_host = "{}:{}".format(resolved_host, resolved_port)
            request = _apply_proxy_set_headers(request, proxy_headers, hostname, backend_host)

        print("[Proxy] Hostname {} forwarded to {}:{}".format(hostname, resolved_host, resolved_port))
        response = forward_request(resolved_host, resolved_port, request, channel_pool)
        conn.sendall(response)
    
    except Exception as e:
        print("[Proxy] Exception handling client {}: {}".format(addr, e))
        try:
            error_response = (
                "HTTP/1.1 500 Internal Server Error\r\n"
                "Content-Type: text/plain\r\n"
                "Content-Length: 21\r\n"
                "Connection: close\r\n"
                "\r\n"
                "Internal Server Error"
            ).encode('utf-8')
            conn.sendall(error_response)
        except:
            pass

def handle_client_threaded(ip, port, conn, addr, routes, channel_pool):
    """
    Handle a client connection in a separate thread.
    This wrapper manages the thread lifecycle for a single client.
    
    :params ip (str): IP address of the proxy server.
    :params port (int): Port number of the proxy server.
    :params conn (socket.socket): Client connection socket.
    :params addr (tuple): Client address (IP, port).
    :params routes (dict): Dictionary mapping hostnames and location.
    :params channel_pool (ChannelPool): Shared channel pool for backend connections.
    """
    try:
        handle_client(ip, port, conn, addr, routes, channel_pool)
    except Exception as e:
        print("[Proxy] Error handling client {}: {}".format(addr, e))
    finally:
        try:
            conn.close()
        except:
            pass

def run_proxy(ip, port, routes):
    """
    Starts the proxy server and listens for incoming connections.
    
    The server binds to the specified IP and port, and for each incoming
    connection, spawns a new thread to handle the client request. Multiple
    clients are handled concurrently using Python threading.
    
    Connection pooling is used to reuse backend connections for improved
    performance and resource utilization.

    :params ip (str): IP address to bind the proxy server.
    :params port (int): Port number to listen on.
    :params routes (dict): Dictionary mapping hostnames and location tuples (proxy_list, policy).
    """

    # Initialize the global channel pool for backend connections
    channel_pool = get_channel_pool(max_pool_size=20, idle_timeout=300)
    
    proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        proxy.bind((ip, port))
        proxy.listen(50)
        print("[Proxy] Listening on IP {} port {}".format(ip, port))
        print("[Proxy] Loaded {} routes".format(len(routes)))
        
        while True:
            try:
                conn, addr = proxy.accept()
                print("[Proxy] Accepted connection from {}".format(addr))
                import sys
                sys.stdout.flush()
                
                # Create a thread to handle this client
                client_thread = threading.Thread(
                    target=handle_client_threaded,
                    args=(ip, port, conn, addr, routes, channel_pool),
                    daemon=True
                )
                client_thread.start()
            except KeyboardInterrupt:
                print("[Proxy] Shutting down at request")
                break
            except Exception as e:
                print("[Proxy] Error accepting connection: {}".format(e))
    except socket.error as e:
        print("[Proxy] Socket error: {}".format(e))
    finally:
        try:
            proxy.close()
            print("[Proxy] Server socket closed")
        except:
            pass
        # Clean up channel pool
        channel_pool.close_all()

def create_proxy(ip, port, routes):
    """
    Entry point for launching the proxy server.

    :params ip (str): IP address to bind the proxy server.
    :params port (int): port number to listen on.
    :params routes (dict): dictionary mapping hostnames and location.
    """

    run_proxy(ip, port, routes)
