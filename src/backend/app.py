# SPDX-FileCopyrightText: 2026 quill4749 (https://github.com/quill4749/Data-Mirror)
# SPDX-License-Identifier: AGPL-3.0-only

"""Data-Mirror — Streamlit UI.

Design goals
------------
* Dynamically discover risk factors from ``data/service_mapping.json``.
* Compute the weighted score live and discretise it into Low / Medium / High.
* Generate factor-specific defence advice from the JSON metadata, not a
  hard-coded three-item dictionary.
* Follow W3C WCAG 2.x practices where Streamlit allows it:
    - semantic H1/H2/H3 headings,
    - native, keyboard-operable widgets (Tab / Shift+Tab / arrow keys),
    - visible focus indicators,
    - high-contrast status cards whose meaning is conveyed by text + icon,
      never by colour alone,
    - ARIA live status / meter semantics and skip-to-content link,
    - reduced-motion support and screen-reader-only text.

Run:
    streamlit run src/backend/app.py
"""

from __future__ import annotations

import base64
import html
import json
import sys
from pathlib import Path

import streamlit as st

# Make sibling modules importable whether Streamlit runs the script directly or
# imports the package.
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:  # package import
    from .risk_config import (
        CRITICAL,
        DEFAULT_MAPPING_PATH,
        OUTPUTS_DIR,
        RISK_LEVELS,
        RISK_SCALE,
        PrivacyMapping,
        load_service_mapping,
        risk_level_label,
        scale_label,
    )
    from .tree_model import (
        TREE_PLOT_FILENAME,
        TREE_RULES_FILENAME,
        TreeTrainingResult,
        export_tree_plot,
        export_tree_rules,
        train_decision_tree,
    )
except ImportError:  # streamlit run src/backend/app.py
    from risk_config import (  # type: ignore[no-redef]
        CRITICAL,
        DEFAULT_MAPPING_PATH,
        OUTPUTS_DIR,
        RISK_LEVELS,
        RISK_SCALE,
        PrivacyMapping,
        load_service_mapping,
        risk_level_label,
        scale_label,
    )
    from tree_model import (  # type: ignore[no-redef]
        TREE_PLOT_FILENAME,
        TREE_RULES_FILENAME,
        TreeTrainingResult,
        export_tree_plot,
        export_tree_rules,
        train_decision_tree,
    )


