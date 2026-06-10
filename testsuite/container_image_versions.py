"""Container registry client for resolving image digests to version tags."""

import logging
import re
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

SEMVER_PATTERN = re.compile(r"^v?\d+\.\d+\.\d+$")

MANIFEST_ACCEPT = ", ".join(
    [
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
    ]
)

MANIFEST_LIST_TYPES = {
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.index.v1+json",
}

_AUTH_URLS = {
    "quay.io": "https://quay.io/v2/auth?service=quay.io&scope=repository:{repo}:pull",
    "ghcr.io": "https://ghcr.io/token?service=ghcr.io&scope=repository:{repo}:pull",
}

_REGISTRY_ALIASES = {
    "docker.dragonflydb.io": "ghcr.io",
}

MAX_TAGS_TO_CHECK = 50

_REDHAT_CATALOG_API = "https://catalog.redhat.com/api/containers/v1/images"
_REDHAT_REGISTRIES = {"registry.redhat.io", "registry.access.redhat.com"}
REDHAT_VERSION_PATTERN = re.compile(r"^v?\d+\.\d+(\.\d+)?(-\d+)?$")


def _version_sort_key(tag):
    """Parse a version tag (e.g., '1.2.3', '26.6-3') into a tuple for sorting."""
    base = tag.lstrip("v").split("-")[0]
    suffix = tag.split("-")[1] if "-" in tag else "0"
    parts = [int(x) for x in base.split(".")]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts) + (int(suffix),)


