# Professional Sports Venues: Five Findings
*NBA · NFL · MLB · NHL — 124 teams, 111 physical venues, 51 metro markets*

![All team venues](report_assets/00_overview_map.png)

## Data and method in brief
Two CSVs were supplied. `pro_venues_clean_final.csv` was used as the source of truth because `pro_venues_clean_final_2_0.csv` carries 57 teams with damaged colour codes (leading zeros dropped, or values like `0E+00`) and the Houston Texans' stadium under its pre-2014 name (Reliant Stadium rather than NRG Stadium). Everything else matched. The cleaned file passed all checks: no missing values, 30/32/30/32 teams for NBA/NFL/MLB/NHL, no duplicate teams or abbreviations, valid coordinates that fall inside each team's stated state or province, and identical coordinates for co-tenant teams. Only one thing was flagged and left unchanged: 32 NHL logo filenames are upper-case and Carolina's uses a `500-dark` folder, which could not be verified offline. Full results are in `data/validation_report.csv`.

"Metro" means venues within 40 km of one another (distance-based, not Census geography). The conclusions are stable to that choice: 25 km and 40 km both give 51 metros, and 60 km gives 48 (it merges Washington/Baltimore, Los Angeles/Anaheim and San Francisco/San Jose).

---

## Finding 1: Co-location is the norm; 108 of 124 teams (87%) share a metro with another league
35 of the 51 metro markets host teams from two or more leagues. 11 markets host all four leagues (New York, Los Angeles, Chicago, Boston, Dallas–Fort Worth, Denver, Detroit, Miami, Minneapolis–St. Paul, Philadelphia and Washington) and together hold 52 teams, or 42% of the total. Only 16 metros have a single league. The league map is therefore largely one map: the same markets keep reappearing.

![Co-location](report_assets/01_colocation.png)

## Finding 2: Building-sharing is an NBA/NHL habit; baseball never shares
Of the 111 physical venues, 13 house more than one team: 11 are NBA+NHL arenas and 2 are NFL stadiums (MetLife for the Giants and Jets, SoFi for the Rams and Chargers). That means 11 of 30 NBA teams (37%) and 11 of 32 NHL teams (34%) share an arena, against 4 of 32 NFL teams (12%) and no MLB teams. Indoor arenas are interchangeable between basketball and hockey, which is why almost every shared building is an NBA/NHL pair.

![Shared venues](report_assets/02_shared_venues.png)

## Finding 3: The NHL is the geographic outlier, and the difference is north–south
The NHL has 7 of the 9 Canadian franchises across the four leagues (the NBA and MLB each have only Toronto; the NFL has none). Its venues span 3,045 km north to south versus 2,196–2,425 km for the others, its centroid sits near 41°N versus 37–38°N, and its venues average 1,480 km from the league centroid compared with 1,270–1,366 km. East–west reach is nearly identical in all four leagues (about 4,300–4,500 km), so league differences lie in latitude, not longitude.

![NHL outlier](report_assets/03_nhl_outlier.png)

## Finding 4: Teams cluster in the east; one corridor holds nearly a fifth of all franchises
K-means on the sphere splits the venues into six regions. The largest, covering the Northeast, Mid-Atlantic, eastern Great Lakes and eastern Canada, contains 37 teams (30%). Within it, the Boston-to-Washington corridor alone holds 23 teams in 5 metros (19%), and the New York area has 9 teams in 7 venues. Overall 56% of teams play east of 90°W while only 26% play west of 105°W. The other regions are the central/Midwest belt (29), the West (22), the Southeast (16), Texas–Plains (13) and the Pacific Northwest/Western Canada (7).

![Regional clusters](report_assets/04_regional_clusters.png)

## Finding 5: Franchise spacing differs sharply, and each league has its own outpost markets
The typical MLB team is only 102 miles from the nearest other MLB franchise, against 169 for the NHL, 187 for the NBA and 190 for the NFL; baseball's low figure comes from same-city pairs (Yankees/Mets, Cubs/White Sox, Dodgers/Angels). The most isolated franchises sit in the Pacific Northwest and Texas: the Seattle Seahawks (704 mi to the nearest NFL team), Seattle Mariners (624 mi), Dallas Stars (547 mi) and Portland Trail Blazers (484 mi). Sixteen metros have only one league: eight NHL-only (six in Canada, plus Columbus and Raleigh), five NBA-only (Memphis, Oklahoma City, Orlando, Portland, San Antonio), two NFL-only (Green Bay, Jacksonville) and one MLB-only (San Diego).

![Spacing and single-league markets](report_assets/05_spacing_single_league.png)

---

## Caveats
* Static charts in this report use plain latitude/longitude axes (no basemap); the dashboard has the full tiled interactive maps.
* Metro membership is distance-based and approximate. Moving the dashboard's radius slider shows how the grouping changes.
* The data holds one current venue per team, with no capacity, opening year or relocation history, so the findings describe today's footprint only.
* Distances are great-circle, not driving distances.
