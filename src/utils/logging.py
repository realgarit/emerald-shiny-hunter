"""
Logging utilities for Pokemon Emerald Shiny Hunter.

Provides a Tee class for dual output to console and log file.
"""

import sys
from datetime import datetime
from pathlib import Path


class Tee:
    """
    Write to multiple file-like objects simultaneously.

    Used to output to both console and log file at the same time.
    """

    def __init__(self, *files):
        self.files = files

    def write(self, obj):
        for f in self.files:
            f.write(obj)
            f.flush()

    def flush(self):
        for f in self.files:
            f.flush()

    def isatty(self):
        # Return True so print() doesn't add extra newlines
        return True


class LogManager:
    """
    Manages logging to both console and file.

    Usage:
        log_manager = LogManager(log_dir, "route101_hunt")
        # ... do stuff ...
        log_manager.cleanup()
    """

    def __init__(self, log_dir: Path, prefix: str = "shiny_hunt"):
        """
        Initialize logging to file and console.

        Args:
            log_dir: Directory to store log files
            prefix: Prefix for log filename
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"{prefix}_{timestamp}.log"

        self.log_file_handle = open(self.log_file, 'w', encoding='utf-8')
        self.original_stdout = sys.stdout
        sys.stdout = Tee(sys.stdout, self.log_file_handle)

    def get_log_path(self) -> Path:
        """Return the path to the current log file."""
        return self.log_file

    def cleanup(self):
        """Restore stdout and close log file."""
        if hasattr(self, 'log_file_handle') and self.log_file_handle:
            sys.stdout = self.original_stdout
            self.log_file_handle.close()
            self.log_file_handle = None
