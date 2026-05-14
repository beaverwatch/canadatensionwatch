import json
import time
import random
import os
import requests
from datetime import datetime

# ============================================
# BEAVER.WATCH — Google Trends Scraper
# + Claude API intégrée
# ============================================

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

KEYWORDS = {
    "payday_loan": {
        "terms": ["prêt payday", "money mart", "prêt rapide"],
        "label_fr": "Prêts Payday",
        "label_en": "Payday Loans",
        "emoji": "💸",
        "weight": 0.30,
    },
    "aide_alimentaire": {
        "terms": ["banque alimentaire", "aide alimentaire", "food bank"],
        "label_fr": "Aide Alimentaire",
        "label_en": "Food Assistance",
        "emoji": "🍞",
        "weight": 0.25,
    },
    "faillite": {
        "terms": ["faillite personnelle", "insolvabilité", "bankruptcy canada"],
        "label_fr": "Faillite",
        "label_en": "Bankruptcy",
        "emoji": "📉",
        "weight": 0.25,
    },
    "logement_stress": {
        "terms": ["aide loyer", "expulsion locataire", "transfert bail"],
        "label_fr": "Stress Logement",
        "label_en": "Housing Stress",
        "emoji": "🏠",
        "weight": 0.20,
    },
}

def get_trend_score(terms, geo="CA"):
    """
    Utilise pytrends pour récupérer les scores Google Trends.
    """
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl='fr-CA', tz=-300, timeout=(10, 25), retries=2)
        time.sleep(random.uniform(2, 5))
        pytrends.build_payload(terms[:5], cat=0, timeframe='now 7-d', geo=geo, gprop='')
        data = pytrends.interest_over_time()
        if data.empty: return None
        scores = [data[t].mean() for t in terms if t in data.columns]
        return round(sum(scores) / len(scores), 1) if scores else None
    except Exception as e:
        print(f"    ⚠️ Trends error: {e}")
        return None

def normalize_score(raw, baseline=30):
    if raw is None: return None
    if raw <= baseline: return round(max(0.05, (raw / baseline) * 0.35), 2)
    excess = raw - baseline
    return round(min(1.0, 0.35 + (excess / (100 - baseline)) * 0.65), 2)

def get_status(score):
    if score is None: return {"label_fr": "N/A", "label_en": "N/A", "color": "gray", "emoji": "❓"}
    if score < 0.35: return {"label_fr": "Normal", "label_en": "Normal", "color": "green", "emoji": "🟢"}
    if score < 0.65: return {"label_fr": "Tension", "label_en": "Tension", "color": "orange", "emoji": "🟠"}
    return {"label_fr": "CRISE", "label_en": "CRISIS", "color": "red", "emoji": "🔴"}

def analyze_trends_with_claude(trends_data):
    if not ANTHROPIC_API_KEY: return None
    print("\n🤖 Claude analyse les tendances Google...")

    national = trends_data.get("national_score", 0)
    keywords = {k: {"score": v.get("stress_score"), "label": v.get("label_fr")}
                for k, v in trends_data.get("keywords", {}).items()}

    prompt = f"""Tu es l'analyste de BEAVER.WATCH.

DONNÉES GOOGLE TRENDS AUJOURD'HUI ({datetime.now().strftime('%Y-%m-%d')}) :
Score national : {national} / 1.0
Catégories : {json.dumps(keywords, ensure_ascii=False)}

Ces données représentent ce que les Canadiens RECHERCHENT sur Google
en lien avec la détresse financière.

Génère UNIQUEMENT ce JSON :

{{
  "analyse_fr": "2-3 phrases. Ce que les recherches Google révèlent sur l'état financier des Canadiens.",
  "analyse_en": "Same in English.",
  "signal_dominant": "Catégorie la plus préoccupante en 4 mots",
  "niveau_alerte": "NORMAL ou TENSION ou CRISE"
}}"""

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 500,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        if response.status_code == 200:
            content = response.json()["content"][0]["text"].strip()
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"): content = content[4:]
            result = json.loads(content.strip())
            print("✅ Claude Trends analysis done!")
            return result
        return None
    except Exception as e:
        print(f"Claude error: {e}"); return None

def run():
    print("🦫 BEAVER.WATCH — Google Trends + Claude API")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 52)

    output = {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": "Google Trends",
        "timeframe": "7 derniers jours",
        "keywords": {},
        "national_score": None,
        "national_status": None,
        "claude_analysis": None,
    }

    print("\n📊 Analyse par catégorie — Canada")
    weighted_scores = []

    for cat_key, cat_info in KEYWORDS.items():
        print(f"\n  🔍 {cat_key}...", end=" ", flush=True)
        raw = get_trend_score(cat_info['terms'], geo="CA")
        stress = normalize_score(raw)
        status = get_status(stress)

        if raw: print(f"Raw: {raw} → Stress: {stress}")
        else: print("N/A")

        output['keywords'][cat_key] = {
            "label_fr": cat_info['label_fr'],
            "label_en": cat_info['label_en'],
            "emoji": cat_info['emoji'],
            "raw_score": raw,
            "stress_score": stress,
            "status": status,
            "weight": cat_info['weight'],
        }
        if stress is not None:
            weighted_scores.append((stress, cat_info['weight']))

    if weighted_scores:
        total_w = sum(w for _, w in weighted_scores)
        national = round(sum(s * w for s, w in weighted_scores) / total_w, 2)
        output['national_score'] = national
        output['national_status'] = get_status(national)
        print(f"\n🍁 NATIONAL Trends: {national} {get_status(national)['emoji']}")

        # Claude analysis
        claude = analyze_trends_with_claude(output)
        if claude:
            output['claude_analysis'] = claude
            print(f"🔮 {claude.get('signal_dominant')}")

    with open('trends_data.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("\n✅ trends_data.json saved")

if __name__ == "__main__":
    run()
