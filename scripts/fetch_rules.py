"""
毎週月曜日に食品表示関連の権威あるサイトを巡回し
最新ガイドライン情報を rules.json に保存するスクリプト

対象：消費者庁・厚労省・農水省・食品安全委員会・業界団体など20以上のサイト
"""

import urllib.request
import urllib.error
import json
import datetime
import hashlib
import re
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RULES_FILE  = os.path.join(SCRIPT_DIR, '..', 'rules.json')

# ──────────────────────────────────────
# 巡回対象サイト一覧
# ──────────────────────────────────────
TARGETS = [
    # ── 消費者庁 ──────────────────────────────
    {
        "category": "消費者庁",
        "name": "消費者庁｜食品表示法等（法令・通知）",
        "url": "https://www.caa.go.jp/policies/policy/food_labeling/food_labeling_act/",
        "key": "caa_main"
    },
    {
        "category": "消費者庁",
        "name": "消費者庁｜食品表示基準について",
        "url": "https://www.caa.go.jp/policies/policy/food_labeling/food_labeling_act/food_labeling_act_index/",
        "key": "caa_standard"
    },
    {
        "category": "消費者庁",
        "name": "消費者庁｜アレルゲン表示",
        "url": "https://www.caa.go.jp/policies/policy/food_labeling/food_labeling_act/food_labeling_act_index/allergy/",
        "key": "caa_allergy"
    },
    {
        "category": "消費者庁",
        "name": "消費者庁｜栄養成分表示",
        "url": "https://www.caa.go.jp/policies/policy/food_labeling/health_promotion/",
        "key": "caa_nutrition"
    },
    {
        "category": "消費者庁",
        "name": "消費者庁｜原料原産地表示",
        "url": "https://www.caa.go.jp/policies/policy/food_labeling/food_labeling_act/food_labeling_act_index/origin/",
        "key": "caa_origin"
    },
    {
        "category": "消費者庁",
        "name": "消費者庁｜食品表示基準Q&A加工食品",
        "url": "https://www.caa.go.jp/policies/policy/food_labeling/food_labeling_act/food_labeling_act_index/",
        "key": "caa_qa"
    },
    {
        "category": "消費者庁",
        "name": "消費者庁｜食品表示に関する総合情報",
        "url": "https://www.caa.go.jp/policies/policy/food_labeling/",
        "key": "caa_general"
    },

    # ── 厚生労働省 ──────────────────────────────
    {
        "category": "厚生労働省",
        "name": "厚労省｜食品添加物",
        "url": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/shokuhin/syokuten/",
        "key": "mhlw_additives"
    },
    {
        "category": "厚生労働省",
        "name": "厚労省｜乳児ボツリヌス症（はちみつ）",
        "url": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000121431.html",
        "key": "mhlw_honey_botulism"
    },
    {
        "category": "厚生労働省",
        "name": "厚労省｜食品の期限表示について",
        "url": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/shokuhin/syokuhin/",
        "key": "mhlw_expiry"
    },
    {
        "category": "厚生労働省",
        "name": "厚労省｜HACCPに沿った衛生管理",
        "url": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/shokuhin/haccp/",
        "key": "mhlw_haccp"
    },

    # ── 農林水産省 ──────────────────────────────
    {
        "category": "農林水産省",
        "name": "農水省｜食品表示・規格",
        "url": "https://www.maff.go.jp/j/syouan/hyoji/",
        "key": "maff_labeling"
    },
    {
        "category": "農林水産省",
        "name": "農水省｜有機農産物・有機JAS",
        "url": "https://www.maff.go.jp/j/jas/jas_kikaku/yuuki.html",
        "key": "maff_organic"
    },
    {
        "category": "農林水産省",
        "name": "農水省｜はちみつ・養蜂関連",
        "url": "https://www.maff.go.jp/j/seisan/kikaku/mitsubachi.html",
        "key": "maff_honey"
    },

    # ── 食品安全委員会 ──────────────────────────
    {
        "category": "食品安全委員会",
        "name": "食品安全委員会｜食品添加物評価",
        "url": "https://www.fsc.go.jp/hyouka/tenkabutsu.html",
        "key": "fsc_additives"
    },

    # ── 専門サイト・業界団体 ──────────────────────────
    {
        "category": "専門サイト",
        "name": "食品表示サポート.COM｜加工食品表示ルール",
        "url": "https://food-labeling.com/rule.html",
        "key": "foodlabeling_rule"
    },
    {
        "category": "専門サイト",
        "name": "食品表示サポート.COM｜アレルゲン表示",
        "url": "https://food-labeling.com/allergy.html",
        "key": "foodlabeling_allergy"
    },
    {
        "category": "専門サイト",
        "name": "食品表示サポート.COM｜栄養成分表示",
        "url": "https://food-labeling.com/nutrition.html",
        "key": "foodlabeling_nutrition"
    },
    {
        "category": "専門サイト",
        "name": "食品表示サポート.COM｜賞味期限・消費期限",
        "url": "https://food-labeling.com/date.html",
        "key": "foodlabeling_date"
    },
    {
        "category": "専門サイト",
        "name": "食品表示サポート.COM｜添加物表示",
        "url": "https://food-labeling.com/additive.html",
        "key": "foodlabeling_additive"
    },
    {
        "category": "専門サイト",
        "name": "食品表示サポート.COM｜原料原産地",
        "url": "https://food-labeling.com/origin.html",
        "key": "foodlabeling_origin"
    },

    # ── はちみつ・養蜂専門 ──────────────────────────
    {
        "category": "はちみつ専門",
        "name": "全国はちみつ公正取引協議会｜はちみつ類の表示",
        "url": "https://www.honey-fair.com/",
        "key": "honey_fair"
    },
    {
        "category": "はちみつ専門",
        "name": "消費者庁｜はちみつ食品表示通知",
        "url": "https://www.caa.go.jp/notice/entry/016893/",
        "key": "caa_honey"
    },
]

