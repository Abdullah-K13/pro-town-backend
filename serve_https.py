"""
Simple HTTPS Server for Square Web Payments SDK Testing
========================================================
Square requires HTTPS for their Web Payments SDK.
This script creates a local HTTPS server to test the payment form.

Usage:
    python serve_https.py

Then open: https://localhost:8443/test_square_frontend.html
"""

import http.server
import ssl
import os

# Configuration
PORT = 8443
CERTFILE = "localhost.pem"

def create_self_signed_cert():
    """Create a self-signed certificate for localhost"""
    try:
        # Check if certificate already exists
        if os.path.exists(CERTFILE):
            print(f"✅ Using existing certificate: {CERTFILE}")
            return True
        
        # Try to create certificate using OpenSSL
        import subprocess
        
        print("🔐 Creating self-signed certificate...")
        cmd = [
            "openssl", "req", "-new", "-x509", "-keyout", CERTFILE, "-out", CERTFILE,
            "-days", "365", "-nodes",
            "-subj", "/C=US/ST=State/L=City/O=Organization/CN=localhost"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Certificate created: {CERTFILE}")
            return True
        else:
            print(f"❌ Failed to create certificate: {result.stderr}")
            return False
            
    except FileNotFoundError:
        print("❌ OpenSSL not found. Please install OpenSSL or use the alternative method below.")
        return False
    except Exception as e:
        print(f"❌ Error creating certificate: {e}")
        return False

def run_server():
    """Run HTTPS server"""
    
    # Change to script directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Create certificate if needed
    if not os.path.exists(CERTFILE):
        print("\n⚠️  No SSL certificate found.")
        print("=" * 70)
        print("OPTION 1: Install OpenSSL and run this script again")
        print("OPTION 2: Use the simpler HTTP method below")
        print("=" * 70)
        print("\nAlternative: Use Python's built-in HTTP server (no HTTPS):")
        print("1. Run: python -m http.server 8000")
        print("2. Open: http://localhost:8000/test_square_frontend.html")
        print("\nNote: Square SDK may still require HTTPS in production mode.")
        print("For testing, you can also deploy to a service like Vercel or Netlify.")
        return
    
    # Create HTTPS server
    server_address = ('', PORT)
    httpd = http.server.HTTPServer(server_address, http.server.SimpleHTTPRequestHandler)
    
    # Wrap with SSL
    httpd.socket = ssl.wrap_socket(
        httpd.socket,
        certfile=CERTFILE,
        server_side=True,
        ssl_version=ssl.PROTOCOL_TLS
    )
    
    print("=" * 70)
    print("🚀 HTTPS Server Running")
    print("=" * 70)
    print(f"📍 URL: https://localhost:{PORT}/test_square_frontend.html")
    print(f"🔐 Certificate: {CERTFILE}")
    print("\n⚠️  Your browser will show a security warning (self-signed cert)")
    print("   Click 'Advanced' → 'Proceed to localhost' to continue")
    print("\n🛑 Press Ctrl+C to stop the server")
    print("=" * 70)
    print()
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped")
        httpd.shutdown()

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("Square Web Payments SDK - HTTPS Test Server")
    print("=" * 70)
    print()
    
    # Try to create certificate
    create_self_signed_cert()
    
    # Run server
    run_server()
