"""
HP_TI Main Entry Point

Starts honeypot services using the ServiceManager.
Supports SSH, HTTP/HTTPS, Telnet, and FTP honeypots.
"""

import asyncio
import sys
import argparse
from pathlib import Path

from honeypot.service_manager import ServiceManager


async def main():
    """Main entry point."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="HP_TI - Honeypot & Threat Intelligence Platform"
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to configuration file (default: config/config.yaml)",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=Path("logs"),
        help="Log directory (default: logs)",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show service status and exit",
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help="Show health check and exit",
    )
    args = parser.parse_args()

    # Create service manager
    print("Initializing HP_TI Honeypot & Threat Intelligence Platform...")
    manager = ServiceManager(config_path=args.config, log_dir=args.log_dir)

    # Handle status/health check commands
    if args.status:
        status = manager.get_status()
        print("\n=== Service Status ===")
        for service_name, service_status in status.items():
            print(f"\n{service_name.upper()}:")
            for key, value in service_status.items():
                print(f"  {key}: {value}")
        return

    if args.health:
        health = await manager.health_check()
        print("\n=== Health Check ===")
        print(f"Overall Status: {health['overall_status'].upper()}")
        print(f"Timestamp: {health['timestamp']}")
        print("\nServices:")
        for service_name, service_health in health['services'].items():
            status_symbol = "✓" if service_health['status'] == 'healthy' else "✗"
            print(f"  {status_symbol} {service_name}: {service_health['status']}")
            if service_health.get('error'):
                print(f"    Error: {service_health['error']}")
        return

    # Run service manager
    try:
        print(f"Starting honeypot services from: {args.log_dir}")
        print("Press Ctrl+C to stop\n")
        await manager.run()
    except KeyboardInterrupt:
        print("\n\nShutdown requested...")
    except Exception as e:
        print(f"\nFatal error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        print("HP_TI shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete")
        sys.exit(0)
