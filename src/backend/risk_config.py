# SPDX-FileCopyrightText: 2026 quill4749 (https://github.com/quill4749/Data-Mirror)
# SPDX-License-Identifier: AGPL-3.0-only

"""Shared, data-driven privacy risk configuration for Data-Mirror.

This module is the single source of truth for:
  * project paths (always absolute, derived from ``__file__``),
  * the scoring scale (0 = Safe, 1 = Medium, 2 = Critical),
  * the academic weight rationale,
  * loading/normalising ``data/service_mapping.json`` (schema v2 + legacy flat schema),
  * weighted score calculation and discretisation into Low / Medium / High classes.

Why the weights look like this
------------------------------
1. Behavioral profiling (weight 2.0)
   Cross-app profiling creates a persistent, hard-to-revoke identity graph. The
   harm is largely irreversible once behavioural data has been linked and resold.
2. Location tracking (weight 1.5)
   ACCESS_FINE_LOCATION / ACCESS_BACKGROUND_LOCATION expose physical movement
   and can reveal home, workplace, health visits, and religious or political
   activity. OS vendors treat it as a highly sensitive permission.
3. Targeted advertising (weight 1.0)
   Third-party ad SDKs and cookies support commercial profiling, but the impact
   is usually narrower than cross-app behavioural or location tracking.
4. Dynamically extended factors (default weight 1.2 - 1.8)
   Microphone, clipboard, contacts, biometric data, etc. can be added without
   editing application code. Weights are stored inside the JSON mapping itself.
"""

from __future__ import annotations

import json
import math
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

# ---------------------------------------------------------------------------
# Path anchors (absolute; safe on macOS, Linux, and Windows)
# ---------------------------------------------------------------------------
BACKEND_DIR: Path = Path(__file__).resolve().parent
SRC_DIR: Path = BACKEND_DIR.parent
PROJECT_ROOT: Path = SRC_DIR.parent

DATA_DIR: Path = PROJECT_ROOT / "data"
OUTPUTS_DIR: Path = PROJECT_ROOT / "outputs"
SERVICE_MAPPING_FILENAME: str = "service_mapping.json"
DEFAULT_MAPPING_PATH: Path = DATA_DIR / SERVICE_MAPPING_FILENAME

SCHEMA_VERSION: str = "2.0"

# ---------------------------------------------------------------------------
# Scan scale / risk classes
# ---------------------------------------------------------------------------
SAFE, MEDIUM, CRITICAL = 0, 1, 2

RISK_SCALE: dict[int, dict[str, str]] = {
    SAFE: {
        "label_zh": "安全",
        "label_en": "Safe",
        "definition": "未發現該項資料收集，或僅為使用者主動觸發的單次功能。",
    },
    MEDIUM: {
        "label_zh": "中等",
        "label_en": "Medium",
        "definition": "與核心功能相關，或需使用者授權後方可使用，但存在一定暴露面。",
    },
    CRITICAL: {
        "label_zh": "嚴重",
        "label_en": "Critical",
        "definition": "高侵略性的背景收集、跨 App 串接，或涉及不可逆的敏感資料。",
    },
}

RISK_LEVELS: dict[int, dict[str, str]] = {
    0: {
        "label_zh": "低風險",
        "label_en": "Low",
        "icon": "✅",
        "tone": "low",
        "summary": "目前暴露面較小，仍建議定期檢視權限與廣告追蹤設定。",
    },
    1: {
        "label_zh": "中風險",
        "label_en": "Medium",
        "icon": "⚠️",
        "tone": "medium",
        "summary": "存在可觀的資料收集行為，建議針對高權重因子優先收緊權限。",
    },
    2: {
        "label_zh": "高風險",
        "label_en": "High",
        "icon": "⛔",
        "tone": "high",
        "summary": "多項高敏感資料可能被長期追蹤，建議立即調整隱私設定並降低使用暴露。",
    },
}

# Low: ratio < 1/3; Medium: 1/3 <= ratio < 2/3; High: ratio >= 2/3.
DEFAULT_THRESHOLDS: dict[str, float] = {
    "low_max_ratio": 1.0 / 3.0,
    "medium_max_ratio": 2.0 / 3.0,
}

# Weight used for factors found in the JSON but not registered here. The
# 1.2 - 1.8 band is reserved for dynamically added sensitive OS permissions.
DEFAULT_UNKNOWN_WEIGHT: float = 1.2
MIN_WEIGHT: float = 0.1
MAX_WEIGHT: float = 5.0


