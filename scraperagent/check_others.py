import csv

rows = []
with open('data/tunisia_labeled_startups_enriched.csv', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append(row)

others = [r for r in rows if r['sector'] == 'other']
print(f"Total 'other': {len(others)}")
print()
print("Name + Website for all 'other' records:")
for r in others:
    print(f"  {r['name']:<40} {r['website']}")
