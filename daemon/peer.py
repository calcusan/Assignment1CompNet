"""
daemon.peer
~~~~~~~~~~~~~~~~~

This module provides a P2P peer client for joining the tracker network,
discovering other peers, initiating P2P connections, and running a listening
server to accept incoming peer connections.

Features:
- Registers with centralized tracker on startup
- Periodically discovers active peers
- Facilitates direct connections to other peers
- Runs a listening server to accept incoming P2P connections
- Handles P2P socket communication (send/receive messages)
"""

import socket
import json
import threading
import time


class Peer:
    """
    P2P Peer client for connecting to a peer network via a centralized tracker.
    
    Attributes:
        peer_id (str): Unique identifier for this peer
        peer_ip (str): IP address of this peer
        peer_port (int): Port number this peer listens on
        tracker_ip (str): IP of the centralized tracker
        tracker_port (int): Port of the centralized tracker
        known_peers (list): List of currently known active peers
        discovery_thread (threading.Thread): Background discovery thread
        discovery_active (bool): Flag to control discovery thread
        discovery_interval (int): Seconds between discovery updates
        server_thread (threading.Thread): Background P2P server thread  
        server_active (bool): Flag to control server thread
    """
    
    def __init__(self, peer_ip, peer_port, tracker_ip, tracker_port,
                 discovery_interval=10):
        """
        Initialize a P2P peer.
        
        :param peer_ip: IP address of this peer
        :param peer_port: Port this peer listens on
        :param tracker_ip: IP of the centralized tracker
        :param tracker_port: Port of the centralized tracker
        :param discovery_interval: How often to query tracker for peers
        """
        self.peer_ip = peer_ip
        self.peer_port = peer_port
        self.peer_id = "{}:{}".format(peer_ip, peer_port)
        
        self.tracker_ip = tracker_ip
        self.tracker_port = tracker_port
        
        self.known_peers = []
        self.known_peers_lock = threading.Lock()
        
        self.discovery_thread = None
        self.discovery_active = False
        self.discovery_interval = discovery_interval
        
        self.keepalive_thread = None
        self.keepalive_active = False
        self.keepalive_interval = 15  # Send keepalive every 15 seconds
        
        self.server_thread = None
        self.server_active = False
        self.server_socket = None
        
        print("[Peer {}] Initialized".format(self.peer_id))
    
    def _send_to_tracker(self, method, path, body=None):
        """
        Send an HTTP request to the tracker.
        
        :param method: HTTP method (GET, POST, etc.)
        :param path: Request path (e.g., '/register')
        :param body: Optional JSON body as dict
        :return: Response dict or None on error
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((self.tracker_ip, self.tracker_port))
            
            # Build HTTP request
            body_str = json.dumps(body) if body else ""
            request  = "{} {} HTTP/1.1\r\n".format(method, path)
            request += "Host: {}:{}\r\n".format(self.tracker_ip, self.tracker_port)
            request += "Content-Type: application/json\r\n"
            request += "Content-Length: {}\r\n".format(len(body_str))
            request += "Connection: close\r\n"
            request += "\r\n"
            request += body_str

            sock.sendall(request.encode())

            # Read response using Content-Length to avoid blocking forever
            raw = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                raw += chunk
                if b"\r\n\r\n" in raw:
                    header_part, _, body_so_far = raw.partition(b"\r\n\r\n")
                    content_length = None
                    for line in header_part.split(b"\r\n"):
                        if line.lower().startswith(b"content-length:"):
                            try:
                                content_length = int(line.split(b":", 1)[1].strip())
                            except ValueError:
                                pass
                            break
                    if content_length is not None and len(body_so_far) >= content_length:
                        break

            sock.close()

            # Parse JSON body from response
            response_str = raw.decode('utf-8', errors='ignore')
            parts = response_str.split('\r\n\r\n', 1)
            body_text = parts[1].strip() if len(parts) > 1 else ""
            
            # Try to extract JSON from the body, handling potential extra data
            try:
                # Find the JSON object (starts with { and ends with })
                start_idx = body_text.find('{')
                end_idx = body_text.rfind('}')
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    json_text = body_text[start_idx:end_idx + 1]
                    return json.loads(json_text)
                else:
                    return json.loads(body_text) if body_text else {}
            except json.JSONDecodeError:
                # If JSON parsing fails, return None to indicate error
                print("[Peer {}] Failed to parse response body: {}".format(self.peer_id, body_text[:100]))
                return None

        except Exception as e:
            print("[Peer {}] Error communicating with tracker: {}".format(
                self.peer_id, e))
            return None
    
    def register(self):
        """
        Register this peer with the centralized tracker.
        
        :return: True if registration successful, False otherwise
        """
        print("[Peer {}] Registering with tracker {}:{}".format(
            self.peer_id, self.tracker_ip, self.tracker_port))
        
        response = self._send_to_tracker('POST', '/register', {
            'ip': self.peer_ip,
            'port': self.peer_port
        })
        
        if response and response.get('status') == 'registered':
            print("[Peer {}] Successfully registered".format(self.peer_id))
            return True
        else:
            print("[Peer {}] Registration failed".format(self.peer_id))
            return False
    
    def discover_peers(self):
        """
        Query the tracker for currently active peers.
        
        :return: List of active peers or None on error
        """
        response = self._send_to_tracker('GET', '/discover')
        
        if not response or response.get('status') != 'ok':
            print("[Peer {}] Discovery query failed".format(self.peer_id))
            return None
        
        peers = response.get('peers', [])
        
        # Update known peers
        with self.known_peers_lock:
            self.known_peers = peers

        # Notify external listener (e.g. p2papp.active_peers)
        if hasattr(self, '_on_peers_updated') and self._on_peers_updated:
            try:
                self._on_peers_updated(peers)
            except Exception as e:
                print("[Peer {}] Callback error: {}".format(self.peer_id, e))

        print("[Peer {}] Discovered {} active peers".format(
            self.peer_id, len(peers)))
        
        return peers
    
    def get_known_peers(self):
        """
        Get list of currently known active peers.
        
        :return: List of peer dictionaries
        """
        with self.known_peers_lock:
            return self.known_peers.copy()
    
    def connect_to_peer(self, target_peer_id):
        """
        Initiate a direct connection to another peer.
        
        :param target_peer_id: Peer ID to connect to (e.g., "127.0.0.1:9002")
        :return: Socket if connection successful, None otherwise
        """
        # Get connection info from tracker
        response = self._send_to_tracker('POST', '/connect', {
            'source_peer_id': self.peer_id,
            'target_peer_id': target_peer_id
        })
        
        if not response or response.get('status') != 'ready':
            print("[Peer {}] Connection request failed".format(self.peer_id))
            return None
        
        target = response.get('target', {})
        target_ip = target.get('ip')
        target_port = target.get('port')
        
        if not target_ip or not target_port:
            print("[Peer {}] Invalid target information".format(self.peer_id))
            return None
        
        # Attempt direct connection
        try:
            print("[Peer {}] Connecting to {} at {}:{}".format(
                self.peer_id, target_peer_id, target_ip, target_port))
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((target_ip, target_port))
            
            print("[Peer {}] Connected to {}".format(self.peer_id, target_peer_id))
            return sock
            
        except Exception as e:
            print("[Peer {}] Failed to connect to {}: {}".format(
                self.peer_id, target_peer_id, e))
            return None
    
    def start_discovery(self, on_peers_updated=None):
        """
        Start the background peer discovery thread.
        Periodically queries tracker for active peers.

        :param on_peers_updated: Optional callback(peers) called whenever the
            peer list is refreshed. Use this to sync external state (e.g. the
            p2papp active_peers list).
        """
        if self.discovery_active:
            print("[Peer {}] Discovery already running".format(self.peer_id))
            return

        self._on_peers_updated = on_peers_updated
        self.discovery_active = True
        self.discovery_thread = threading.Thread(
            target=self._discovery_worker,
            daemon=True
        )
        self.discovery_thread.start()
        print("[Peer {}] Discovery thread started (interval: {}s)".format(
            self.peer_id, self.discovery_interval))
    
    def stop_discovery(self):
        """Stop the background discovery thread."""
        self.discovery_active = False
        if self.discovery_thread:
            self.discovery_thread.join(timeout=2)
        print("[Peer {}] Discovery thread stopped".format(self.peer_id))
    
    def start_keepalive(self):
        """
        Start the background keepalive thread to maintain registration.
        """
        if self.keepalive_active:
            print("[Peer {}] Keepalive already running".format(self.peer_id))
            return
        
        self.keepalive_active = True
        self.keepalive_thread = threading.Thread(
            target=self._keepalive_worker,
            daemon=True
        )
        self.keepalive_thread.start()
        print("[Peer {}] Keepalive thread started (interval: {}s)".format(
            self.peer_id, self.keepalive_interval))
    
    def stop_keepalive(self):
        """Stop the keepalive background thread."""
        self.keepalive_active = False
        if self.keepalive_thread:
            self.keepalive_thread.join(timeout=2)
        print("[Peer {}] Keepalive thread stopped".format(self.peer_id))
    
    def start_server(self):
        """
        Start the P2P listening server in background thread.
        Accepts incoming connections from other peers.
        """
        if self.server_active:
            print("[Peer {}] Server already running".format(self.peer_id))
            return
        
        self.server_active = True
        self.server_thread = threading.Thread(
            target=self._server_worker,
            daemon=True
        )
        self.server_thread.start()
        print("[Peer {}] P2P server started on port {}".format(
            self.peer_id, self.peer_port))
    
    def stop_server(self):
        """Stop the P2P listening server."""
        self.server_active = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        if self.server_thread:
            self.server_thread.join(timeout=2)
        print("[Peer {}] P2P server stopped".format(self.peer_id))
    
    def _server_worker(self):
        """Background worker thread that accepts incoming peer connections."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.peer_ip, self.peer_port))
            self.server_socket.listen(5)
            
            print("[Peer {}] Listening for incoming connections on port {}".format(
                self.peer_id, self.peer_port))
            
            while self.server_active:
                try:
                    self.server_socket.settimeout(1.0)  # Timeout so we can check active flag
                    client_sock, client_addr = self.server_socket.accept()
                    
                    # Handle incoming connection in separate thread
                    handler_thread = threading.Thread(
                        target=self._handle_incoming_connection,
                        args=(client_sock, client_addr),
                        daemon=True
                    )
                    handler_thread.start()
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.server_active:
                        print("[Peer {}] Server error: {}".format(self.peer_id, e))
                        
        except Exception as e:
            print("[Peer {}] Failed to start server: {}".format(self.peer_id, e))
        finally:
            if self.server_socket:
                try:
                    self.server_socket.close()
                except:
                    pass
    
    def _handle_incoming_connection(self, client_sock, client_addr):
        """Handle an incoming connection from another peer."""
        try:
            print("[Peer {}] Incoming connection from {}".format(
                self.peer_id, client_addr))
            
            # Receive message
            data = b""
            while True:
                chunk = client_sock.recv(1024)
                if not chunk:
                    break
                data += chunk
            
            if data:
                message = json.loads(data.decode('utf-8'))
                print("[Peer {}] Received from {}: {}".format(
                    self.peer_id, client_addr, message))
                
                # Send response
                response = {
                    "status": "received",
                    "from_peer": self.peer_id,
                    "message_echo": message.get('msg', 'no message')
                }
                client_sock.sendall(json.dumps(response).encode() + b'\n')
                print("[Peer {}] Sent response to {}".format(
                    self.peer_id, client_addr))
                    
        except Exception as e:
            print("[Peer {}] Error handling connection: {}".format(
                self.peer_id, e))
        finally:
            client_sock.close()
    
    def _discovery_worker(self):
        """Background worker thread that periodically discovers peers."""
        while self.discovery_active:
            try:
                time.sleep(self.discovery_interval)
                peers = self.discover_peers()
                # Only update if discovery succeeded
                if peers is not None:
                    pass  # discover_peers already calls the callback
            except Exception as e:
                print("[Peer {}] Discovery worker error: {}".format(
                    self.peer_id, e))
    
    def _keepalive_worker(self):
        """Background worker thread that periodically sends keepalive to tracker."""
        while self.keepalive_active:
            try:
                time.sleep(self.keepalive_interval)
                self._send_keepalive()
            except Exception as e:
                print("[Peer {}] Keepalive worker error: {}".format(
                    self.peer_id, e))
    
    def _send_keepalive(self):
        """Send a keepalive message to the tracker to refresh our registration."""
        response = self._send_to_tracker('POST', '/register', {
            'ip': self.peer_ip,
            'port': self.peer_port
        })
        
        if response and response.get('status') == 'registered':
            print("[Peer {}] Keepalive sent successfully".format(self.peer_id))
        else:
            print("[Peer {}] Keepalive failed".format(self.peer_id))
    
    def send_message_to_peer(self, sock, message):
        """
        Send a message to a connected peer.
        
        :param sock: Connected socket to peer
        :param message: Message dict to send (will be JSON encoded)
        :return: True if successful, False otherwise
        """
        try:
            message_json = json.dumps(message)
            sock.sendall(message_json.encode() + b'\n')
            print("[Peer {}] Sent message: {}".format(self.peer_id, message_json))
            return True
        except Exception as e:
            print("[Peer {}] Error sending message: {}".format(self.peer_id, e))
            return False
    
    def receive_message_from_peer(self, sock):
        """
        Receive a message from a connected peer.
        
        :param sock: Connected socket to peer
        :return: Message dict or None on error
        """
        try:
            data = sock.recv(1024).decode('utf-8')
            if not data:
                return None
            message = json.loads(data.strip())
            print("[Peer {}] Received message: {}".format(self.peer_id, message))
            return message
        except Exception as e:
            print("[Peer {}] Error receiving message: {}".format(self.peer_id, e))
            return None
    
    def print_status(self):
        """Print current peer status."""
        peers = self.get_known_peers()
        print("\n[Peer {}] === Status ===".format(self.peer_id))
        print("[Peer {}] ID: {}".format(self.peer_id, self.peer_id))
        print("[Peer {}] Known peers: {}".format(self.peer_id, len(peers)))
        for peer in peers:
            if peer['peer_id'] != self.peer_id:  # Don't list self
                print("[Peer {}]   - {} ({}:{})".format(
                    self.peer_id, peer['peer_id'], peer['ip'], peer['port']))
        print("[Peer {}] ==============\n".format(self.peer_id))