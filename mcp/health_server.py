"""
Health HTTP endpoint for MCP server.

Provides a simple HTTP health check endpoint that can be polled to verify:
1. SurrealDB is accessible
2. Ingestion has completed (optional)
"""

import os
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from threading import Thread

logger = logging.getLogger(__name__)


def check_surrealdb() -> bool:
    """Check if SurrealDB is accessible (module-level for reuse)."""
    import urllib.request
    surrealdb_url = os.getenv('SURREALDB_URL', 'http://localhost:8000')
    try:
        req = urllib.request.Request(f'{surrealdb_url}/health')
        with urllib.request.urlopen(req, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def check_ingestion_complete() -> bool:
    """Check if ingestion has completed (module-level for reuse)."""
    status_file = '/app/status/ingestion_complete'
    if not os.path.exists(status_file):
        return False
    try:
        with open(status_file, 'r') as f:
            return f.read().strip() == 'complete'
    except Exception:
        return False


def get_health_response() -> tuple[dict, int]:
    """
    Return (JSON body, status_code) for the health endpoint.
    Status 200 when SurrealDB is reachable (so Docker healthcheck passes).
    """
    surrealdb_ok = check_surrealdb()
    ingestion_complete = check_ingestion_complete()
    if surrealdb_ok and ingestion_complete:
        status = 'ready'
    elif surrealdb_ok and not ingestion_complete:
        status = 'waiting_for_ingestion'
    else:
        status = 'unhealthy'
    status_code = 200 if surrealdb_ok else 503
    body = {
        'status': status,
        'surrealdb': 'ok' if surrealdb_ok else 'unavailable',
        'ingestion': 'complete' if ingestion_complete else 'pending'
    }
    return body, status_code


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
        
        body, status_code = get_health_response()
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(body).encode('utf-8'))


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