# ---------------------------------------------------------------------------
# Page + accessible styling
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Data-Mirror 數位足跡與隱私風險檢測",
    page_icon="🔍",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
  :root {
    --dm-ink: #111827;
    --dm-muted: #374151;
    --dm-surface: #f8fafc;
    --dm-border: #374151;
    --dm-low: #0b6b3a;
    --dm-medium: #8a4b00;
    --dm-high: #a4161a;
    --dm-focus: #0b57d0;
  }

  /* Visible keyboard focus for every interactive element (WCAG 2.4.7). */
  a:focus-visible,
  button:focus-visible,
  input:focus-visible,
  textarea:focus-visible,
  select:focus-visible,
  [role="button"]:focus-visible,
  [role="radio"]:focus-visible,
  [tabindex]:focus-visible {
    outline: 3px solid var(--dm-focus) !important;
    outline-offset: 3px !important;
  }

  /* Skip link becomes visible on keyboard focus (WCAG 2.4.1). */
  .dm-skip-link {
    position: absolute;
    left: -9999px;
    top: 0;
    z-index: 10000;
    background: #ffffff;
    color: #0b3d91;
    padding: 0.7rem 1rem;
    border: 3px solid #0b3d91;
    border-radius: 0.4rem;
    font-weight: 700;
  }
  .dm-skip-link:focus {
    left: 1rem;
    top: 1rem;
  }

  .dm-risk-card {
    border: 2px solid var(--dm-border);
    border-left-width: 10px;
    border-radius: 0.6rem;
    background: #ffffff;
    color: var(--dm-ink);
    padding: 1rem 1.2rem;
    margin: 0.4rem 0 0.8rem 0;
  }
  .dm-risk-card h3 {
    margin: 0.15rem 0 0.45rem 0;
    font-size: 1.35rem;
    line-height: 1.35;
  }
  .dm-risk-card p {
    margin: 0.25rem 0;
    color: var(--dm-ink);
  }
  .dm-risk-low { border-left-color: var(--dm-low); }
  .dm-risk-medium { border-left-color: var(--dm-medium); }
  .dm-risk-high { border-left-color: var(--dm-high); }

  .dm-eyebrow {
    font-size: 0.85rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--dm-muted);
  }

  .dm-meter {
    height: 1.15rem;
    width: 100%;
    background: #e5e7eb;
    border: 2px solid var(--dm-border);
    border-radius: 999px;
    overflow: hidden;
    margin: 0.2rem 0 0.4rem 0;
  }
  .dm-fill { display: block; height: 100%; }
  .dm-fill-low { background: var(--dm-low); }
  .dm-fill-medium { background: var(--dm-medium); }
  .dm-fill-high { background: var(--dm-high); }

  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }

  .dm-advice {
    border: 2px solid #cbd5e1;
    border-left: 8px solid var(--dm-focus);
    border-radius: 0.5rem;
    padding: 0.9rem 1rem;
    background: var(--dm-surface);
    color: var(--dm-ink);
    margin-bottom: 0.75rem;
  }
  .dm-advice h3 { margin: 0 0 0.4rem 0; font-size: 1.1rem; }
  .dm-advice p { margin: 0.35rem 0; color: var(--dm-ink); }

  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
      scroll-behavior: auto !important;
    }
  }

  @media (max-width: 640px) {
    .dm-risk-card { padding: 0.85rem; }
  }
</style>
<a class="dm-skip-link" href="#dm-main">跳至主要內容</a>
<span id="dm-main" tabindex="-1"></span>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Data + model loaders (cached for responsiveness)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def get_mapping(mapping_path: str, file_stamp: str) -> PrivacyMapping:
    # file_stamp invalidates the cache when the JSON is regenerated.
    _ = file_stamp
    return load_service_mapping(mapping_path)


def file_stamp(path: Path) -> str:
    try:
        stat = path.stat()
    except OSError:
        return "missing"
    return f"{stat.st_mtime_ns}:{stat.st_size}"


def mapping_signature(mapping: PrivacyMapping) -> str:
    factors = "|".join(
        f"{factor.key}:{factor.weight}:{factor.label_zh}"
        for factor in mapping.factors
    )
    thresholds = (
        f"{mapping.thresholds['low_max_ratio']}:"
        f"{mapping.thresholds['medium_max_ratio']}"
    )
    services = "|".join(
        f"{name}:" + ",".join(str(scores[factor.key]) for factor in mapping.factors)
        for name, scores in mapping.services.items()
    )
    return f"{mapping.schema_version}|{factors}|{thresholds}|{services}"


@st.cache_resource(show_spinner=False)
def get_tree(cache_key: str, mapping_path: str, file_stamp_value: str) -> TreeTrainingResult:
    # cache_key/file_stamp_value participate in Streamlit's cache hash; the
    # mapping is reloaded from its own cache.
    _ = (cache_key, file_stamp_value)
    return train_decision_tree(get_mapping(mapping_path, file_stamp_value))


def format_scale(value: int) -> str:
    entry = RISK_SCALE.get(int(value), RISK_SCALE[0])
    return f"{entry['label_zh']}（{entry['label_en']}）"


