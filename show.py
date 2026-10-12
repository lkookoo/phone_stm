import json
d = json.load(open("ov.json", encoding="utf-8"))
for t in d.get("ticks", []):
    print(f"  {t['symbol']:8s} {t['price']:>12}  ({t.get('source')})")
