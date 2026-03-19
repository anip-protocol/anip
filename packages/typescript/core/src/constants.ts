export const PROTOCOL_VERSION = "anip/0.11";
export const MANIFEST_VERSION = "0.10.0";
export const DEFAULT_PROFILE = {
  core: "1.0",
  cost: "1.0",
  capability_graph: "1.0",
  state_session: "1.0",
  observability: "1.0",
};
export const SUPPORTED_ALGORITHMS = ["ES256"] as const;
export const LEAF_HASH_PREFIX = 0x00;
export const NODE_HASH_PREFIX = 0x01;
