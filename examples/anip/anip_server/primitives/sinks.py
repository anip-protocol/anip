"""Checkpoint sink interface and implementations."""
import json
import os
from abc import ABC, abstractmethod
from typing import Any


class CheckpointSink(ABC):
    """Interface for publishing checkpoints to external storage."""

    @abstractmethod
    def publish(self, checkpoint: dict[str, Any]) -> None:
        """Publish a checkpoint. Should be idempotent."""
        ...


class LocalFileSink(CheckpointSink):
    """Writes checkpoints as JSON files to a local directory.

    Reference implementation — not a real external anchor.
    """

    def __init__(self, directory: str) -> None:
        self._directory = directory
        os.makedirs(directory, exist_ok=True)

    def publish(self, checkpoint: dict[str, Any]) -> None:
        filename = f"{checkpoint['checkpoint_id']}.json"
        path = os.path.join(self._directory, filename)
        with open(path, "w") as f:
            json.dump(checkpoint, f, indent=2, sort_keys=True)
