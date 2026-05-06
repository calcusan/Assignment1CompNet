#!/usr/bin/env python
"""
start_p2p
~~~~~~~~~~~~~~~~~

Entry point for launching a P2P chat peer application.

Each peer:
  1. Registers itself with the tracker (start_tracker.py)
  2. Discovers other active peers
  3. Runs the P2P AsynapRous HTTP server to receive messages

Usage::

    python start_p2p.py --server-ip 0.0.0.0 --server-port 9001 \\
                        --tracker-ip 127.0.0.1 --tracker-port 9000

"""
import argparse
import sys

from apps.p2papp import create_p2p_app, active_peers
from daemon.peer import Peer

PORT = 9001
TRACKER_PORT = 9000


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='P2PPeer',
        description='Start a P2P chat peer',
        epilog='P2P chat peer daemon'
    )
    parser.add_argument('--server-ip', default='0.0.0.0',
                        help='IP address to bind this peer server')
    parser.add_argument('--server-port', type=int, default=PORT,
                        help='Port for this peer server')
    parser.add_argument('--tracker-ip', default='127.0.0.1',
                        help='Tracker IP address')
    parser.add_argument('--tracker-port', type=int, default=TRACKER_PORT,
                        help='Tracker port')

    args = parser.parse_args()

    # Register with tracker and discover peers
    peer = Peer(
        peer_ip=args.server_ip if args.server_ip != '0.0.0.0' else '127.0.0.1',
        peer_port=args.server_port,
        tracker_ip=args.tracker_ip,
        tracker_port=args.tracker_port,
        discovery_interval=5,
    )

    registered = peer.register()
    if not registered:
        # Retry registration a few times in case tracker is starting up
        import time
        for attempt in range(3):
            print("[Main] Retrying registration in 2 seconds... (attempt {}/{})".format(attempt + 1, 3))
            time.sleep(2)
            registered = peer.register()
            if registered:
                break
    
    if registered:
        known = peer.discover_peers()
        if known is not None:
            # Update p2papp's peer list
            active_peers.clear()
            active_peers.extend(known)
        else:
            known = []

        # Keep p2papp.active_peers in sync on every future discovery poll
        def sync_peers(peers):
            if peers is not None:
                active_peers.clear()
                active_peers.extend(peers)

        peer.start_discovery(on_peers_updated=sync_peers)
        peer.start_keepalive()
    else:
        print("[Main] Warning: could not register with tracker after retries. Running in standalone mode.")

    print("[Main] Starting P2P app on {}:{}".format(args.server_ip, args.server_port))

    try:
        create_p2p_app(args.server_ip, args.server_port, peers=list(active_peers))
    except KeyboardInterrupt:
        print("\n[Main] Shutting down...")
        peer.stop_discovery()
        sys.exit(0)