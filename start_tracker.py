#!/usr/bin/env python
"""
start_tracker.py

Launcher script for the P2P Tracker application.
Initializes the tracker server and starts listening for peer connections.

Usage:
    python start_tracker.py [--server-ip IP] [--server-port PORT]

Default:
    python start_tracker.py
    # Runs on 127.0.0.1:9000
"""

import sys
import argparse
from apps import create_trackerapp
from daemon.tracker import get_tracker


def main():
    """Parse arguments and start the tracker server."""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Start P2P Tracker Server')
    parser.add_argument('--server-ip', type=str, default='127.0.0.1',
                        help='Server IP address (default: 127.0.0.1)')
    parser.add_argument('--server-port', type=int, default=9000,
                        help='Server port (default: 9000)')
    
    args = parser.parse_args()
    
    print("[Main] Starting P2P Tracker Application")
    print("[Main] Server: {}:{}".format(args.server_ip, args.server_port))
    
    # Create tracker app
    app = create_trackerapp()
    
    # Prepare address
    app.prepare_address(args.server_ip, args.server_port)
    
    # Get tracker and start keepalive
    tracker = get_tracker()
    tracker.start_keepalive()
    
    print("[Main] Tracker keepalive started")
    print("[Main] Listening on {}:{}".format(args.server_ip, args.server_port))
    
    # Run the app
    try:
        app.run()
    except KeyboardInterrupt:
        print("\n[Main] Shutting down...")
        tracker.stop_keepalive()
        sys.exit(0)


if __name__ == '__main__':
    main()
