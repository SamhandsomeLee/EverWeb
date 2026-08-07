"""Contract: kimi_primary planned ScoringPathProviderManifest completeness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from everweb.config import (
    ManifestCompletenessError,
    assert_manifest_complete,
    build_planned_scoring_path_manifest,
    load_model_routes,
    profile_config_digest,
)
from everweb.domain import (
    KIMI_PRIMARY_PROFILE,
    KIMI_PRIMARY_ROLES,
    ScoringPathProviderManifest,
)
from everweb.domain.sensitive import contains_sensitive_content

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROUTES = ROOT / "config" / "model_routes.toml"


def test_load_default_kimi_primary_routes() -> None:
    routes = load_model_routes(DEFAULT_ROUTES)
    assert routes.primary_profile == KIMI_PRIMARY_PROFILE
    profile = routes.profiles[KIMI_PRIMARY_PROFILE]
    assert set(profile.roles) == set(KIMI_PRIMARY_ROLES)
    assert profile.provider_family == "moonshot"
    for role in KIMI_PRIMARY_ROLES:
        assert profile.roles[role].provider == "moonshot"
        assert profile.roles[role].model == "kimi-k2.6"


def test_planned_manifest_is_complete_for_seven_roles() -> None:
    routes = load_model_routes(DEFAULT_ROUTES)
    manifest = build_planned_scoring_path_manifest(routes)
    assert_manifest_complete(manifest)
    assert isinstance(manifest, ScoringPathProviderManifest)
    assert manifest.profile_name == KIMI_PRIMARY_PROFILE
    assert len(manifest.calls) == len(KIMI_PRIMARY_ROLES)
    roles = [call.role for call in manifest.calls]
    assert roles == list(KIMI_PRIMARY_ROLES)
    for call in manifest.calls:
        assert call.provider == "moonshot"
        assert call.configured_model == "kimi-k2.6"
        assert call.returned_model is None
        assert call.endpoint_host == "api.moonshot.ai"
        assert call.route_id == KIMI_PRIMARY_PROFILE
        assert call.route_generation == 0
        assert call.config_digest == manifest.config_digest


def test_config_digest_is_stable_and_non_empty() -> None:
    first = load_model_routes(DEFAULT_ROUTES)
    second = load_model_routes(DEFAULT_ROUTES)
    digest_a = first.profile_digests[KIMI_PRIMARY_PROFILE]
    digest_b = second.profile_digests[KIMI_PRIMARY_PROFILE]
    assert digest_a
    assert digest_a == digest_b
    assert digest_a == profile_config_digest(first.profiles[KIMI_PRIMARY_PROFILE])


def test_manifest_dump_has_no_secrets_or_latest() -> None:
    manifest = build_planned_scoring_path_manifest(load_model_routes(DEFAULT_ROUTES))
    dumped = json.dumps(manifest.model_dump(mode="json"), ensure_ascii=True)
    assert "latest" not in dumped.casefold()
    assert "moonshot_api_key" not in dumped.casefold()
    assert "authorization" not in dumped.casefold()
    assert "reasoning" not in dumped.casefold()
    assert not contains_sensitive_content(dumped)
    assert "MOONSHOT_API_KEY" not in DEFAULT_ROUTES.read_text(encoding="utf-8")


def test_missing_role_fails_completeness(tmp_path: Path) -> None:
    routes = load_model_routes(DEFAULT_ROUTES)
    manifest = build_planned_scoring_path_manifest(routes)
    incomplete = ScoringPathProviderManifest(
        profile_name=manifest.profile_name,
        config_digest=manifest.config_digest,
        calls=tuple(call for call in manifest.calls if call.role != "verifier"),
    )
    with pytest.raises(ManifestCompletenessError, match="verifier"):
        assert_manifest_complete(incomplete)


def test_incomplete_toml_is_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "model_routes.toml"
    bad.write_text(
        """
[model]
primary_profile = "kimi_primary"

[profile.kimi_primary]
provider_family = "moonshot"
task_analyzer = { provider = "moonshot", model = "kimi-k2.6", mode = "thinking" }
navigator = { provider = "moonshot", model = "kimi-k2.6", mode = "thinking" }
""",
        encoding="utf-8",
    )
    with pytest.raises(Exception, match="missing roles"):
        load_model_routes(bad)


def test_latest_alias_is_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "model_routes.toml"
    bad.write_text(
        """
[model]
primary_profile = "kimi_primary"

[profile.kimi_primary]
provider_family = "moonshot"
task_analyzer = { provider = "moonshot", model = "kimi-k2.6", mode = "thinking" }
navigator = { provider = "moonshot", model = "kimi-k2.6", mode = "thinking" }
navigator_fast = { provider = "moonshot", model = "kimi-k2.6", mode = "instant" }
summarizer = { provider = "moonshot", model = "kimi-k2.6", mode = "instant" }
extractor = { provider = "moonshot", model = "kimi-k2.6", mode = "thinking" }
verifier = { provider = "moonshot", model = "kimi-k2.6", mode = "thinking" }
vision = { provider = "moonshot", model = "latest" }
""",
        encoding="utf-8",
    )
    with pytest.raises(Exception, match="latest"):
        load_model_routes(bad)
