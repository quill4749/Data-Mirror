# Data-Mirror

**授權條款：** [GNU AGPL v3.0（AGPL-3.0-only）](LICENSE)　｜　**定位：** 開源、教育導向的隱私風險檢測工具

📌 **Data Mirror：看見你的數位足跡**

Data Mirror 是一個開源、教育導向的隱私風險檢測工具。它把 App 與網路服務的資料收集行為轉換成可理解的分數、風險等級與具體防禦建議，讓數位權利不再只是抽象概念。

## 文件導覽

- [設計理念](docs/concept.md)：為什麼要做 Data Mirror，以及它扮演的三個角色。
- [示範情境](examples/demo-scenarios.md)：七個可重現的使用案例，含實際分數與防禦建議。
- [資料來源與引用](docs/sources.md)：商店隱私標籤、權限文件、開源掃描工具與各服務查證入口。
- [README](README.md)：安裝、執行、JSON schema 與動態擴充方式。

---

## 核心功能

- **動態風險因子**：所有特徵與權重都存放在 `data/service_mapping.json`，新增麥克風、剪貼簿、螢幕錄製等因子時不需修改模型或 UI。
- **加權評分**：依因子敏感度計算加權總分，再以比例制離散化為低／中／高風險。
- **決策樹透明化**：使用 `DecisionTreeClassifier` 產生可閱讀的規則，並輸出 `outputs/tree_rules.txt` 與 `outputs/decision_tree.png`。
- **即時互動介面**：Streamlit 介面會隨選擇即時更新分數、風險等級與防禦建議。
- **無障礙設計**：語意化標題、鍵盤操作、可見焦點、高對比狀態卡、ARIA live/meter、圖片的替代文字，以及 `prefers-reduced-motion` 支援。
- **跨平台路徑防呆**：所有路徑均由 `pathlib.Path(__file__).resolve()` 推算絕對路徑；資料檔缺失時會自動生成，避免 `FileNotFoundError`。

---

## 專案結構

```text
Data-Mirror/
├── data/
│   └── service_mapping.json      # schema v2：因子權重 + 服務風險矩陣
├── outputs/                      # 由程式產生，未納入版本控制
│   ├── tree_rules.txt            # 文字版決策規則
│   └── decision_tree.png         # 決策樹視覺化
├── src/
│   ├── __init__.py
│   └── backend/
│       ├── __init__.py
│       ├── risk_config.py        # 共用路徑、權重、載入與評分邏輯
│       ├── service_collector.py  # 產生 service_mapping.json（正式入口）
│       ├── tree_model.py         # 動態特徵 + 決策樹訓練與輸出
│       └── app.py                # Streamlit 互動介面
├── LICENSE                       # GNU AGPL v3.0（AGPL-3.0-only）
├── THIRD_PARTY_NOTICES.md        # 第三方授權與通知
├── requirements.txt
└── README.md
```

---

## 快速開始

```bash
python3 -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 1. 產生結構化風險矩陣（若 data/service_mapping.json 已存在也會重新整理）
python src/backend/service_collector.py

# 2. 訓練決策樹並輸出規則與圖表
python src/backend/tree_model.py

# 3. 啟動網頁介面
streamlit run src/backend/app.py
```

> `app.py` 也會在資料檔缺失時自動呼叫 collector。舊版 `data_collector.py` 相容入口已移除，請統一使用 `service_collector.py`。

---

## 評分方法與學理依據

### 掃描分級

採用開源隱私掃描常見的 0 / 1 / 2 分級：

| 分數 | 等級 | 定義 |
|---:|---|---|
| 0 | 安全 Safe | 未發現該項收集，或僅為使用者主動觸發的單次功能 |
| 1 | 中等 Medium | 與核心功能相關，或需使用者授權，但仍有暴露面 |
| 2 | 嚴重 Critical | 高侵略性背景收集、跨 App 串接，或不可逆的敏感資料 |

### 因子權重

