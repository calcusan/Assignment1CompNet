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
daemon.channel
~~~~~~~~~~~~~~~~~

This module provides channel and connection pool management for the proxy server.
It implements connection reuse, pooling, and channel lifecycle management to improve
performance and resource utilization when forwarding requests to backend servers.

Requirements:
-----------------
- socket: provides socket networking interface.
- threading: enables thread-safe pool operations.
- queue: provides thread-safe queue for idle connections.

"""
import socket
import threading
from queue import Queue
from datetime import datetime, timedelta

class Channel:
    """
    Represents a single connection channel to a backend server.
    
    A Channel encapsulates a socket connection with state tracking and
    timeout management. It can be reused for multiple requests.
    
    Attributes:
        host (str): Backend server hostname/IP.
        port (int): Backend server port.
        socket (socket.socket): The underlying socket connection.
        created_at (datetime): When the channel was created.
        last_used (datetime): When the channel was last used.
        is_active (bool): Whether the channel is currently in use.
    """
    
    def __init__(self, host, port):
        """
        Initialize a new Channel to a backend server.
        
        :param host (str): IP address or hostname of the backend server.
        :param port (int): Port number of the backend server.
        """
        self.host = host
        self.port = port
        self.socket = None
        self.created_at = datetime.now()
        self.last_used = datetime.now()
        self.is_active = False
        self.is_connected = False
        
    def connect(self):
        """
        Establish a socket connection to the backend server.
        
        :rtype: bool - True if connection successful, False otherwise.
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.is_connected = True
            self.last_used = datetime.now()
            print("[Channel] Connected to {}:{}".format(self.host, self.port))
            return True
        except socket.error as e:
            print("[Channel] Connection failed to {}:{}: {}".format(self.host, self.port, e))
            self.is_connected = False
            return False
    
    def send_request(self, request):
        """
        Send an HTTP request through this channel.
        
        :param request (str): The HTTP request string.
        :rtype: bytes - Response from the backend server.
        :raises socket.error: If connection is lost or send fails.
        """
        if not self.is_connected or self.socket is None:
            return None
            
        try:
            if isinstance(request, str):
                request = request.encode()
            self.socket.sendall(request)

            # Read response using Content-Length so we don't block forever
            # waiting for the backend to close the socket.
            self.socket.settimeout(10)
            raw = b""
            while True:
                chunk = self.socket.recv(4096)
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
                    if content_length is not None:
                        if len(body_so_far) >= content_length:
                            break
                    else:
                        # No Content-Length: keep reading until timeout/close
                        try:
                            while True:
                                chunk = self.socket.recv(4096)
                                if not chunk:
                                    break
                                raw += chunk
                        except socket.timeout:
                            pass
                        break

            self.last_used = datetime.now()
            return raw if raw else None
        except socket.timeout:
            print("[Channel] Timeout reading response from {}:{}".format(self.host, self.port))
            self.is_connected = False
            self.close()
            return None
        except socket.error as e:
            print("[Channel] Error sending request: {}".format(e))
            self.is_connected = False
            self.close()
            return None
    
    def close(self):
        """Close the socket connection."""
        if self.socket:
            try:
                self.socket.close()
            except socket.error:
                pass
            self.socket = None
            self.is_connected = False
            print("[Channel] Closed connection to {}:{}".format(self.host, self.port))
    
    def is_idle(self):
        """
        Check if the channel is idle (not currently in use).
        
        :rtype: bool - True if idle, False if active.
        """
        return not self.is_active
    
    def is_stale(self, timeout_seconds=300):
        """
        Check if the channel hasn't been used for a while.
        
        :param timeout_seconds (int): Maximum idle time in seconds (default: 5 minutes).
        :rtype: bool - True if stale, False otherwise.
        """
        idle_time = (datetime.now() - self.last_used).total_seconds()
        return idle_time > timeout_seconds
    
    def mark_active(self):
        """Mark this channel as being used."""
        self.is_active = True
    
    def mark_idle(self):
        """Mark this channel as available for reuse."""
        self.is_active = False


