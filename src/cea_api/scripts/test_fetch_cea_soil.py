"""
Test CEA Soil Health API
========================
Tests the CrossEurAsia Soil Nutrient Map API and shows exactly
what the real response looks like — nutrient names, URL structure,
and whether statistics are included or only map URLs.
 
Usage:
    python src/cea_api/scripts/test_fetch_cea_soil.py
    python src/cea_api/scripts/test_fetch_cea_soil.py --farm_id NORCAJ2338
"""
 
import requests
import json
import argparse
from pathlib import Path
 
CEA_SOIL_URL = "https://ohob6203na.execute-api.ap-south-1.amazonaws.com/farm-soil-mar-2026"
DEFAULT_FARM  = "NORPIU0954"
 
 
def test_farm(farm_id: str) -> None:
    print("=" * 60)
    print("CEA SOIL HEALTH API — RESPONSE EXPLORER")
    print("=" * 60)
    print(f"  Endpoint: {CEA_SOIL_URL}")
    print(f"  Farm ID:  {farm_id}")
    print()
 
    try:
        response = requests.get(CEA_SOIL_URL, params={"farm_id": farm_id}, timeout=30)
        print(f"  HTTP Status: {response.status_code}")
 
        if response.status_code != 200:
            print(f"  ❌ Unexpected status. Body: {response.text[:200]}")
            return
 
        data = response.json()
 
    except requests.exceptions.Timeout:
        print("  ❌ Request timed out after 30 seconds")
        return
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return
 
    # ── Top-level structure ───────────────────────────────────────────────────
    print(f"\n📦 TOP-LEVEL KEYS IN RESPONSE:")
    for key in data.keys():
        val = data[key]
        if isinstance(val, dict):
            print(f"  '{key}': dict with {len(val)} entries")
        elif isinstance(val, str):
            print(f"  '{key}': string — '{val[:60]}'")
        else:
            print(f"  '{key}': {type(val).__name__} — {val}")
 
    # ── Maps structure ────────────────────────────────────────────────────────
    maps = data.get("maps", {})
    if not maps:
        print(f"\n⚠️  No 'maps' key found. Full response:\n{json.dumps(data, indent=2)[:500]}")
        return
 
    print(f"\n🗺️  NUTRIENTS RETURNED ({len(maps)} total):")
    for nutrient_name, nutrient_value in maps.items():
        if isinstance(nutrient_value, str):
            # Just a URL
            print(f"  '{nutrient_name}': URL ({len(nutrient_value)} chars)")
        elif isinstance(nutrient_value, dict):
            # Could have stats + URL
            print(f"  '{nutrient_name}': dict with keys {list(nutrient_value.keys())}")
        else:
            print(f"  '{nutrient_name}': {type(nutrient_value).__name__} — {nutrient_value}")
 
    # ── Key finding: stats or just URLs? ─────────────────────────────────────
    first_val = list(maps.values())[0]
    print(f"\n🔍 KEY FINDING:")
    if isinstance(first_val, str):
        print(f"  ⚠️  Nutrient values are PLAIN URLs only — no statistics in response")
        print(f"  Statistics (min/max/mean) are only visible inside the HTML map")
        print(f"\n  Sample URL (first 120 chars):")
        print(f"  {first_val[:120]}...")
        print(f"\n  → For Tableau charts: ask CEA to add statistics to the response")
        print(f"  → For map viewing: open URL in browser (valid for 1 hour)")
    elif isinstance(first_val, dict):
        print(f"  ✅ Nutrient values are dicts — may contain statistics!")
        print(f"  Keys found: {list(first_val.keys())}")
 
    # ── Test a second farm to check availability ──────────────────────────────
    print(f"\n🔄 TESTING A SECOND FARM (NORCAJ2338)...")
    try:
        r2 = requests.get(CEA_SOIL_URL, params={"farm_id": "NORCAJ2338"}, timeout=15)
        d2 = r2.json()
        if "maps" in d2:
            print(f"  ✅ NORCAJ2338 has data — {len(d2['maps'])} nutrients")
        elif "message" in str(d2):
            print(f"  ⚠️  NORCAJ2338: No data available")
        else:
            print(f"  Response: {str(d2)[:100]}")
    except Exception as e:
        print(f"  ❌ {e}")
 
    # ── Save full raw response ────────────────────────────────────────────────
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"cea_soil_response_{farm_id}.json"
 
    # Save without the full URL values (too long) — just structure
    safe_data = {
        "farm_id": data.get("farm_id"),
        "num_nutrients": len(maps),
        "nutrient_names": list(maps.keys()),
        "value_type": type(first_val).__name__,
        "value_keys_if_dict": list(first_val.keys()) if isinstance(first_val, dict) else None,
        "sample_url_preview": first_val[:80] + "..." if isinstance(first_val, str) else None,
    }
    with open(output_path, "w") as f:
        json.dump(safe_data, f, indent=2)
    print(f"\n💾 Summary saved to: {output_path}")
    print("=" * 60)
 
 
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--farm_id", default=DEFAULT_FARM,
                        help=f"Farm ID to test (default: {DEFAULT_FARM})")
    args = parser.parse_args()
    test_farm(args.farm_id)