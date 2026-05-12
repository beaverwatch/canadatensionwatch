import requests
from bs4 import BeautifulSoup
import json
import time
import random
from datetime import datetime

# ============================================
# BEAVER.WATCH — Kijiji Stress Index Scraper
# Runs daily via GitHub Actions
# Output: kijiji_data.json
# ============================================

# Cities config
CITIES = {
    "montreal": {"id": "1700281", "name": "Montréal"},
    "toronto":  {"id": "1700272", "name": "Toronto"},
    "vancouver":{"id": "1700254", "name": "Vancouver"},
}

# Stress categories — what we track
CATEGORIES = {
    "outils": {
        "label_fr": "Outils & Équipement",
        "label_en": "Tools & Equipment",
        "signal":   "Entrepreneurs liquidating",
        "emoji":    "🔧",
        "weight":   0.35
    },
    "ps5-xbox": {
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

HEADERS_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

def get_count(keyword, city_id, retries=3):
    """Scrape Kijiji listing count for a keyword in a city."""
    url = f"https://www.kijiji.ca/b-{city_id}/{keyword}/k0l{city_id}"
    
    for attempt in range(retries):
        try:
            headers = {
                "User-Agent": random.choice(HEADERS_POOL),
                "Accept-Language": "fr-CA,fr;q=0.9,en-CA;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Referer": "https://www.kijiji.ca/",
            }
            resp = requests.get(url, headers=headers, timeout=12)
            
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # Try multiple selectors (Kijiji changes these)
                selectors = [
                    {"attrs": {"data-testid": "total-count"}},
                    {"class_": "resultsShowingCount"},
                    {"class_": "searchResultsHeader"},
                ]
                
                for sel in selectors:
                    el = soup.find(True, sel) if "class_" not in sel else soup.find(class_=sel.get("class_"))
                    if not el and "attrs" in sel:
                        el = soup.find(attrs=sel["attrs"])
                    if el:
                        digits = ''.join(filter(str.isdigit, el.get_text()))
                        if digits:
                            return int(digits)
                
                # Fallback: count listing cards
                cards = soup.find_all("li", {"data-testid": "listing-card-list-item"})
                if cards:
                    return len(cards)
                    
            # Rate limit pause between retries
            time.sleep(random.uniform(3, 7))
            
        except Exception as e:
            print(f"  ⚠️  Attempt {attempt+1} failed for {keyword}/{city_id}: {e}")
            time.sleep(random.uniform(5, 10))
    
    return None  # Could not get data

def calculate_stress_score(counts, baseline):
    """
    Calculate stress score 0-1 based on % change from baseline.
    +5%  → normal (0.0–0.3)
    +15% → tension (0.4–0.6)
    +30% → crisis  (0.7–1.0)
    """
    if not baseline or baseline == 0:
        return None
    
    change_pct = ((counts - baseline) / baseline) * 100
    
    if change_pct <= 5:
        return round(0.1 + (change_pct / 5) * 0.2, 2)
    elif change_pct <= 15:
        return round(0.3 + ((change_pct - 5) / 10) * 0.3, 2)
    elif change_pct <= 30:
        return round(0.6 + ((change_pct - 15) / 15) * 0.3, 2)
    else:
        return min(1.0, round(0.9 + ((change_pct - 30) / 30) * 0.1, 2))

def get_status(score):
    if score is None:
        return {"label_fr": "Données manquantes", "label_en": "No data", "color": "gray", "emoji": "❓"}
    elif score < 0.35:
        return {"label_fr": "Normal", "label_en": "Normal", "color": "green", "emoji": "🟢"}
    elif score < 0.60:
        return {"label_fr": "Tension", "label_en": "Tension", "color": "orange", "emoji": "🟠"}
    else:
        return {"label_fr": "CRISE", "label_en": "CRISIS", "color": "red", "emoji": "🔴"}

def run_scraper():
    print("🦫 BEAVER.WATCH — Kijiji Stress Index Scraper")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)
    
    # Try to load existing baseline
    try:
        with open('kijiji_baseline.json', 'r') as f:
            baseline = json.load(f)
        print("✅ Baseline loaded")
    except:
        baseline = {}
        print("⚠️  No baseline found — today's data will become baseline")
    
    output = {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "cities": {},
        "national_score": None,
        "national_status": None,
    }
    
    all_scores = []
    
    for city_key, city_info in CITIES.items():
        print(f"\n📍 {city_info['name']}")
        city_data = {"name_fr": city_info['name'], "categories": {}, "composite_score": None}
        city_scores = []
        
        for cat_key, cat_info in CATEGORIES.items():
            print(f"  🔍 {cat_key}...", end=" ", flush=True)
            
            # Polite delay between requests
            time.sleep(random.uniform(4, 9))
            
            count = get_count(cat_key, city_info['id'])
            
            if count is not None:
                print(f"{count:,} listings")
            else:
                print("N/A")
            
            # Get baseline for this city+category
            baseline_key = f"{city_key}_{cat_key}"
            baseline_count = baseline.get(baseline_key)
            
            score = calculate_stress_score(count, baseline_count) if (count and baseline_count) else None
            status = get_status(score)
            
            cat_result = {
                "label_fr":      cat_info['label_fr'],
                "label_en":      cat_info['label_en'],
                "emoji":         cat_info['emoji'],
                "signal":        cat_info['signal'],
                "count":         count,
                "baseline":      baseline_count,
                "change_pct":    round(((count - baseline_count) / baseline_count * 100), 1) if (count and baseline_count) else None,
                "score":         score,
                "status":        status,
                "weight":        cat_info['weight'],
            }
            
            city_data['categories'][cat_key] = cat_result
            
            if score is not None:
                city_scores.append(score * cat_info['weight'])
            
            # Save to baseline if none exists
            if baseline_count is None and count:
                baseline[baseline_key] = count
        
        # Composite city score
        if city_scores:
            composite = round(sum(city_scores) / sum(
                cat_info['weight'] for cat_key, cat_info in CATEGORIES.items()
                if f"{city_key}_{cat_key}" in baseline or True
            ), 2)
            city_data['composite_score'] = composite
            city_data['composite_status'] = get_status(composite)
            all_scores.append(composite)
            print(f"\n  📊 {city_info['name']} Stress Score: {composite}")
        
        output['cities'][city_key] = city_data
    
    # National score
    if all_scores:
        national = round(sum(all_scores) / len(all_scores), 2)
        output['national_score'] = national
        output['national_status'] = get_status(national)
        print(f"\n🍁 NATIONAL Kijiji Stress Score: {national}")
    
    # Save results
    with open('kijiji_data.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("\n✅ kijiji_data.json saved")
    
    # Update baseline with today's data
    with open('kijiji_baseline.json', 'w', encoding='utf-8') as f:
        json.dump(baseline, f, ensure_ascii=False, indent=2)
    print("✅ kijiji_baseline.json updated")
    
    return output

if __name__ == "__main__":
    run_scraper()