def render_risk_card(risk_class: int, total: float, maximum: float) -> None:
    meta = RISK_LEVELS[risk_class]
    percent = (total / maximum * 100.0) if maximum > 0 else 0.0
    tone = meta["tone"]
    st.markdown(
        f"""
<section class="dm-risk-card dm-risk-{tone}" role="status" aria-live="polite" aria-atomic="true">
  <p class="dm-eyebrow">整體風險評估</p>
  <h3>{html.escape(meta['icon'])} 風險等級：{html.escape(meta['label_zh'])}（{html.escape(meta['label_en'])}）</h3>
  <p><strong>加權總分：</strong>{total:.1f} / {maximum:.1f}（{percent:.1f}%）</p>
  <p>{html.escape(meta['summary'])}</p>
</section>
<div class="dm-meter" role="meter" aria-valuemin="0" aria-valuemax="100"
     aria-valuenow="{percent:.0f}" aria-label="加權風險分數百分比">
  <span class="dm-fill dm-fill-{tone}" style="width:{percent:.1f}%"></span>
</div>
<p class="sr-only">加權風險分數為百分之 {percent:.0f}。</p>
""",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("Data Mirror：數位足跡與隱私風險檢測")
st.markdown(
    "透過**動態風險因子**、**加權評分**與**決策樹模型**，"
    "看見日常服務可能蒐集的資料，並取得具體的隱私防禦建議。"
)
st.caption(
    "無障礙操作提示：使用 Tab / Shift+Tab 移動焦點，空白鍵或 Enter 操作，"
    "方向鍵切換選項。所有風險狀態同時以文字與圖示呈現，不依賴顏色判讀。"
)

try:
    mapping_stamp = file_stamp(DEFAULT_MAPPING_PATH)
    mapping = get_mapping(str(DEFAULT_MAPPING_PATH), mapping_stamp)
except Exception as exc:  # defensive: the loader itself is already resilient
    st.error(f"無法載入風險資料：{exc}")
    st.code("python src/backend/service_collector.py", language="bash")
    st.stop()

if not mapping.services:
    st.error(
        "找不到可用的服務資料。請先產生 `data/service_mapping.json`，"
        "再重新整理本頁。"
    )
    st.code("python src/backend/service_collector.py", language="bash")
    st.stop()

st.caption(f"資料來源：`{mapping.source_path or DEFAULT_MAPPING_PATH}`")

# ---------------------------------------------------------------------------
# 1. Service selection
# ---------------------------------------------------------------------------
st.header("1. 選擇您使用的服務")
st.markdown(
    "勾選日常使用的 App 或網路服務。系統會取各服務中**每一項風險因子的最高值**"
    "作為預設暴露向量；您也可以在下一步微調。"
)

service_names = list(mapping.services.keys())
selected_services = st.multiselect(
    "服務（可複選）",
    options=service_names,
    help="使用 Tab 鍵移動焦點，輸入關鍵字搜尋，按 Enter 或空白鍵選取。",
)

# When the service selection (or feature space) changes, refresh the factor
# radio defaults. Manual edits are preserved while the selection is unchanged.
selection_signature = json.dumps(
    {
        "services": selected_services,
        "factors": [factor.key for factor in mapping.factors],
    },
    ensure_ascii=False,
    sort_keys=True,
)
if st.session_state.get("_dm_selection_signature") != selection_signature:
    auto_levels = mapping.aggregate_levels(selected_services)
    for factor in mapping.factors:
        st.session_state[f"_dm_level_{factor.key}"] = auto_levels[factor.key]
    st.session_state["_dm_selection_signature"] = selection_signature

# ---------------------------------------------------------------------------
# 2. Dynamic factor controls
# ---------------------------------------------------------------------------
st.header("2. 檢視與微調風險因子")
with st.expander("進階設定：逐項調整風險因子等級", expanded=False):
    st.caption(
        "等級定義：0 = 安全（Safe）、1 = 中等（Medium）、2 = 嚴重（Critical）。"
        "預設值來自所選服務的最高暴露值。"
    )
    levels: dict[str, int] = {}
    for factor in mapping.factors:
        levels[factor.key] = st.radio(
            f"{factor.label_zh}（權重 {factor.weight:g}）",
            options=[0, 1, 2],
            format_func=format_scale,
            horizontal=True,
            key=f"_dm_level_{factor.key}",
            help=f"{factor.description} 評分依據：{factor.rationale}",
        )

# ---------------------------------------------------------------------------
# 3. Live weighted score + risk level
# ---------------------------------------------------------------------------
st.header("3. 即時風險評估")
weighted_total = mapping.weighted_score(levels)
maximum_score = mapping.max_score
risk_class = mapping.classify_score(weighted_total)
score_ratio = mapping.score_ratio(weighted_total)

if not selected_services and weighted_total <= 0:
    st.info(
        "請先在上方選擇至少一項服務，或展開「進階設定」調整風險因子，"
        "系統會即時計算加權總分。"
    )
else:
    render_risk_card(risk_class, weighted_total, maximum_score)

    metric_cols = st.columns(3)
    metric_cols[0].metric(
        "加權總分",
        f"{weighted_total:.1f}",
        help="公式：Σ（風險因子等級 × 因子權重）。",
    )
    metric_cols[1].metric(
        "風險比例",
        f"{score_ratio * 100:.1f}%",
        help="加權總分 ÷ 所有因子皆為 Critical 時的最高可能分數。",
    )
    metric_cols[2].metric(
        "已觸發因子",
        f"{sum(1 for value in levels.values() if value > 0)} / {len(mapping.factors)}",
        help="等級大於 0 的風險因子數量。",
    )

    low_max = mapping.thresholds["low_max_ratio"] * 100
    medium_max = mapping.thresholds["medium_max_ratio"] * 100
    st.caption(
        f"離散化門檻：低風險 < {low_max:.1f}%；"
        f"中風險 {low_max:.1f}% – {medium_max:.1f}%；"
        f"高風險 ≥ {medium_max:.1f}%。"
    )

    st.subheader("風險因子明細")
    factor_rows = []
    for factor in sorted(
        mapping.factors,
        key=lambda item: levels.get(item.key, 0) * item.weight,
        reverse=True,
    ):
        level = levels.get(factor.key, 0)
        factor_rows.append(
            {
                "風險因子": f"{factor.label_zh}（{factor.key}）",
                "等級": f"{level} · {scale_label(level)}",
                "權重": factor.weight,
                "加權分數": round(level * factor.weight, 2),
                "說明": factor.description,
            }
        )
    st.dataframe(
        factor_rows,
        hide_index=True,
        width="stretch",
        column_config={
            "權重": st.column_config.NumberColumn(format="%.2f"),
            "加權分數": st.column_config.NumberColumn(format="%.2f"),
        },
    )

# ---------------------------------------------------------------------------
# 4. Dynamic defence advice
# ---------------------------------------------------------------------------
st.header("4. 具體隱私防禦建議")
active_factors = [
    factor for factor in mapping.factors if levels.get(factor.key, 0) > 0
]
active_factors.sort(
    key=lambda factor: levels.get(factor.key, 0) * factor.weight, reverse=True
)

if not active_factors:
    st.success(
        "目前所有風險因子均為「安全」。仍建議定期檢查 App 權限、"
        "廣告追蹤設定與帳號的第三方授權。"
    )
else:
    st.markdown(
        "以下建議依**加權風險貢獻**由高至低排序；請優先處理等級為「嚴重」的項目。"
    )
    for factor in active_factors:
        level = levels.get(factor.key, 0)
        contribution = round(level * factor.weight, 2)
        urgency = "立即處理" if level == CRITICAL else "建議調整"
        st.markdown(
            f"""
<div class="dm-advice">
  <h3>{html.escape(factor.label_zh)}：{html.escape(scale_label(level))}（{urgency}）</h3>
  <p><strong>權重：</strong>{factor.weight:g}　
     <strong>本項加權分數：</strong>{contribution:g}　
     <strong>因子代碼：</strong>{html.escape(factor.key)}</p>
  <p>{html.escape(factor.advice)}</p>
</div>
""",
            unsafe_allow_html=True,
        )
        with st.expander(f"為什麼「{factor.label_zh}」是風險因子？"):
            st.markdown(f"**收集面說明：** {factor.description}")
            st.markdown(f"**學理依據：** {factor.rationale}")

safe_factors = [
    factor.label_zh for factor in mapping.factors if levels.get(factor.key, 0) == 0
]
if safe_factors:
    st.caption("目前維持在安全等級的因子：" + "、".join(safe_factors))

# ---------------------------------------------------------------------------
# 5. Per-service ranking
# ---------------------------------------------------------------------------
if selected_services:
    st.header("5. 各服務風險排行")
    service_rows = []
    for service_name in selected_services:
        service_levels = mapping.levels_for_service(service_name)
        service_total = mapping.weighted_score(service_levels)
        service_class = mapping.classify_score(service_total)
        top_factors = sorted(
            mapping.factors,
            key=lambda factor: service_levels.get(factor.key, 0) * factor.weight,
            reverse=True,
        )[:2]
        service_rows.append(
            {
                "服務": service_name,
                "加權分數": round(service_total, 2),
                "風險比例": f"{mapping.score_ratio(service_total) * 100:.1f}%",
                "風險等級": f"{RISK_LEVELS[service_class]['icon']} "
                f"{risk_level_label(service_class)}",
                "主要暴露因子": "、".join(
                    factor.label_zh
                    for factor in top_factors
                    if service_levels.get(factor.key, 0) > 0
                )
                or "無顯著因子",
            }
        )
    service_rows.sort(key=lambda row: row["加權分數"], reverse=True)
    st.dataframe(service_rows, hide_index=True, width="stretch")
    top_service = service_rows[0]
    top_class = mapping.classify_score(
        mapping.weighted_score(mapping.levels_for_service(top_service["服務"]))
    )
    st.markdown(
        f"優先檢視：**{top_service['服務']}**（"
        f"{risk_level_label(top_class)}，加權分數 {top_service['加權分數']:.1f}）。"
    )

# ---------------------------------------------------------------------------
# 6. Decision tree transparency
# ---------------------------------------------------------------------------
st.header("6. 決策樹模型與透明化")
try:
    with st.spinner("正在訓練動態決策樹…"):
        tree_result = get_tree(
            mapping_signature(mapping),
            str(DEFAULT_MAPPING_PATH),
            mapping_stamp,
        )
except Exception as exc:
    st.warning(f"目前無法訓練決策樹模型：{exc}")
    tree_result = None

if tree_result is not None:
    tree_prediction = tree_result.predict_level(levels)
    st.caption(
        f"模型以 {tree_result.training_size:,} 筆 0/1/2 因子組合訓練，"
        f"特徵數 {len(tree_result.feature_names)}，最大深度 {tree_result.max_depth}。"
    )

    model_cols = st.columns(2)
    model_cols[0].metric(
        "決策樹模型判定",
        risk_level_label(tree_prediction),
        help="DecisionTreeClassifier 的離散類別預測（0=低、1=中、2=高）。",
    )
    model_cols[1].metric(
        "加權公式判定",
        risk_level_label(risk_class),
        help="依 JSON 權重即時計算的規則判定；為 UI 顯示的主要風險等級。",
    )
    if tree_prediction != risk_class:
        st.caption(
            "模型判定與加權公式不同：決策樹是離散化後的近似規則，"
            "在分類門檻附近可能出現差異；請以加權公式與因子明細為主要依據。"
        )

    rules_path = OUTPUTS_DIR / TREE_RULES_FILENAME
    plot_path = OUTPUTS_DIR / TREE_PLOT_FILENAME

    if st.button("重新產生決策樹輸出檔案"):
        try:
            rules_path = export_tree_rules(tree_result, rules_path)
            plot_path = export_tree_plot(tree_result, plot_path)
            st.success(f"已更新：{rules_path.name}、{plot_path.name}")
        except Exception as exc:
            st.error(f"輸出失敗：{exc}")

    # Create artefacts on first run (or after deletion) without rewriting every
    # rerun.
    if not rules_path.exists() or not plot_path.exists():
        try:
            rules_path = export_tree_rules(tree_result, rules_path)
            plot_path = export_tree_plot(tree_result, plot_path)
        except Exception as exc:
            st.warning(f"無法自動產生輸出檔案：{exc}")

    with st.expander("查看文字版決策規則（tree_rules.txt）", expanded=False):
        st.code(tree_result.rules_text, language="text")

    if plot_path.exists():
        encoded = base64.b64encode(plot_path.read_bytes()).decode("ascii")
        st.markdown(
            f"""
<figure style="margin:0.5rem 0 1rem 0;">
  <img src="data:image/png;base64,{encoded}"
       alt="Data-Mirror 決策樹視覺化。根節點依權重最高的風險因子切分，葉節點顯示低、中、高風險類別與比例。完整文字規則可在上方展開區塊閱讀。"
       style="width:100%;height:auto;border:1px solid #cbd5e1;border-radius:0.4rem;" />
  <figcaption style="font-size:0.9rem;color:#374151;margin-top:0.35rem;">
    圖：決策樹視覺化。若圖片不易閱讀，請使用下方的文字規則或下載 PNG 放大檢視。
  </figcaption>
</figure>
""",
            unsafe_allow_html=True,
        )

    download_cols = st.columns(2)
    with download_cols[0]:
        st.download_button(
            "下載文字版決策規則",
            data=tree_result.rules_text,
            file_name=TREE_RULES_FILENAME,
            mime="text/plain",
            width="stretch",
        )
    with download_cols[1]:
        if plot_path.exists():
            st.download_button(
                "下載決策樹 PNG",
                data=plot_path.read_bytes(),
                file_name=TREE_PLOT_FILENAME,
                mime="image/png",
                width="stretch",
            )

# ---------------------------------------------------------------------------
# 7. Methodology / academic rationale
# ---------------------------------------------------------------------------
st.header("7. 評分方法與學理依據")
st.markdown(
    """
**加權公式**

`加權總分 = Σ（風險因子等級 × 因子權重）`

`風險比例 = 加權總分 ÷ Σ（2 × 所有因子權重）`

為避免新增因子後門檻失真，類別採**比例制**離散化：
低風險 < 33.3% ≤ 中風險 < 66.7% ≤ 高風險。
DecisionTreeClassifier 只接收這些離散標籤（0 / 1 / 2），因此不會出現 continuous label 錯誤。
"""
)
st.markdown("**掃描分級（0 / 1 / 2）**")
for level, entry in RISK_SCALE.items():
    st.markdown(
        f"- **{level} = {entry['label_zh']}（{entry['label_en']}）**：{entry['definition']}"
    )

st.markdown("**因子權重與依據**")
for factor in mapping.factors:
    st.markdown(
        f"- **{factor.label_zh}（{factor.weight:g}）**：{factor.rationale}"
    )

st.markdown(
    "權重與因子全部儲存在 `data/service_mapping.json` 的 `risk_factors` 中。"
    "新增麥克風、剪貼簿、螢幕錄製等因子時，只需擴充 JSON 或呼叫 "
    "`PrivacyRiskCollector.register_factor()`，模型與 UI 會自動採用，不需改寫固定清單。"
)

st.markdown("---")
st.caption(
    "Data-Mirror 為教育與自我檢視用途。分數基於公開隱私標籤與開源掃描邏輯的"
    "近似整理，不構成法律、資安稽核或任何形式的保證。"
)
