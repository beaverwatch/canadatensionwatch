import requests
import json
import time
import random
import re
from datetime import datetime
from calendar import monthrange

# ============================================
# BEAVER.WATCH — Kijiji Stress Index Scraper
# Version 2.0
# Features:
#   - Title parsing (Gemini-optimized)
#   - Payday Alert Logic
#   - Monthly Report Generation
# ============================================

CITIES = {
    "montreal": {"id": "1700281", "name": "Montréal"},
    "toronto":  {"id": "1700272", "name": "Toronto"},
    "vancouver":{"id": "1700254", "name": "Vancouver"},
}

CATEGORIES = {
    "outils": {
        "label_fr": "Outils & Équipement",
        "label_en": "Tools & Equipment",
        "signal":   "Entrepreneurs liquidating",
        "emoji":    "🔧",
        "weight":   0.35
    },
    "electronique": {
        "label_fr": "Consoles & Électronique",
        "label_en": "Electronics & Gaming",
        "signal":   "Households selling assets",
        "emoji":    "🎮",
        "weight":   0.25
    },
    "transfert-bail": {
        "label_fr": "Transfert de Bail",
        "label_en": "Lease Transfers",
        "signal":   "People fleeing housing costs",
        "emoji":    "🏠",
        "weight":   0.25
    },
    "bijoux-montres": {
        "label_fr": "Bijoux & Montres",
        "label_en": "Jewelry & Watches",
        "signal":   "Families selling valuables",
        "emoji":    "💍",
        "weight":   0.15
    },
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
]

# ============================================
# PAYDAY LOGIC
# ============================================

def get_pay_period():
    """
    Determines if we are before or after payday.
    Day 1-14  = Before Payday (stress builds)
    Day 15-31 = After Payday (stress should drop)
    """
    today = datetime.now().day
    month = datetime.now().month
    year = datetime.now().year
    days_in_month = monthrange(year, month)[1]

    if today <= 14:
        days_until_payday = 15 - today
        return {
            "period": "avant-paye",
            "period_en": "before-payday",
            "label_fr": "Avant la Paye",
            "label_en": "Before Payday",
            "day_of_month": today,
            "days_until_payday": days_until_payday,
            "days_since_payday": None,
            "emoji": "📉"
        }
    else:
        days_since = today - 15
        return {
            "period": "apres-paye",
            "period_en": "after-payday",
            "label_fr": "Après la Paye",
            "label_en": "After Payday",
            "day_of_month": today,
            "days_until_payday": None,
            "days_since_payday": days_since,
            "emoji": "📈"
        }

def check_payday_alert(national_score, pay_period, history):
    """
    PAYDAY ALERT:
    If score stays >= 0.50 after payday + 3 days
    = Canadians so indebted paycheque doesn't help
    """
    alert = False
    alert_level = None
    message_fr = None
    message_en = None

    if pay_period["period"] == "apres-paye":
        days_since = pay_period["days_since_payday"]

        if days_since >= 3 and national_score >= 0.65:
            alert = True
            alert_level = "CRITIQUE"
            message_fr = "🚨 ALERTE AVANT-PAYE : Le stress Kijiji reste CRITIQUE après la paye. Les Canadiens sont si endettés que le chèque de paye ne suffit plus."
            message_en = "🚨 PAYDAY ALERT: Kijiji stress remains CRITICAL after payday. Canadians are so indebted their paycheque no longer helps."

        elif days_since >= 3 and national_score >= 0.50:
            alert = True
            alert_level = "TENSION"
            message_fr = "⚠️ ALERTE AVANT-PAYE : Le stress Kijiji reste élevé après la paye. Signal de détresse financière persistante."
            message_en = "⚠️ PAYDAY ALERT: Kijiji stress remains high after payday. Signal of persistent financial distress."

    return {
        "active": alert,
        "level": alert_level,
        "days_since_payday": pay_period.get("days_since_payday"),
        "message_fr": message_fr,
        "message_en": message_en,
    }

# ============================================
# SCRAPER
# ============================================

def get_count(keyword, city_id):
    """
    Gemini method: parse <title> tag only.
    Light, stable, stealthy.
    """
    url = f"https://www.kijiji.ca/b-{city_id}/{keyword}/k0l{city_id}"

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "fr-CA,fr;q=0.9,en-CA;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.kijiji.ca/",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)

        if resp.status_code != 200:
            print(f"HTTP {resp.status_code}")
            return None

        title_match = re.search(r'<title[^>]*>(.*?)</title>', resp.text, re.IGNORECASE | re.DOTALL)
        if not title_match:
            print("no title")
            return None

        title = title_match.group(1).strip()
        print(f'"{title[:55]}"', end=" → ")

        if any(x in title.lower() for x in ["aucune", "no ads", "0 annonce", "0 ad"]):
            print("0")
            return 0

        numbers = re.findall(r'\d[\d\s,\.]*\d|\d', title)
        for raw in numbers:
            cleaned = re.sub(r'[\s,\.]', '', raw)
            if cleaned.isdigit() and int(cleaned) > 0:
                print(int(cleaned))
                return int(cleaned)

        print("parse failed")
        return None

    except requests.Timeout:
        print("timeout")
        return None
    except Exception as e:
        print(f"error: {e}")
        return None

