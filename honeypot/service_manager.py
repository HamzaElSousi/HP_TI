"""
Service manager for HP_TI honeypot services.

Orchestrates multiple honeypot services (SSH, HTTP, Telnet, FTP) with
unified start/stop, health monitoring, and graceful shutdown.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from honeypot.config.config_loader import load_config, HoneypotConfig
from honeypot.logging.logger import get_honeypot_logger
from honeypot.services.ssh_honeypot import SSHHoneypot
from honeypot.services.http_honeypot import HTTPHoneypot
from honeypot.services.telnet_honeypot import TelnetHoneypot
from honeypot.services.ftp_honeypot import FTPHoneypot

logger = logging.getLogger(__name__)


class ServiceStatus:
    """Status of a honeypot service."""

    def __init__(self, name: str):
        self.name = name
        self.running = False
        self.start_time: Optional[datetime] = None
        self.stop_time: Optional[datetime] = None
        self.error: Optional[str] = None
        self.task: Optional[asyncio.Task] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert status to dictionary."""
        return {
            "name": self.name,
            "running": self.running,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "stop_time": self.stop_time.isoformat() if self.stop_time else None,
            "uptime_seconds": (
                (datetime.utcnow() - self.start_time).total_seconds()
                if self.start_time and self.running
                else None
            ),
            "error": self.error,
        }


