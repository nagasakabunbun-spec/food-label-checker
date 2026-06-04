"""
① システムプロンプトの内部ルールをGroq AIで検証
② 全サイトの取得内容をGroq AIが「知識サマリー」に合成してrules.jsonに保存
→ アプリは毎回この合成知識をプロンプトに注入して精度を自動向上させる
"""

import json
import os
import re
import urllib.request
import datetime

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR    = os.path.join(SCRIPT_DIR, '..')
INDEX_HTML  = os.path.join(ROOT_DIR, 'index.html')
RULES_JSON  = os.path.join(ROOT_DIR, 'rules.json')
REPORT_JSON = os.path.join(ROOT_DIR, 'validation-report.json')

GROQ_API_KEY  = os.environ.get('GROQ_API_KEY', '')
GROQ_ENDPOINT = 'https://api.groq.com/openai/v1/chat/completions'
MODEL         = 'llama-3.3-70b-versatile'


# ──────────────────────────────────────
# Groq API ヘルパー
# ──────────────────────────────────────
def call_groq(system: str, user: str, max_tokens: int = 4096, json_mode: bool = True) -> str:
    body = json.dumps({
        'model': MODEL,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user',   'content': user}
        ],
        'temperature': 0.1,
        'max_tokens':  max_tokens,
        **({"response_format": {"type": "json_object"}} if json_mode else {})
    }).encode('utf-8')
    req = urllib.request.Request(
        GROQ_ENDPOINT,
        data=body,
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {GROQ_API_KEY}'}
    )
    with urllib.request.urlopen(req, timeout=90) as res:
        data = json.loads(res.read().decode('utf-8'))
    return data['choices'][0]['message']['content']


def safe_parse_json(raw: str) -> dict:
    s = raw.index('{')
    e = raw.rindex('}')
    return json.loads(raw[s:e + 1])


# ──────────────────────────────────────
# Step 1: 知識合成
# ──────────────────────────────────────
def synthesize_knowledge(rules_data: dict) -> dict:
    """
    20以上のサイトから取得した生テキストをGroq AIが要約・構造化し
    アプリが即座に使える「知識サマリー」を生成する
    """
    print("  ① 知識合成中（全サイト内容をAIが統合）...")

    # 全サイトの内容を結合
    all_content_parts = []
    for src in rules_data.get('sources', {}).values():
        if src.get('content') and not src['content'].startswith('['):
            all_content_parts.append(f"【{src['name']}】\n{src['content'][:2000]}")
    for src in rules_data.get('honey_sources', {}).values():
        if src.get('content') and not src['content'].startswith('['):
            all_content_parts.append(f"【{src['name']}（はちみつ）】\n{src['content'][:1500]}")

    all_content = '\n\n---\n\n'.join(all_content_parts[:15])  # 上位15件

    system = """あなたは日本の食品表示法・食品表示基準の最上位専門家です。
複数の権威あるサイトから取得した最新情報をもとに、食品ラベルチェックAIが使う「知識サマリー」を作成してください。
必ずJSON形式のみで返答してください。"""

    user = f"""以下は消費者庁・厚労省・農水省・専門サイトなど複数の権威あるサイトから取得した最新の食品表示関連情報です。
この情報を統合・整理して、食品ラベルチェックAIのための精度の高い知識サマリーをJSON形式で作成してください。

【取得した最新情報】
{all_content}

以下のJSON形式で出力してください：
{{
  "synthesized_at": "{datetime.date.today().isoformat()}",
  "mandatory_labels": {{
    "summary": "必須表示項目の最新の要点（500文字以内）",
    "recent_changes": "最近の法改正・変更点（あれば）"
  }},
  "allergen_rules": {{
    "mandatory_8": ["えび","かに","くるみ","小麦","そば","卵","乳","落花生"],
    "recommended_20": ["アーモンド","あわび","いか","いくら","オレンジ","カシューナッツ","キウイフルーツ","牛肉","ごま","さけ","さば","ゼラチン","大豆","鶏肉","バナナ","豚肉","まつたけ","もも","やまいも","りんご"],
    "display_rules": "アレルゲン表示の最新ルール要点",
    "recent_changes": "最近の変更点（くるみ義務化等）"
  }},
  "additive_rules": {{
    "summary": "添加物表示の最新ルール要点（区分表示・一括名称等）",
    "key_points": ["重要ポイント1", "重要ポイント2"]
  }},
  "nutrition_rules": {{
    "summary": "栄養成分表示の最新ルール要点",
    "mandatory_5": ["熱量","たんぱく質","脂質","炭水化物","食塩相当量"],
    "exemptions": "免除条件の要点"
  }},
  "origin_rules": {{
    "summary": "原料原産地表示の最新ルール要点",
    "key_rule": "重量割合1位のみ義務（2位以降は任意）"
  }},
  "honey_rules": {{
    "infant_warning": "乳児への注意文の最新要件",
    "quality_display": "はちみつ品質表示の要点",
    "organic_rules": "有機はちみつ表示の要件",
    "origin_rules": "はちみつ産地表示の要点"
  }},
  "expiry_rules": {{
    "consumption_date": "消費期限の定義・対象品目",
    "best_before": "賞味期限の定義・対象品目",
    "key_distinction": "両者の違いの要点"
  }},
  "common_mistakes": ["よくある誤りや落とし穴1", "よくある誤りや落とし穴2", "よくある誤りや落とし穴3"],
  "sites_summary": "参照したサイトの概要と信頼性評価"
}}"""

    try:
        raw = call_groq(system, user, max_tokens=3000)
        return safe_parse_json(raw)
    except Exception as e:
        print(f"    ⚠️ 知識合成エラー: {e}")
        return {"error": str(e), "synthesized_at": datetime.date.today().isoformat()}