# ============================================
# SCORING
# ============================================

def calculate_score(current, baseline):
    if baseline is None or baseline == 0 or current is None:
        return None
    change = ((current - baseline) / baseline) * 100
    if change <= 0:
        return max(0.05, round(0.15 + (change / 200), 2))
    elif change <= 5:
        return round(0.15 + (change / 5) * 0.20, 2)
    elif change <= 15:
        return round(0.35 + ((change - 5) / 10) * 0.30, 2)
    elif change <= 30:
        return round(0.65 + ((change - 15) / 15) * 0.25, 2)
    else:
        return min(1.0, round(0.90 + ((change - 30) / 50) * 0.10, 2))

def get_status(score):
    if score is None:
        return {"label_fr": "N/A", "label_en": "N/A", "color": "gray", "emoji": "❓"}
    if score < 0.35:
        return {"label_fr": "Normal", "label_en": "Normal", "color": "green", "emoji": "🟢"}
    if score < 0.65:
        return {"label_fr": "Tension", "label_en": "Tension", "color": "orange", "emoji": "🟠"}
    return {"label_fr": "CRISE", "label_en": "CRISIS", "color": "red", "emoji": "🔴"}

# ============================================
# MONTHLY REPORT
# ============================================

def generate_monthly_report(history, current_score, city_scores):
    """
    Runs on 1st of each month.
    Calculates monthly averages, trends, and predictions.
    """
    now = datetime.now()
    is_first_of_month = (now.day == 1)

    if not is_first_of_month:
        return None

    month_key = now.strftime("%Y-%m")
    prev_month = datetime.now().replace(day=1)

    # Get all entries from last month
    last_month_entries = [
        v for k, v in history.items()
        if k.startswith(month_key)
    ]

    if not last_month_entries:
        return None

    scores = [e["national_score"] for e in last_month_entries if e.get("national_score")]

    if not scores:
        return None

    avg_score = round(sum(scores) / len(scores), 2)
    max_score = round(max(scores), 2)
    min_score = round(min(scores), 2)

    # Trend: compare first half vs second half
    mid = len(scores) // 2
    first_half = sum(scores[:mid]) / max(mid, 1)
    second_half = sum(scores[mid:]) / max(len(scores) - mid, 1)
    trend = "hausse" if second_half > first_half else "baisse"
    trend_en = "rising" if second_half > first_half else "falling"

    # Most stressed city
    most_stressed_city = max(city_scores, key=city_scores.get) if city_scores else "N/A"

    # Interpretation
    if avg_score >= 0.65:
        interpretation_fr = f"🔴 Mois de CRISE. Score moyen {avg_score}. Détresse économique généralisée au Canada."
        interpretation_en = f"🔴 CRISIS month. Average score {avg_score}. Widespread economic distress in Canada."
    elif avg_score >= 0.40:
        interpretation_fr = f"🟠 Mois de TENSION. Score moyen {avg_score}. Stress économique persistant."
        interpretation_en = f"🟠 TENSION month. Average score {avg_score}. Persistent economic stress."
    else:
        interpretation_fr = f"🟢 Mois NORMAL. Score moyen {avg_score}. Situation relativement stable."
        interpretation_en = f"🟢 NORMAL month. Average score {avg_score}. Relatively stable situation."

    return {
        "month": month_key,
        "month_label_fr": now.strftime("%B %Y"),
        "month_label_en": now.strftime("%B %Y"),
        "avg_score": avg_score,
        "max_score": max_score,
        "min_score": min_score,
        "trend_fr": trend,
        "trend_en": trend_en,
        "most_stressed_city": most_stressed_city,
        "city_averages": city_scores,
        "interpretation_fr": interpretation_fr,
        "interpretation_en": interpretation_en,
        "data_points": len(scores),
        "generated": now.strftime("%Y-%m-%d"),
    }

# ============================================
# MAIN
# ============================================

