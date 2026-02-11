"""
Health HTTP endpoint for MCP server.

Provides a simple HTTP health check endpoint that can be polled to verify:
1. Qdrant is accessible
2. Ingestion has completed (optional)
"""

import os
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from threading import Thread
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)


def get_health_status() -> Tuple[Dict[str, Any], int]:
    """
    Compute health status (reusable for HTTP handler or FastMCP custom route).

    Returns:
        Tuple of (response_dict, http_status_code).
    """
    qdrant_ok = _check_qdrant()
    ingestion_complete = _check_ingestion_complete()
    if qdrant_ok and ingestion_complete:
        status_code = 200
        status = 'ready'
    elif qdrant_ok and not ingestion_complete:
        status_code = 503
        status = 'waiting_for_ingestion'
    else:
        status_code = 503
        status = 'unhealthy'
    response = {
        'status': status,
        'qdrant': 'ok' if qdrant_ok else 'unavailable',
        'backend_type': 'qdrant',
        'ingestion': 'complete' if ingestion_complete else 'pending',
    }
    return response, status_code


def _check_qdrant() -> bool:
    """Check if Qdrant is accessible."""
    import urllib.request
    qdrant_url = os.getenv('QDRANT_URL', 'http://qdrant:6333')
    try:
        # Qdrant root endpoint returns version info
        req = urllib.request.Request(f'{qdrant_url}/')
        with urllib.request.urlopen(req, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def _check_ingestion_complete() -> bool:
    """Check if ingestion has completed."""
    status_file = '/app/status/ingestion_complete'
    if not os.path.exists(status_file):
        return False
    try:
        with open(status_file, 'r') as f:
            return f.read().strip() == 'complete'
    except Exception:
        return False


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP handler for health endpoint."""
    
    def log_message(self, format, *args):
        """Suppress default HTTP logging (use our logger instead)."""
        pass
    
    def do_GET(self):
        """Handle GET request to /health."""
        if self.path != '/health':
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')
            return
        response, status_code = get_health_status()
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode('utf-8'))


def start_health_server(port: int = 8001, host: str = '0.0.0.0'):
    """
    Start health check HTTP server in background thread.
    
    Args:
        port: Port to listen on (default: 8001)
        host: Host to bind to (default: 0.0.0.0)
    """
    server = HTTPServer((host, port), HealthHandler)
    
    def run_server():
        logger.info(f"🏥 Health server listening on {host}:{port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logger.info("🛑 Health server shutting down")
            server.shutdown()
    
    thread = Thread(target=run_server, daemon=True)
    thread.start()
    
    return server


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    server = start_health_server()
    
    # Keep main thread alive
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.shutdown()
