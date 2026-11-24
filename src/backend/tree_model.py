from sklearn.tree import DecisionTreeClassifier, export_text, plot_tree
import matplotlib.pyplot as plt
import json

# 載入服務映射資料
with open("../data/service_mapping.json") as f:
    service_mapping = json.load(f)

# 範例訓練資料生成（假資料，方便 demo）
X = []
y = []

services = list(service_mapping.keys())
risk_types = ["location_tracking", "behavioral_profiling", "targeted_ads"]

for service in services:
    features = [service_mapping[service][r] for r in risk_types]
    X.append(features)
    y.append(sum(features))  # 簡單總風險分數

# 建立決策樹
clf = DecisionTreeClassifier()
clf.fit(X, y)

# 可視化決策樹
plt.figure(figsize=(12,8))
plot_tree(clf, feature_names=risk_types, class_names=[str(i) for i in range(0,7)], filled=True)
plt.savefig("../outputs/decision_tree.png")

# 輸出文字版決策規則
tree_rules = export_text(clf, feature_names=risk_types)
with open("../outputs/tree_rules.txt", "w") as f:
    f.write(tree_rules)

print("Decision tree model created! Rules saved in outputs/tree_rules.txt")
