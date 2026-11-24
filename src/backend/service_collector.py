# SPDX-FileCopyrightText: 2026 quill4749 (https://github.com/quill4749/Data-Mirror)
# SPDX-License-Identifier: AGPL-3.0-only

"""Collect and generate ``data/service_mapping.json``.

The file is intentionally *data-driven*: every risk dimension lives in the JSON
metadata (``risk_factors``), so adding a new factor such as microphone or
clipboard access does not require changes in ``tree_model.py`` or ``app.py``.

Scan scale (open-source privacy scanner convention):
    0 = Safe      - no meaningful collection, or user-initiated one-off use
    1 = Medium    - tied to core functionality, or requires explicit consent
    2 = Critical  - aggressive background collection / cross-app linkage

Run directly:
    python src/backend/service_collector.py

Import and extend:
    collector = PrivacyRiskCollector()
    collector.register_factor("screen_recording", weight=1.6, ...)
    collector.register_service("my_app", {"screen_recording": 2})
    collector.generate_mapping_file()
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

try:  # package import: src.backend.service_collector
    from .risk_config import (
        DEFAULT_MAPPING_PATH,
        DEFAULT_RISK_FACTORS,
        DEFAULT_THRESHOLDS,
        DEFAULT_UNKNOWN_WEIGHT,
        RISK_SCALE,
        SCHEMA_VERSION,
        RiskFactor,
        _generic_advice,
        _humanise,
        _safe_level,
        _safe_weight,
        save_mapping_payload,
    )
except ImportError:  # script import: python src/backend/service_collector.py
    from risk_config import (  # type: ignore[no-redef]
        DEFAULT_MAPPING_PATH,
        DEFAULT_RISK_FACTORS,
        DEFAULT_THRESHOLDS,
        DEFAULT_UNKNOWN_WEIGHT,
        RISK_SCALE,
        SCHEMA_VERSION,
        RiskFactor,
        _generic_advice,
        _humanise,
        _safe_level,
        _safe_weight,
        save_mapping_payload,
    )


# ---------------------------------------------------------------------------
# Baseline dataset
# ---------------------------------------------------------------------------
# Sources synthesised from public app-store privacy labels, OS permission
# documentation, and open-source mobile privacy scanners (Exodus, MobSF,
# εxodus-style trackers). Values are educational approximations, not audits.
DEFAULT_SERVICE_SCORES: "OrderedDict[str, dict[str, int]]" = OrderedDict(
    [
        (
            "instagram",
            {
                "location_tracking": 2,
                "behavioral_profiling": 2,
                "targeted_ads": 2,
                "microphone_access": 1,
                "clipboard_tracking": 2,
                "contacts_access": 2,
                "biometric_data": 0,
            },
        ),
        (
            "tiktok",
            {
                "location_tracking": 1,
                "behavioral_profiling": 2,
                "targeted_ads": 2,
                "microphone_access": 2,
                "clipboard_tracking": 2,
                "contacts_access": 1,
                "biometric_data": 0,
            },
        ),
        (
            "google_maps",
            {
                "location_tracking": 2,
                "behavioral_profiling": 1,
                "targeted_ads": 0,
                "microphone_access": 1,
                "clipboard_tracking": 0,
                "contacts_access": 0,
                "biometric_data": 0,
            },
        ),
        (
            "uber",
            {
                "location_tracking": 2,
                "behavioral_profiling": 1,
                "targeted_ads": 1,
                "microphone_access": 1,
                "clipboard_tracking": 0,
                "contacts_access": 1,
                "biometric_data": 0,
            },
        ),
        (
            "whatsapp",
            {
                "location_tracking": 1,
                "behavioral_profiling": 1,
                "targeted_ads": 0,
                "microphone_access": 2,
                "clipboard_tracking": 1,
                "contacts_access": 2,
                "biometric_data": 0,
            },
        ),
        (
            "signal",
            {
                "location_tracking": 1,
                "behavioral_profiling": 0,
                "targeted_ads": 0,
                "microphone_access": 2,
                "clipboard_tracking": 0,
                "contacts_access": 2,
                "biometric_data": 0,
            },
        ),
        (
            "spotify",
            {
                "location_tracking": 0,
                "behavioral_profiling": 1,
                "targeted_ads": 2,
                "microphone_access": 1,
                "clipboard_tracking": 0,
                "contacts_access": 0,
                "biometric_data": 0,
            },
        ),
        (
            "notion",
            {
                "location_tracking": 0,
                "behavioral_profiling": 0,
                "targeted_ads": 1,
                "microphone_access": 0,
                "clipboard_tracking": 1,
                "contacts_access": 0,
                "biometric_data": 0,
            },
        ),
        (
            "mobile_banking",
            {
                "location_tracking": 1,
                "behavioral_profiling": 1,
                "targeted_ads": 0,
                "microphone_access": 1,
                "clipboard_tracking": 1,
                "contacts_access": 1,
                "biometric_data": 2,
            },
        ),
        (
            "calculator_app",
            {
                "location_tracking": 0,
                "behavioral_profiling": 0,
                "targeted_ads": 1,
                "microphone_access": 0,
                "clipboard_tracking": 0,
                "contacts_access": 0,
                "biometric_data": 0,
            },
        ),
    ]
)


class PrivacyRiskCollector:
    """Build the structured privacy-risk matrix consumed by the model and UI."""

    def __init__(
        self,
        factors: "OrderedDict[str, RiskFactor] | None" = None,
        services: "OrderedDict[str, dict[str, int]] | None" = None,
    ) -> None:
        self.factors: "OrderedDict[str, RiskFactor]" = OrderedDict()
        for factor in DEFAULT_RISK_FACTORS:
            self.factors[factor.key] = factor

        if factors:
            for key, factor in factors.items():
                self.factors[key] = factor

        self.services: "OrderedDict[str, dict[str, int]]" = OrderedDict()
        if services is None:
            for name, scores in DEFAULT_SERVICE_SCORES.items():
                self.register_service(name, scores)
        else:
            for name, scores in services.items():
                self.register_service(name, scores)

    # -- dynamic extension API ------------------------------------------------
    def register_factor(
        self,
        key: str,
        *,
        weight: float | None = None,
        label_zh: str | None = None,
        label_en: str | None = None,
        description: str | None = None,
        rationale: str | None = None,
        advice: str | None = None,
    ) -> RiskFactor:
        """Add or update a risk dimension without touching any other module."""

        key = str(key).strip()
        if not key:
            raise ValueError("Risk factor key must not be empty.")
        existing = self.factors.get(key)
        factor = RiskFactor(
            key=key,
            label_zh=label_zh or (existing.label_zh if existing else _humanise(key)),
            label_en=label_en
            or (existing.label_en if existing else key.replace("_", " ").title()),
            weight=_safe_weight(
                weight if weight is not None else (existing.weight if existing else None),
                fallback=DEFAULT_UNKNOWN_WEIGHT,
            ),
            description=description
            if description is not None
            else (existing.description if existing else ""),
            rationale=rationale
            if rationale is not None
            else (existing.rationale if existing else ""),
            advice=advice
            if advice is not None
            else (existing.advice if existing else _generic_advice(key)),
        )
        self.factors[key] = factor
        # Keep every service row dimensionally complete.
        for scores in self.services.values():
            scores.setdefault(key, 0)
        return factor

    def register_service(
        self,
        name: str,
        scores: Mapping[str, Any],
        *,
        replace: bool = True,
    ) -> None:
        """Add a service; unknown factors are auto-registered with weight 1.2."""

        service_name = str(name).strip()
        if not service_name:
            raise ValueError("Service name must not be empty.")
        if not replace and service_name in self.services:
            return

        clean: dict[str, int] = {}
        for key, value in scores.items():
            factor_key = str(key).strip()
            if not factor_key:
                continue
            if factor_key not in self.factors:
                self.register_factor(factor_key)
            clean[factor_key] = _safe_level(value)

        self.services[service_name] = {
            factor.key: clean.get(factor.key, 0) for factor in self.factors.values()
        }

    # -- data access ----------------------------------------------------------
    def fetch_service_data(self) -> dict[str, dict[str, int]]:
        """Return a defensive copy of the current service matrix."""

        return {
            name: {
                factor.key: scores.get(factor.key, 0)
                for factor in self.factors.values()
            }
            for name, scores in self.services.items()
        }

    def build_payload(self) -> dict[str, Any]:
        """Build the schema-v2 JSON payload (metadata + services)."""

        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "description": (
                "Data-Mirror privacy risk matrix. Scores: 0=Safe, 1=Medium, "
                "2=Critical. Weights live in risk_factors so the feature space "
                "can be extended without code changes."
            ),
            "risk_scale": {str(level): entry for level, entry in RISK_SCALE.items()},
            "risk_thresholds": dict(DEFAULT_THRESHOLDS),
            "risk_factors": {
                key: factor.to_dict() for key, factor in self.factors.items()
            },
            "services": self.fetch_service_data(),
        }

    def generate_mapping_file(self, output_path: str | Path | None = None) -> Path:
        """Write ``service_mapping.json`` atomically and return its absolute path."""

        target = save_mapping_payload(self.build_payload(), output_path or DEFAULT_MAPPING_PATH)
        print(f"[Success] Structured privacy risk matrix written to: {target}")
        return target


def main() -> None:
    collector = PrivacyRiskCollector()
    target = collector.generate_mapping_file()
    print(f"[Info] {len(collector.services)} services, {len(collector.factors)} factors.")
    print(f"[Info] Absolute path: {target}")


if __name__ == "__main__":
    main()
