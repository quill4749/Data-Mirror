import json
from tree_model import clf
from sklearn.tree import export_text

# 風險建議
advice_map = {
    "location_tracking": "Consider turning off location tracking when not needed.",
    "targeted_ads": "Review ad personalization settings.",
    "behavioral_profiling": "Limit app permissions and tracking."
}

# 載入服務映射
with open("./data/service_mapping.json") as f:
    service_mapping = json.load(f)

# 使用者選擇服務
selected_services = input("Enter services you use (comma separated, e.g., instagram, google_maps): ").split(",")
selected_services = [s.strip().lower() for s in selected_services]

features = []
risks = []

for service in selected_services:
    if service in service_mapping:
        f = [service_mapping[service][r] for r in ["location_tracking", "behavioral_profiling", "targeted_ads"]]
        features.append(f)
        for r, score in zip(["location_tracking", "behavioral_profiling", "targeted_ads"], f):
            if score > 0:
                risks.append(r)

# 總風險分數
total_score = sum([sum(f) for f in features])
if total_score <= 2:
    overall_risk = "LOW"
elif total_score <= 4:
    overall_risk = "MEDIUM"
else:
    overall_risk = "HIGH"

# 建議
suggestions = set([advice_map[r] for r in risks])

print("\n=== Risk Analysis Result ===")
print(f"Selected services: {selected_services}")
print(f"Total Risk Score: {total_score}")
print(f"Overall Risk Level: {overall_risk}")
print("Suggestions:")
for s in suggestions:
    print(f"- {s}")

# 顯示決策樹規則
tree_rules = export_text(clf, feature_names=["location_tracking", "behavioral_profiling", "targeted_ads"])
print("\nDecision Tree Rules:")
print(tree_rules)
