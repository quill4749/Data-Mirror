# 資料來源與引用（Sources）

本文件說明 `data/service_mapping.json` 中風險分數的**來源類型**與**可查證的入口**。

> **查詢日期：** 2026-11-24
> **重要說明：** 目前專案的分數是維護者依公開資訊人工彙整的**教學性近似值**，不是掃描器的直接輸出，也**沒有逐筆保存標籤截圖或報告快照**。本文件提供的是「可以到哪裡查證」的入口，而非「某個分數等於某個欄位」的逐項對照。

---

## 一、分數的產生方式

1. 風險因子與權重定義於 `src/backend/risk_config.py`。
2. 各服務的 `0`（Safe）／`1`（Medium）／`2`（Critical）分數定義於 `src/backend/service_collector.py` 的 `DEFAULT_SERVICE_SCORES`。
3. 執行 `python src/backend/service_collector.py` 後輸出 `data/service_mapping.json`。

每一筆分數是多個線索的綜合判斷，例如「位置追蹤 = 2」可能同時參考：商店隱私標籤是否列出位置、權限是否包含精確／背景定位、掃描工具是否發現位置相關 SDK。

---

## 二、通用方法論來源

### 1. 商店隱私標籤

| 來源 | 說明 | 連結 |
|---|---|---|
| Apple App Store「App 隱私權」 | 開發者申報的資料收集類別、是否用於追蹤、是否與身分連結，以及用途 | <https://developer.apple.com/app-store/app-privacy-details/> |
| Apple App Tracking Transparency（ATT） | 跨 App 追蹤需取得使用者同意 | <https://developer.apple.com/documentation/apptrackingtransparency> |
| Apple Privacy Manifest | App 與 SDK 需宣告必要理由 API 與資料使用 | <https://developer.apple.com/documentation/bundleresources/privacy_manifest_files> |
| Google Play「資料安全性」 | 開發者申報收集／分享的資料類別、用途、傳輸加密與刪除機制 | <https://support.google.com/googleplay/android-developer/answer/10787469> |

### 2. 作業系統權限文件

| 來源 | 說明 | 連結 |
|---|---|---|
| Android Permissions overview | 權限分類、dangerous permission 與執行期授權 | <https://developer.android.com/guide/topics/permissions/overview> |
| Android Location permissions | 精確／概略／背景定位的申請與限制 | <https://developer.android.com/develop/sensors-and-location/location/permissions> |
| Android Copy and paste | 剪貼簿存取與 Android 10+ 的限制 | <https://developer.android.com/develop/ui/views/touch-and-input/copy-paste> |
| Google Play Advertising ID | 廣告識別碼（AD_ID）政策與重設機制 | <https://support.google.com/googleplay/android-developer/answer/6048248> |
| Apple Information Property List | `Info.plist` 的 usage description 鍵（定位、麥克風、通訊錄、Face ID 等） | <https://developer.apple.com/documentation/bundleresources/information_property_list> |

### 3. 開源隱私掃描工具

| 工具 | 用途 | 連結 |
|---|---|---|
| Exodus Privacy / εxodus | 分析 Android APK 的權限與內嵌追蹤器，提供公開報告 | <https://exodus-privacy.eu.org/>　／　<https://reports.exodus-privacy.eu.org/> |
| MobSF (Mobile Security Framework) | Android／iOS 靜態與動態安全分析，列出權限、SDK、硬編碼字串等 | <https://github.com/MobSF/Mobile-Security-Framework-MobSF> |
| TrackerControl | 以 Exodus 追蹤器資料庫檢視與阻擋 Android 上的追蹤 | <https://github.com/TrackerControl/tracker-control-android> |

這些工具證明的是「App 要求哪些能力／內嵌哪些 SDK」，**不保證**資料一定被收集或外傳。本專案未執行這些工具，也未將它們的報告匯入。

---

## 三、各服務的查證入口

商店頁面中的「App 隱私權」與「資料安全性」區塊，就是本專案所稱的隱私標籤。實際內容會隨 App 版本、地區與登入狀態變動，請以查詢當下頁面為準。