class ChannelPool:
    """
    Manages a pool of connection channels to backend servers.
    
    The ChannelPool maintains a collection of reusable connections for each
    backend server, reducing the overhead of creating new connections for
    each request. It implements thread-safe pooling with connection reuse,
    idle timeout management, and pool size limits.
    
    Attributes:
        pools (dict): Dictionary mapping (host, port) to Queue of available channels.
        active_channels (dict): Dictionary tracking active channels.
        max_pool_size (int): Maximum channels per backend.
        idle_timeout (int): Seconds before idle connections are closed.
        lock (threading.Lock): Thread-safe access to pool structures.
    """
    
    def __init__(self, max_pool_size=10, idle_timeout=300):
        """
        Initialize a new ChannelPool.
        
        :param max_pool_size (int): Maximum connections per backend (default: 10).
        :param idle_timeout (int): Seconds to keep idle channels (default: 300).
        """
        self.pools = {}  # Maps (host, port) -> Queue of idle channels
        self.active_channels = {}  # Maps (host, port) -> list of active channels
        self.max_pool_size = max_pool_size
        self.idle_timeout = idle_timeout
        self.lock = threading.Lock()
        print("[ChannelPool] Initialized with max_pool_size={}, idle_timeout={}s".format(
            max_pool_size, idle_timeout))
    
    def get_channel(self, host, port):
        """
        Get or create a channel to the specified backend server.
        
        This method attempts to reuse an idle channel. If no idle channels
        are available and the pool hasn't reached max size, creates a new one.
        Otherwise, waits for a channel to become available.
        
        :param host (str): Backend server IP/hostname.
        :param port (int): Backend server port.
        :rtype: Channel - A usable channel to the backend.
        """
        key = (host, port)
        
        with self.lock:
            # Initialize pool for this backend if needed
            if key not in self.pools:
                self.pools[key] = Queue(maxsize=self.max_pool_size)
                self.active_channels[key] = []
        
        # Try to get an idle channel
        try:
            channel = self.pools[key].get_nowait()
            # If the channel is dead, reconnect it before reusing
            if not channel.is_connected:
                channel.close()
                if not channel.connect():
                    channel = None
                    raise Exception("reconnect failed")
            print("[ChannelPool] Reused channel to {}:{}".format(host, port))
        except:
            # No idle channels available
            with self.lock:
                if len(self.active_channels[key]) < self.max_pool_size:
                    # Create a new channel
                    channel = Channel(host, port)
                    if not channel.connect():
                        return None
                    self.active_channels[key].append(channel)
                    print("[ChannelPool] Created new channel to {}:{} ({} active)".format(
                        host, port, len(self.active_channels[key])))
                else:
                    # Pool exhausted, wait for a channel to become available
                    print("[ChannelPool] Pool exhausted for {}:{}, waiting...".format(host, port))
                    channel = self.pools[key].get(timeout=30)
                    print("[ChannelPool] Got waiting channel for {}:{}".format(host, port))
        
        channel.mark_active()
        return channel
    
    def release_channel(self, channel):
        """
        Release a channel back to the pool for reuse.
        
        :param channel (Channel): The channel to release.
        """
        if not channel:
            return
        
        key = (channel.host, channel.port)
        channel.mark_idle()
        
        with self.lock:
            if key in self.pools:
                try:
                    self.pools[key].put_nowait(channel)
                    print("[ChannelPool] Released channel to {}:{}".format(key[0], key[1]))
                except:
                    print("[ChannelPool] Could not release channel, closing it")
                    channel.close()
    
    def cleanup_stale_channels(self):
        """
        Close and remove idle channels that have exceeded the timeout.
        
        This should be called periodically to clean up unused connections.
        """
        with self.lock:
            for key in list(self.pools.keys()):
                queue = self.pools[key]
                channels_to_remove = []
                
                # Check all idle channels
                while not queue.empty():
                    try:
                        channel = queue.get_nowait()
                        if channel.is_stale(self.idle_timeout):
                            channel.close()
                            print("[ChannelPool] Closed stale channel to {}:{}".format(key[0], key[1]))
                        else:
                            channels_to_remove.append(channel)
                    except:
                        break
                
                # Put back non-stale channels
                for channel in channels_to_remove:
                    try:
                        queue.put_nowait(channel)
                    except:
                        channel.close()
    
    def close_all(self):
        """Close all channels in the pool."""
        with self.lock:
            for key in self.pools.keys():
                queue = self.pools[key]
                while not queue.empty():
                    try:
                        channel = queue.get_nowait()
                        channel.close()
                    except:
                        pass
            
            for key in self.active_channels.keys():
                for channel in self.active_channels[key]:
                    channel.close()
        
        print("[ChannelPool] Closed all channels")
    
    def get_pool_stats(self):
        """
        Get statistics about the current pool state.
        
        :rtype: dict - Statistics including active/idle counts per backend.
        """
        stats = {}
        with self.lock:
            for key in self.pools.keys():
                host, port = key
                idle_count = self.pools[key].qsize()
                active_count = len(self.active_channels.get(key, []))
                stats["{host}:{port}".format(host=host, port=port)] = {
                    "idle": idle_count,
                    "active": active_count,
                    "total": idle_count + active_count
                }
        return stats


# Global channel pool instance
_channel_pool = None

def get_channel_pool(max_pool_size=10, idle_timeout=300):
    """
    Get or create the global channel pool instance.
    
    :param max_pool_size (int): Maximum connections per backend.
    :param idle_timeout (int): Idle connection timeout in seconds.
    :rtype: ChannelPool - The global pool instance.
    """
    global _channel_pool
    if _channel_pool is None:
        _channel_pool = ChannelPool(max_pool_size, idle_timeout)
    return _channel_pool