| 風險因子 | 權重 | 學理依據 |
|---|---:|---|
| 行為側寫 Behavioral Profiling | **2.0** | 隱私侵害具不可逆性；跨 App 長期追蹤會形成持久、難以撤回的個人輪廓與識別碼關聯。 |
| 位置追蹤 Location Tracking | **1.5** | `ACCESS_FINE_LOCATION` / 背景定位屬 OS 高敏感權限，可推論住家、工作地、醫療與宗教活動。 |
| 精準廣告 Targeted Ads | **1.0** | 第三方廣告 SDK 與 Cookie 支撐商業行銷與再行銷，影響範圍通常較前兩者窄。 |
| 麥克風 Microphone | **1.8** | 可捕捉私人對話與環境聲音，內容難以撤回，風險接近行為側寫。 |
| 通訊錄 Contacts | **1.4** | 會揭露非使用者的第三人資料，形成社交圖譜外洩，且難以補救。 |
| 剪貼簿 Clipboard | **1.2** | 常承載 OTP、密碼、地址等高價值秘密，外洩後果直接。 |
| 生物特徵 Biometric | **1.7** | 指紋、臉部等特徵無法更換，一旦外洩即永久暴露。 |

未在權重表中定義的新因子會使用 **1.2** 作為預設權重；動態擴充因子的建議範圍為 **1.2–1.8**。所有權重都儲存在 JSON 的 `risk_factors` 中，可依研究或場域需求調整。

### 公式與離散化

```text
加權總分 = Σ（因子等級 × 因子權重）
風險比例 = 加權總分 ÷ Σ（2 × 所有因子權重）
```

比例制門檻：

```text
低風險：ratio < 1/3
中風險：1/3 <= ratio < 2/3
高風險：ratio >= 2/3
```

使用比例而非固定絕對分數，是因為新增因子會改變最高可能分數；比例制可讓門檻在動態擴充後保持穩定。

`DecisionTreeClassifier` 不接受連續標籤，因此模型訓練前會先依上述門檻把加權分數轉成離散類別 `0 / 1 / 2`。決策樹是加權公式的可解釋近似；若在門檻邊界出現模型與公式不一致，UI 會同時顯示兩者，並以加權公式作為主要判定。

---

## JSON 結構（schema v2）

```json
{
  "schema_version": "2.0",
  "risk_thresholds": {
    "low_max_ratio": 0.3333,
    "medium_max_ratio": 0.6667
  },
  "risk_factors": {
    "location_tracking": {
      "label_zh": "位置追蹤",
      "label_en": "Location Tracking",
      "weight": 1.5,
      "description": "精確定位、背景定位與移動路徑。",
      "rationale": "ACCESS_FINE_LOCATION 屬高敏感權限。",
      "advice": "將非導航 App 的定位改為「僅使用期間」。"
    }
  },
  "services": {
    "instagram": {
      "location_tracking": 2,
      "behavioral_profiling": 2
    }
  }
}
```

舊版扁平格式（`{"instagram": {"location_tracking": 2}}`）仍可讀取，會自動補上預設因子定義。

---

## 動態擴充因子

```python
from service_collector import PrivacyRiskCollector

collector = PrivacyRiskCollector()
collector.register_factor(
    "screen_recording",
    weight=1.6,
    label_zh="螢幕錄製",
    label_en="Screen Recording",
    description="背景錄製螢幕或畫面內容。",
    rationale="可能捕捉訊息、密碼與金融資訊，且難以撤回。",
    advice="撤銷非必要 App 的螢幕錄製與無障礙服務權限。",
)
collector.register_service(
    "my_app",
    {"screen_recording": 2, "location_tracking": 1},
)
collector.generate_mapping_file()
```

重新執行 `tree_model.py` 或重新整理 Streamlit 頁面後，模型與 UI 會自動採用新因子，不需要修改任何固定清單。

---

## 輸出檔案

| 檔案 | 說明 |
|---|---|
| `data/service_mapping.json` | 動態因子權重、分級定義與服務風險矩陣 |
| `outputs/tree_rules.txt` | 文字版決策規則、特徵順序、權重與門檻 |
| `outputs/decision_tree.png` | 以 matplotlib 繪製的決策樹（不需安裝 Graphviz） |

---

## 無障礙與透明度