@dataclass(frozen=True)
class RiskFactor:
    """A single dynamically discoverable risk dimension."""

    key: str
    label_zh: str
    label_en: str
    weight: float
    description: str = ""
    rationale: str = ""
    advice: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "label_zh": self.label_zh,
            "label_en": self.label_en,
            "weight": self.weight,
            "description": self.description,
            "rationale": self.rationale,
            "advice": self.advice,
        }

    @classmethod
    def from_dict(cls, key: str, raw: Mapping[str, Any]) -> "RiskFactor":
        return cls(
            key=key,
            label_zh=str(raw.get("label_zh") or _humanise(key)),
            label_en=str(raw.get("label_en") or key.replace("_", " ").title()),
            weight=_safe_weight(raw.get("weight"), fallback=DEFAULT_UNKNOWN_WEIGHT),
            description=str(raw.get("description") or ""),
            rationale=str(raw.get("rationale") or ""),
            advice=str(raw.get("advice") or _generic_advice(key)),
        )


# ---------------------------------------------------------------------------
# Default (academic) factor registry
# ---------------------------------------------------------------------------
def _default_factor_specs() -> tuple[dict[str, Any], ...]:
    return (
        {
            "key": "behavioral_profiling",
            "label_zh": "行為側寫",
            "label_en": "Behavioral Profiling",
            "weight": 2.0,
            "description": "跨 App 追蹤識別碼、裝置指紋、感測器與使用行為的長期彙整。",
            "rationale": (
                "隱私侵害具有不可逆性：行為資料一旦被交叉連結、建模並轉售，"
                "使用者幾乎無法撤回。跨 App 長期追蹤也會形成難以逃逸的個人輪廓，"
                "因此給予最高權重 2.0。"
            ),
            "advice": (
                "在 iOS 關閉「允許 App 要求追蹤」，Android 重置廣告 ID 並關閉個人化廣告；"
                "定期檢視「應用程式與網站存取權」及第三方登入授權，移除不必要連結。"
            ),
        },
        {
            "key": "location_tracking",
            "label_zh": "位置追蹤",
            "label_en": "Location Tracking",
            "weight": 1.5,
            "description": "精確定位、背景定位、移動路徑與常去地點的收集。",
            "rationale": (
                "ACCESS_FINE_LOCATION 與 ACCESS_BACKGROUND_LOCATION 屬作業系統最高敏感度"
                "權限之一，可推論住家、工作地、醫療與宗教活動；權重 1.5 反映其高敏感度，"
                "但通常需使用者授權，故略低於跨 App 行為側寫。"
            ),
            "advice": (
                "將非導航類 App 的定位改為「僅使用期間」或「永不」，關閉「精確位置」，"
                "並在系統設定中檢查「背景位置」與 Google/Apple 的定位紀錄。"
            ),
        },
        {
            "key": "targeted_ads",
            "label_zh": "精準廣告",
            "label_en": "Targeted Ads",
            "weight": 1.0,
            "description": "第三方廣告 SDK、Cookie、廣告識別碼與再行銷標籤。",
            "rationale": (
                "第三方 SDK 與 Cookie 支撐商業行銷與再行銷，雖涉及資料共享，"
                "但影響範圍通常較行為側寫與位置追蹤窄，因此基準權重為 1.0。"
            ),
            "advice": (
                "定期清除網站 Cookie，重置廣告識別碼（IDFA / GAID），"
                "並在瀏覽器啟用追蹤保護或使用容器化分頁隔離第三方追蹤。"
            ),
        },
        {
            "key": "microphone_access",
            "label_zh": "麥克風存取",
            "label_en": "Microphone Access",
            "weight": 1.8,
            "description": "背景或非使用期間的麥克風收音、語音內容與環境聲音分析。",
            "rationale": (
                "麥克風可捕捉私人對話與環境聲音，且內容難以撤回；"
                "若可在背景存取，風險接近行為側寫，故預設權重 1.8。"
            ),
            "advice": (
                "僅授予通話或錄音 App 麥克風權限，並設定為「僅使用期間」；"
                "在系統隱私指示器中定期檢查最近存取麥克風的 App。"
            ),
        },
        {
            "key": "clipboard_tracking",
            "label_zh": "剪貼簿追蹤",
            "label_en": "Clipboard Tracking",
            "weight": 1.2,
            "description": "讀取剪貼簿內容，可能包含密碼、一次性驗證碼、地址或私人訊息。",
            "rationale": (
                "剪貼簿常短暫承載高價值秘密（OTP、密碼、地址）。"
                "雖然收集量通常較小，但外洩後果直接，故列為 1.2 的動態擴充因子。"
            ),
            "advice": (
                "在 iOS 開啟「允許貼上」提示並拒絕不明 App 的讀取；"
                "Android 13 以上會顯示剪貼簿存取通知，請定期檢查並避免複製敏感資訊。"
            ),
        },
        {
            "key": "contacts_access",
            "label_zh": "通訊錄存取",
            "label_en": "Contacts Access",
            "weight": 1.4,
            "description": "上傳通訊錄、社交圖譜、電話號碼與聯絡人關聯。",
            "rationale": (
                "通訊錄會揭露非使用者的第三人資料，形成社交圖譜外洩；"
                "其影響擴及他人且難以補救，故給予 1.4 權重。"
            ),
            "advice": (
                "撤銷非通訊或社群核心功能 App 的通訊錄權限；"
                "若必須使用，僅開放單一聯絡人而非完整通訊錄。"
            ),
        },
        {
            "key": "biometric_data",
            "label_zh": "生物特徵",
            "label_en": "Biometric Data",
            "weight": 1.7,
            "description": "指紋、臉部、聲紋、步態或其他不可更換的身分特徵。",
            "rationale": (
                "生物特徵無法像密碼一樣更換，一旦外洩即永久暴露；"
                "其不可逆性高，故預設權重 1.7。"
            ),
            "advice": (
                "優先使用裝置本機安全區（Secure Enclave / Keystore）處理生物辨識，"
                "避免將臉部或指紋影像上傳雲端；檢查 App 是否要求不必要的生物辨識。"
            ),
        },
    )


