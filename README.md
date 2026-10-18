# Professional Sports Venue Dashboard (NBA · NFL · MLB · NHL)

## Run it
```bash
pip install -r requirements.txt
python build_data.py data/pro_venues_clean_final.csv   # optional: regenerates cleaned data, validation log, report charts
streamlit run app.py
```
`data/venues_clean.csv` is already built, so `streamlit run app.py` works immediately.

## Files
| File | Purpose |
|---|---|
| `app.py` | Streamlit dashboard (Folium map + Plotly charts), 5 tabs |
| `venue_lib.py` | Cleaning/validation, metro clustering, haversine distances, k-means regions |
| `build_data.py` | Runs the pipeline, writes `data/*.csv`, draws `report_assets/*.png` |
| `data/venues_clean.csv` | Cleaned dataset (124 teams, 11 raw + derived columns) |
| `data/validation_report.csv` | Every validation check and its result |
| `data/source_comparison.csv` | Field-level diff between the two uploaded CSVs |
| `FINDINGS_REPORT.md` / `.html` | Five findings with charts (the HTML is self-contained) |

## Dashboard tabs
1. **Venue map**: every venue; filters for league, country, state/province, city, shared-venue only; basemap and colour-mode switches; popups list every tenant.
2. **League comparison**: scorecard, teams/venues/metros, regional mix, latitude & longitude spread, state heat-map, shared markets matrix.
3. **Team directory**: searchable cards with logo, abbreviation, primary/alternate colour and venue; detail view with co-tenants and nearest teams.
4. **Geospatial analysis**: k-means regional clusters, metro markets, A→B distance tool, "within N miles", franchise spacing, closest venue pairs.
5. **Data quality**: validation results, two-file comparison, missing values, CSV downloads.

The sidebar **metro radius** slider (default 40 km) controls how nearby venues are grouped into one market.

## Method notes
* Distances are great-circle (haversine). Metro = DBSCAN on venue coordinates (default 40 km), named by hand for readability; it approximates, but is not, Census CBSA geography.
* Regional clusters = k-means on 3-D unit-sphere coordinates (avoids longitude wrap/distortion).
* Logo URLs are used as supplied; the app hides any image that fails to load.
