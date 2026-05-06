# AsynapRous – Merged Project
## CO3094 Assignment 1 – Non-Blocking HTTP Server & Chat Application


## Project Structure

```
.
├── daemon/
│   ├── asynaprous.py     # Decorator-based RESTful router
│   ├── backend.py        # Backend server (threading / callback / coroutine)
│   ├── proxy.py          # Reverse proxy with load balancing + ChannelPool
│   ├── channel.py        # Channel & ChannelPool (connection reuse)
│   ├── httpadapter.py    # HTTP lifecycle + auth (Basic + Cookie sessions)
│   ├── request.py        # HTTP request parser (RFC 2617 auth, RFC 6265 cookies)
│   ├── response.py       # HTTP response builder (401, 200+Set-Cookie, etc.)
│   ├── peer.py           # P2P peer client (register, discover, connect)
│   ├── tracker.py        # Centralized PeerRegistry (keepalive, timeout)
│   ├── dictionary.py     # CaseInsensitiveDict
│   └── utils.py          # Auth helpers (encode/decode Basic, session token)
├── apps/
│   ├── sampleapp.py      # Sample AsynapRous app (/login, /echo, /hello)
│   ├── trackerapp.py     # Tracker REST API (/register, /discover, /connect)
│   └── p2papp.py         # P2P chat app (/send-peer, /broadcast-peer, /local-send)
├── config/
│   └── proxy.conf        # Virtual-host routing rules
├── www/                  # Static HTML pages
├── static/               # CSS, images
├── start_proxy.py        # Launch proxy server
├── start_backend.py      # Launch backend server
├── start_tracker.py      # Launch tracker (centralized peer registry)
├── start_sampleapp.py    # Launch sample AsynapRous webapp
└── start_p2p.py          # Launch a P2P chat peer
```

---

## Running the System

### 1. Start the Tracker (centralized server)
```bash
python start_tracker.py --server-ip 0.0.0.0 --server-port 9000
```

### 2. Start the Proxy
```bash
python start_proxy.py --server-ip 0.0.0.0 --server-port 8080
```

### 3. Start the Backend
```bash
python start_backend.py --server-ip 0.0.0.0 --server-port 9001
```

### 4. Start the Sample AsynapRous App
```bash
python start_sampleapp.py --server-ip 0.0.0.0 --server-port 2026
```

### 5. Start a P2P Peer
```bash
# Peer A
python start_p2p.py --server-ip 0.0.0.0 --server-port 9101 \
                    --tracker-ip 127.0.0.1 --tracker-port 9000

# Peer B
python start_p2p.py --server-ip 0.0.0.0 --server-port 9102 \
                    --tracker-ip 127.0.0.1 --tracker-port 9000
```

---

## Non-Blocking Modes

Set the `ASYNC_MODE` environment variable before starting the backend:

```bash
ASYNC_MODE=threading  python start_backend.py   # default: one thread per connection
ASYNC_MODE=callback   python start_backend.py   # selectors event-driven
ASYNC_MODE=coroutine  python start_backend.py   # asyncio async/await
```

---

## Authentication

- **Basic Auth** (RFC 2617/7235): send `Authorization: Basic <base64(user:pass)>` header
- **Cookie Session** (RFC 6265): POST `/login` with `{"username": "admin", "password": "admin123"}`
  to receive a `Set-Cookie: session_token=...` header

Default users: `admin/admin123`, `user1/password1`, `user2/password2`

---

## P2P Chat API

| Method | Endpoint | Description |
|---|---|---|
| POST | `/register` | Register peer with tracker |
| GET  | `/discover` | Get active peer list from tracker |
| POST | `/connect` | Get connection info for a target peer |
| POST | `/send-peer` | Receive a direct message |
| POST | `/broadcast-peer` | Receive a broadcast message |
| POST | `/local-send` | Send a message from local UI to peers |