DEFAULT_RISK_FACTORS: tuple[RiskFactor, ...] = tuple(
    RiskFactor(**spec) for spec in _default_factor_specs()
)
CORE_FACTOR_DEFAULTS: dict[str, RiskFactor] = {
    factor.key: factor for factor in DEFAULT_RISK_FACTORS
}


def _humanise(key: str) -> str:
    return key.replace("_", " ").replace("-", " ").strip().title() or "未命名因子"


def _generic_advice(key: str) -> str:
    return (
        f"請在系統隱私設定中檢查「{_humanise(key)}」相關權限，"
        "僅授予核心功能必要的最小權限，並優先選擇「僅使用期間」或「每次詢問」。"
    )


def _safe_weight(value: Any, fallback: float = DEFAULT_UNKNOWN_WEIGHT) -> float:
    try:
        weight = float(value)
    except (TypeError, ValueError):
        return fallback
    if not math.isfinite(weight):
        return fallback
    return min(MAX_WEIGHT, max(MIN_WEIGHT, round(weight, 2)))


def _safe_level(value: Any) -> int:
    """Coerce a JSON score into the 0 / 1 / 2 scan scale."""

    try:
        level = int(value)
    except (TypeError, ValueError):
        return SAFE
    return min(CRITICAL, max(SAFE, level))


def resolve_path(path: str | Path | None, default: Path) -> Path:
    """Return an absolute path, resolving relative input against the repo root."""

    if path is None:
        return default.resolve()
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return candidate.resolve()


def scale_label(level: int, language: str = "zh") -> str:
    entry = RISK_SCALE.get(_safe_level(level), RISK_SCALE[SAFE])
    return entry["label_zh"] if language.startswith("zh") else entry["label_en"]


def risk_level_label(level: int, language: str = "zh") -> str:
    entry = RISK_LEVELS.get(_safe_level(level), RISK_LEVELS[0])
    return entry["label_zh"] if language.startswith("zh") else entry["label_en"]


