import requests
import csv

url = "https://mcgisweb.co.middlesex.nj.us/elections/api/election/2018-11-6"
r = requests.get(url)
response = r.json()
results = []

for race in response['races']:
    if race.has_key('office'):
        office = race['office']
        level = race['level']
        for choice in race['choices']:
            candidate = choice['name']
            if choice.has_key('party'):
                party = choice['party']
            else:
                party = None
            for result in choice['results']:
                if result.has_key('wards'):
                    for ward in result['wards']:
                        for dist in ward['dists']:
                            results.append(['Middlesex', result['muni'], ward['ward'], dist['dist'], level, office, candidate, party, dist['votes']])

with open("20181106__nj__general__middlesex__precinct2.csv", "wt") as csvfile:
    w = csv.writer(csvfile)
    w.writerow(['county', 'muni', 'ward', 'district', 'level', 'office', 'candidate', 'party', 'votes'])
    w.writerows(results)