def run():
    print("🦫 BEAVER.WATCH — Kijiji Stress Index v2.0")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("🔍 Method: Title parsing (Gemini-optimized)")
    print("📊 Features: Payday Alert + Monthly Report")
    print("=" * 52)

    # Load files
    try:
        with open('kijiji_baseline.json', 'r') as f:
            baseline = json.load(f)
        print("✅ Baseline loaded")
    except FileNotFoundError:
        baseline = {}
        print("⚠️  No baseline — today becomes baseline")

    try:
        with open('kijiji_history.json', 'r') as f:
            history = json.load(f)
        print("✅ History loaded")
    except FileNotFoundError:
        history = {}
        print("⚠️  No history — starting fresh")

    # Pay period
    pay_period = get_pay_period()
    print(f"\n💰 Pay Period: {pay_period['label_fr']} (Jour {pay_period['day_of_month']})")

    output = {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "version": "2.0",
        "pay_period": pay_period,
        "payday_alert": None,
        "cities": {},
        "national_score": None,
        "national_status": None,
        "monthly_report": None,
    }

    all_city_scores = []
    city_composite_scores = {}

    for city_key, city_info in CITIES.items():
        print(f"\n📍 {city_info['name']}")
        city_result = {
            "name_fr": city_info['name'],
            "name_en": city_info['name'],
            "categories": {},
            "composite_score": None,
            "composite_status": None,
        }
        weighted_scores = []

        for cat_key, cat_info in CATEGORIES.items():
            delay = random.uniform(6, 14)
            time.sleep(delay)
            print(f"  [{delay:.0f}s] {cat_key}: ", end="", flush=True)

            count = get_count(cat_key, city_info['id'])

            bkey = f"{city_key}_{cat_key}"
            base_count = baseline.get(bkey)

            if base_count is None and count is not None:
                baseline[bkey] = count
                base_count = count

            score = calculate_score(count, base_count)
            status = get_status(score)
            change_pct = None
            if count is not None and base_count:
                change_pct = round(((count - base_count) / base_count) * 100, 1)

            city_result['categories'][cat_key] = {
                "label_fr":   cat_info['label_fr'],
                "label_en":   cat_info['label_en'],
                "emoji":      cat_info['emoji'],
                "signal":     cat_info['signal'],
                "count":      count,
                "baseline":   base_count,
                "change_pct": change_pct,
                "score":      score,
                "status":     status,
                "weight":     cat_info['weight'],
            }

            if score is not None:
                weighted_scores.append((score, cat_info['weight']))

        # City composite
        if weighted_scores:
            total_w = sum(w for _, w in weighted_scores)
            composite = round(sum(s * w for s, w in weighted_scores) / total_w, 2)
            city_result['composite_score'] = composite
            city_result['composite_status'] = get_status(composite)
            all_city_scores.append(composite)
            city_composite_scores[city_key] = composite
            print(f"\n  📊 {city_info['name']}: {composite} {get_status(composite)['emoji']}")

        output['cities'][city_key] = city_result

    # National score
    if all_city_scores:
        national = round(sum(all_city_scores) / len(all_city_scores), 2)
        output['national_score'] = national
        output['national_status'] = get_status(national)
        print(f"\n🍁 NATIONAL: {national} {get_status(national)['emoji']}")

        # Payday alert
        payday_alert = check_payday_alert(national, pay_period, history)
        output['payday_alert'] = payday_alert
        if payday_alert['active']:
            print(f"\n{payday_alert['message_fr']}")

        # Save to history
        date_key = datetime.now().strftime("%Y-%m-%d")
        history[date_key] = {
            "national_score": national,
            "city_scores": city_composite_scores,
            "pay_period": pay_period['period'],
            "date": date_key,
        }

        # Monthly report (runs on 1st of month)
        monthly = generate_monthly_report(history, national, city_composite_scores)
        if monthly:
            output['monthly_report'] = monthly
            print(f"\n📋 RAPPORT MENSUEL GÉNÉRÉ: {monthly['month']}")

            # Save monthly reports
            try:
                with open('kijiji_monthly_reports.json', 'r') as f:
                    monthly_reports = json.load(f)
            except FileNotFoundError:
                monthly_reports = {}

            monthly_reports[monthly['month']] = monthly
            with open('kijiji_monthly_reports.json', 'w', encoding='utf-8') as f:
                json.dump(monthly_reports, f, ensure_ascii=False, indent=2)
            print("✅ kijiji_monthly_reports.json saved")

    # Save all files
    with open('kijiji_data.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("\n✅ kijiji_data.json saved")

    with open('kijiji_baseline.json', 'w', encoding='utf-8') as f:
        json.dump(baseline, f, ensure_ascii=False, indent=2)
    print("✅ kijiji_baseline.json saved")

    with open('kijiji_history.json', 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print("✅ kijiji_history.json saved")

    print("\n🦫 Done!")

if __name__ == "__main__":
    run()
