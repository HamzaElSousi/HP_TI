"""
Log collector for HP_TI.

Monitors honeypot log files and processes new entries in real-time.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional, Callable, List
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent
import time

logger = logging.getLogger(__name__)


class LogFileHandler(FileSystemEventHandler):
    """
    File system event handler for log files.

    Monitors log files for modifications and triggers processing.
    """

    def __init__(self, callback: Callable[[str, List[str]], None]):
        """
        Initialize log file handler.

        Args:
            callback: Function to call with (file_path, new_lines)
        """
        super().__init__()
        self.callback = callback
        self.file_positions: dict[str, int] = {}
        self.logger = logging.getLogger(f"{__name__}.LogFileHandler")

    def on_modified(self, event):
        """
        Handle file modification event.

        Args:
            event: File system event
        """
        if event.is_directory:
            return

        # Only process .log files
        if not event.src_path.endswith(".log"):
            return

        self.logger.debug(f"File modified: {event.src_path}")
        self._process_file(event.src_path)

    def _process_file(self, file_path: str) -> None:
        """
        Process new lines from a modified log file.

        Args:
            file_path: Path to log file
        """
        try:
            # Get current file size
            current_size = Path(file_path).stat().st_size

            # Get last known position
            last_position = self.file_positions.get(file_path, 0)

            # Read new lines if file has grown
            if current_size > last_position:
                with open(file_path, "r", encoding="utf-8") as f:
                    # Seek to last position
                    f.seek(last_position)

                    # Read new lines
                    new_lines = f.readlines()

                    # Update position
                    self.file_positions[file_path] = f.tell()

                # Process new lines if any
                if new_lines:
                    self.logger.info(
                        f"Found {len(new_lines)} new lines in {file_path}"
                    )
                    self.callback(file_path, new_lines)

            # Handle file truncation (rotation)
            elif current_size < last_position:
                self.logger.info(f"File truncated/rotated: {file_path}")
                self.file_positions[file_path] = 0
                self._process_file(file_path)  # Reprocess from start

        except Exception as e:
            self.logger.error(f"Error processing file {file_path}: {e}", exc_info=True)

    def initialize_files(self, directory: Path) -> None:
        """
        Initialize tracking for existing log files.

        Args:
            directory: Directory containing log files
        """
        for log_file in directory.glob("*.log"):
            try:
                # Set initial position to end of file
                file_size = log_file.stat().st_size
                self.file_positions[str(log_file)] = file_size
                self.logger.debug(
                    f"Initialized tracking for {log_file} at position {file_size}"
                )
            except Exception as e:
                self.logger.error(f"Error initializing {log_file}: {e}")


class LogCollector:
    """
    Log collector that monitors honeypot log directories.

    Uses file system events to detect new log entries and process them.
    """

    def __init__(
        self, log_directory: Path, process_callback: Callable[[str, List[str]], None]
    ):
        """
        Initialize log collector.

        Args:
            log_directory: Directory to monitor for log files
            process_callback: Function to call with (file_path, new_lines)
        """
        self.log_directory = Path(log_directory)
        self.process_callback = process_callback
        self.observer: Optional[Observer] = None
        self.handler: Optional[LogFileHandler] = None
        self.logger = logging.getLogger(f"{__name__}.LogCollector")

        # Ensure directory exists
        self.log_directory.mkdir(parents=True, exist_ok=True)

    def start(self) -> None:
        """Start monitoring log directory."""
        # Create file system event handler
        self.handler = LogFileHandler(self.process_callback)

        # Initialize existing files
        self.handler.initialize_files(self.log_directory)

        # Create and start observer
        self.observer = Observer()
        self.observer.schedule(
            self.handler, str(self.log_directory), recursive=False
        )
        self.observer.start()

        self.logger.info(f"Log collector started, monitoring {self.log_directory}")

    def stop(self) -> None:
        """Stop monitoring log directory."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.logger.info("Log collector stopped")

    async def run_async(self) -> None:
        """
        Run log collector asynchronously.

        Keeps the collector running until stopped.
        """
        self.start()

        try:
            # Keep running until interrupted
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            self.logger.info("Log collector cancelled")
        finally:
            self.stop()


class BatchProcessor:
    """
    Batches log entries for efficient processing.

    Accumulates entries and flushes them periodically or when batch size is reached.
    """

    def __init__(
        self,
        batch_size: int = 100,
        flush_interval: float = 10.0,
        process_callback: Callable[[List[str]], None] = None,
    ):
        """
        Initialize batch processor.

        Args:
            batch_size: Maximum batch size before auto-flush
            flush_interval: Maximum time between flushes (seconds)
            process_callback: Function to call with batched entries
        """
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.process_callback = process_callback
        self.buffer: List[str] = []
        self.last_flush_time = time.time()
        self.logger = logging.getLogger(f"{__name__}.BatchProcessor")
        self._lock = asyncio.Lock()

    async def add(self, entry: str) -> None:
        """
        Add entry to batch.

        Args:
            entry: Log entry to add
        """
        async with self._lock:
            self.buffer.append(entry)

            # Check if we should flush
            should_flush = (
                len(self.buffer) >= self.batch_size
                or (time.time() - self.last_flush_time) >= self.flush_interval
            )

            if should_flush:
                await self.flush()

    async def flush(self) -> None:
        """Flush buffered entries."""
        async with self._lock:
            if not self.buffer:
                return

            batch = self.buffer.copy()
            self.buffer.clear()
            self.last_flush_time = time.time()

            self.logger.debug(f"Flushing batch of {len(batch)} entries")

        # Process batch outside of lock
        if self.process_callback:
            try:
                self.process_callback(batch)
            except Exception as e:
                self.logger.error(f"Error processing batch: {e}", exc_info=True)

    async def run_periodic_flush(self) -> None:
        """
        Run periodic flush in background.

        Flushes buffer at regular intervals even if not full.
        """
        try:
            while True:
                await asyncio.sleep(self.flush_interval)
                await self.flush()
        except asyncio.CancelledError:
            # Flush any remaining entries before stopping
            await self.flush()
            self.logger.info("Batch processor stopped")
