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
apps.p2papp
~~~~~~~~~~~~~~~~~

P2P Chat application built on the AsynapRous framework.

This module implements the peer-side chat handler. Each peer runs this app
as a small HTTP server. Other peers (or the local UI) send HTTP requests to
these endpoints to exchange messages.

Roles:
  - /send-peer     : receive a direct message from another peer
  - /broadcast-peer: receive a broadcast message from the network
  - /local-send    : triggered by the local UI / client to push a message
                     out to other peers (direct or broadcast)

Non-blocking send uses asyncio.open_connection() and asyncio.gather() so
that outgoing messages to multiple peers do not block each other.

Merged from:
- repo4 (2005nglong-source): P2P send/broadcast/receive logic
"""

import json
import asyncio
import socket

from daemon.asynaprous import AsynapRous

app = AsynapRous()

# List of currently active peers populated at runtime.
# Format: [{"ip": "x.x.x.x", "port": 9001}, ...]
# Updated externally (e.g. by calling discover_peers() on the Peer object).
active_peers = []

# This peer's own IP – filled in when create_p2p_app() is called
_my_ip = "127.0.0.1"
_my_port = 9000

# Incoming message buffer: the UI polls /get-messages to fetch these.
# Each entry: {"channel": "broadcast"|"ip:port", "sender": str, "text": str}
_message_buffer = []
_message_buffer_lock = __import__('threading').Lock()


# =========================================================
# 1. RECEIVING SIDE (this peer acts as server)
# =========================================================

@app.route('/send-peer', methods=['POST'])
def receive_direct_message(headers, body):
    """Handle a direct message sent from another peer.

    Expected JSON body::

        {"sender_ip": "x.x.x.x", "message": "hello"}

    :param headers: Request headers dict.
    :param body: Raw request body string.
    :rtype bytes: JSON confirmation.
    """
    try:
        data = json.loads(body)
        sender = data.get("sender_ip", "Unknown")
        msg = data.get("message", "")
        print("[P2PApp] Direct message from {}: {}".format(sender, msg))
        channel = sender  # direct messages keyed by sender ip:port
        with _message_buffer_lock:
            _message_buffer.append({"channel": channel, "sender": sender, "text": msg})
        return json.dumps({"status": "success", "info": "Message received"}).encode('utf-8')
    except Exception as e:
        return json.dumps({"status": "error", "info": str(e)}).encode('utf-8')


@app.route('/broadcast-peer', methods=['POST'])
def receive_broadcast_message(headers, body):
    """Handle a broadcast message from the peer network.

    Expected JSON body::

        {"sender_ip": "x.x.x.x", "message": "hello everyone"}

    :param headers: Request headers dict.
    :param body: Raw request body string.
    :rtype bytes: JSON confirmation.
    """
    try:
        data = json.loads(body)
        sender = data.get("sender_ip", "Unknown")
        msg = data.get("message", "")
        print("[P2PApp] Broadcast from {}: {}".format(sender, msg))
        with _message_buffer_lock:
            _message_buffer.append({"channel": "broadcast", "sender": sender, "text": msg})
        return json.dumps({"status": "success"}).encode('utf-8')
    except Exception as e:
        return json.dumps({"status": "error", "info": str(e)}).encode('utf-8')


# =========================================================
# 2. SENDING SIDE (this peer acts as client, non-blocking)
# =========================================================

async def send_p2p_message(target_ip, target_port, message, endpoint="/send-peer"):
    """Open a non-blocking async connection to a peer and send a message.

    Uses asyncio.open_connection() for non-blocking I/O. The HTTP request
    is formatted as a POST with a JSON body.

    :param target_ip (str): IP of the target peer.
    :param target_port (int): Port of the target peer.
    :param message (str): Message text to send.
    :param endpoint (str): AsynapRous route on the target peer.
    """
    try:
        reader, writer = await asyncio.open_connection(target_ip, target_port)

        payload = json.dumps({"sender_ip": _my_ip, "message": message})
        http_request = (
            "POST {} HTTP/1.1\r\n"
            "Host: {}:{}\r\n"
            "Content-Type: application/json\r\n"
            "Content-Length: {}\r\n"
            "Connection: close\r\n"
            "\r\n"
            "{}"
        ).format(endpoint, target_ip, target_port, len(payload), payload)

        writer.write(http_request.encode('utf-8'))
        await writer.drain()

        # Read acknowledgement (optional)
        response = await reader.read(1024)
        print("[P2PApp] ACK from {}:{} -> {}".format(
            target_ip, target_port, response[:100]))

        writer.close()
        await writer.wait_closed()

    except Exception as e:
        print("[P2PApp] Error sending to {}:{} - {}".format(target_ip, target_port, e))


async def broadcast_message(message):
    """Send a message to all currently known peers in parallel.

    Uses asyncio.gather() so all outgoing connections are initiated
    concurrently without blocking each other.

    :param message (str): Message to broadcast.
    """
    tasks = [
        send_p2p_message(peer["ip"], peer["port"], message, endpoint="/broadcast-peer")
        for peer in active_peers
    ]
    if tasks:
        await asyncio.gather(*tasks)
        print("[P2PApp] Broadcast sent to {} peer(s)".format(len(tasks)))


# =========================================================
# 3. LOCAL TRIGGER (called by the UI / client JS)
# =========================================================

@app.route('/local-send', methods=['POST'])
def trigger_send_from_ui(headers, body):
    """UI calls this endpoint to instruct the backend to send a message.

    Expected JSON body::

        {
            "message": "hello",
            "type": "broadcast"         // or "direct"
            "target_ip": "x.x.x.x",    // required for direct
            "target_port": 9002         // required for direct
        }

    :param headers: Request headers dict.
    :param body: Raw request body string.
    :rtype bytes: JSON status.
    """
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return json.dumps({"status": "error", "info": "Invalid JSON"}).encode('utf-8')

    msg = data.get("message", "")
    chat_type = data.get("type", "broadcast")

    try:
        loop = asyncio.new_event_loop()
        if chat_type == 'broadcast':
            loop.run_until_complete(broadcast_message(msg))
        else:
            target_ip = data.get("target_ip")
            target_port = int(data.get("target_port", 9000))
            loop.run_until_complete(send_p2p_message(target_ip, target_port, msg))
    finally:
        loop.close()

    return json.dumps({"status": "sent"}).encode('utf-8')


@app.route('/get-peers', methods=['GET'])
def get_peers(headers, body):
    """Return the current list of active peers so the chat UI can populate channels.

    :rtype bytes: JSON list of peers.
    """
    return json.dumps({"status": "ok", "peers": active_peers}).encode('utf-8')


@app.route('/get-messages', methods=['GET'])
def get_messages(headers, body):
    """Return and clear the incoming message buffer for the UI to poll.

    :rtype bytes: JSON list of buffered messages.
    """
    with _message_buffer_lock:
        msgs = list(_message_buffer)
        _message_buffer.clear()
    return json.dumps({"status": "ok", "messages": msgs}).encode('utf-8')


# =========================================================
# 4. STATIC FILE SERVING (HTML/CSS/JS for UI)
# =========================================================

def _build_html_response(content_bytes):
    """Build a complete HTTP response with HTML content-type.
    
    :param content_bytes: Raw file bytes
    :rtype bytes: Complete HTTP response (headers + body)
    """
    return (
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: text/html; charset=utf-8\r\n"
        "Content-Length: {}\r\n"
        "Cache-Control: no-cache\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).format(len(content_bytes)).encode('utf-8') + content_bytes


@app.route('/', methods=['GET'])
def serve_chat_root(headers, body):
    """Serve chat.html at the root path.

    :rtype bytes: Complete HTTP response with HTML content.
    """
    try:
        with open('www/chat.html', 'rb') as f:
            return _build_html_response(f.read())
    except FileNotFoundError:
        error_body = b'<html><body><h1>404 Not Found</h1><p>chat.html not found</p></body></html>'
        return (
            "HTTP/1.1 404 Not Found\r\n"
            "Content-Type: text/html\r\n"
            "Content-Length: {}\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).format(len(error_body)).encode('utf-8') + error_body


@app.route('/chat.html', methods=['GET'])
def serve_chat_html(headers, body):
    """Serve chat.html explicitly.

    :rtype bytes: Complete HTTP response with HTML content.
    """
    try:
        with open('www/chat.html', 'rb') as f:
            return _build_html_response(f.read())
    except FileNotFoundError:
        error_body = b'<html><body><h1>404 Not Found</h1><p>chat.html not found</p></body></html>'
        return (
            "HTTP/1.1 404 Not Found\r\n"
            "Content-Type: text/html\r\n"
            "Content-Length: {}\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).format(len(error_body)).encode('utf-8') + error_body


def create_p2p_app(ip, port, peers=None):
    """Initialise and launch the P2P chat app.

    :param ip (str): IP address to bind this peer's server.
    :param port (int): Port to listen on.
    :param peers (list): Optional initial list of known peers.
    """
    global _my_ip, _my_port, active_peers
    _my_ip = ip
    _my_port = port
    if peers:
        active_peers = peers
    app.prepare_address(ip, port)
    app.run()