# はちみつ専門ターゲットを別リストとして管理
HONEY_KEYS = {"honey_fair", "caa_honey", "maff_honey", "mhlw_honey_botulism"}


def fetch_text(url: str, max_chars: int = 4000) -> str:
    """URLからテキストを取得してHTMLタグを除去"""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; FoodLabelChecker/2.0; +https://nagasakabunbun-spec.github.io/food-label-checker/)",
                "Accept-Language": "ja,en;q=0.9"
            }
        )
        with urllib.request.urlopen(req, timeout=20) as res:
            raw = res.read().decode('utf-8', errors='replace')

        # HTML→テキスト変換
        text = re.sub(r'<script[^>]*>.*?</script>', '', raw, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>',  '', text, flags=re.DOTALL)
        text = re.sub(r'<!--.*?-->',                '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>',                  ' ', text)
        text = re.sub(r'&nbsp;',  ' ', text)
        text = re.sub(r'&amp;',   '&', text)
        text = re.sub(r'&lt;',    '<', text)
        text = re.sub(r'&gt;',    '>', text)
        text = re.sub(r'&[a-z]+;','',  text)
        text = re.sub(r'\s+',     ' ', text).strip()
        return text[:max_chars]

    except urllib.error.HTTPError as e:
        return f"[HTTP {e.code} エラー: {url}]"
    except Exception as e:
        return f"[取得エラー: {type(e).__name__}: {e}]"


def md5(text: str) -> str:
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def main():
    today = datetime.date.today().isoformat()
    print(f"=== ガイドライン取得開始: {today} ===")
    print(f"  対象サイト数: {len(TARGETS)}")

    # 既存データ読み込み
    if os.path.exists(RULES_FILE):
        with open(RULES_FILE, encoding='utf-8') as f:
            existing = json.load(f)
    else:
        existing = {}

    existing_sources       = existing.get("sources", {})
    existing_honey_sources = existing.get("honey_sources", {})

    sources       = {}
    honey_sources = {}
    updates_detected = []
    errors = []

    for t in TARGETS:
        key = t["key"]
        print(f"  [{t['category']}] 取得中: {t['name'][:50]}")
        text = fetch_text(t["url"])

        if text.startswith("["):
            print(f"    ⚠️ {text}")
            errors.append({"key": key, "error": text})
            # エラー時は既存データを維持
            prev = existing_sources.get(key) or existing_honey_sources.get(key)
            if prev:
                text = prev.get("content", "")
            else:
                text = ""

        new_hash = md5(text)

        if key in HONEY_KEYS:
            old_hash = existing_honey_sources.get(key, {}).get("hash", "")
        else:
            old_hash = existing_sources.get(key, {}).get("hash", "")

        changed = (new_hash != old_hash) and bool(old_hash) and not text.startswith("[")
        if changed:
            updates_detected.append(t['name'])
            print(f"    🔔 更新を検出")

        entry = {
            "name":         t["name"],
            "category":     t["category"],
            "url":          t["url"],
            "hash":         new_hash,
            "content":      text,
            "last_fetched": today,
            "changed":      changed
        }

        if key in HONEY_KEYS:
            honey_sources[key] = entry
        else:
            sources[key] = entry

    # rules.json 書き出し
    rules = {
        "version":          today,
        "last_checked":     today,
        "has_updates":      len(updates_detected) > 0,
        "updates_detected": updates_detected,
        "fetch_errors":     errors,
        "site_count":       len(TARGETS),
        "sources":          sources,
        "honey_sources":    honey_sources
    }

    with open(RULES_FILE, 'w', encoding='utf-8') as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)

    print(f"\n=== 取得完了 ===")
    print(f"  成功: {len(TARGETS) - len(errors)} / {len(TARGETS)} サイト")
    if updates_detected:
        print(f"  更新検出: {', '.join(updates_detected)}")
    if errors:
        print(f"  エラー: {len(errors)} サイト")
    print(f"  → {RULES_FILE} に保存")


if __name__ == "__main__":
    main()