| 服務 key | 服務 | Apple App Store | Google Play |
|---|---|---|---|
| `instagram` | Instagram | <https://apps.apple.com/us/app/instagram/id389801252> | <https://play.google.com/store/apps/details?id=com.instagram.android> |
| `tiktok` | TikTok | <https://apps.apple.com/us/app/tiktok/id835599320> | <https://play.google.com/store/apps/details?id=com.zhiliaoapp.musically> |
| `google_maps` | Google Maps | <https://apps.apple.com/us/app/google-maps/id585027354> | <https://play.google.com/store/apps/details?id=com.google.android.apps.maps> |
| `uber` | Uber | <https://apps.apple.com/us/app/uber/id368677368> | <https://play.google.com/store/apps/details?id=com.ubercab> |
| `whatsapp` | WhatsApp | <https://apps.apple.com/us/app/whatsapp-messenger/id310633997> | <https://play.google.com/store/apps/details?id=com.whatsapp> |
| `signal` | Signal | <https://apps.apple.com/us/app/signal-private-messenger/id686449807> | <https://play.google.com/store/apps/details?id=org.thoughtcrime.securesms> |
| `spotify` | Spotify | <https://apps.apple.com/us/app/spotify-music-and-podcasts/id324684580> | <https://play.google.com/store/apps/details?id=com.spotify.music> |
| `notion` | Notion | <https://apps.apple.com/us/app/notion-notes-docs-tasks/id1232780281> | <https://play.google.com/store/apps/details?id=notion.id> |
| `mobile_banking` | 行動銀行（通用類別） | 無單一 App；請以實際往來銀行 App 的商店頁面為準 | 同左 |
| `calculator_app` | 計算機 App（通用類別） | 無單一 App；請以實際安裝的計算機 App 商店頁面為準 | 同左 |

> 行動銀行與計算機是**類別**而非特定產品，因此沒有單一來源。文件中的分數是此類 App 的常見行為輪廓，實務上應以你實際使用的 App 為準。

---

## 四、因子與證據類型對照

| 因子 | 主要證據類型 |
|---|---|
| `behavioral_profiling` | 商店標籤的 Identifiers／Usage Data／Tracking、跨 App SDK、廣告識別碼 |
| `location_tracking` | 商店標籤 Location、`ACCESS_FINE_LOCATION`／`ACCESS_BACKGROUND_LOCATION`、iOS 定位 usage description |
| `targeted_ads` | 商店標籤 Advertising／Third-Party Advertising、AD_ID、廣告 SDK |
| `microphone_access` | `RECORD_AUDIO`、`NSMicrophoneUsageDescription`、背景收音能力 |
| `clipboard_tracking` | 剪貼簿存取行為與系統提示、相關 SDK |
| `contacts_access` | `READ_CONTACTS`、`NSContactsUsageDescription`、通訊錄上傳行為 |
| `biometric_data` | `USE_BIOMETRIC`、`NSFaceIDUsageDescription`、本機安全區處理方式 |

---

## 五、更新與重現

```bash
# 重新產生風險矩陣
python src/backend/service_collector.py

# 重新訓練決策樹並輸出規則與圖表
python src/backend/tree_model.py

# 啟動互動介面
streamlit run src/backend/app.py
```

若你要調整分數，請修改 `DEFAULT_SERVICE_SCORES` 或使用 `register_service()`，再重新產生；直接手改 JSON 會在下次產生時被覆蓋。

---

## 六、限制

- 商店隱私標籤由開發者自行申報，平台不逐項驗證。
- 同一 App 在不同地區、版本、登入狀態下的揭露可能不同。
- 掃描工具只能觀察「能力」與「嵌入的 SDK」，不能證明實際資料流向。
- 本專案的分數沒有逐筆引用與快照，不適合作為法律、資安稽核或採購決策的唯一依據。

若發現連結失效或內容與分數明顯不符，請開 issue 回報。
