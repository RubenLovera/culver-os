"""
connectors/base.py — Abstract base class for CulverOS connectors.

A connector reads data from an external source and deposits files into
the agent vault's raw/ directory, making them available for vault-ingest.py.

To build a connector:
1. Subclass BaseConnector
2. Implement name(), validate_config(), and run()
3. Place your connector in connectors/{connector_name}.py
4. Add it to config.json under connectors.enabled[]
5. See connectors/README.md for details and examples
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class DepositedFile:
    """Represents a file deposited in raw/ by a connector."""
    path: str           # Relative path within agent vault raw/ dir
    content: str        # File content
    source_url: str = ""  # Original URL or identifier (for frontmatter)
    title: str = ""     # Human-readable title


class BaseConnector(ABC):

    @abstractmethod
    def name(self) -> str:
        """Return the connector's identifier (e.g. 'obsidian_sync')."""

    @abstractmethod
    def validate_config(self, config: dict) -> bool:
        """
        Validate that the connector's config section is complete.
        Called before run(). Return False to abort run with a clear error.
        """

    @abstractmethod
    def run(self, config: dict, raw_dir: str) -> list[DepositedFile]:
        """
        Read from external source, write files to raw_dir, return list of deposited files.

        config:   the connector's section from config.json
        raw_dir:  absolute path to the agent vault's raw/ directory

        Each deposited file should be written to disk AND returned in the list
        so vault-ingest.py can track what's new.
        """