# ---------------------------------------------------------------------------
# Normalised mapping object
# ---------------------------------------------------------------------------
@dataclass
class PrivacyMapping:
    """Normalised service mapping with dynamically discovered factors."""

    services: dict[str, dict[str, int]] = field(default_factory=dict)
    factors: tuple[RiskFactor, ...] = field(default_factory=tuple)
    thresholds: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_THRESHOLDS)
    )
    schema_version: str = SCHEMA_VERSION
    generated_at: str | None = None
    source_path: Path | None = None

    @property
    def feature_names(self) -> list[str]:
        return [factor.key for factor in self.factors]

    @property
    def factor_map(self) -> dict[str, RiskFactor]:
        return {factor.key: factor for factor in self.factors}

    @property
    def max_score(self) -> float:
        """Maximum attainable weighted score (every factor at Critical)."""

        return round(sum(factor.weight * CRITICAL for factor in self.factors), 4)

    def weighted_score(self, levels: Mapping[str, int]) -> float:
        return round(
            sum(
                _safe_level(levels.get(factor.key, SAFE)) * factor.weight
                for factor in self.factors
            ),
            4,
        )

    def score_ratio(self, total_weighted_score: float) -> float:
        if self.max_score <= 0:
            return 0.0
        return min(1.0, max(0.0, float(total_weighted_score) / self.max_score))

    def classify_score(self, total_weighted_score: float) -> int:
        """Discretise a continuous weighted score into 0 / 1 / 2.

        A ratio-based scale keeps the classes stable when the user adds new
        factors to the JSON. This is the discrete label consumed by
        ``DecisionTreeClassifier`` (which must not receive continuous y).
        """

        ratio = self.score_ratio(total_weighted_score)
        low_max = self.thresholds.get("low_max_ratio", DEFAULT_THRESHOLDS["low_max_ratio"])
        medium_max = self.thresholds.get(
            "medium_max_ratio", DEFAULT_THRESHOLDS["medium_max_ratio"]
        )
        if ratio < low_max:
            return 0
        if ratio < medium_max:
            return 1
        return 2

    def classify_levels(self, levels: Mapping[str, int]) -> int:
        return self.classify_score(self.weighted_score(levels))

    def levels_for_service(self, service_name: str) -> dict[str, int]:
        raw = self.services.get(service_name, {})
        return {factor.key: _safe_level(raw.get(factor.key, SAFE)) for factor in self.factors}

    def aggregate_levels(
        self, service_names: Iterable[str], reducer=max
    ) -> dict[str, int]:
        """Aggregate several services into one exposure vector.

        Default is the per-factor maximum: overall exposure is driven by the
        worst service for each data category, not by the number of apps.
        """

        names = list(service_names)
        if not names:
            return {factor.key: SAFE for factor in self.factors}
        return {
            factor.key: reducer(
                _safe_level(self.services.get(name, {}).get(factor.key, SAFE))
                for name in names
            )
            for factor in self.factors
        }


def _normalise_thresholds(raw: Any) -> dict[str, float]:
    if not isinstance(raw, Mapping):
        return dict(DEFAULT_THRESHOLDS)
    low = raw.get("low_max_ratio", DEFAULT_THRESHOLDS["low_max_ratio"])
    medium = raw.get("medium_max_ratio", DEFAULT_THRESHOLDS["medium_max_ratio"])
    try:
        low_f = float(low)
        medium_f = float(medium)
    except (TypeError, ValueError):
        return dict(DEFAULT_THRESHOLDS)
    if not (0.0 < low_f < medium_f < 1.0):
        return dict(DEFAULT_THRESHOLDS)
    return {"low_max_ratio": low_f, "medium_max_ratio": medium_f}


