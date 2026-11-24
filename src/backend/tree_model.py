# SPDX-FileCopyrightText: 2026 quill4749 (https://github.com/quill4749/Data-Mirror)
# SPDX-License-Identifier: AGPL-3.0-only

"""Train, explain, and export the Data-Mirror privacy decision tree.

Key design points
-----------------
* Features are discovered dynamically from ``data/service_mapping.json``; no
  fixed three-factor list is hard-coded.
* The weighted score is continuous, but ``DecisionTreeClassifier`` requires a
  discrete target. We therefore map the score ratio to three discrete labels
  (0 = Low, 1 = Medium, 2 = High) *before* fitting the tree.
* The tree is trained on an exhaustive 0/1/2 grid so every combination of
  factors is represented, including dynamic factors added later.
* Outputs:
    - ``outputs/tree_rules.txt``
    - ``outputs/decision_tree.png``

Run directly:
    python src/backend/tree_model.py
"""

from __future__ import annotations

import itertools
import math
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")  # must happen before pyplot import (headless-safe)

import matplotlib.pyplot as plt  # noqa: E402
from sklearn.tree import (  # noqa: E402
    DecisionTreeClassifier,
    export_text,
    plot_tree,
)

try:  # package import
    from .risk_config import (
        CRITICAL,
        OUTPUTS_DIR,
        PrivacyMapping,
        SAFE,
        load_service_mapping,
        resolve_path,
        risk_level_label,
    )
except ImportError:  # script import
    from risk_config import (  # type: ignore[no-redef]
        CRITICAL,
        OUTPUTS_DIR,
        PrivacyMapping,
        SAFE,
        load_service_mapping,
        resolve_path,
        risk_level_label,
    )


TREE_RULES_FILENAME = "tree_rules.txt"
TREE_PLOT_FILENAME = "decision_tree.png"
DEFAULT_TREE_RULES_PATH = OUTPUTS_DIR / TREE_RULES_FILENAME
DEFAULT_TREE_PLOT_PATH = OUTPUTS_DIR / TREE_PLOT_FILENAME

# Exhaustive 3^n grids are cheap up to ~9 factors (19,683 rows). Above that we
# sample deterministically to keep memory and training time bounded.
MAX_EXHAUSTIVE_FACTORS = 9
MAX_SAMPLED_ROWS = 30_000
RANDOM_SEED = 42
# Real service rows are up-weighted so the interpretable (shallow) tree keeps
# the known services correct while still generalising across the 0/1/2 grid.
SERVICE_SAMPLE_WEIGHT = 5.0


@dataclass
class TreeTrainingResult:
    """Everything the UI needs to explain and export the trained tree."""

    classifier: DecisionTreeClassifier
    feature_names: tuple[str, ...]
    class_names: tuple[str, ...]
    training_size: int
    max_depth: int
    rules_text: str

    def predict_level(self, levels: Mapping[str, int]) -> int:
        vector = [[int(levels.get(name, SAFE)) for name in self.feature_names]]
        return int(self.classifier.predict(vector)[0])


def build_training_data(
    mapping: PrivacyMapping,
) -> tuple[list[list[int]], list[int], list[float]]:
    """Create an exhaustive 0/1/2 grid and derive discrete labels.

    Labels are computed from the weighted score *ratio*, which keeps the
    Low/Medium/High boundaries stable when the number of factors grows.
    Real services are appended with a higher sample weight so the shallow,
    human-readable tree does not misclassify the services users actually see.
    """

    feature_names = mapping.feature_names
    if not feature_names:
        raise ValueError(
            "No risk factors found. Check data/service_mapping.json or run "
            "`python src/backend/service_collector.py`."
        )

    if len(feature_names) <= MAX_EXHAUSTIVE_FACTORS:
        combos: Iterable[Sequence[int]] = itertools.product(
            range(CRITICAL + 1), repeat=len(feature_names)
        )
    else:
        rng = random.Random(RANDOM_SEED)

        def _sample() -> Iterable[Sequence[int]]:
            for _ in range(MAX_SAMPLED_ROWS):
                yield tuple(rng.randint(SAFE, CRITICAL) for _ in feature_names)

        combos = _sample()

    features: list[list[int]] = []
    labels: list[int] = []
    weights: list[float] = []
    for combo in combos:
        levels = dict(zip(feature_names, combo))
        features.append(list(combo))
        labels.append(mapping.classify_levels(levels))
        weights.append(1.0)

    for service_name in mapping.services:
        service_levels = mapping.levels_for_service(service_name)
        features.append([service_levels[key] for key in feature_names])
        labels.append(mapping.classify_levels(service_levels))
        weights.append(SERVICE_SAMPLE_WEIGHT)

    return features, labels, weights


