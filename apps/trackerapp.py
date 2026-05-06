"""
apps.trackerapp
~~~~~~~~~~~~~~~~~

This module provides a P2P tracker application that exposes
REST endpoints for peer registration, discovery, and connection facilitation.

Endpoints:
- POST /register: Register a new peer
- GET /discover: Get list of active peers
- POST /connect: Get connection details to initiate P2P connection
"""

import sys
import os
import json
import logging

from daemon import AsynapRous
from daemon.tracker import get_tracker

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create tracker app
app = AsynapRous()
tracker = get_tracker()


@app.route('/register', methods=['POST'])
def register(headers="", body=""):
    """
    Register a new peer with the tracker.
    
    Request body: {
        "ip": "127.0.0.1",
        "port": 9001
    }
    
    Response: {
        "status": "registered",
        "peer_id": "127.0.0.1:9001"
    }
    
    :param headers: Request headers
    :param body: JSON request body
    """
    try:
        # Parse request body
        request_data = json.loads(body) if body else {}
        ip = request_data.get('ip')
        port = request_data.get('port')
        
        # Validate input
        if not ip or not port:
            response = {
                "status": "error",
                "message": "Missing ip or port"
            }
            return json.dumps(response).encode('utf-8')
        
        # Validate port is integer
        try:
            port = int(port)
        except (ValueError, TypeError):
            response = {
                "status": "error",
                "message": "Port must be an integer"
            }
            return json.dumps(response).encode('utf-8')
        
        # Register peer
        peer_id = tracker.register_peer(ip, port)
        
        response = {
            "status": "registered",
            "peer_id": peer_id,
            "message": "Peer registered successfully"
        }
        print("[TrackerApp] Peer registered: {} ({}:{})".format(peer_id, ip, port))
        
        return json.dumps(response).encode('utf-8')
        
    except json.JSONDecodeError:
        response = {
            "status": "error",
            "message": "Invalid JSON in request body"
        }
        return json.dumps(response).encode('utf-8')
    except Exception as e:
        print("[TrackerApp] Error in register: {}".format(e))
        response = {
            "status": "error",
            "message": "Internal server error"
        }
        return json.dumps(response).encode('utf-8')


@app.route('/discover', methods=['GET'])
def discover(headers="", body=""):
    """
    Get list of currently active peers.
    
    Response: {
        "status": "ok",
        "peers": [
            {"peer_id": "127.0.0.1:9001", "ip": "127.0.0.1", "port": 9001},
            {"peer_id": "127.0.0.1:9002", "ip": "127.0.0.1", "port": 9002},
            ...
        ],
        "count": 2
    }
    
    :param headers: Request headers
    :param body: Request body (not used)
    """
    try:
        # Get list of active peers
        active_peers = tracker.get_active_peers()
        
        response = {
            "status": "ok",
            "peers": active_peers,
            "count": len(active_peers)
        }
        print("[TrackerApp] Discover request: {} active peers".format(len(active_peers)))
        
        return json.dumps(response).encode('utf-8')
        
    except Exception as e:
        print("[TrackerApp] Error in discover: {}".format(e))
        response = {
            "status": "error",
            "message": "Internal server error"
        }
        return json.dumps(response).encode('utf-8')


@app.route('/connect', methods=['POST'])
def connect(headers="", body=""):
    """
    Initiate a P2P connection between two peers.
    
    Request body: {
        "source_peer_id": "127.0.0.1:9001",
        "target_peer_id": "127.0.0.1:9002"
    }
    
    Response: {
        "status": "ready",
        "target": {
            "ip": "127.0.0.1",
            "port": 9002
        }
    }
    
    :param headers: Request headers
    :param body: JSON request body
    """
    try:
        # Parse request body
        request_data = json.loads(body) if body else {}
        source_peer_id = request_data.get('source_peer_id')
        target_peer_id = request_data.get('target_peer_id')
        
        # Validate input
        if not source_peer_id or not target_peer_id:
            response = {
                "status": "error",
                "message": "Missing source_peer_id or target_peer_id"
            }
            return json.dumps(response).encode('utf-8')
        
        # Get target peer info
        target_peer = tracker.get_peer(target_peer_id)
        
        if not target_peer:
            response = {
                "status": "error",
                "message": "Target peer not found"
            }
            print("[TrackerApp] Connect: Target peer {} not found".format(target_peer_id))
            return json.dumps(response).encode('utf-8')
        
        # Return connection info
        response = {
            "status": "ready",
            "target": {
                "peer_id": target_peer_id,
                "ip": target_peer['ip'],
                "port": target_peer['port']
            },
            "message": "Ready to connect to target peer"
        }
        print("[TrackerApp] Connect: {} -> {}".format(source_peer_id, target_peer_id))
        
        return json.dumps(response).encode('utf-8')
        
    except json.JSONDecodeError:
        response = {
            "status": "error",
            "message": "Invalid JSON in request body"
        }
        return json.dumps(response).encode('utf-8')
    except Exception as e:
        print("[TrackerApp] Error in connect: {}".format(e))
        response = {
            "status": "error",
            "message": "Internal server error"
        }
        return json.dumps(response).encode('utf-8')


@app.route('/status', methods=['GET'])
def status(headers="", body=""):
    """
    Get tracker status information.
    
    Response: {
        "status": "ok",
        "total_peers": 5,
        "active_peers": 3
    }
    """
    try:
        all_peers = tracker.get_all_peers()
        active_count = tracker.get_peer_count()
        
        response = {
            "status": "ok",
            "total_peers": len(all_peers),
            "active_peers": active_count,
            "timeout_seconds": tracker.timeout_seconds
        }
        
        return json.dumps(response).encode('utf-8')
        
    except Exception as e:
        print("[TrackerApp] Error in status: {}".format(e))
        response = {
            "status": "error",
            "message": "Internal server error"
        }
        return json.dumps(response).encode('utf-8')


def create_trackerapp():
    """Create and return the tracker app instance with routes registered."""
    return app
