"""ANIP protocol constants."""

PROTOCOL_VERSION = "anip/0.3"
MANIFEST_VERSION = "0.3.0"
DEFAULT_PROFILE = {
    "core": "1.0",
    "cost": "1.0",
    "capability_graph": "1.0",
    "state_session": "1.0",
    "observability": "1.0",
}
SUPPORTED_ALGORITHMS = ["ES256"]
LEAF_HASH_PREFIX = b"\x00"
NODE_HASH_PREFIX = b"\x01"
