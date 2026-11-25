"""Web configuration shared by search/fetch tools and the root schema."""

from pydantic import Field

from nanobot.config_base import Base


class WebSearchConfig(Base):
    """Web search configuration."""
    provider: str = "duckduckgo"
    api_key: str = ""
    base_url: str = ""
    max_results: int = 5
    timeout: int = 30


class WebFetchConfig(Base):
    """Web fetch tool configuration."""
    use_jina_reader: bool = True
    # Self-hosted webfetcher (e.g. the GPU-BEAST service technews already uses):
    # tried before Jina/readability when set, since it's LAN-local and keeps
    # fetched URLs off a third-party reader. Expects a GET {url}/md?url=... that
    # returns {"success": bool, "markdown": str, "engine": str}.
    webfetcher_url: str = ""


class WebToolsConfig(Base):
    """Web tools configuration."""
    enable: bool = True
    use_proxy: bool = False
    user_agent: str | None = None
    search: WebSearchConfig = Field(default_factory=WebSearchConfig)
    fetch: WebFetchConfig = Field(default_factory=WebFetchConfig)
