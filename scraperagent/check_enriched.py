import csv

rows = []
with open('data/tunisia_labeled_startups_enriched.csv', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append(row)

print(f"Total records: {len(rows)}")
print()

# Sector breakdown
sectors = {}
for r in rows:
    s = r['sector']
    sectors[s] = sectors.get(s, 0) + 1

print("Sector breakdown:")
for s, c in sorted(sectors.items(), key=lambda x: -x[1]):
    bar = "#" * (c // 5)
    print(f"  {s:<15} {c:>4}  {bar}")

print()

# Confidence breakdown
conf = {}
for r in rows:
    c = r['confidence']
    conf[c] = conf.get(c, 0) + 1

print("Confidence breakdown:")
for c, n in sorted(conf.items(), key=lambda x: -x[1]):
    print(f"  {c:<10} {n:>4}")

print()

# Missing data check
missing_sector = sum(1 for r in rows if not r['sector'] or r['sector'] == 'other')
missing_year   = sum(1 for r in rows if not r['year_founded'])
print(f"'other' or missing sector : {missing_sector}")
print(f"Missing year_founded      : {missing_year}")

print()
print("Sample rows (first 10):")
for r in rows[:10]:
    print(f"  {r['name']:<35} sector={r['sector']:<15} conf={r['confidence']}")