- 使用 `st.title` / `st.header` / `st.subheader` 建立語意化標題層級。
- 所有互動元件皆為原生、可用 Tab / Shift+Tab / 方向鍵操作的 Streamlit 元件。
- 提供可見的 `:focus-visible` 焦點框與「跳至主要內容」連結。
- 風險狀態同時以文字、圖示與數值呈現，不依賴顏色判讀。
- 風險卡使用 `role="status"` / `aria-live`，進度條使用 `role="meter"`。
- 決策樹圖片提供 `alt` 文字與可下載的文字規則替代方案。
- 支援 `prefers-reduced-motion`，降低動態效果。

---

## 資料來源與限制

風險分數是根據公開 App 隱私標籤、作業系統權限文件與開源行動隱私掃描邏輯（例如第三方追蹤器與權限分析）整理的**教育性近似值**，不是即時稽核結果。本工具不構成法律、資安稽核或任何形式的保證；實際資料收集行為可能隨 App 版本、地區與使用者設定而異。

各來源的官方文件、各服務的商店頁面與查證方式，請見 [docs/sources.md](docs/sources.md)。

---

## 授權條款

本專案採用 **GNU Affero General Public License version 3（AGPL-3.0-only）** 授權。

- **完整授權條文：** [LICENSE](LICENSE)
- **官方授權說明：** <https://www.gnu.org/licenses/agpl-3.0.html>
- **Copyright (C) 2026 quill4749 (https://github.com/quill4749/Data-Mirror)**

你可以自由使用、研究、修改與散布本專案；若散布修改後的版本，必須以相同授權提供對應原始碼，保留著作權與授權聲明，並標示修改內容。以上僅為摘要，法律效力以 [LICENSE](LICENSE) 全文為準。

### 網路服務條款（AGPL §13）

AGPL-3.0 與 GPL-3.0 最大的差異，在於它把「網路服務」也納入 copyleft 範圍。若你修改本專案，並以網路服務（例如公開的 Streamlit 網站）形式讓使用者互動，即使沒有散布軟體本身，也必須依 AGPL §13 向這些使用者提供 **Corresponding Source（對應原始碼）**，包含你所修改的版本。

實務上可透過頁面上的「原始碼」連結、`/source` 端點或其他清楚可見的方式提供。若只是在本機執行、或未修改地部署本專案，仍建議保留本節與 `LICENSE` 的連結，以利使用者取得授權資訊與原始碼。

---

## 第三方引用與素材說明

### 軟體依賴

本專案透過 `requirements.txt` 安裝第三方套件，**未將這些套件的原始碼 vendoring 進本 repo**。各套件仍受其原授權條款約束：

| 套件 / 執行環境 | 用途 | 授權 |
|---|---|---|
| [Streamlit](https://streamlit.io/) | 網頁互動介面 | Apache License 2.0 |
| [scikit-learn](https://scikit-learn.org/) | 決策樹分類與規則輸出 | BSD 3-Clause |
| [Matplotlib](https://matplotlib.org/) | 決策樹圖表繪製 | Matplotlib License（BSD 相容） |
| [pandas](https://pandas.pydata.org/) | 表格資料處理 | BSD 3-Clause |
| [NumPy](https://numpy.org/) | 數值運算 | BSD 3-Clause |
| [Python](https://www.python.org/) | 執行環境 | PSF License 2.0 |

完整依賴樹與授權資訊，請以實際安裝環境中的套件 metadata 為準。若你要再散布本專案的執行環境或容器映像，請一併保留第三方套件的授權與通知。更完整的授權與通知內容整理於 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

### Streamlit 的授權與標示

Streamlit 以 **Apache License 2.0** 釋出，與 AGPL-3.0 相容。本專案只在程式碼中透過 `import streamlit` 使用它，未修改、未 fork、也未將 Streamlit 原始碼放進本 repo，因此：

- **不需要**在自有程式碼檔案加入 Streamlit 的授權標頭。
- **不需要**在 README 或介面上逐字重現 Apache-2.0 全文（本 repo 未散布 Streamlit 原始碼）。
- 若你打包執行環境（例如 Docker image、`venv`、可執行檔）一併散布 Streamlit，則必須保留 Streamlit 套件內的 `LICENSE` 與任何 `NOTICE` 檔案，並在第三方授權清單中標示。
- 若在介面上提及 Streamlit，僅以「技術依賴」描述，**不得使用 Streamlit 的商標、Logo 或暗示官方背書**。Apache-2.0 §6 明確排除商標授權。

本專案的[第三方授權清單](THIRD_PARTY_NOTICES.md)已記錄 Streamlit 與其他依賴的授權、用途與注意事項。

### 資料、商標與素材

- `data/service_mapping.json` 中的服務名稱與分數，是根據公開的 App 隱私標籤、Android／iOS 權限文件與開源隱私掃描概念**重新整理與教學化**而成；本 repo 未包含任何第三方資料庫的原始傾印、App 圖示、截圖、Logo、字型、音樂或影片。
- Instagram、TikTok、Google Maps、Uber、WhatsApp、Signal、Spotify、Notion 等名稱與商標，屬各自權利人所有。本專案僅將它們用於服務辨識與教育說明，**不代表任何關聯、贊助、合作或背書**。
- 文件中提及 Exodus Privacy、MobSF、εxodus 等開源工具，僅作為方法論與資料來源類型的說明；本 repo 未包含其程式碼、資料集或商標素材。
- `outputs/decision_tree.png` 由本專案程式透過 Matplotlib 即時生成，不包含第三方圖片素材；此類產出檔未納入版本控制。Matplotlib 使用的字型由其套件提供，未另外複製字型檔。
- `LICENSE` 為 Free Software Foundation 公布的 AGPL-3.0 官方條文；該授權允許逐字複製與散布授權文件本身。

若你發現任何授權標示缺漏或疑似未授權素材，請開 issue 或聯絡維護者，我們會儘速確認與修正。

---

## 免責聲明

本專案、文件、分數與建議僅供**教育、研究與自我檢視**使用，不構成法律、資安、醫療、財務或任何專業領域的意見，也不保證能偵測所有資料收集行為。

- 風險分數是公開資訊的近似整理，可能因 App 版本、地區、裝置、使用者授權與平台政策而改變。
- 決策樹是加權公式的可解釋近似；在分類門檻附近，模型判定可能與公式不同。介面會同時顯示兩者，實際判讀請以加權公式、因子明細與原始資料為主要依據。
- 本專案不對任何特定服務作出安全性、合法性或可信度的保證，也不代表任何服務商的立場。
- 使用者應自行評估是否採用本工具、如何調整隱私設定，以及相關決策的後果。
- 依 AGPL-3.0 第 15、16 條，本軟體以「現狀」提供，不提供任何明示或默示的擔保；因使用或無法使用本軟體所造成的損害，作者與貢獻者不負賠償責任。法律效力以 [LICENSE](LICENSE) 全文為準。

若將本專案部署為公開網站或服務，請自行處理資料保護、Cookie／分析工具、存取控制、速率限制與當地法規遵循等事宜。

---

## 安全與隱私實務

- 本 repo 目前**不含**私密金鑰、API token、資料庫密碼、雲端憑證或個人帳號資料。
- 本專案預設不要求使用者登入，也不會將使用者的服務選擇上傳到本專案控制的伺服器；服務風險資料來自靜態 JSON。
- `.gitignore` 已排除常見憑證檔（`.env`、`*.pem`、`*.key`、`*.p12`、`*.pfx`、`*.jks`、`*.keystore`、`credentials.json`、`secrets.json` 等）。新增環境變數時，請使用 `.env` 並確認未被追蹤。
- 第三方套件、部署平台或瀏覽器仍可能有其自身的遥測與記錄設定；部署前請依實際環境檢視。
- 若要在公開環境提供服務，建議加上 HTTPS、最小權限、依賴更新與定期安全掃描。

---

## 授權連結摘要

- [LICENSE](LICENSE)
- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
- [GNU AGPL v3.0 官方頁面](https://www.gnu.org/licenses/agpl-3.0.html)
- [GNU AGPL v3.0 常見問答](https://www.gnu.org/licenses/gpl-faq.html)