class ServiceManager:
    """
    Manages all honeypot services.

    Coordinates starting, stopping, and monitoring of SSH, HTTP, Telnet,
    and FTP honeypot services.
    """

    def __init__(self, config_path: Optional[Path] = None, log_dir: Optional[Path] = None):
        """
        Initialize service manager.

        Args:
            config_path: Path to configuration file
            log_dir: Directory for log files
        """
        # Load configuration
        self.config = load_config(config_path)
        self.log_dir = log_dir or Path("logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Initialize logger
        self.logger = get_honeypot_logger("service_manager", self.log_dir, log_format="json")

        # Service instances
        self.services: Dict[str, Any] = {}
        self.status: Dict[str, ServiceStatus] = {}

        # Initialize services
        self._init_services()

        # Shutdown flag
        self.shutdown_requested = False

    def _init_services(self) -> None:
        """Initialize all honeypot services based on configuration."""
        # SSH honeypot
        if self.config.ssh.enabled:
            self.services["ssh"] = SSHHoneypot(self.config.ssh, self.log_dir)
            self.status["ssh"] = ServiceStatus("ssh")
            self.logger.info("SSH honeypot initialized")

        # HTTP honeypot
        if self.config.http.enabled:
            self.services["http"] = HTTPHoneypot(self.config.http, self.log_dir)
            self.status["http"] = ServiceStatus("http")
            self.logger.info("HTTP honeypot initialized")

        # Telnet honeypot
        if self.config.telnet.enabled:
            self.services["telnet"] = TelnetHoneypot(self.config.telnet, self.log_dir)
            self.status["telnet"] = ServiceStatus("telnet")
            self.logger.info("Telnet honeypot initialized")

        # FTP honeypot
        if self.config.ftp.enabled:
            self.services["ftp"] = FTPHoneypot(self.config.ftp, self.log_dir)
            self.status["ftp"] = ServiceStatus("ftp")
            self.logger.info("FTP honeypot initialized")

        if not self.services:
            self.logger.warning("No honeypot services enabled in configuration")

    async def start_all(self) -> None:
        """Start all enabled honeypot services."""
        self.logger.info(
            f"Starting {len(self.services)} honeypot services",
            extra={
                "event_type": "services_starting",
                "component": "service_manager",
                "service_count": len(self.services),
                "services": list(self.services.keys()),
            },
        )

        # Start all services concurrently
        tasks = []
        for name, service in self.services.items():
            task = asyncio.create_task(self._start_service(name, service))
            tasks.append(task)

        # Wait for all services to start
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log results
        success_count = sum(1 for r in results if r is True)
        self.logger.info(
            f"Started {success_count}/{len(self.services)} services successfully",
            extra={
                "event_type": "services_started",
                "component": "service_manager",
                "success_count": success_count,
                "total_count": len(self.services),
            },
        )

    async def _start_service(self, name: str, service: Any) -> bool:
        """
        Start a single honeypot service.

        Args:
            name: Service name
            service: Service instance

        Returns:
            True if started successfully, False otherwise
        """
        try:
            self.logger.info(f"Starting {name} honeypot service")
            status = self.status[name]

            # Create service task
            status.task = asyncio.create_task(service.start())
            status.running = True
            status.start_time = datetime.utcnow()
            status.error = None

            self.logger.info(
                f"{name} honeypot service started",
                extra={
                    "event_type": "service_started",
                    "component": "service_manager",
                    "service": name,
                },
            )
            return True

        except Exception as e:
            self.logger.error(
                f"Failed to start {name} honeypot service: {e}",
                extra={
                    "event_type": "service_start_failed",
                    "component": "service_manager",
                    "service": name,
                    "error": str(e),
                },
                exc_info=True,
            )
            self.status[name].error = str(e)
            self.status[name].running = False
            return False

    async def stop_all(self) -> None:
        """Stop all running honeypot services."""
        self.logger.info(
            "Stopping all honeypot services",
            extra={
                "event_type": "services_stopping",
                "component": "service_manager",
            },
        )

        # Stop all services concurrently
        tasks = []
        for name, service in self.services.items():
            if self.status[name].running:
                task = asyncio.create_task(self._stop_service(name, service))
                tasks.append(task)

        # Wait for all services to stop
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self.logger.info(
            "All honeypot services stopped",
            extra={
                "event_type": "services_stopped",
                "component": "service_manager",
            },
        )

    async def _stop_service(self, name: str, service: Any) -> None:
        """
        Stop a single honeypot service.

        Args:
            name: Service name
            service: Service instance
        """
        try:
            self.logger.info(f"Stopping {name} honeypot service")
            status = self.status[name]

            # Stop the service
            service.stop()

            # Cancel the task if it exists
            if status.task and not status.task.done():
                status.task.cancel()
                try:
                    await status.task
                except asyncio.CancelledError:
                    pass

            status.running = False
            status.stop_time = datetime.utcnow()

            self.logger.info(
                f"{name} honeypot service stopped",
                extra={
                    "event_type": "service_stopped",
                    "component": "service_manager",
                    "service": name,
                },
            )

        except Exception as e:
            self.logger.error(
                f"Error stopping {name} honeypot service: {e}",
                extra={
                    "event_type": "service_stop_error",
                    "component": "service_manager",
                    "service": name,
                    "error": str(e),
                },
            )

    async def restart_service(self, name: str) -> bool:
        """
        Restart a specific honeypot service.

        Args:
            name: Service name

        Returns:
            True if restarted successfully, False otherwise
        """
        if name not in self.services:
            self.logger.error(f"Service {name} not found")
            return False

        self.logger.info(f"Restarting {name} honeypot service")

        # Stop the service
        await self._stop_service(name, self.services[name])

        # Wait a moment
        await asyncio.sleep(1)

        # Start the service
        return await self._start_service(name, self.services[name])

    def get_status(self, name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get status of honeypot services.

        Args:
            name: Optional service name (if None, returns all)

        Returns:
            Status dictionary
        """
        if name:
            if name in self.status:
                return self.status[name].to_dict()
            else:
                return {"error": f"Service {name} not found"}
        else:
            return {
                name: status.to_dict() for name, status in self.status.items()
            }

    def get_service_list(self) -> List[str]:
        """
        Get list of all configured services.

        Returns:
            List of service names
        """
        return list(self.services.keys())

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on all services.

        Returns:
            Health status dictionary
        """
        health = {
            "overall_status": "healthy",
            "services": {},
            "timestamp": datetime.utcnow().isoformat(),
        }

        unhealthy_count = 0

        for name, status in self.status.items():
            service_health = {
                "status": "healthy" if status.running else "unhealthy",
                "running": status.running,
                "error": status.error,
            }

            if not status.running:
                unhealthy_count += 1

            health["services"][name] = service_health

        if unhealthy_count == len(self.services):
            health["overall_status"] = "critical"
        elif unhealthy_count > 0:
            health["overall_status"] = "degraded"

        return health

    async def monitor_services(self, interval: int = 60) -> None:
        """
        Monitor services and restart if they fail.

        Args:
            interval: Check interval in seconds
        """
        self.logger.info(
            f"Starting service monitoring (interval: {interval}s)",
            extra={
                "event_type": "monitoring_started",
                "component": "service_manager",
                "interval": interval,
            },
        )

        while not self.shutdown_requested:
            try:
                # Check each service
                for name, status in self.status.items():
                    # If service should be running but task is done, restart it
                    if status.running and status.task and status.task.done():
                        exception = status.task.exception() if not status.task.cancelled() else None

                        if exception:
                            self.logger.error(
                                f"{name} service failed: {exception}",
                                extra={
                                    "event_type": "service_failed",
                                    "component": "service_manager",
                                    "service": name,
                                    "error": str(exception),
                                },
                            )
                            status.error = str(exception)

                        self.logger.warning(f"{name} service stopped unexpectedly, restarting...")
                        await self.restart_service(name)

                # Wait before next check
                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Monitoring error: {e}", exc_info=True)
                await asyncio.sleep(interval)

        self.logger.info("Service monitoring stopped")

    async def run(self) -> None:
        """Run the service manager with monitoring and signal handling."""
        # Set up signal handlers
        loop = asyncio.get_running_loop()

        def signal_handler(sig):
            self.logger.info(f"Received signal {sig}, initiating shutdown")
            self.shutdown_requested = True

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))

        try:
            # Start all services
            await self.start_all()

            # Start monitoring
            monitor_task = asyncio.create_task(self.monitor_services())

            # Wait for shutdown signal
            while not self.shutdown_requested:
                await asyncio.sleep(1)

            # Cancel monitoring
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

        finally:
            # Stop all services
            await self.stop_all()

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics for all services.

        Returns:
            Dictionary with service statistics
        """
        stats = {
            "total_services": len(self.services),
            "running_services": sum(1 for s in self.status.values() if s.running),
            "stopped_services": sum(1 for s in self.status.values() if not s.running),
            "services": {},
        }

        for name, service in self.services.items():
            service_stats = {
                "status": self.status[name].to_dict(),
            }

            # Get service-specific stats if available
            if hasattr(service, "get_sessions"):
                sessions = service.get_sessions()
                service_stats["total_sessions"] = len(sessions)

            stats["services"][name] = service_stats

        return stats


async def main():
    """Main entry point for service manager."""
    # Parse command line arguments
    import argparse

    parser = argparse.ArgumentParser(description="HP_TI Honeypot Service Manager")
    parser.add_argument(
        "--config", type=Path, help="Path to configuration file"
    )
    parser.add_argument(
        "--log-dir", type=Path, default=Path("logs"), help="Log directory"
    )
    args = parser.parse_args()

    # Create service manager
    manager = ServiceManager(config_path=args.config, log_dir=args.log_dir)

    # Run service manager
    await manager.run()


if __name__ == "__main__":
    asyncio.run(main())
