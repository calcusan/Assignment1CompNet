#!/usr/bin/env python
"""Quick test to verify HTTP pipeline works"""

import socket
import json

def send_request(host, port, method, path, body=""):
    """Send HTTP request and get response"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host, port))
        
        # Build HTTP request
        request = "{} {} HTTP/1.1\r\n".format(method, path)
        request += "Host: {}:{}\r\n".format(host, port)
        request += "Content-Type: application/json\r\n"
        if body:
            request += "Content-Length: {}\r\n".format(len(body))
        request += "Connection: close\r\n"
        request += "\r\n"
        if body:
            request += body
        
        print("[TEST] Sending request:")
        print(request)
        print("-" * 50)
        
        sock.sendall(request.encode())
        
        # Receive response
        response = b""
        while True:
            chunk = sock.recv(1024)
            if not chunk:
                break
            response += chunk
        
        print("[TEST] Received response:")
        print(response.decode('utf-8', errors='ignore'))
        print("-" * 50)
        
    finally:
        sock.close()

if __name__ == "__main__":
    print("=" * 50)
    print("Testing POST /login")
    print("=" * 50)
    send_request("127.0.0.1", 9000, "POST", "/login", "{}")
    
    print("\n" + "=" * 50)
    print("Testing POST /echo")
    print("=" * 50)
    send_request("127.0.0.1", 9000, "POST", "/echo", '{"message": "hello"}')
    
    print("\n" + "=" * 50)
    print("Testing PUT /hello")
    print("=" * 50)
    send_request("127.0.0.1", 9000, "PUT", "/hello", '{}')
