"""
SSH Honeypot Service

Low-interaction SSH honeypot that logs authentication attempts,
captures commands, and simulates a realistic SSH environment.
"""

import asyncio
import socket
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import paramiko
from paramiko import ServerInterface, Transport, AUTH_FAILED, AUTH_SUCCESSFUL
from paramiko.channel import Channel

from honeypot.logging.logger import get_honeypot_logger, create_session_logger
from honeypot.config.config_loader import HoneypotSSHConfig


class SSHServerInterface(ServerInterface):
    """
    Custom SSH server interface for honeypot.

    Handles authentication and channel requests, logging all attempts.
    """

    def __init__(self, session_id: str, source_ip: str, logger):
        """
        Initialize SSH server interface.

        Args:
            session_id: Unique session identifier
            source_ip: Client IP address
            logger: Logger instance
        """
        super().__init__()
        self.session_id = session_id
        self.source_ip = source_ip
        self.logger = logger
        self.auth_attempts: List[Dict[str, Any]] = []

    def check_auth_password(self, username: str, password: str) -> int:
        """
        Check password authentication (always fails for honeypot).

        Args:
            username: Attempted username
            password: Attempted password

        Returns:
            AUTH_FAILED to reject authentication
        """
        self.logger.info(
            "SSH authentication attempt",
            extra={
                "event_type": "auth_attempt",
                "component": "ssh_honeypot",
                "username": username,
                "password": password,
                "auth_method": "password",
                "success": False,
            },
        )

        self.auth_attempts.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "username": username,
                "password": password,
                "method": "password",
                "success": False,
            }
        )

        return AUTH_FAILED

    def check_auth_publickey(self, username: str, key: paramiko.PKey) -> int:
        """
        Check public key authentication (always fails for honeypot).

        Args:
            username: Attempted username
            key: Public key

        Returns:
            AUTH_FAILED to reject authentication
        """
        key_type = key.get_name()
        key_fingerprint = key.get_fingerprint().hex()

        self.logger.info(
            "SSH public key authentication attempt",
            extra={
                "event_type": "auth_attempt",
                "component": "ssh_honeypot",
                "username": username,
                "auth_method": "publickey",
                "key_type": key_type,
                "key_fingerprint": key_fingerprint,
                "success": False,
            },
        )

        self.auth_attempts.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "username": username,
                "method": "publickey",
                "key_type": key_type,
                "key_fingerprint": key_fingerprint,
                "success": False,
            }
        )

        return AUTH_FAILED

    def get_allowed_auths(self, username: str) -> str:
        """
        Get allowed authentication methods.

        Args:
            username: Username

        Returns:
            Comma-separated list of allowed auth methods
        """
        return "password,publickey"

    def check_channel_request(self, kind: str, chanid: int) -> int:
        """
        Check channel request.

        Args:
            kind: Channel kind
            chanid: Channel ID

        Returns:
            OPEN_SUCCEEDED or OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
        """
        self.logger.debug(
            f"Channel request: {kind}",
            extra={
                "event_type": "channel_request",
                "component": "ssh_honeypot",
                "channel_kind": kind,
                "channel_id": chanid,
            },
        )

        if kind == "session":
            return paramiko.OPEN_SUCCEEDED

        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_shell_request(self, channel: Channel) -> bool:
        """
        Check shell request.

        Args:
            channel: SSH channel

        Returns:
            True to accept shell request
        """
        self.logger.info(
            "Shell requested",
            extra={
                "event_type": "shell_request",
                "component": "ssh_honeypot",
            },
        )
        return True

    def check_channel_pty_request(
        self,
        channel: Channel,
        term: bytes,
        width: int,
        height: int,
        pixelwidth: int,
        pixelheight: int,
        modes: bytes,
    ) -> bool:
        """
        Check PTY request.

        Args:
            channel: SSH channel
            term: Terminal type
            width: Terminal width
            height: Terminal height
            pixelwidth: Pixel width
            pixelheight: Pixel height
            modes: Terminal modes

        Returns:
            True to accept PTY request
        """
        self.logger.debug(
            "PTY requested",
            extra={
                "event_type": "pty_request",
                "component": "ssh_honeypot",
                "terminal": term.decode("utf-8", errors="ignore"),
                "dimensions": f"{width}x{height}",
            },
        )
        return True

    def check_channel_exec_request(self, channel: Channel, command: bytes) -> bool:
        """
        Check exec request.

        Args:
            channel: SSH channel
            command: Command to execute

        Returns:
            True to accept exec request
        """
        cmd = command.decode("utf-8", errors="ignore")
        self.logger.info(
            "Command execution requested",
            extra={
                "event_type": "command_exec",
                "component": "ssh_honeypot",
                "command": cmd,
            },
        )
        return True


