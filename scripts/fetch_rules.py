"""
毎週月曜日に消費者庁・食品表示関連サイトから最新ガイドラインを取得し
rules.json を更新するスクリプト
"""
import urllib.request
import urllib.error
import json
import datetime
import hashlib
import re
import os

# ──────────────────────────────────────
# 取得対象URL
# ──────────────────────────────────────
TARGETS = [
    {
        "name": "消費者庁｜食品表示法等（法令・通知）",
        "url": "https://www.caa.go.jp/policies/policy/food_labeling/food_labeling_act/",
        "key": "caa_main"
    },
    {
        "name": "消費者庁｜食品表示基準について",
        "url": "https://www.caa.go.jp/policies/policy/food_labeling/food_labeling_act/food_labeling_act_index/",
        "key": "caa_standard"
    },
    {
        "name": "消費者庁｜アレルゲン表示",
        "url": "https://www.caa.go.jp/policies/policy/food_labeling/food_labeling_act/food_labeling_act_index/allergy/",
        "key": "caa_allergy"
    },
    {
        "name": "消費者庁｜栄養成分表示",
        "url": "https://www.caa.go.jp/policies/policy/food_labeling/health_promotion/",
        "key": "caa_nutrition"
    },
    {
        "name": "食品表示サポート.COM｜加工食品の表示ルール",
        "url": "https://food-labeling.com/rule.html",
        "key": "foodlabeling_rule"
    },
    {
        "name": "食品表示サポート.COM｜アレルゲン表示",
        "url": "https://food-labeling.com/allergy.html",
        "key": "foodlabeling_allergy"
    },
]

HONEY_TARGETS = [
    {
        "name": "厚生労働省｜乳児ボツリヌス症の予防について",
        "url": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000121431.html",
        "key": "mhlw_honey"
    },
]

RULES_FILE = os.path.join(os.path.dirname(__file__), '..', 'rules.json')


def fetch_text(url: str) -> str:
    """URLからテキストを取得してHTMLタグを除去"""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; FoodLabelChecker/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=15) as res:
            raw = res.read().decode('utf-8', errors='replace')
        # HTMLタグ除去
        text = re.sub(r'<script[^>]*>.*?</script>', '', raw, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&[a-z]+;', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        # 先頭5000文字を取得（関連部分が多いため）
        return text[:5000]
    except Exception as e:
        return f"[取得エラー: {e}]"


def md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def main():
    today = datetime.date.today().isoformat()
    print(f"=== ガイドライン更新チェック開始: {today} ===")

    # 既存の rules.json を読み込む
    if os.path.exists(RULES_FILE):
        with open(RULES_FILE, encoding='utf-8') as f:
            existing = json.load(f)
    else:
        existing = {"sources": {}, "honey_sources": {}}

    sources = {}
    honey_sources = {}
    updates_detected = []

    # 通常ターゲット取得
    for t in TARGETS:
        print(f"  取得中: {t['name']}")
        text = fetch_text(t['url'])
        new_hash = md5(text)
        old_hash = existing.get("sources", {}).get(t['key'], {}).get("hash", "")
        changed = new_hash != old_hash
        if changed and old_hash:
            updates_detected.append(t['name'])
            print(f"    → 更新検出！")
        sources[t['key']] = {
            "name": t['name'],
            "url": t['url'],
            "hash": new_hash,
            "content": text,
            "last_fetched": today,
            "changed": changed
        }

    # はちみつ関連ターゲット取得
    for t in HONEY_TARGETS:
        print(f"  取得中（はちみつ）: {t['name']}")
        text = fetch_text(t['url'])
        new_hash = md5(text)
        old_hash = existing.get("honey_sources", {}).get(t['key'], {}).get("hash", "")
        changed = new_hash != old_hash
        if changed and old_hash:
            updates_detected.append(t['name'])
            print(f"    → 更新検出！")
        honey_sources[t['key']] = {
            "name": t['name'],
            "url": t['url'],
            "hash": new_hash,
            "content": text,
            "last_fetched": today,
            "changed": changed
        }

    # rules.json 書き出し
    rules = {
        "version": today,
        "last_checked": today,
        "has_updates": len(updates_detected) > 0,
        "updates_detected": updates_detected,
        "sources": sources,
        "honey_sources": honey_sources
    }

    with open(RULES_FILE, 'w', encoding='utf-8') as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)

    print(f"\n=== 完了 ===")
    if updates_detected:
        print(f"更新されたページ: {', '.join(updates_detected)}")
    else:
        print("更新なし")


if __name__ == "__main__":
    main()
