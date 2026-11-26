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
    # Self-hosted webfetcher (e.g. the LAN service technews already uses):
    # tried before Jina/readability when set, since it's LAN-local and keeps
    # fetched URLs off a third-party reader. Expects a GET {url}/md?url=... that
    # returns {"success": bool, "markdown": str, "engine": str}.
    webfetcher_url: str = ""
    # Seconds to wait for /md. The webfetcher service can take ~60 s on a slow
    # page (a 30 s moli attempt, then a 30 s retry), plus queueing behind its
    # concurrency limit; a shorter wait abandons that work and falls through
    # to Jina, handing the URL to the third party after all.
    webfetcher_timeout_s: float = 75.0


class WebToolsConfig(Base):
    """Web tools configuration."""
    enable: bool = True
    use_proxy: bool = False
    user_agent: str | None = None
    search: WebSearchConfig = Field(default_factory=WebSearchConfig)
    fetch: WebFetchConfig = Field(default_factory=WebFetchConfig)