class ContainerRegistryResolver:
    """Resolves container image digests to semver version tags via registry APIs."""

    def __init__(self, timeout: float = 10.0):
        self._client = httpx.Client(timeout=timeout, follow_redirects=True)
        self._tokens: dict[tuple[str, str], Optional[str]] = {}
        self._httpx_logger = logging.getLogger("httpx")
        self._httpx_log_level = self._httpx_logger.level

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        self._httpx_logger.setLevel(logging.WARNING)
        return self

    def __exit__(self, *args):
        self._httpx_logger.setLevel(self._httpx_log_level)
        self.close()

    def resolve_digest_to_tag(self, image_ref: str, digest: str) -> Optional[str]:
        """Resolve an image digest to its semver version tag.

        Args:
            image_ref: Full image reference (e.g., "quay.io/keycloak/keycloak:latest").
            digest: Image digest (e.g., "sha256:abc123...").

        Returns:
            Matched semver tag or None.
        """
        if not digest:
            return None

        try:
            registry, repository = self._parse_image_ref(image_ref)
        except ValueError:
            logger.warning("Cannot parse image reference: %s", image_ref)
            return None

        if registry in _REDHAT_REGISTRIES:
            return self._resolve_via_redhat_catalog(repository, digest)

        token = self._get_auth_token(registry, repository)
        tags = self._fetch_semver_tags(registry, repository, token)
        if not tags:
            logger.debug("No semver tags found for %s/%s", registry, repository)
            return None

        for tag in tags[:MAX_TAGS_TO_CHECK]:
            if self._digest_matches(registry, repository, tag, digest, token):
                return tag

        logger.debug("No tag matched digest %s for %s/%s", digest[:20], registry, repository)
        return None

    def _resolve_via_redhat_catalog(self, repository: str, digest: str) -> Optional[str]:
        """Resolve a digest to a version tag using the Red Hat catalog API."""
        try:
            resp = self._client.get(
                _REDHAT_CATALOG_API,
                params={
                    "filter": f"repositories.repository=={repository}",
                    "page_size": 50,
                    "sort_by": "creation_date[desc]",
                },
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
        except (httpx.HTTPError, KeyError) as exc:
            logger.warning("Red Hat catalog query failed for %s: %s", repository, exc)
            return None

        for image in data:
            for repo in image.get("repositories", []):
                if repo.get("repository") != repository:
                    continue
                repo_digest = repo.get("manifest_list_digest") or repo.get("manifest_schema2_digest")
                if repo_digest != digest:
                    continue
                tags = [t["name"] for t in repo.get("tags", []) if REDHAT_VERSION_PATTERN.match(t.get("name", ""))]
                if tags:
                    tags.sort(key=_version_sort_key, reverse=True)
                    return tags[0]

        logger.debug("No Red Hat catalog match for %s digest %s", repository, digest[:20])
        return None

    @staticmethod
    def _parse_image_ref(image_ref: str) -> tuple[str, str]:
        """Parse image reference into (registry, repository)."""
        ref = image_ref.split("@")[0].split(":")[0]

        parts = ref.split("/")
        if len(parts) < 2 or "." not in parts[0]:
            raise ValueError(f"Cannot determine registry from: {image_ref}")

        registry = parts[0]
        repository = "/".join(parts[1:])
        return registry, repository

    def _get_auth_token(self, registry: str, repository: str) -> Optional[str]:
        """Get anonymous pull token for a registry."""
        actual_registry = _REGISTRY_ALIASES.get(registry, registry)
        cache_key = (actual_registry, repository)
        if cache_key in self._tokens:
            return self._tokens[cache_key]

        auth_url_template = _AUTH_URLS.get(actual_registry)
        if not auth_url_template:
            self._tokens[cache_key] = None
            return None

        try:
            resp = self._client.get(auth_url_template.format(repo=repository))
            resp.raise_for_status()
            data = resp.json()
            token = data.get("token") or data.get("access_token")
            self._tokens[cache_key] = token
            return token
        except (httpx.HTTPError, KeyError) as exc:
            logger.warning("Failed to get auth token for %s/%s: %s", registry, repository, exc)
            self._tokens[cache_key] = None
            return None

    def _fetch_semver_tags(self, registry: str, repository: str, token: Optional[str]) -> list[str]:
        """Fetch semver tags from registry, sorted newest-first."""
        actual_registry = _REGISTRY_ALIASES.get(registry, registry)
        url: Optional[str] = f"https://{actual_registry}/v2/{repository}/tags/list?n=1000"
        headers = self._auth_headers(token)

        all_tags: list[str] = []
        while url:
            try:
                resp = self._client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                all_tags.extend(data.get("tags") or [])

                url = self._next_page_url(resp, actual_registry)
            except (httpx.HTTPError, KeyError) as exc:
                logger.warning("Failed to fetch tags for %s/%s: %s", registry, repository, exc)
                break

        semver_tags = [t for t in all_tags if SEMVER_PATTERN.match(t)]
        semver_tags.sort(key=_version_sort_key, reverse=True)
        return semver_tags

    def _digest_matches(
        self, registry: str, repository: str, tag: str, target_digest: str, token: Optional[str]
    ) -> bool:
        """Check if a tag's manifest digest matches the target."""
        actual_registry = _REGISTRY_ALIASES.get(registry, registry)
        url = f"https://{actual_registry}/v2/{repository}/manifests/{tag}"
        headers = {**self._auth_headers(token), "Accept": MANIFEST_ACCEPT}

        try:
            resp = self._client.get(url, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.debug("Failed to get manifest for %s:%s: %s", repository, tag, exc)
            return False

        header_digest = resp.headers.get("docker-content-digest", "")
        if header_digest == target_digest:
            return True

        content_type = resp.headers.get("content-type", "")
        if content_type in MANIFEST_LIST_TYPES:
            return self._check_manifest_list(resp.json(), target_digest)

        return False

    @staticmethod
    def _check_manifest_list(manifest_list: dict, target_digest: str) -> bool:
        """Check if any platform manifest in a manifest list matches the target digest."""
        for manifest in manifest_list.get("manifests", []):
            if manifest.get("digest") == target_digest:
                return True
        return False

    @staticmethod
    def _auth_headers(token: Optional[str]) -> dict[str, str]:
        """Build Authorization header dict."""
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}

    @staticmethod
    def _next_page_url(resp: httpx.Response, registry: str) -> Optional[str]:
        """Parse Link header for next page URL."""
        link = resp.headers.get("link", "")
        if not link:
            return None

        match = re.search(r"<([^>]+)>;\s*rel=\"next\"", link)
        if not match:
            return None

        next_url = match.group(1)
        if next_url.startswith("http"):
            return next_url
        return f"https://{registry}{next_url}"