def build_rules_text(
    classifier: DecisionTreeClassifier,
    mapping: PrivacyMapping,
    training_size: int,
    feature_names: Sequence[str],
    class_names: Sequence[str],
) -> str:
    weights = ", ".join(
        f"{factor.key}={factor.weight:g} ({factor.label_zh})" for factor in mapping.factors
    )
    low_max = mapping.thresholds["low_max_ratio"] * 100
    medium_max = mapping.thresholds["medium_max_ratio"] * 100
    rules = export_text(
        classifier,
        feature_names=list(feature_names),
        class_names=list(class_names),
        decimals=1,
        show_weights=True,
        max_depth=12,
    )
    header = "\n".join(
        [
            "Data-Mirror - Privacy Risk Decision Tree",
            "=" * 72,
            f"Generated (UTC): {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
            f"Mapping schema: {mapping.schema_version}",
            f"Training samples: {training_size} (0/1/2 grid + observed services)",
            f"Feature order: {', '.join(feature_names)}",
            f"Factor weights: {weights}",
            f"Maximum weighted score: {mapping.max_score:g}",
            (
                "Discrete label thresholds: "
                f"Low < {low_max:.1f}% <= Medium < {medium_max:.1f}% <= High"
            ),
            "Class labels: 0=Low, 1=Medium, 2=High",
            "",
            "Note: the tree is an interpretable approximation of the weighted",
            "score formula. Near class boundaries, the tree may disagree with",
            "the exact weighted calculation; the UI shows both for transparency.",
            "=" * 72,
            "",
            rules,
        ]
    )
    return header


def train_decision_tree(
    mapping: PrivacyMapping | None = None,
    *,
    max_depth: int = 6,
    min_samples_leaf: int = 1,
    random_state: int = RANDOM_SEED,
) -> TreeTrainingResult:
    """Train on the dynamic feature grid and return an explainable result."""

    mapping = mapping or load_service_mapping()
    if not mapping.factors:
        raise ValueError("The mapping contains no risk factors.")

    features, labels, sample_weights = build_training_data(mapping)
    classifier = DecisionTreeClassifier(
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        random_state=random_state,
    )
    classifier.fit(features, labels, sample_weight=sample_weights)

    # class_names must follow classifier.classes_ order.
    class_names = tuple(
        risk_level_label(int(class_id), language="en")
        for class_id in classifier.classes_
    )
    feature_names = tuple(mapping.feature_names)
    rules_text = build_rules_text(
        classifier,
        mapping,
        training_size=len(features),
        feature_names=feature_names,
        class_names=class_names,
    )
    return TreeTrainingResult(
        classifier=classifier,
        feature_names=feature_names,
        class_names=class_names,
        training_size=len(features),
        max_depth=max_depth,
        rules_text=rules_text,
    )


def export_tree_rules(
    result: TreeTrainingResult,
    output_path: str | Path | None = None,
) -> Path:
    target = resolve_path(output_path, DEFAULT_TREE_RULES_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(result.rules_text, encoding="utf-8")
    return target


def export_tree_plot(
    result: TreeTrainingResult,
    output_path: str | Path | None = None,
) -> Path:
    """Render the tree with matplotlib (no Graphviz binary required)."""

    target = resolve_path(output_path, DEFAULT_TREE_PLOT_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)

    leaves = max(1, result.classifier.get_n_leaves())
    depth = result.classifier.get_depth()
    width = min(42.0, max(14.0, math.sqrt(leaves) * 3.2))
    height = min(26.0, max(9.0, (depth + 1) * 2.2))

    fig, ax = plt.subplots(figsize=(width, height), dpi=160)
    plot_tree(
        result.classifier,
        feature_names=list(result.feature_names),
        class_names=list(result.class_names),
        filled=True,
        rounded=True,
        impurity=False,
        proportion=False,
        precision=2,
        fontsize=9,
        ax=ax,
    )
    ax.set_title(
        "Data-Mirror Privacy Risk Decision Tree "
        f"({result.training_size} samples, depth={depth})",
        fontsize=14,
        pad=16,
    )
    fig.tight_layout()
    fig.savefig(target, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return target


def train_and_export(
    mapping: PrivacyMapping | None = None,
    *,
    outputs_dir: str | Path | None = None,
) -> tuple[TreeTrainingResult, Path, Path]:
    """Train and write both required output artefacts."""

    mapping = mapping or load_service_mapping()
    result = train_decision_tree(mapping)

    output_dir = resolve_path(outputs_dir, OUTPUTS_DIR)
    rules_path = export_tree_rules(result, output_dir / TREE_RULES_FILENAME)
    plot_path = export_tree_plot(result, output_dir / TREE_PLOT_FILENAME)
    return result, rules_path, plot_path


def main() -> None:
    mapping = load_service_mapping()
    result, rules_path, plot_path = train_and_export(mapping)
    print("[Success] Decision tree trained.")
    print(f"  Factors ({len(result.feature_names)}): {', '.join(result.feature_names)}")
    print(f"  Samples: {result.training_size}")
    print(f"  Rules: {rules_path}")
    print(f"  Plot:  {plot_path}")


if __name__ == "__main__":
    main()
