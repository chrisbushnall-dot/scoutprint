from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SENSITIVE_QUERY_KEYS = {"apikey", "api_key", "api_token", "token", "key"}


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_bytes(content)
    temporary.replace(path)


def write_provenance(path: Path, metadata: dict[str, Any]) -> None:
    payload = (json.dumps(metadata, indent=2, sort_keys=True, default=str) + "\n").encode()
    atomic_write(path.with_suffix(path.suffix + ".meta.json"), payload)


class CachedJsonClient:
    """Credential-safe, retrying JSON downloader with immutable request caching."""

    def __init__(
        self,
        provider: str,
        raw_dir: Path,
        *,
        usage_class: str,
        terms_url: str,
        delay_seconds: float = 0.1,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.provider = provider
        self.raw_dir = raw_dir
        self.usage_class = usage_class
        self.terms_url = terms_url
        self.delay_seconds = delay_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {"Accept": "application/json", "User-Agent": "Scoutprint/0.1 private research"}
        )
        if headers:
            self.session.headers.update(headers)
        retry = Retry(
            total=4,
            connect=4,
            read=4,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
            respect_retry_after_header=True,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    @staticmethod
    def _public_url(url: str, params: dict[str, Any]) -> str:
        safe_params = {
            key: ("<redacted>" if key.lower() in SENSITIVE_QUERY_KEYS else value)
            for key, value in params.items()
        }
        parts = urlsplit(url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(safe_params), ""))

    def get(
        self,
        relative_cache_path: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        force: bool = False,
    ) -> dict[str, Any] | list[Any]:
        destination = self.raw_dir / relative_cache_path
        if destination.exists() and destination.stat().st_size and not force:
            return json.loads(destination.read_text())
        request_params = {key: value for key, value in (params or {}).items() if value is not None}
        response = self.session.get(url, params=request_params, timeout=90)
        response.raise_for_status()
        content = response.content
        payload = response.json()
        atomic_write(destination, content)
        write_provenance(
            destination,
            {
                "provider": self.provider,
                "source_url": self._public_url(url, request_params),
                "terms_url": self.terms_url,
                "usage_class": self.usage_class,
                "storage": "private_vps_only",
                "retrieved_at": datetime.now(UTC).isoformat(),
                "checksum_sha256": sha256_bytes(content),
                "bytes": len(content),
                "http_status": response.status_code,
                "quota": {
                    key: value
                    for key, value in response.headers.items()
                    if any(token in key.lower() for token in ("rate", "quota", "request"))
                },
            },
        )
        time.sleep(self.delay_seconds)
        return payload