def _ordered_union(*groups: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for group in groups:
        for key in group:
            if key not in seen:
                seen.add(key)
                ordered.append(key)
    return ordered


def normalise_mapping(
    raw: Mapping[str, Any] | None,
    source_path: Path | None = None,
) -> PrivacyMapping:
    """Normalise schema v2 and legacy flat mappings into ``PrivacyMapping``.

    Schema v2::

        {
          "schema_version": "2.0",
          "risk_factors": {"location_tracking": {"weight": 1.5, ...}},
          "services": {"instagram": {"location_tracking": 2, ...}}
        }

    Legacy schema (still supported)::

        {"instagram": {"location_tracking": 2, ...}}
    """

    if not isinstance(raw, Mapping):
        return PrivacyMapping(
            factors=DEFAULT_RISK_FACTORS,
            thresholds=dict(DEFAULT_THRESHOLDS),
            source_path=source_path,
        )

    payload = dict(raw)

    if isinstance(payload.get("services"), Mapping):
        raw_services = payload.get("services") or {}
        raw_factor_meta = payload.get("risk_factors") or {}
        schema_version = str(payload.get("schema_version") or SCHEMA_VERSION)
        generated_at = payload.get("generated_at")
        thresholds = _normalise_thresholds(
            payload.get("risk_thresholds") or payload.get("thresholds")
        )
    else:
        # Legacy flat format: every top-level entry is a service.
        raw_services = {
            str(name): scores
            for name, scores in payload.items()
            if not str(name).startswith("_") and isinstance(scores, Mapping)
        }
        raw_factor_meta = {}
        schema_version = "1.0"
        generated_at = None
        thresholds = dict(DEFAULT_THRESHOLDS)

    clean_services: dict[str, dict[str, Any]] = {}
    service_factor_order: list[str] = []
    for name, scores in raw_services.items():
        if not isinstance(scores, Mapping):
            continue
        clean_scores = {
            str(key): _safe_level(value)
            for key, value in scores.items()
            if not str(key).startswith("_")
        }
        clean_services[str(name)] = clean_scores
        service_factor_order.extend(clean_scores.keys())

    metadata = raw_factor_meta if isinstance(raw_factor_meta, Mapping) else {}
    factor_order = _ordered_union(
        [str(key) for key in metadata.keys()],
        service_factor_order,
    )

    factors: list[RiskFactor] = []
    for key in factor_order:
        raw_meta = metadata.get(key, {})
        raw_meta = raw_meta if isinstance(raw_meta, Mapping) else {}
        base = CORE_FACTOR_DEFAULTS.get(key)
        if base is not None:
            merged = base.to_dict()
            merged.update(
                {
                    field_name: value
                    for field_name, value in raw_meta.items()
                    if field_name in merged and value not in (None, "")
                }
            )
            factor = RiskFactor.from_dict(key, merged)
        else:
            factor = RiskFactor.from_dict(key, raw_meta)
        factors.append(factor)

    factor_keys = [factor.key for factor in factors]
    services: dict[str, dict[str, int]] = {
        name: {
            key: _safe_level(scores.get(key, SAFE))
            for key in factor_keys
        }
        for name, scores in clean_services.items()
    }

    return PrivacyMapping(
        services=services,
        factors=tuple(factors),
        thresholds=thresholds,
        schema_version=schema_version,
        generated_at=str(generated_at) if generated_at else None,
        source_path=source_path,
    )


def fallback_mapping(source_path: Path | None = None) -> PrivacyMapping:
    """A safe, empty mapping that still exposes the default factor registry."""

    return PrivacyMapping(
        services={},
        factors=DEFAULT_RISK_FACTORS,
        thresholds=dict(DEFAULT_THRESHOLDS),
        schema_version=SCHEMA_VERSION,
        source_path=source_path,
    )


def load_service_mapping(
    path: str | Path | None = None,
    *,
    auto_generate: bool = True,
) -> PrivacyMapping:
    """Load the JSON mapping without ever leaking ``FileNotFoundError``.

    If the file is missing, the canonical collector is invoked automatically.
    If generation or parsing fails, a warning is emitted and an empty-but-valid
    mapping is returned so callers can render a helpful UI instead of crashing.
    """

    target = resolve_path(path, DEFAULT_MAPPING_PATH)

    if not target.exists() and auto_generate:
        try:
            try:
                from .service_collector import PrivacyRiskCollector
            except ImportError:  # script execution: src/backend on sys.path
                from service_collector import PrivacyRiskCollector

            PrivacyRiskCollector().generate_mapping_file(target)
        except Exception as exc:  # pragma: no cover - defensive path
            warnings.warn(
                f"Could not auto-generate {target}: {exc}. "
                "Run `python src/backend/service_collector.py` manually.",
                RuntimeWarning,
                stacklevel=2,
            )

    if not target.exists():
        warnings.warn(
            f"Service mapping not found at {target}; using an empty fallback mapping.",
            RuntimeWarning,
            stacklevel=2,
        )
        return fallback_mapping(target)

    try:
        with target.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        warnings.warn(
            f"Could not read {target}: {exc}; using an empty fallback mapping.",
            RuntimeWarning,
            stacklevel=2,
        )
        return fallback_mapping(target)

    return normalise_mapping(raw, source_path=target)


def save_mapping_payload(payload: Mapping[str, Any], path: str | Path | None = None) -> Path:
    """Atomically write a mapping payload to disk and return the absolute path."""

    target = resolve_path(path, DEFAULT_MAPPING_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=4)
        handle.write("\n")
    tmp.replace(target)
    return target


__all__ = [
    "BACKEND_DIR",
    "SRC_DIR",
    "PROJECT_ROOT",
    "DATA_DIR",
    "OUTPUTS_DIR",
    "DEFAULT_MAPPING_PATH",
    "SERVICE_MAPPING_FILENAME",
    "SCHEMA_VERSION",
    "SAFE",
    "MEDIUM",
    "CRITICAL",
    "RISK_SCALE",
    "RISK_LEVELS",
    "DEFAULT_THRESHOLDS",
    "DEFAULT_UNKNOWN_WEIGHT",
    "DEFAULT_RISK_FACTORS",
    "CORE_FACTOR_DEFAULTS",
    "RiskFactor",
    "PrivacyMapping",
    "resolve_path",
    "scale_label",
    "risk_level_label",
    "normalise_mapping",
    "fallback_mapping",
    "load_service_mapping",
    "save_mapping_payload",
]
