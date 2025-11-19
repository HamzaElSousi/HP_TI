"""
Pattern detector for HP_TI.

Detects attack patterns and correlates events across sessions and IPs.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AttackPattern:
    """Represents a detected attack pattern."""

    pattern_type: str
    severity: str
    description: str
    indicators: Dict[str, Any]
    first_seen: datetime
    last_seen: datetime
    occurrence_count: int
    confidence_score: float


class PatternDetector:
    """
    Detects attack patterns from honeypot data.

    Identifies coordinated attacks, brute force attempts, and other patterns.
    """

    def __init__(self, time_window: int = 600):
        """
        Initialize pattern detector.

        Args:
            time_window: Time window in seconds for pattern detection
        """
        self.time_window = time_window
        self.logger = logging.getLogger(__name__)

        # Tracking data structures
        self.ip_activity: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.credential_usage: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)
        self.command_sequences: Dict[str, List[str]] = defaultdict(list)

    def analyze_session(self, session_data: Dict[str, Any]) -> List[AttackPattern]:
        """
        Analyze a session for attack patterns.

        Args:
            session_data: Session data dictionary with auth attempts and commands

        Returns:
            List of detected attack patterns
        """
        patterns = []

        # Extract session info
        source_ip = session_data.get("source_ip")
        auth_attempts = session_data.get("auth_attempts", [])
        commands = session_data.get("commands", [])

        # Detect brute force
        if len(auth_attempts) > 5:
            pattern = self._detect_brute_force(source_ip, auth_attempts)
            if pattern:
                patterns.append(pattern)

        # Detect credential stuffing
        if auth_attempts:
            pattern = self._detect_credential_stuffing(source_ip, auth_attempts)
            if pattern:
                patterns.append(pattern)

        # Detect reconnaissance
        if commands:
            pattern = self._detect_reconnaissance(source_ip, commands)
            if pattern:
                patterns.append(pattern)

        # Detect automated attack tools
        if commands:
            pattern = self._detect_automated_tools(commands)
            if pattern:
                patterns.append(pattern)

        return patterns

    def _detect_brute_force(
        self, ip: str, auth_attempts: List[Dict[str, Any]]
    ) -> Optional[AttackPattern]:
        """
        Detect brute force authentication attempts.

        Args:
            ip: Source IP address
            auth_attempts: List of authentication attempts

        Returns:
            AttackPattern if detected, None otherwise
        """
        if len(auth_attempts) < 5:
            return None

        # Get unique credentials
        credentials = set(
            (a.get("username"), a.get("password"))
            for a in auth_attempts
            if a.get("username") and a.get("password")
        )

        # Calculate attempt rate
        if len(auth_attempts) >= 2:
            first_attempt = auth_attempts[0].get("timestamp")
            last_attempt = auth_attempts[-1].get("timestamp")

            if isinstance(first_attempt, str):
                first_attempt = datetime.fromisoformat(first_attempt.replace("Z", "+00:00"))
            if isinstance(last_attempt, str):
                last_attempt = datetime.fromisoformat(last_attempt.replace("Z", "+00:00"))

            duration = (last_attempt - first_attempt).total_seconds()
            rate = len(auth_attempts) / max(duration, 1)
        else:
            rate = 0

        # Determine severity
        if len(auth_attempts) > 50:
            severity = "critical"
        elif len(auth_attempts) > 20:
            severity = "high"
        elif len(auth_attempts) > 10:
            severity = "medium"
        else:
            severity = "low"

        return AttackPattern(
            pattern_type="brute_force",
            severity=severity,
            description=f"Brute force attack from {ip} with {len(auth_attempts)} attempts",
            indicators={
                "source_ip": ip,
                "attempt_count": len(auth_attempts),
                "unique_credentials": len(credentials),
                "attempt_rate_per_second": round(rate, 2),
                "usernames": list(set(a.get("username") for a in auth_attempts)),
            },
            first_seen=auth_attempts[0].get("timestamp"),
            last_seen=auth_attempts[-1].get("timestamp"),
            occurrence_count=len(auth_attempts),
            confidence_score=min(100.0, len(auth_attempts) * 2),
        )

    def _detect_credential_stuffing(
        self, ip: str, auth_attempts: List[Dict[str, Any]]
    ) -> Optional[AttackPattern]:
        """
        Detect credential stuffing attacks.

        Credential stuffing uses known username/password pairs from breaches.

        Args:
            ip: Source IP address
            auth_attempts: List of authentication attempts

        Returns:
            AttackPattern if detected, None otherwise
        """
        # Look for common patterns in credential stuffing
        # - Few retry attempts per credential
        # - Many different credentials
        # - Low rate (slower than brute force)

        credentials = [
            (a.get("username"), a.get("password"))
            for a in auth_attempts
            if a.get("username") and a.get("password")
        ]

        if len(credentials) < 10:
            return None

        # Count attempts per credential
        cred_counts = Counter(credentials)

        # Credential stuffing typically tries each credential only once or twice
        max_retries = max(cred_counts.values())
        if max_retries > 3:
            return None  # Likely brute force instead

        # High number of unique credentials with low retry count
        unique_ratio = len(cred_counts) / len(credentials)
        if unique_ratio < 0.7:
            return None

        return AttackPattern(
            pattern_type="credential_stuffing",
            severity="high",
            description=f"Credential stuffing from {ip} with {len(cred_counts)} unique credentials",
            indicators={
                "source_ip": ip,
                "total_attempts": len(credentials),
                "unique_credentials": len(cred_counts),
                "max_retries_per_credential": max_retries,
                "sample_usernames": list(set(a.get("username") for a in auth_attempts[:10])),
            },
            first_seen=auth_attempts[0].get("timestamp"),
            last_seen=auth_attempts[-1].get("timestamp"),
            occurrence_count=len(credentials),
            confidence_score=unique_ratio * 100,
        )

    def _detect_reconnaissance(
        self, ip: str, commands: List[Dict[str, Any]]
    ) -> Optional[AttackPattern]:
        """
        Detect reconnaissance activity.

        Looks for information gathering commands.

        Args:
            ip: Source IP address
            commands: List of executed commands

        Returns:
            AttackPattern if detected, None otherwise
        """
        # Common reconnaissance commands
        recon_commands = {
            "whoami", "id", "uname", "hostname", "pwd", "ls", "cat /etc/passwd",
            "cat /proc/version", "ifconfig", "ip addr", "netstat", "ps aux",
            "w", "who", "last", "env", "printenv"
        }

        command_list = [c.get("command", "") for c in commands]
        recon_matches = []

        for cmd in command_list:
            cmd_lower = cmd.lower().strip()
            if any(recon_cmd in cmd_lower for recon_cmd in recon_commands):
                recon_matches.append(cmd)

        if len(recon_matches) < 3:
            return None

        return AttackPattern(
            pattern_type="reconnaissance",
            severity="medium",
            description=f"Reconnaissance activity from {ip}",
            indicators={
                "source_ip": ip,
                "recon_commands": recon_matches,
                "total_commands": len(command_list),
                "recon_percentage": round(len(recon_matches) / len(command_list) * 100, 1),
            },
            first_seen=commands[0].get("timestamp"),
            last_seen=commands[-1].get("timestamp"),
            occurrence_count=len(recon_matches),
            confidence_score=min(100.0, len(recon_matches) * 10),
        )

    def _detect_automated_tools(
        self, commands: List[Dict[str, Any]]
    ) -> Optional[AttackPattern]:
        """
        Detect usage of automated attack tools.

        Looks for command patterns typical of automated tools.

        Args:
            commands: List of executed commands

        Returns:
            AttackPattern if detected, None otherwise
        """
        command_list = [c.get("command", "") for c in commands]

        # Signatures of common attack tools
        tool_signatures = {
            "metasploit": ["meterpreter", "msf", "payload"],
            "nmap": ["nmap", "ncat", "nc -"],
            "wget_curl": ["wget", "curl http"],
            "reverse_shell": ["bash -i", "/bin/sh", "/bin/bash", "nc -e"],
            "privilege_escalation": ["sudo -s", "su -", "sudo su"],
        }

        detected_tools = []

        for tool_name, signatures in tool_signatures.items():
            for cmd in command_list:
                cmd_lower = cmd.lower()
                if any(sig in cmd_lower for sig in signatures):
                    detected_tools.append(tool_name)
                    break

        if not detected_tools:
            return None

        return AttackPattern(
            pattern_type="automated_tools",
            severity="high",
            description=f"Automated attack tools detected: {', '.join(detected_tools)}",
            indicators={
                "detected_tools": detected_tools,
                "total_commands": len(command_list),
                "suspicious_commands": [
                    cmd for cmd in command_list
                    if any(
                        sig in cmd.lower()
                        for sigs in tool_signatures.values()
                        for sig in sigs
                    )
                ],
            },
            first_seen=commands[0].get("timestamp"),
            last_seen=commands[-1].get("timestamp"),
            occurrence_count=len(detected_tools),
            confidence_score=min(100.0, len(detected_tools) * 30),
        )

    def detect_distributed_attack(
        self, sessions: List[Dict[str, Any]]
    ) -> Optional[AttackPattern]:
        """
        Detect distributed/coordinated attacks.

        Looks for same credentials or patterns across multiple IPs.

        Args:
            sessions: List of session data dictionaries

        Returns:
            AttackPattern if detected, None otherwise
        """
        if len(sessions) < 3:
            return None

        # Group by credentials
        cred_to_ips: Dict[tuple, set] = defaultdict(set)

        for session in sessions:
            source_ip = session.get("source_ip")
            auth_attempts = session.get("auth_attempts", [])

            for attempt in auth_attempts:
                username = attempt.get("username")
                password = attempt.get("password")
                if username and password:
                    cred_to_ips[(username, password)].add(source_ip)

        # Find credentials used by multiple IPs
        distributed_creds = {
            cred: ips for cred, ips in cred_to_ips.items() if len(ips) >= 3
        }

        if not distributed_creds:
            return None

        # Get all involved IPs
        all_ips = set()
        for ips in distributed_creds.values():
            all_ips.update(ips)

        return AttackPattern(
            pattern_type="distributed_attack",
            severity="critical",
            description=f"Distributed attack from {len(all_ips)} IPs using {len(distributed_creds)} common credentials",
            indicators={
                "ip_count": len(all_ips),
                "source_ips": list(all_ips),
                "common_credentials": [
                    {"username": u, "password": p[:3] + "***", "ip_count": len(ips)}
                    for (u, p), ips in list(distributed_creds.items())[:10]
                ],
            },
            first_seen=min(s.get("start_time") for s in sessions),
            last_seen=max(s.get("start_time") for s in sessions),
            occurrence_count=len(distributed_creds),
            confidence_score=min(100.0, len(all_ips) * 10),
        )
