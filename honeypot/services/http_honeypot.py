"""
HTTP/HTTPS Honeypot Service

Low-interaction HTTP honeypot that simulates web servers and admin panels.
Captures web-based attacks including SQL injection, XSS, path traversal, etc.
"""

import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from flask import Flask, request, Response, render_template_string
import threading

from honeypot.logging.logger import get_honeypot_logger, create_session_logger
from honeypot.config.config_loader import HoneypotHTTPConfig


class HTTPHoneypot:
    """
    Low-interaction HTTP/HTTPS honeypot.

    Simulates common web applications and admin panels to attract
    and log web-based attacks.
    """

    # Fake admin panel HTML
    ADMIN_PANEL_HTML = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Login</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 50px; background: #f0f0f0; }
            .login-box {
                max-width: 400px;
                margin: 100px auto;
                background: white;
                padding: 30px;
                border-radius: 5px;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
            }
            h2 { color: #333; }
            input { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; }
            button {
                width: 100%;
                padding: 10px;
                background: #007bff;
                color: white;
                border: none;
                cursor: pointer;
            }
            button:hover { background: #0056b3; }
            .error { color: red; margin-top: 10px; }
        </style>
    </head>
    <body>
        <div class="login-box">
            <h2>Administrator Login</h2>
            <form method="POST" action="{{ request.path }}">
                <input type="text" name="username" placeholder="Username" required>
                <input type="password" name="password" placeholder="Password" required>
                <button type="submit">Login</button>
            </form>
            {% if error %}
            <div class="error">{{ error }}</div>
            {% endif %}
        </div>
    </body>
    </html>
    """

    # Common vulnerable paths that attackers look for
    VULNERABLE_PATHS = {
        "/admin", "/wp-admin", "/administrator", "/phpmyadmin",
        "/admin/login", "/admin/login.php", "/wp-login.php",
        "/login", "/login.php", "/admin.php",
        "/.env", "/config.php", "/configuration.php",
        "/backup.sql", "/database.sql", "/db_backup.sql",
        "/shell.php", "/c99.php", "/r57.php", "/webshell.php",
        "/uploads", "/upload", "/files",
        "/.git", "/.svn", "/.htaccess"
    }

    def __init__(self, config: HoneypotHTTPConfig, log_dir: Path):
        """
        Initialize HTTP honeypot.

        Args:
            config: HTTP honeypot configuration
            log_dir: Directory for log files
        """
        self.config = config
        self.log_dir = log_dir
        self.logger = get_honeypot_logger("http", log_dir, log_format="json")
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = str(uuid.uuid4())
        self.running = False
        self.sessions: Dict[str, Dict[str, Any]] = {}

        # Setup routes
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Setup Flask routes for the honeypot."""

        # Catch all routes
        @self.app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'])
        @self.app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'])
        def catch_all(path):
            return self._handle_request(path)

    def _handle_request(self, path: str) -> Response:
        """
        Handle all incoming HTTP requests.

        Args:
            path: Request path

        Returns:
            HTTP response
        """
        session_id = str(uuid.uuid4())
        source_ip = request.remote_addr

        # Create session logger
        session_logger = create_session_logger(self.logger, session_id, source_ip)

        # Log request details
        request_data = {
            "event_type": "http_request",
            "component": "http_honeypot",
            "method": request.method,
            "path": f"/{path}",
            "full_url": request.url,
            "query_string": request.query_string.decode('utf-8', errors='ignore'),
            "headers": dict(request.headers),
            "user_agent": request.user_agent.string,
            "referrer": request.referrer,
            "content_length": request.content_length,
        }

        # Log POST data (potential attack payloads)
        if request.method == 'POST':
            try:
                if request.is_json:
                    request_data["post_data"] = request.get_json()
                else:
                    request_data["post_data"] = request.form.to_dict()
            except Exception as e:
                request_data["post_data_error"] = str(e)

        session_logger.info(
            f"{request.method} {path}",
            extra=request_data
        )

        # Store session
        self.sessions[session_id] = {
            "session_id": session_id,
            "source_ip": source_ip,
            "timestamp": datetime.utcnow().isoformat(),
            "request": request_data
        }

        # Detect attack types
        attack_type = self._detect_attack_type(path, request)
        if attack_type:
            session_logger.warning(
                f"Potential attack detected: {attack_type}",
                extra={
                    "event_type": "attack_detected",
                    "component": "http_honeypot",
                    "attack_type": attack_type,
                    "path": f"/{path}",
                    "indicators": self._extract_attack_indicators(path, request)
                }
            )

        # Return appropriate response
        return self._generate_response(path, request)

    def _detect_attack_type(self, path: str, request) -> Optional[str]:
        """
        Detect type of web attack.

        Args:
            path: Request path
            request: Flask request object

        Returns:
            Attack type string or None
        """
        full_path = f"/{path}"
        query = request.query_string.decode('utf-8', errors='ignore').lower()

        # SQL Injection detection
        sql_patterns = [
            "' or '1'='1", "union select", "select * from",
            "'; drop table", "or 1=1", "' or 'a'='a"
        ]
        if any(pattern in query.lower() for pattern in sql_patterns):
            return "sql_injection"

        # XSS detection
        xss_patterns = ["<script>", "javascript:", "onerror=", "onload=", "<img src="]
        if any(pattern in query.lower() for pattern in xss_patterns):
            return "xss"

        # Path traversal detection
        if "../" in full_path or "..%2f" in full_path.lower():
            return "path_traversal"

        # Command injection
        cmd_patterns = [";", "|", "`", "$(", "${"]
        if any(pattern in query for pattern in cmd_patterns):
            return "command_injection"

        # Webshell access attempt
        if any(shell in full_path.lower() for shell in [".php", "shell", "c99", "r57", "webshell"]):
            return "webshell_access"

        # Admin panel probing
        if any(admin in full_path.lower() for admin in ["/admin", "/wp-admin", "/phpmyadmin"]):
            return "admin_probing"

        # Config file access
        if any(config in full_path.lower() for config in [".env", "config.", ".git", ".htaccess"]):
            return "config_exposure"

        return None

    def _extract_attack_indicators(self, path: str, request) -> Dict[str, Any]:
        """
        Extract indicators of compromise from request.

        Args:
            path: Request path
            request: Flask request object

        Returns:
            Dictionary of attack indicators
        """
        return {
            "path": f"/{path}",
            "method": request.method,
            "query_string": request.query_string.decode('utf-8', errors='ignore'),
            "user_agent": request.user_agent.string,
            "suspicious_headers": [
                {k: v} for k, v in request.headers.items()
                if k.lower() in ['x-forwarded-for', 'x-real-ip', 'referer']
            ]
        }

    def _generate_response(self, path: str, request) -> Response:
        """
        Generate appropriate response based on request.

        Args:
            path: Request path
            request: Flask request object

        Returns:
            Flask response
        """
        full_path = f"/{path}"

        # Admin panels - show fake login
        if any(admin in full_path.lower() for admin in ["/admin", "/wp-admin", "/login", "/phpmyadmin"]):
            if request.method == 'POST':
                # Log login attempt
                username = request.form.get('username', '')
                password = request.form.get('password', '')

                self.logger.info(
                    "HTTP admin login attempt",
                    extra={
                        "event_type": "http_login_attempt",
                        "component": "http_honeypot",
                        "source_ip": request.remote_addr,
                        "path": full_path,
                        "username": username,
                        "password": password,
                        "success": False
                    }
                )

                # Return error
                return Response(
                    render_template_string(self.ADMIN_PANEL_HTML, error="Invalid credentials"),
                    status=401,
                    content_type='text/html'
                )
            else:
                # Show login form
                return Response(
                    render_template_string(self.ADMIN_PANEL_HTML, error=None),
                    status=200,
                    content_type='text/html'
                )

        # Config files - return 403
        if any(config in full_path.lower() for config in [".env", "config.", ".git", ".htaccess"]):
            return Response("403 Forbidden", status=403)

        # Shell files - return 404
        if any(shell in full_path.lower() for shell in ["shell", "c99", "r57", "webshell"]):
            return Response("404 Not Found", status=404)

        # Default - return generic page
        return Response(
            "<html><head><title>Welcome</title></head><body><h1>Welcome</h1></body></html>",
            status=200,
            content_type='text/html'
        )

    async def start(self) -> None:
        """Start the HTTP honeypot server."""
        self.running = True

        self.logger.info(
            f"HTTP honeypot starting on {self.config.host}:{self.config.port}",
            extra={
                "event_type": "honeypot_started",
                "component": "http_honeypot",
                "host": self.config.host,
                "port": self.config.port,
            }
        )

        # Run Flask in a separate thread
        def run_flask():
            self.app.run(
                host=self.config.host,
                port=self.config.port,
                debug=False,
                use_reloader=False,
                threaded=True
            )

        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()

        # Keep the async function running
        while self.running:
            await asyncio.sleep(1)

    def stop(self) -> None:
        """Stop the HTTP honeypot server."""
        self.running = False

        self.logger.info(
            "HTTP honeypot stopped",
            extra={"event_type": "honeypot_stopped", "component": "http_honeypot"}
        )

    def get_sessions(self) -> List[Dict[str, Any]]:
        """
        Get all captured sessions.

        Returns:
            List of session dictionaries
        """
        return list(self.sessions.values())
