# 第三方授權與通知（Third-Party Notices）

本專案（Data-Mirror）以 **AGPL-3.0-only** 釋出。下列第三方元件並非本專案原始碼的一部分，而是透過 `requirements.txt` 安裝或由相依套件帶入；它們各自受其原授權條款約束。

> 本清單僅為整理與說明，不取代各套件隨附的完整授權文件。實際版本與授權內容請以你安裝環境中的套件 `metadata` 與 `LICENSE` 檔案為準。

## 一、執行期依賴

| 元件 | 本專案用途 | 授權 | 官方頁面 |
|---|---|---|---|
| Streamlit | 網頁互動介面 | Apache License 2.0 | <https://streamlit.io/> |
| scikit-learn | 決策樹分類與規則輸出 | BSD 3-Clause | <https://scikit-learn.org/> |
| Matplotlib | 決策樹圖表繪製 | Matplotlib License（BSD 相容） | <https://matplotlib.org/> |
| pandas | 表格資料處理 | BSD 3-Clause | <https://pandas.pydata.org/> |
| NumPy | 數值運算（多為間接依賴） | BSD 3-Clause | <https://numpy.org/> |
| Python | 執行環境 | PSF License 2.0 | <https://www.python.org/> |

部分套件（例如 NumPy）會一併帶入 OpenBLAS／LAPACK 等二進位函式庫。這些元件通常以 BSD 相容授權釋出，並附有各自的著作權聲明；若你要再散布執行環境或容器映像，請保留對應的授權與通知檔案。

## 二、Streamlit 特別說明

- **授權：** Apache License 2.0。
- **使用方式：** 本專案以 `import streamlit` 呼叫其公開 API，未修改、未 fork、未將 Streamlit 原始碼納入本 repo。
- **是否需要標頭：** 本專案自有程式碼不需加入 Streamlit 的授權標頭。
- **是否需要全文：** 若僅散布本專案原始碼，不需重現 Apache-2.0 全文；若連同執行環境（例如 Docker image、`venv`）一起散布，則必須保留 Streamlit 套件內的 `LICENSE` 與任何 `NOTICE` 檔案。
- **商標：** Apache-2.0 §6 不授予商標權。請勿使用 Streamlit 的名稱、Logo 或任何暗示官方背書、贊助或合作的表述；本專案僅以文字描述其為技術依賴。
- **與 AGPL 的相容性：** Apache-2.0 與 AGPL-3.0 相容。本專案以獨立套件形式使用 Streamlit，未將其程式碼與本專案合併成單一作品。

## 三、資料、商標與素材

- `data/service_mapping.json` 中的服務名稱與分數，是根據公開的 App 隱私標籤、Android／iOS 權限文件與開源隱私掃描概念**重新整理與教學化**而成。
- 本 repo 未包含任何第三方資料庫的原始傾印、App 圖示、截圖、Logo、字型、音樂或影片。
- Instagram、TikTok、Google Maps、Uber、WhatsApp、Signal、Spotify、Notion 等名稱與商標，屬各自權利人所有。本專案僅將它們用於服務辨識與教育說明，不代表任何關聯、贊助、合作或背書。
- `outputs/decision_tree.png` 由本專案程式透過 Matplotlib 即時生成，不包含外部圖片素材。Matplotlib 使用其套件自帶的字型，未另外複製字型檔進本 repo。

## 四、授權文件本身

`LICENSE` 為 Free Software Foundation 公布的 GNU Affero General Public License v3.0 官方條文。該授權允許逐字複製與散布授權文件本身。

## 五、回報授權問題

若你發現任何授權標示缺漏、版本不符或疑似未授權素材，請在 GitHub 開 issue，或聯絡維護者：

- 維護者：quill4749
- 專案：<https://github.com/quill4749/Data-Mirror>

我們會儘速確認並修正。