# ──────────────────────────────────────
# Step 2: システムプロンプト検証
# ──────────────────────────────────────
def extract_system_prompt(html: str) -> str:
    m = re.search(r'const systemPrompt = `(.*?)`;', html, re.DOTALL)
    return m.group(1).strip() if m else ''


def validate_prompt(system_prompt: str, knowledge_summary: dict) -> dict:
    """合成された最新知識でシステムプロンプトを検証"""
    print("  ② システムプロンプト検証中...")

    knowledge_text = json.dumps(knowledge_summary, ensure_ascii=False, indent=2)[:3000]

    system = """あなたは日本の食品表示法・食品表示基準の最上位専門家です。
提供されたシステムプロンプトを最新の知識サマリーと照合して検証してください。
必ずJSON形式のみで返答してください。"""

    user = f"""【検証対象：システムプロンプト（要約）】
{system_prompt[:4000]}

【最新知識サマリー（各権威サイトから合成）】
{knowledge_text}

上記のシステムプロンプトを徹底的に検証し、以下のJSON形式で返答してください：
{{
  "is_valid": true,
  "critical_count": 0,
  "warning_count": 0,
  "critical_issues": [
    {{"item": "項目名", "current": "現在の記述（要約）", "correct": "正しい記述", "reason": "理由"}}
  ],
  "warnings": [
    {{"item": "項目名", "reason": "改善推奨の理由"}}
  ],
  "overall_assessment": "全体評価コメント（1〜3文）"
}}

critical_issues：法令と明らかに矛盾する重大な誤り
warnings：不正確・不完全・誤解を招く可能性がある記述"""

    try:
        raw = call_groq(system, user, max_tokens=2000)
        result = safe_parse_json(raw)
        result['critical_count'] = len(result.get('critical_issues', []))
        result['warning_count']  = len(result.get('warnings', []))
        return result
    except Exception as e:
        print(f"    ⚠️ 検証エラー: {e}")
        return {"is_valid": True, "critical_count": 0, "warning_count": 0,
                "critical_issues": [], "warnings": [],
                "overall_assessment": f"検証エラー: {e}"}


# ──────────────────────────────────────
# メイン
# ──────────────────────────────────────
def main():
    today = datetime.date.today().isoformat()
    print(f"=== 検証＆知識合成開始: {today} ===")

    if not GROQ_API_KEY:
        print("ERROR: GROQ_API_KEY が設定されていません")
        # 空のレポートを保存
        with open(REPORT_JSON, 'w', encoding='utf-8') as f:
            json.dump({"validated_at": today, "skipped": True, "critical_count": 0,
                       "warning_count": 0, "critical_issues": [], "warnings": []}, f,
                      ensure_ascii=False, indent=2)
        return

    # rules.json 読み込み
    if not os.path.exists(RULES_JSON):
        print("ERROR: rules.json が見つかりません。先に fetch_rules.py を実行してください。")
        return
    with open(RULES_JSON, encoding='utf-8') as f:
        rules_data = json.load(f)

    # ── Step 1: 知識合成 ──────────────────
    knowledge_summary = synthesize_knowledge(rules_data)

    # rules.json に knowledge_summary を追加保存
    rules_data['knowledge_summary'] = knowledge_summary
    rules_data['knowledge_updated_at'] = today
    with open(RULES_JSON, 'w', encoding='utf-8') as f:
        json.dump(rules_data, f, ensure_ascii=False, indent=2)
    print(f"    → knowledge_summary を rules.json に保存")

    # ── Step 2: システムプロンプト検証 ──────
    with open(INDEX_HTML, encoding='utf-8') as f:
        html = f.read()
    system_prompt = extract_system_prompt(html)
    if not system_prompt:
        print("ERROR: systemPrompt の抽出に失敗")
        return
    print(f"    システムプロンプト: {len(system_prompt)}文字")

    validation = validate_prompt(system_prompt, knowledge_summary)

    # ── 検証レポート保存 ──────────────────
    report = {
        "validated_at":       today,
        "is_valid":           validation.get('is_valid', True),
        "critical_count":     validation.get('critical_count', 0),
        "warning_count":      validation.get('warning_count', 0),
        "critical_issues":    validation.get('critical_issues', []),
        "warnings":           validation.get('warnings', []),
        "overall_assessment": validation.get('overall_assessment', ''),
        "sites_checked":      rules_data.get('site_count', 0),
        "knowledge_summary_available": bool(knowledge_summary)
    }
    with open(REPORT_JSON, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # ── 結果表示 ──────────────────────────
    print(f"\n=== 完了 ===")
    print(f"  巡回サイト数: {report['sites_checked']}")
    print(f"  知識合成: {'✅' if knowledge_summary else '⚠️'}")
    print(f"  ルール検証: {'✅ 問題なし' if report['is_valid'] else '⚠️ 問題あり'}")
    print(f"  重大な問題: {report['critical_count']}件")
    print(f"  警告: {report['warning_count']}件")
    if report['critical_issues']:
        for i in report['critical_issues']:
            print(f"    ❌ {i.get('item')}: {i.get('reason')}")
    print(f"  {report['overall_assessment']}")


if __name__ == '__main__':
    main()
