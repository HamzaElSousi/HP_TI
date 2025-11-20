"""
Telnet Honeypot Service

Low-interaction Telnet honeypot that simulates IoT devices and legacy systems.
Captures Telnet-based attacks targeting routers, cameras, and other devices.
"""

import asyncio
import socket
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

from honeypot.logging.logger import get_honeypot_logger, create_session_logger
from honeypot.config.config_loader import HoneypotTelnetConfig


class TelnetHoneypot:
    """
    Low-interaction Telnet honeypot.

    Simulates IoT devices (routers, cameras, DVRs) commonly targeted
    by botnets and automated attacks.
    """

    # Device simulation profiles
    DEVICE_PROFILES = {
        "router": {
            "banner": "Welcome to Generic Router\r\nLogin: ",
            "hostname": "router",
            "prompt": "router> ",
        },
        "camera": {
            "banner": "IP Camera System v2.1\r\nlogin: ",
            "hostname": "ipcam",
            "prompt": "ipcam# ",
        },
        "dvr": {
            "banner": "DVR System Console\r\nUsername: ",
            "hostname": "dvr",
            "prompt": "dvr$ ",
        }
    }

    # Fake command responses
    FAKE_RESPONSES = {
        "help": "Available commands: help, exit, reboot, status, config, show\r\n",
        "?": "Available commands: help, exit, reboot, status, config, show\r\n",
        "exit": "Goodbye\r\n",
        "quit": "Goodbye\r\n",
        "reboot": "System rebooting...\r\n",
        "status": "System Status: OK\r\nUptime: 45 days\r\nMemory: 128MB\r\n",
        "show": "Device Information\r\nModel: Generic IoT Device\r\nFirmware: 2.1.5\r\n",
        "config": "Configuration:\r\nIP: 192.168.1.1\r\nMask: 255.255.255.0\r\n",
        "ls": "bin  dev  etc  lib  proc  sbin  tmp  usr  var\r\n",
        "pwd": "/root\r\n",
        "whoami": "root\r\n",
        "id": "uid=0(root) gid=0(root) groups=0(root)\r\n",
    }

    def __init__(self, config: HoneypotTelnetConfig, log_dir: Path, device_type: str = "router"):
        """
        Initialize Telnet honeypot.

        Args:
            config: Telnet honeypot configuration
            log_dir: Directory for log files
            device_type: Device profile to simulate (router, camera, dvr)
        """
        self.config = config
        self.log_dir = log_dir
        self.device_type = device_type
        self.device_profile = self.DEVICE_PROFILES.get(device_type, self.DEVICE_PROFILES["router"])
        self.logger = get_honeypot_logger("telnet", log_dir, log_format="json")
        self.running = False
        self.server_socket: Optional[socket.socket] = None
        self.sessions: Dict[str, Dict[str, Any]] = {}

    async def start(self) -> None:
        """Start the Telnet honeypot server."""
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.server_socket.bind((self.config.host, self.config.port))
            self.server_socket.listen(100)

            self.logger.info(
                f"Telnet honeypot started on {self.config.host}:{self.config.port} (device: {self.device_type})",
                extra={
                    "event_type": "honeypot_started",
                    "component": "telnet_honeypot",
                    "host": self.config.host,
                    "port": self.config.port,
                    "device_type": self.device_type,
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
            self.logger.error(f"Failed to start Telnet honeypot: {e}")
            raise
        finally:
            if self.server_socket:
                self.server_socket.close()

    def stop(self) -> None:
        """Stop the Telnet honeypot server."""
        self.running = False
        if self.server_socket:
            self.server_socket.close()

        self.logger.info(
            "Telnet honeypot stopped",
            extra={"event_type": "honeypot_stopped", "component": "telnet_honeypot"}
        )

    def _handle_connection(self, client_socket: socket.socket, client_addr: tuple) -> None:
        """
        Handle individual Telnet connection.

        Args:
            client_socket: Client socket
            client_addr: Client address (ip, port)
        """
        session_id = str(uuid.uuid4())
        source_ip = client_addr[0]
        source_port = client_addr[1]

        session_logger = create_session_logger(self.logger, session_id, source_ip)

        session_logger.info(
            "New Telnet connection",
            extra={
                "event_type": "connection_attempt",
                "component": "telnet_honeypot",
                "source_port": source_port,
                "device_type": self.device_type,
            }
        )

        # Store session info
        self.sessions[session_id] = {
            "session_id": session_id,
            "source_ip": source_ip,
            "source_port": source_port,
            "start_time": datetime.utcnow().isoformat(),
            "auth_attempts": [],
            "commands": [],
            "device_type": self.device_type,
        }

        try:
            client_socket.settimeout(300)  # 5 minute timeout

            # Send banner
            self._send(client_socket, self.device_profile["banner"])

            # Authentication phase
            authenticated = self._handle_authentication(
                client_socket, session_id, session_logger
            )

            if authenticated:
                # Command phase
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
                "Telnet session ended",
                extra={
                    "event_type": "session_ended",
                    "component": "telnet_honeypot",
                    "session_data": self.sessions[session_id],
                }
            )

    def _handle_authentication(
        self, client_socket: socket.socket, session_id: str, logger
    ) -> bool:
        """
        Handle authentication phase.

        Args:
            client_socket: Client socket
            session_id: Session identifier
            logger: Session logger

        Returns:
            True if allowing access (always False for honeypot), False otherwise
        """
        max_attempts = 3
        attempts = 0

        while attempts < max_attempts:
            try:
                # Get username
                username = self._receive_line(client_socket, timeout=30)
                if not username:
                    return False

                # Send password prompt
                self._send(client_socket, "Password: ")

                # Get password
                password = self._receive_line(client_socket, timeout=30)
                if not password:
                    return False

                # Log authentication attempt
                logger.info(
                    "Telnet authentication attempt",
                    extra={
                        "event_type": "auth_attempt",
                        "component": "telnet_honeypot",
                        "username": username,
                        "password": password,
                        "auth_method": "password",
                        "success": False,
                    }
                )

                # Store attempt
                self.sessions[session_id]["auth_attempts"].append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "username": username,
                    "password": password,
                    "success": False,
                })

                # Always reject (it's a honeypot!)
                self._send(client_socket, "Login incorrect\r\n")
                self._send(client_socket, self.device_profile["banner"])

                attempts += 1

            except Exception as e:
                logger.debug(f"Auth error: {e}")
                return False

        # Too many attempts
        self._send(client_socket, "Too many login failures\r\n")
        return False

    def _handle_commands(
        self, client_socket: socket.socket, session_id: str, logger
    ) -> None:
        """
        Handle command execution phase.

        Args:
            client_socket: Client socket
            session_id: Session identifier
            logger: Session logger
        """
        # Send prompt
        self._send(client_socket, self.device_profile["prompt"])

        while True:
            try:
                # Receive command
                command = self._receive_line(client_socket, timeout=300)
                if not command:
                    break

                # Strip whitespace
                command = command.strip()

                if not command:
                    self._send(client_socket, self.device_profile["prompt"])
                    continue

                # Log command
                logger.info(
                    f"Command received: {command}",
                    extra={
                        "event_type": "command_received",
                        "component": "telnet_honeypot",
                        "command": command,
                    }
                )

                # Store command
                self.sessions[session_id]["commands"].append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "command": command,
                })

                # Check for exit commands
                if command.lower() in ["exit", "quit", "logout"]:
                    self._send(client_socket, "Goodbye\r\n")
                    break

                # Send fake response
                response = self._get_fake_response(command)
                self._send(client_socket, response)

                # Send prompt again
                self._send(client_socket, self.device_profile["prompt"])

            except Exception as e:
                logger.debug(f"Command handling error: {e}")
                break

    def _get_fake_response(self, command: str) -> str:
        """
        Get fake response for command.

        Args:
            command: Command string

        Returns:
            Fake response string
        """
        cmd_lower = command.lower().strip()

        # Check for exact matches
        if cmd_lower in self.FAKE_RESPONSES:
            return self.FAKE_RESPONSES[cmd_lower]

        # Check for partial matches
        if cmd_lower.startswith("cat ") or cmd_lower.startswith("more "):
            return "Permission denied\r\n"
        elif cmd_lower.startswith("cd "):
            return ""  # No output for cd
        elif cmd_lower.startswith("wget ") or cmd_lower.startswith("curl "):
            return "Command not found\r\n"
        elif cmd_lower.startswith("rm ") or cmd_lower.startswith("del "):
            return "Permission denied\r\n"
        else:
            return f"{command.split()[0]}: command not found\r\n"

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

                # Check for newline
                if chunk in [b'\n', b'\r']:
                    # Consume any additional CR/LF
                    sock.settimeout(0.1)
                    try:
                        while True:
                            next_char = sock.recv(1)
                            if next_char not in [b'\n', b'\r']:
                                # Put it back (can't really do this, so just ignore)
                                break
                    except socket.timeout:
                        pass

                    sock.settimeout(timeout)
                    return buffer.decode('utf-8', errors='ignore').strip()

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
