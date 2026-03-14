"""Checkpoint sink interface and implementations."""
import json
import os
from abc import ABC, abstractmethod
from typing import Any


class CheckpointSink(ABC):
    """Interface for publishing signed checkpoints to external storage."""

    @abstractmethod
    def publish(self, signed_checkpoint: dict[str, Any]) -> None:
        """Publish a signed checkpoint (body + detached JWS signature)."""
        ...


class LocalFileSink(CheckpointSink):
    """Writes signed checkpoints as JSON files to a local directory."""

    def __init__(self, directory: str) -> None:
        self._directory = directory
        os.makedirs(directory, exist_ok=True)

    def publish(self, signed_checkpoint: dict[str, Any]) -> None:
        body = signed_checkpoint["body"]
        filename = f"{body['checkpoint_id']}.json"
        path = os.path.join(self._directory, filename)
        with open(path, "w") as f:
            json.dump(signed_checkpoint, f, indent=2, sort_keys=True)
