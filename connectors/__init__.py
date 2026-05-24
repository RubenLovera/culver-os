from connectors.obsidian_sync import ObsidianSyncConnector
from connectors.github import GitHubConnector
from connectors.notion import NotionConnector
from connectors.granola import GranolaConnector

REGISTRY: dict[str, type] = {
    "obsidian_sync": ObsidianSyncConnector,
    "github": GitHubConnector,
    "notion": NotionConnector,
    "granola": GranolaConnector,
}
