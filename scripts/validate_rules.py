"""
食品ラベルチェッカーのシステムプロンプト（内部ルール）を
Groq AI + 最新ガイドライン（rules.json）で毎週検証するスクリプト

検出する問題例：
- 法令の名称・条文番号の誤り
- アレルゲン品目リストの不足・誤り
- 義務/努力義務の分類の誤り
- 表示ルールの記述が実際の法令と異なる
- 新しい法改正への未対応
"""

import json
import os
import re
import urllib.request
import datetime

# ──────────────────────────────────────
# 設定
# ──────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.join(SCRIPT_DIR, '..')
INDEX_HTML = os.path.join(ROOT_DIR, 'index.html')
RULES_JSON = os.path.join(ROOT_DIR, 'rules.json')
REPORT_JSON = os.path.join(ROOT_DIR, 'validation-report.json')

GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
GROQ_ENDPOINT = 'https://api.groq.com/openai/v1/chat/completions'
MODEL = 'llama-3.3-70b-versatile'


def extract_system_prompt(html_content: str) -> str:
    """index.html からシステムプロンプト部分を抽出"""
    match = re.search(
        r'const systemPrompt = `(.*?)`;',
        html_content,
        re.DOTALL
    )
    if match:
        return match.group(1).strip()
    return ''


def load_rules_context(rules_data: dict) -> str:
    """rules.json から参考情報を組み立て"""
    parts = []
    for src in list(rules_data.get('sources', {}).values())[:4]:
        if src.get('content'):
            parts.append(f"【{src['name']}】\n{src['content'][:1500]}")
    for src in rules_data.get('honey_sources', {}).values():
        if src.get('content'):
            parts.append(f"【{src['name']}】\n{src['content'][:800]}")
    return '\n\n'.join(parts)


def call_groq(system: str, user: str) -> str:
    """Groq API を呼び出してレスポンスを返す"""
    body = json.dumps({
        'model': MODEL,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user}
        ],
        'temperature': 0.1,
        'max_tokens': 3000,
        'response_format': {'type': 'json_object'}
    }).encode('utf-8')

    req = urllib.request.Request(
        GROQ_ENDPOINT,
        data=body,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {GROQ_API_KEY}'
        }
    )
    with urllib.request.urlopen(req, timeout=60) as res:
        data = json.loads(res.read().decode('utf-8'))
    return data['choices'][0]['message']['content']


def validate(system_prompt: str, rules_context: str) -> dict:
    """Groq AI でシステムプロンプトを検証"""
    system = """あなたは日本の食品表示法・食品表示基準の最上位専門家です。
提供されたシステムプロンプト（AIへの食品表示チェック指示）を、消費者庁の最新ガイドライン情報と照合して検証してください。

以下の観点で問題を見つけてください：
1. 法令の条文番号・名称の誤り
2. アレルゲン必須品目の不足・誤記（現行：えび・かに・くるみ・小麦・そば・卵・乳・落花生の8品目）
3. 義務表示と努力義務の分類の誤り
4. 表示ルールの説明が実際の法令と矛盾している箇所
5. 2024年以降の法改正への未対応
6. 消費期限・賞味期限の定義の誤り
7. 原材料名・添加物の区分表示ルールの誤り
8. 原料原産地名の義務条件の誤り
9. 一括表示法・個別表示法の定義の誤り
10. その他、事業者が誤った対応をするリスクのある記述

必ず以下のJSON形式のみで返答してください：
{
  "is_valid": true,
  "total_issues": 0,
  "critical_issues": [],
  "warnings": [],
  "suggestions": [],
  "overall_assessment": "全体的な評価コメント（1〜3文）"
}

critical_issues：法令と明らかに矛盾・誤りのある重大な問題（事業者が違反行為を行う可能性がある）
warnings：不正確・不完全・曖昧な記述（誤解を招く可能性がある）
suggestions：改善の余地がある箇所（現時点で問題ではないが精度向上のため）

各issue/warning/suggestionの形式：
{
  "item": "問題のある項目名",
  "current": "現在の記述（要約）",
  "correct": "正しい記述または修正案",
  "reason": "なぜ問題なのかの説明"
}"""

    user = f"""【検証対象：システムプロンプト】
{system_prompt}

【参照：消費者庁サイトより取得した最新ガイドライン情報】
{rules_context}

上記のシステムプロンプトを徹底的に検証し、誤り・不備・曖昧な記述をすべて指摘してください。"""

    raw = call_groq(system, user)
    start = raw.index('{')
    end = raw.rindex('}')
    return json.loads(raw[start:end + 1])


def save_report(result: dict, had_error: str = ''):
    today = datetime.date.today().isoformat()
    report = {
        'validated_at': today,
        'is_valid': result.get('is_valid', False),
        'total_issues': result.get('total_issues', 0),
        'critical_count': len(result.get('critical_issues', [])),
        'warning_count': len(result.get('warnings', [])),
        'suggestion_count': len(result.get('suggestions', [])),
        'critical_issues': result.get('critical_issues', []),
        'warnings': result.get('warnings', []),
        'suggestions': result.get('suggestions', []),
        'overall_assessment': result.get('overall_assessment', ''),
        'error': had_error
    }
    with open(REPORT_JSON, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return report


def main():
    today = datetime.date.today().isoformat()
    print(f'=== システムプロンプト検証開始: {today} ===')

    if not GROQ_API_KEY:
        print('ERROR: GROQ_API_KEY が設定されていません')
        save_report({}, 'GROQ_API_KEY未設定')
        return

    # index.html からシステムプロンプト抽出
    with open(INDEX_HTML, encoding='utf-8') as f:
        html = f.read()
    system_prompt = extract_system_prompt(html)
    if not system_prompt:
        print('ERROR: systemPrompt の抽出に失敗しました')
        save_report({}, 'systemPrompt抽出失敗')
        return
    print(f'  システムプロンプト抽出完了（{len(system_prompt)}文字）')

    # rules.json 読み込み
    rules_context = ''
    if os.path.exists(RULES_JSON):
        with open(RULES_JSON, encoding='utf-8') as f:
            rules_data = json.load(f)
        rules_context = load_rules_context(rules_data)
        print(f'  ガイドライン情報読み込み完了')

    # Groq で検証
    print('  AI検証中...')
    try:
        result = validate(system_prompt, rules_context)
    except Exception as e:
        print(f'ERROR: 検証API呼び出し失敗: {e}')
        save_report({}, str(e))
        return

    report = save_report(result)

    print(f'\n=== 検証結果 ===')
    print(f'  全体評価: {"✅ 問題なし" if report["is_valid"] else "⚠️ 問題あり"}')
    print(f'  重大な問題: {report["critical_count"]}件')
    print(f'  警告: {report["warning_count"]}件')
    print(f'  提案: {report["suggestion_count"]}件')
    if report['critical_issues']:
        print('\n  【重大な問題】')
        for i in report['critical_issues']:
            print(f'  - {i.get("item")}: {i.get("reason")}')
    print(f'\n  {report["overall_assessment"]}')
    print(f'\n  レポート保存: {REPORT_JSON}')


if __name__ == '__main__':
    main()
