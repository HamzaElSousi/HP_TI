"""
FTP Honeypot Service

Low-interaction FTP honeypot that simulates file servers.
Captures FTP-based attacks and file transfer attempts.
"""

import asyncio
import socket
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

from honeypot.logging.logger import get_honeypot_logger, create_session_logger
from honeypot.config.config_loader import HoneypotFTPConfig


class FTPHoneypot:
    """
    Low-interaction FTP honeypot.

    Simulates FTP servers with fake directory structures and files.
    Logs all file operations and authentication attempts.
    """

    # FTP response codes
    RESPONSE_220 = "220 FTP Server ready\r\n"
    RESPONSE_230 = "230 User logged in\r\n"
    RESPONSE_331 = "331 Password required\r\n"
    RESPONSE_421 = "421 Service not available\r\n"
    RESPONSE_530 = "530 Login incorrect\r\n"
    RESPONSE_200 = "200 Command okay\r\n"
    RESPONSE_215 = "215 UNIX Type: L8\r\n"
    RESPONSE_221 = "221 Goodbye\r\n"
    RESPONSE_250 = "250 Requested file action okay\r\n"
    RESPONSE_257 = "257 \"/\" is current directory\r\n"
    RESPONSE_500 = "500 Command not understood\r\n"
    RESPONSE_502 = "502 Command not implemented\r\n"
    RESPONSE_550 = "550 File not found\r\n"

    # Fake directory structure
    FAKE_FILES = [
        "README.txt",
        "index.html",
        "config.ini",
        "data.csv",
        "backup.zip",
        "log.txt"
    ]

    FAKE_DIRS = [
        "uploads",
        "downloads",
        "public",
        "private",
        "backups"
    ]

    def __init__(self, config: HoneypotFTPConfig, log_dir: Path):
        """
        Initialize FTP honeypot.

        Args:
            config: FTP honeypot configuration
            log_dir: Directory for log files
        """
        self.config = config
        self.log_dir = log_dir
        self.logger = get_honeypot_logger("ftp", log_dir, log_format="json")
        self.running = False
        self.server_socket: Optional[socket.socket] = None
        self.sessions: Dict[str, Dict[str, Any]] = {}

    async def start(self) -> None:
        """Start the FTP honeypot server."""
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.server_socket.bind((self.config.host, self.config.port))
            self.server_socket.listen(100)

            self.logger.info(
                f"FTP honeypot started on {self.config.host}:{self.config.port}",
                extra={
                    "event_type": "honeypot_started",
                    "component": "ftp_honeypot",
                    "host": self.config.host,
                    "port": self.config.port,
                }
            )

            while self.running:
                try:
                    self.server_socket.settimeout(1.0)
                    client_socket, client_addr = self.server_socket.accept()

                    # Handle connection in separate thread
                    threading.Thread(
                        target=self._handle_connection,
                        args=(client_socket, client_addr),
                        daemon=True,
                    ).start()

                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        self.logger.error(f"Error accepting connection: {e}")

        except Exception as e:
            self.logger.error(f"Failed to start FTP honeypot: {e}")
            raise
        finally:
            if self.server_socket:
                self.server_socket.close()

    def stop(self) -> None:
        """Stop the FTP honeypot server."""
        self.running = False
        if self.server_socket:
            self.server_socket.close()

        self.logger.info(
            "FTP honeypot stopped",
            extra={"event_type": "honeypot_stopped", "component": "ftp_honeypot"}
        )

    def _handle_connection(self, client_socket: socket.socket, client_addr: tuple) -> None:
        """
        Handle individual FTP connection.

        Args:
            client_socket: Client socket
            client_addr: Client address (ip, port)
        """
        session_id = str(uuid.uuid4())
        source_ip = client_addr[0]
        source_port = client_addr[1]

        session_logger = create_session_logger(self.logger, session_id, source_ip)

        session_logger.info(
            "New FTP connection",
            extra={
                "event_type": "connection_attempt",
                "component": "ftp_honeypot",
                "source_port": source_port,
            }
        )

        # Store session info
        self.sessions[session_id] = {
            "session_id": session_id,
            "source_ip": source_ip,
            "source_port": source_port,
            "start_time": datetime.utcnow().isoformat(),
            "commands": [],
            "auth_attempts": [],
            "authenticated": False,
            "username": None,
        }

        try:
            client_socket.settimeout(300)  # 5 minute timeout

            # Send welcome banner
            self._send(client_socket, self.RESPONSE_220)

            # Handle FTP commands
            self._handle_commands(client_socket, session_id, session_logger)

        except Exception as e:
            session_logger.debug(f"Connection error: {e}")
        finally:
            try:
                client_socket.close()
            except:
                pass

            # Log session end
            self.sessions[session_id]["end_time"] = datetime.utcnow().isoformat()
            session_logger.info(
                "FTP session ended",
                extra={
                    "event_type": "session_ended",
                    "component": "ftp_honeypot",
                    "session_data": self.sessions[session_id],
                }
            )

    def _handle_commands(
        self, client_socket: socket.socket, session_id: str, logger
    ) -> None:
        """
        Handle FTP commands.

        Args:
            client_socket: Client socket
            session_id: Session identifier
            logger: Session logger
        """
        while True:
            try:
                # Receive command
                command = self._receive_line(client_socket, timeout=300)
                if not command:
                    break

                # Parse command
                parts = command.strip().split(None, 1)
                if not parts:
                    continue

                cmd = parts[0].upper()
                arg = parts[1] if len(parts) > 1 else ""

                # Log command
                logger.info(
                    f"FTP command: {cmd} {arg}",
                    extra={
                        "event_type": "ftp_command",
                        "component": "ftp_honeypot",
                        "command": cmd,
                        "argument": arg,
                    }
                )

                # Store command
                self.sessions[session_id]["commands"].append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "command": cmd,
                    "argument": arg,
                })

                # Handle command
                response = self._handle_ftp_command(
                    cmd, arg, session_id, logger
                )
                self._send(client_socket, response)

                # Check for quit
                if cmd == "QUIT":
                    break

            except Exception as e:
                logger.debug(f"Command handling error: {e}")
                break

    def _handle_ftp_command(
        self, cmd: str, arg: str, session_id: str, logger
    ) -> str:
        """
        Handle individual FTP command.

        Args:
            cmd: FTP command
            arg: Command argument
            session_id: Session identifier
            logger: Session logger

        Returns:
            FTP response string
        """
        session = self.sessions[session_id]

        # USER command
        if cmd == "USER":
            session["username"] = arg
            return self.RESPONSE_331

        # PASS command
        elif cmd == "PASS":
            username = session.get("username", "anonymous")

            # Log authentication attempt
            logger.info(
                "FTP authentication attempt",
                extra={
                    "event_type": "auth_attempt",
                    "component": "ftp_honeypot",
                    "username": username,
                    "password": arg,
                    "auth_method": "password",
                    "success": False,
                }
            )

            # Store auth attempt
            session["auth_attempts"].append({
                "timestamp": datetime.utcnow().isoformat(),
                "username": username,
                "password": arg,
                "success": False,
            })

            # Always reject (it's a honeypot!)
            return self.RESPONSE_530

        # SYST command
        elif cmd == "SYST":
            return self.RESPONSE_215

        # PWD command
        elif cmd == "PWD":
            return self.RESPONSE_257

        # CWD command
        elif cmd == "CWD":
            # Log directory change attempt
            logger.info(
                f"Directory change attempt: {arg}",
                extra={
                    "event_type": "ftp_cwd",
                    "component": "ftp_honeypot",
                    "directory": arg,
                }
            )
            return self.RESPONSE_250

        # LIST command
        elif cmd == "LIST":
            # Would need data connection in real FTP
            return self.RESPONSE_502

        # RETR command (download)
        elif cmd == "RETR":
            logger.info(
                f"File download attempt: {arg}",
                extra={
                    "event_type": "ftp_download",
                    "component": "ftp_honeypot",
                    "filename": arg,
                }
            )
            return self.RESPONSE_550  # File not found

        # STOR command (upload)
        elif cmd == "STOR":
            logger.info(
                f"File upload attempt: {arg}",
                extra={
                    "event_type": "ftp_upload",
                    "component": "ftp_honeypot",
                    "filename": arg,
                }
            )
            return self.RESPONSE_550  # Can't create file

        # QUIT command
        elif cmd == "QUIT":
            return self.RESPONSE_221

        # TYPE command (ASCII/Binary mode)
        elif cmd == "TYPE":
            return self.RESPONSE_200

        # PORT/PASV commands (data connection)
        elif cmd in ["PORT", "PASV"]:
            return self.RESPONSE_502  # Not implemented

        # Unknown command
        else:
            return self.RESPONSE_500

    def _send(self, sock: socket.socket, data: str) -> None:
        """
        Send data to client.

        Args:
            sock: Client socket
            data: Data to send
        """
        try:
            sock.sendall(data.encode('utf-8'))
        except Exception as e:
            self.logger.debug(f"Send error: {e}")

    def _receive_line(self, sock: socket.socket, timeout: int = 30) -> Optional[str]:
        """
        Receive a line of data from client.

        Args:
            sock: Client socket
            timeout: Receive timeout in seconds

        Returns:
            Received line or None
        """
        sock.settimeout(timeout)
        buffer = b""

        try:
            while True:
                chunk = sock.recv(1)
                if not chunk:
                    return None

                buffer += chunk

                # Check for CRLF
                if buffer.endswith(b'\r\n'):
                    return buffer[:-2].decode('utf-8', errors='ignore')

                # Limit buffer size
                if len(buffer) > 1024:
                    return buffer.decode('utf-8', errors='ignore')

        except socket.timeout:
            return None
        except Exception as e:
            self.logger.debug(f"Receive error: {e}")
            return None

    def get_sessions(self) -> List[Dict[str, Any]]:
        """
        Get all captured sessions.

        Returns:
            List of session dictionaries
        """
        return list(self.sessions.values())
