"""
HP_TI Main Entry Point

Starts honeypot services based on configuration.
"""

import asyncio
import sys
from pathlib import Path
import signal
from typing import List

from honeypot.config.config_loader import get_config
from honeypot.services.ssh_honeypot import SSHHoneypot
from honeypot.logging.logger import setup_logger


class HoneypotManager:
    """
    Manager for all honeypot services.

    Handles starting, stopping, and coordinating multiple honeypot instances.
    """

    def __init__(self):
        """Initialize honeypot manager."""
        self.config = get_config()
        self.logger = setup_logger(
            "hp_ti.manager",
            level=self.config.logging.level,
            log_format=self.config.logging.format,
        )
        self.honeypots: List = []
        self.running = False

    async def start(self) -> None:
        """Start all enabled honeypot services."""
        self.logger.info("Starting HP_TI Honeypot Manager")
        self.logger.info(f"Environment: {self.config.app.environment}")

        log_dir = Path(self.config.logging.dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        # Start SSH honeypot if enabled
        if self.config.ssh.enabled:
            self.logger.info("Initializing SSH honeypot")
            ssh_honeypot = SSHHoneypot(self.config.ssh, log_dir)
            self.honeypots.append(("ssh", ssh_honeypot))

        # Start all honeypots
        tasks = []
        for name, honeypot in self.honeypots:
            self.logger.info(f"Starting {name} honeypot")
            task = asyncio.create_task(honeypot.start())
            tasks.append(task)

        if not tasks:
            self.logger.warning("No honeypots enabled in configuration")
            return

        self.running = True
        self.logger.info(f"Started {len(tasks)} honeypot service(s)")

        # Wait for all honeypots
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            self.logger.info("Honeypot manager shutting down")
        except Exception as e:
            self.logger.error(f"Error in honeypot manager: {e}", exc_info=True)

    def stop(self) -> None:
        """Stop all honeypot services."""
        self.logger.info("Stopping all honeypots")

        for name, honeypot in self.honeypots:
            try:
                self.logger.info(f"Stopping {name} honeypot")
                honeypot.stop()
            except Exception as e:
                self.logger.error(f"Error stopping {name} honeypot: {e}")

        self.running = False
        self.logger.info("HP_TI Honeypot Manager stopped")


def signal_handler(signum, frame):
    """
    Handle shutdown signals.

    Args:
        signum: Signal number
        frame: Current stack frame
    """
    print("\nReceived shutdown signal, stopping honeypots...")
    sys.exit(0)


async def main():
    """Main entry point."""
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create and start manager
    manager = HoneypotManager()

    try:
        await manager.start()
    except KeyboardInterrupt:
        print("\nShutdown requested...")
    except Exception as e:
        manager.logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        manager.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete")
        sys.exit(0)