class SSHHoneypot:
    """
    Low-interaction SSH Honeypot.

    Simulates an SSH server, logs authentication attempts and commands,
    but provides no real shell access.
    """

    # Fake command responses
    FAKE_RESPONSES = {
        "whoami": "root\n",
        "pwd": "/root\n",
        "uname": "Linux\n",
        "uname -a": "Linux ubuntu 5.4.0-42-generic #46-Ubuntu SMP Fri Jul 10 00:24:02 UTC 2020 x86_64 x86_64 x86_64 GNU/Linux\n",
        "id": "uid=0(root) gid=0(root) groups=0(root)\n",
        "hostname": "ubuntu-server\n",
        "ls": "Desktop  Documents  Downloads  Music  Pictures  Videos\n",
        "ls -la": "total 32\ndrwxr-xr-x 6 root root 4096 Nov 19 10:00 .\ndrwxr-xr-x 3 root root 4096 Nov 19 09:00 ..\n-rw-r--r-- 1 root root  220 Nov 19 09:00 .bash_logout\n-rw-r--r-- 1 root root 3771 Nov 19 09:00 .bashrc\ndrwxr-xr-x 2 root root 4096 Nov 19 10:00 Desktop\ndrwxr-xr-x 2 root root 4096 Nov 19 10:00 Documents\n",
    }

    def __init__(self, config: HoneypotSSHConfig, log_dir: Path):
        """
        Initialize SSH honeypot.

        Args:
            config: SSH honeypot configuration
            log_dir: Directory for log files
        """
        self.config = config
        self.log_dir = log_dir
        self.logger = get_honeypot_logger("ssh", log_dir, log_format="json")
        self.running = False
        self.server_socket: Optional[socket.socket] = None
        self.sessions: Dict[str, Dict[str, Any]] = {}

        # Generate or load SSH host key
        self.host_key = self._get_or_create_host_key()

    def _get_or_create_host_key(self) -> paramiko.RSAKey:
        """
        Get or create SSH host key.

        Returns:
            RSA host key
        """
        key_path = self.log_dir / "ssh_host_key.pem"

        if key_path.exists():
            self.logger.info("Loading existing SSH host key")
            return paramiko.RSAKey.from_private_key_file(str(key_path))
        else:
            self.logger.info("Generating new SSH host key")
            key = paramiko.RSAKey.generate(2048)
            key.write_private_key_file(str(key_path))
            return key

    async def start(self) -> None:
        """
        Start the SSH honeypot server.
        """
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.server_socket.bind((self.config.host, self.config.port))
            self.server_socket.listen(100)

            self.logger.info(
                f"SSH honeypot started on {self.config.host}:{self.config.port}",
                extra={
                    "event_type": "honeypot_started",
                    "component": "ssh_honeypot",
                    "host": self.config.host,
                    "port": self.config.port,
                },
            )

            while self.running:
                try:
                    # Accept connections with timeout
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
            self.logger.error(f"Failed to start SSH honeypot: {e}")
            raise
        finally:
            if self.server_socket:
                self.server_socket.close()

    def stop(self) -> None:
        """Stop the SSH honeypot server."""
        self.running = False
        if self.server_socket:
            self.server_socket.close()

        self.logger.info(
            "SSH honeypot stopped",
            extra={"event_type": "honeypot_stopped", "component": "ssh_honeypot"},
        )

    def _handle_connection(self, client_socket: socket.socket, client_addr: tuple) -> None:
        """
        Handle individual SSH connection.

        Args:
            client_socket: Client socket
            client_addr: Client address (ip, port)
        """
        session_id = str(uuid.uuid4())
        source_ip = client_addr[0]
        source_port = client_addr[1]

        session_logger = create_session_logger(self.logger, session_id, source_ip)

        session_logger.info(
            "New SSH connection",
            extra={
                "event_type": "connection_attempt",
                "component": "ssh_honeypot",
                "source_port": source_port,
            },
        )

        # Store session info
        self.sessions[session_id] = {
            "session_id": session_id,
            "source_ip": source_ip,
            "source_port": source_port,
            "start_time": datetime.utcnow().isoformat(),
            "commands": [],
        }

        try:
            # Create SSH transport
            transport = Transport(client_socket)
            transport.add_server_key(self.host_key)
            transport.set_subsystem_handler("sftp", paramiko.SFTPServer)

            # Set banner
            transport.local_version = self.config.banner

            # Create server interface
            server = SSHServerInterface(session_id, source_ip, session_logger)

            # Start SSH server
            transport.start_server(server=server)

            # Wait for authentication
            channel = transport.accept(self.config.session_timeout)

            if channel is not None:
                session_logger.info(
                    "Channel opened",
                    extra={"event_type": "channel_opened", "component": "ssh_honeypot"},
                )

                # Handle commands
                self._handle_channel(channel, session_id, session_logger)

                channel.close()

            # Store auth attempts in session
            self.sessions[session_id]["auth_attempts"] = server.auth_attempts

        except Exception as e:
            session_logger.error(
                f"Error handling connection: {e}",
                extra={"event_type": "connection_error", "component": "ssh_honeypot"},
            )
        finally:
            try:
                transport.close()
                client_socket.close()
            except:
                pass

            # Log session end
            self.sessions[session_id]["end_time"] = datetime.utcnow().isoformat()
            session_logger.info(
                "SSH session ended",
                extra={
                    "event_type": "session_ended",
                    "component": "ssh_honeypot",
                    "session_data": self.sessions[session_id],
                },
            )

    def _handle_channel(self, channel: Channel, session_id: str, logger) -> None:
        """
        Handle SSH channel and process commands.

        Args:
            channel: SSH channel
            session_id: Session identifier
            logger: Session logger
        """
        try:
            # Send fake prompt
            channel.send("root@ubuntu-server:~# ")

            buffer = b""
            while True:
                # Read data with timeout
                if channel.recv_ready():
                    data = channel.recv(1024)
                    if not data:
                        break

                    buffer += data

                    # Check for newline (command submitted)
                    if b"\n" in buffer or b"\r" in buffer:
                        command = buffer.strip().decode("utf-8", errors="ignore")
                        buffer = b""

                        if command:
                            logger.info(
                                f"Command received: {command}",
                                extra={
                                    "event_type": "command_received",
                                    "component": "ssh_honeypot",
                                    "command": command,
                                },
                            )

                            # Store command
                            self.sessions[session_id]["commands"].append(
                                {
                                    "timestamp": datetime.utcnow().isoformat(),
                                    "command": command,
                                }
                            )

                            # Send fake response
                            response = self._get_fake_response(command)
                            channel.send(response)

                        # Send prompt again
                        channel.send("root@ubuntu-server:~# ")

                # Check if channel is still open
                if channel.closed:
                    break

        except Exception as e:
            logger.debug(f"Channel handling error: {e}")

    def _get_fake_response(self, command: str) -> str:
        """
        Get fake response for command.

        Args:
            command: Command string

        Returns:
            Fake response string
        """
        # Check for exact matches
        if command in self.FAKE_RESPONSES:
            return self.FAKE_RESPONSES[command]

        # Check for partial matches
        cmd_lower = command.lower().strip()

        if cmd_lower.startswith("cat ") or cmd_lower.startswith("more "):
            return "Permission denied\n"
        elif cmd_lower.startswith("cd "):
            return ""  # No output for cd
        elif cmd_lower == "exit":
            return "logout\n"
        elif cmd_lower.startswith("wget ") or cmd_lower.startswith("curl "):
            return "Command not found\n"
        else:
            return f"bash: {command.split()[0]}: command not found\n"

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session data by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session data or None if not found
        """
        return self.sessions.get(session_id)

    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """
        Get all session data.

        Returns:
            List of all sessions
        """
        return list(self.sessions.values())
