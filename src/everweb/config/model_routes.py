"""Load kimi_primary model routes and build planned scoring-path manifests."""

from __future__ import annotations

import hashlib
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from everweb.config.errors import ConfigError, ManifestCompletenessError
from everweb.domain import (
    KIMI_PRIMARY_PROFILE,
    KIMI_PRIMARY_ROLES,
    ScoringPathProviderCall,
    ScoringPathProviderManifest,
)

DEFAULT_MODEL_ROUTES_PATH = (
    Path(__file__).resolve().parents[3] / "config" / "model_routes.toml"
)
MOONSHOT_ENDPOINT_HOST = "api.moonshot.ai"
FIXED_PROVIDER = "moonshot"
FIXED_MODEL = "kimi-k2.6"
PLANNED_TIMESTAMP = datetime(1970, 1, 1, tzinfo=UTC)


class RoleBinding(BaseModel):
    """One profile role binding from model_routes.toml."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    mode: str | None = None


class ProfileConfig(BaseModel):
    """Validated kimi_primary-style profile."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: str = Field(min_length=1)
    provider_family: str = Field(min_length=1)
    roles: dict[str, RoleBinding]


class ModelRoutesConfig(BaseModel):
    """Loaded model route configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    primary_profile: str = Field(min_length=1)
    profiles: dict[str, ProfileConfig]
    source_path: str = Field(min_length=1)
    profile_digests: dict[str, str]


def _require_mapping(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{label} must be a table")
    return value


def _parse_role_binding(raw: object, *, role: str) -> RoleBinding:
    data = _require_mapping(raw, label=f"role {role!r}")
    provider = data.get("provider")
    model = data.get("model")
    if not isinstance(provider, str) or not provider.strip():
        raise ConfigError(f"role {role!r} provider must be a non-empty str")
    if not isinstance(model, str) or not model.strip():
        raise ConfigError(f"role {role!r} model must be a non-empty str")
    if provider.strip() == "latest" or model.strip() == "latest":
        raise ConfigError(f"role {role!r} must not use latest aliases")
    mode = data.get("mode")
    if mode is not None and (not isinstance(mode, str) or not mode.strip()):
        raise ConfigError(f"role {role!r} mode must be a non-empty str when set")
    extras = set(data) - {"provider", "model", "mode"}
    if extras:
        raise ConfigError(f"role {role!r} has unsupported keys: {sorted(extras)}")
    return RoleBinding(
        provider=provider.strip(),
        model=model.strip(),
        mode=None if mode is None else mode.strip(),
    )


def _canonical_profile_bytes(profile: ProfileConfig) -> bytes:
    lines = [
        f'name={profile.name}',
        f'provider_family={profile.provider_family}',
    ]
    for role in sorted(profile.roles):
        binding = profile.roles[role]
        mode = "" if binding.mode is None else f",mode={binding.mode}"
        lines.append(
            f"role.{role}=provider={binding.provider},model={binding.model}{mode}"
        )
    return ("\n".join(lines) + "\n").encode("utf-8")


def profile_config_digest(profile: ProfileConfig) -> str:
    return hashlib.sha256(_canonical_profile_bytes(profile)).hexdigest()


def _validate_kimi_primary(profile: ProfileConfig) -> None:
    if profile.provider_family != FIXED_PROVIDER:
        raise ConfigError(
            f"profile {profile.name!r} provider_family must be {FIXED_PROVIDER!r}"
        )
    missing = [role for role in KIMI_PRIMARY_ROLES if role not in profile.roles]
    if missing:
        raise ConfigError(
            f"profile {profile.name!r} missing roles: {missing}"
        )
    unexpected = sorted(set(profile.roles) - set(KIMI_PRIMARY_ROLES))
    if unexpected:
        raise ConfigError(
            f"profile {profile.name!r} has unsupported roles: {unexpected}"
        )
    for role, binding in profile.roles.items():
        if binding.provider != FIXED_PROVIDER:
            raise ConfigError(
                f"role {role!r} provider must be {FIXED_PROVIDER!r}"
            )
        if binding.model != FIXED_MODEL:
            raise ConfigError(f"role {role!r} model must be {FIXED_MODEL!r}")


def load_model_routes(path: Path | None = None) -> ModelRoutesConfig:
    """Load and validate model_routes.toml (kimi_primary only in W1-008)."""

    routes_path = DEFAULT_MODEL_ROUTES_PATH if path is None else path
    if not routes_path.is_file():
        raise ConfigError(f"model routes file not found: {routes_path}")
    raw = tomllib.loads(routes_path.read_text(encoding="utf-8"))
    model_section = _require_mapping(raw.get("model"), label="model")
    primary = model_section.get("primary_profile")
    if not isinstance(primary, str) or not primary.strip():
        raise ConfigError("model.primary_profile must be a non-empty str")
    primary = primary.strip()
    if primary != KIMI_PRIMARY_PROFILE:
        raise ConfigError(
            f"W1-008 only supports primary_profile={KIMI_PRIMARY_PROFILE!r}"
        )

    profiles_raw = _require_mapping(raw.get("profile"), label="profile")
    if set(profiles_raw) != {KIMI_PRIMARY_PROFILE}:
        raise ConfigError(
            "W1-008 only allows profile.kimi_primary in model_routes.toml"
        )

    profile_table = _require_mapping(
        profiles_raw[KIMI_PRIMARY_PROFILE],
        label="profile.kimi_primary",
    )
    provider_family = profile_table.get("provider_family")
    if not isinstance(provider_family, str) or not provider_family.strip():
        raise ConfigError("provider_family must be a non-empty str")

    roles: dict[str, RoleBinding] = {}
    for key, value in profile_table.items():
        if key == "provider_family":
            continue
        roles[key] = _parse_role_binding(value, role=key)

    profile = ProfileConfig(
        name=KIMI_PRIMARY_PROFILE,
        provider_family=provider_family.strip(),
        roles=roles,
    )
    _validate_kimi_primary(profile)
    digest = profile_config_digest(profile)
    return ModelRoutesConfig(
        primary_profile=primary,
        profiles={profile.name: profile},
        source_path=str(routes_path.resolve()),
        profile_digests={profile.name: digest},
    )


def build_planned_scoring_path_manifest(
    routes: ModelRoutesConfig,
    *,
    profile_name: str = KIMI_PRIMARY_PROFILE,
) -> ScoringPathProviderManifest:
    """Build a planned (pre-call) scoring-path manifest for completeness checks."""

    profile = routes.profiles.get(profile_name)
    if profile is None:
        raise ConfigError(f"unknown profile: {profile_name!r}")
    digest = routes.profile_digests[profile_name]
    calls: list[ScoringPathProviderCall] = []
    for role in KIMI_PRIMARY_ROLES:
        binding = profile.roles[role]
        calls.append(
            ScoringPathProviderCall(
                role=role,
                provider=binding.provider,
                configured_model=binding.model,
                returned_model=None,
                endpoint_host=MOONSHOT_ENDPOINT_HOST,
                request_id=None,
                route_id=profile_name,
                route_generation=0,
                started_at=PLANNED_TIMESTAMP,
                finished_at=PLANNED_TIMESTAMP,
                config_digest=digest,
            )
        )
    return ScoringPathProviderManifest(
        profile_name=profile_name,
        config_digest=digest,
        calls=tuple(calls),
    )


def assert_manifest_complete(
    manifest: ScoringPathProviderManifest,
    *,
    required_roles: tuple[str, ...] = KIMI_PRIMARY_ROLES,
) -> None:
    """Fail closed when any required formal-context role is missing."""

    present = {call.role for call in manifest.calls}
    missing = [role for role in required_roles if role not in present]
    if missing:
        raise ManifestCompletenessError(
            f"manifest {manifest.profile_name!r} missing roles: {missing}"
        )
    for role in required_roles:
        matches = [call for call in manifest.calls if call.role == role]
        if len(matches) != 1:
            raise ManifestCompletenessError(
                f"manifest {manifest.profile_name!r} role {role!r} "
                f"must appear exactly once; found {len(matches)}"
            )
