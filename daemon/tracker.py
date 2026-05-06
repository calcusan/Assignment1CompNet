"""
daemon.tracker
~~~~~~~~~~~~~~~~~

This module provides a centralized P2P tracker for managing peer registration,
peer discovery, and peer keepalive (heartbeat) functionality.

The PeerRegistry maintains an in-memory list of active peers with thread-safe
operations. It tracks peer IP addresses, ports, and timestamps for timeout management.

Features:
- Thread-safe peer registration
- Peer discovery with active peer list
- Automatic peer timeout/removal
- Background keepalive thread for cleanup
"""

import threading
import time
from datetime import datetime


class PeerRegistry:
    """
    In-memory registry for tracking active P2P peers.
    
    Maintains a dictionary of peers with their connection details and
    last-seen timestamps. Provides thread-safe operations for registering,
    discovering, and removing peers.
    
    Attributes:
        peers (dict): Dictionary mapping peer_id -> {ip, port, timestamp, status}
        lock (threading.Lock): Thread lock for safe concurrent access
        keepalive_thread (threading.Thread): Background thread for peer cleanup
        keepalive_active (bool): Flag to control keepalive thread
        timeout_seconds (int): Seconds before peer is considered inactive
        keepalive_interval (int): Seconds between keepalive checks
    """
    
    def __init__(self, timeout_seconds=30, keepalive_interval=10):
        """
        Initialize the PeerRegistry.
        
        :param timeout_seconds: How long before a peer is considered inactive
        :param keepalive_interval: How often to check for inactive peers
        """
        self.peers = {}
        self.lock = threading.Lock()
        self.timeout_seconds = timeout_seconds
        self.keepalive_interval = keepalive_interval
        self.keepalive_active = False
        self.keepalive_thread = None
        
    def register_peer(self, ip, port):
        """
        Register a new peer or update existing peer.
        
        :param ip (str): IP address of the peer
        :param port (int): Port number of the peer
        :return: Peer ID in format "{ip}:{port}"
        """
        peer_id = "{}:{}".format(ip, port)
        
        with self.lock:
            self.peers[peer_id] = {
                'ip': ip,
                'port': port,
                'timestamp': time.time(),
                'status': 'active'
            }
            print("[Tracker] Registered peer {} at {}:{}".format(peer_id, ip, port))
        
        return peer_id
    
    def get_active_peers(self, exclude_peer_id=None):
        """
        Get list of currently active peers.
        
        :param exclude_peer_id: Optional peer ID to exclude from results
        :return: List of peer dictionaries {ip, port, peer_id}
        """
        with self.lock:
            active_peers = []
            for peer_id, peer_info in self.peers.items():
                # Skip excluded peer
                if exclude_peer_id and peer_id == exclude_peer_id:
                    continue
                
                # Check if peer is still active
                time_diff = time.time() - peer_info['timestamp']
                if time_diff <= self.timeout_seconds:
                    active_peers.append({
                        'peer_id': peer_id,
                        'ip': peer_info['ip'],
                        'port': peer_info['port'],
                        'timestamp': peer_info['timestamp']
                    })
            
            return active_peers
    
    def get_peer(self, peer_id):
        """
        Get information about a specific peer.
        
        :param peer_id: The peer ID to look up
        :return: Peer dictionary {ip, port, timestamp} or None if not found
        """
        with self.lock:
            if peer_id in self.peers:
                return self.peers[peer_id].copy()
            return None
    
    def refresh_peer(self, peer_id):
        """
        Update the timestamp for a peer (heartbeat).
        
        :param peer_id: The peer ID to refresh
        :return: True if peer exists and was refreshed, False otherwise
        """
        with self.lock:
            if peer_id in self.peers:
                self.peers[peer_id]['timestamp'] = time.time()
                print("[Tracker] Refreshed peer {}".format(peer_id))
                return True
            return False
    
    def remove_peer(self, peer_id):
        """
        Manually remove a peer from the registry.
        
        :param peer_id: The peer ID to remove
        :return: True if peer was removed, False if not found
        """
        with self.lock:
            if peer_id in self.peers:
                del self.peers[peer_id]
                print("[Tracker] Removed peer {}".format(peer_id))
                return True
            return False
    
    def get_all_peers(self):
        """
        Get all peers in registry (including inactive).
        
        :return: List of all peer dictionaries
        """
        with self.lock:
            all_peers = []
            for peer_id, peer_info in self.peers.items():
                all_peers.append({
                    'peer_id': peer_id,
                    'ip': peer_info['ip'],
                    'port': peer_info['port'],
                    'timestamp': peer_info['timestamp'],
                    'status': peer_info['status']
                })
            return all_peers
    
    def cleanup_inactive_peers(self):
        """
        Remove peers that have exceeded the timeout threshold.
        
        :return: List of removed peer IDs
        """
        removed_peers = []
        current_time = time.time()
        
        with self.lock:
            peers_to_remove = []
            for peer_id, peer_info in self.peers.items():
                time_diff = current_time - peer_info['timestamp']
                if time_diff > self.timeout_seconds:
                    peers_to_remove.append(peer_id)
            
            # Remove inactive peers
            for peer_id in peers_to_remove:
                del self.peers[peer_id]
                removed_peers.append(peer_id)
                print("[Tracker] Timeout: Removed inactive peer {}".format(peer_id))
        
        return removed_peers
    
    def start_keepalive(self):
        """
        Start the background keepalive thread for automatic cleanup.
        Thread runs in daemon mode and checks for inactive peers periodically.
        """
        if self.keepalive_active:
            print("[Tracker] Keepalive already running")
            return
        
        self.keepalive_active = True
        self.keepalive_thread = threading.Thread(
            target=self._keepalive_worker,
            daemon=True
        )
        self.keepalive_thread.start()
        print("[Tracker] Keepalive thread started (check interval: {}s, timeout: {}s)".format(
            self.keepalive_interval, self.timeout_seconds))
    
    def stop_keepalive(self):
        """Stop the keepalive background thread."""
        self.keepalive_active = False
        if self.keepalive_thread:
            self.keepalive_thread.join(timeout=2)
        print("[Tracker] Keepalive thread stopped")
    
    def _keepalive_worker(self):
        """
        Background worker thread that periodically cleans up inactive peers.
        """
        while self.keepalive_active:
            try:
                time.sleep(self.keepalive_interval)
                removed = self.cleanup_inactive_peers()
                if removed:
                    print("[Tracker] Keepalive cleaned up {} peer(s)".format(len(removed)))
            except Exception as e:
                print("[Tracker] Keepalive error: {}".format(e))
    
    def get_peer_count(self):
        """
        Get count of active peers.
        
        :return: Number of currently active peers
        """
        with self.lock:
            active_count = 0
            current_time = time.time()
            for peer_info in self.peers.values():
                time_diff = current_time - peer_info['timestamp']
                if time_diff <= self.timeout_seconds:
                    active_count += 1
            return active_count
    
    def print_status(self):
        """Print current registry status to console."""
        with self.lock:
            print("\n[Tracker] === Status ===")
            print("[Tracker] Total peers: {}".format(len(self.peers)))
            print("[Tracker] Active peers: {}".format(self.get_peer_count()))
            for peer_id, info in self.peers.items():
                age = time.time() - info['timestamp']
                status = "**TIMEOUT**" if age > self.timeout_seconds else "**ACTIVE**"
                print("[Tracker]   {} {} (age: {:.1f}s)".format(peer_id, status, age))
            print("[Tracker] ==============\n")


# Global tracker instance
_tracker_instance = None


def get_tracker():
    """Get or create the global tracker instance."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = PeerRegistry()
    return _tracker_instance


def create_tracker(timeout_seconds=30, keepalive_interval=10):
    """Create and initialize a tracker with custom settings."""
    global _tracker_instance
    _tracker_instance = PeerRegistry(timeout_seconds, keepalive_interval)
    return _tracker_instance
