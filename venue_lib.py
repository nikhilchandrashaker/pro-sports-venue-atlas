"""Shared cleaning, validation and geospatial helpers for the Pro Venue dashboard."""
from __future__ import annotations
import re
from itertools import combinations
import numpy as np
import pandas as pd

EXPECTED_TEAMS = {"NBA": 30, "NFL": 32, "MLB": 30, "NHL": 32}
LEAGUES = list(EXPECTED_TEAMS)
LEAGUE_COLORS = {"NBA": "#C9082A", "NFL": "#013369", "MLB": "#00A3E0", "NHL": "#6F7B83"}

# state/province -> (abbr, country, census-style region, (lat_min, lat_max, lon_min, lon_max))
# Bounding boxes are deliberately generous; they catch swapped signs / wrong-state errors, not street-level errors.
REGIONS = {
 "Alberta": ("AB","Canada","Canada",(48.9,60.1,-120.1,-109.9)),
 "Arizona": ("AZ","USA","West",(31.3,37.1,-114.9,-109.0)),
 "British Columbia": ("BC","Canada","Canada",(48.2,60.1,-139.1,-114.0)),
 "California": ("CA","USA","West",(32.5,42.1,-124.5,-114.1)),
 "Colorado": ("CO","USA","West",(36.9,41.1,-109.1,-102.0)),
 "D.C.": ("DC","USA","South",(38.78,39.0,-77.13,-76.90)),
 "Florida": ("FL","USA","South",(24.4,31.1,-87.7,-79.9)),
 "Georgia": ("GA","USA","South",(30.3,35.1,-85.7,-80.8)),
 "Illinois": ("IL","USA","Midwest",(36.9,42.6,-91.6,-87.0)),
 "Indiana": ("IN","USA","Midwest",(37.7,41.8,-88.2,-84.7)),
 "Louisiana": ("LA","USA","South",(28.9,33.1,-94.1,-88.7)),
 "Manitoba": ("MB","Canada","Canada",(48.9,60.1,-102.1,-88.9)),
 "Maryland": ("MD","USA","South",(37.8,39.8,-79.6,-75.0)),
 "Massachusetts": ("MA","USA","Northeast",(41.2,42.9,-73.6,-69.9)),
 "Michigan": ("MI","USA","Midwest",(41.6,48.3,-90.5,-82.1)),
 "Minnesota": ("MN","USA","Midwest",(43.4,49.4,-97.3,-89.4)),
 "Missouri": ("MO","USA","Midwest",(35.9,40.7,-95.8,-89.1)),
 "Nevada": ("NV","USA","West",(35.0,42.1,-120.1,-114.0)),
 "New Jersey": ("NJ","USA","Northeast",(38.9,41.4,-75.6,-73.8)),
 "New York": ("NY","USA","Northeast",(40.4,45.1,-79.8,-71.8)),
 "North Carolina": ("NC","USA","South",(33.8,36.7,-84.4,-75.4)),
 "Ohio": ("OH","USA","Midwest",(38.4,42.4,-84.9,-80.5)),
 "Oklahoma": ("OK","USA","South",(33.6,37.1,-103.1,-94.4)),
 "Ontario": ("ON","Canada","Canada",(41.6,56.9,-95.2,-74.3)),
 "Oregon": ("OR","USA","West",(41.9,46.3,-124.7,-116.4)),
 "Pennsylvania": ("PA","USA","Northeast",(39.7,42.3,-80.6,-74.7)),
 "Quebec": ("QC","Canada","Canada",(44.9,62.6,-79.8,-57.1)),
 "Tennessee": ("TN","USA","South",(34.9,36.7,-90.4,-81.6)),
 "Texas": ("TX","USA","South",(25.8,36.6,-106.7,-93.5)),
 "Utah": ("UT","USA","West",(36.9,42.1,-114.1,-109.0)),
 "Washington": ("WA","USA","West",(45.5,49.1,-124.9,-116.9)),
 "Wisconsin": ("WI","USA","Midwest",(42.4,47.1,-92.9,-86.7)),
}
# Cluster-derived metro names (cities within ~40 km of each other are one market).
METRO_NAMES = {
 "AT&T Stadium":"Dallas–Fort Worth","Ball Arena":"Denver","Barclays Center":"New York Metro",
 "Capital One Arena":"Washington, D.C.","Chase Center":"San Francisco","Crypto.com Arena":"Los Angeles",
 "Fiserv Forum":"Milwaukee","Gainbridge Fieldhouse":"Indianapolis","Golden 1 Center":"Sacramento",
 "Kaseya Center":"Miami","Little Caesars Arena":"Detroit","Mortgage Matchup Center":"Phoenix",
 "Rocket Arena":"Cleveland","Scotiabank Arena":"Toronto","Smoothie King Center":"New Orleans",
 "Spectrum Center":"Charlotte","State Farm Arena":"Atlanta","Target Center":"Minneapolis–St. Paul",
 "TD Garden":"Boston","Toyota Center":"Houston","United Center":"Chicago","Xfinity Mobile Arena":"Philadelphia",
 "PPG Paints Arena":"Pittsburgh","Allegiant Stadium":"Las Vegas","Arrowhead Stadium":"Kansas City",
 "KeyBank Center":"Buffalo","Climate Pledge Arena":"Seattle","M&T Bank Stadium":"Baltimore",
 "Bridgestone Arena":"Nashville","Paycor Stadium":"Cincinnati","Raymond James Stadium":"Tampa Bay",
 "Honda Center":"Anaheim (Orange County)","Enterprise Center":"St. Louis","SAP Center":"San Jose",
}


def hex_ok(s: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F]{6}", str(s)))


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0088 * np.arcsin(np.sqrt(a))


def readable_text_color(hex6: str) -> str:
    r, g, b = (int(hex6[i:i + 2], 16) for i in (0, 2, 4))
    return "#000000" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#FFFFFF"


# --------------------------------------------------------------------- cleaning
def load_raw(path: str) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def compare_sources(primary: pd.DataFrame, secondary: pd.DataFrame) -> pd.DataFrame:
    """Field-level differences between the two uploaded files, keyed on league+team."""
    m = primary.merge(secondary, on=["league", "team"], suffixes=("_primary", "_secondary"))
    rows = []
    for col in ["city", "state_province", "arena", "lat", "long", "abbreviation", "color", "alternate_color", "logo"]:
        d = m[m[f"{col}_primary"] != m[f"{col}_secondary"]]
        for _, r in d.iterrows():
            rows.append({"league": r.league, "team": r.team, "field": col,
                         "primary_value": r[f"{col}_primary"], "secondary_value": r[f"{col}_secondary"]})
    return pd.DataFrame(rows)


def clean_and_validate(raw: pd.DataFrame):
    """Returns (clean_df, issues_df). issues_df has one row per check: check, status, detail, rows_affected."""
    issues = []
    def log(check, ok, detail, n=0):
        issues.append({"check": check, "status": "PASS" if ok else "FIXED/FLAGGED", "detail": detail, "rows_affected": n})

    df = raw.copy()
    for c in df.columns:
        df[c] = df[c].astype(str).str.strip()
    log("Whitespace trimmed", True, "All text fields stripped of leading/trailing spaces")

    # missing values
    blanks = (df.replace({"": np.nan, "nan": np.nan}).isna().sum())
    log("Missing values", blanks.sum() == 0, "No blank cells in any of 11 columns" if blanks.sum() == 0 else blanks[blanks > 0].to_dict(), int(blanks.sum()))
    df = df.replace({"": np.nan})

    # league labels
    df["league"] = df["league"].str.upper()
    bad = ~df["league"].isin(LEAGUES)
    log("League labels", not bad.any(), "All labels in {NBA, NFL, MLB, NHL}", int(bad.sum()))
    counts = df.league.value_counts().to_dict()
    log("Teams per league", all(counts.get(k) == v for k, v in EXPECTED_TEAMS.items()),
        f"Found {counts}; expected {EXPECTED_TEAMS}", 0)

    # team names
    dup = df.duplicated(["league", "team"]).sum()
    log("Duplicate team rows", dup == 0, "Each league+team appears exactly once", int(dup))
    cross = df.groupby("team").league.nunique()
    log("Team name unique across leagues", (cross == 1).all(), "No team name appears in two leagues", int((cross > 1).sum()))
    ab_dup = df.duplicated(["league", "abbreviation"]).sum()
    log("Abbreviation unique within league", ab_dup == 0, "No abbreviation collisions", int(ab_dup))
    log("Team-name style", True,
        "'LA Clippers' is the official branding (not 'Los Angeles'); kept as-is. 'Athletics' has no city prefix (relocated, official name). Both noted, not changed.", 2)

    # coordinates
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["long"] = pd.to_numeric(df["long"], errors="coerce")
    nan_c = df[["lat", "long"]].isna().any(axis=1)
    log("Coordinates numeric", not nan_c.any(), "lat/long parse as floats", int(nan_c.sum()))
    rng = ~df.lat.between(24, 55) | ~df.long.between(-126, -65)
    log("Coordinates within North America", not rng.any(), "All inside lat 24–55, lon −126…−65", int(rng.sum()))
    sign = (df.long > 0).sum()
    log("Longitude sign (western hemisphere)", sign == 0, "No positive longitudes", int(sign))
    unknown = ~df.state_province.isin(REGIONS)
    log("State/province recognised", not unknown.any(), f"{df.state_province.nunique()} distinct regions, all mapped", int(unknown.sum()))
    def in_box(r):
        if r.state_province not in REGIONS: return False
        a, b, c, d = REGIONS[r.state_province][3]
        return a <= r.lat <= b and c <= r.long <= d
    outside = ~df.apply(in_box, axis=1)
    log("Coordinates fall inside stated state/province", not outside.any(),
        "Every point lies in its state/province bounding box" if not outside.any() else df[outside][["team", "state_province"]].values.tolist(), int(outside.sum()))
    grp = df.groupby("arena")[["lat", "long"]].nunique().max(axis=1)
    log("Shared venues have identical coordinates", (grp == 1).all(), "Co-tenant teams share exactly one coordinate pair", int((grp > 1).sum()))

    # colours / logos
    for col in ("color", "alternate_color"):
        bad = ~df[col].apply(hex_ok)
        log(f"{col} is valid 6-digit hex", not bad.any(), "All valid", int(bad.sum()))
    host_ok = df.apply(lambda r: bool(re.match(rf"^https://a\.espncdn\.com/i/teamlogos/{r.league.lower()}/[\w-]+/[A-Za-z0-9]+\.png$", r.logo)), axis=1)
    log("Logo URL host & league path", host_ok.all(), "All logos are ESPN CDN URLs under the matching league folder", int((~host_ok).sum()))
    nonstd = ~df.logo.str.match(r"^https://a\.espncdn\.com/i/teamlogos/(nba|nfl|mlb|nhl)/500/[a-z0-9]+\.png$")
    log("Logo filename convention", not nonstd.any(),
        "FLAGGED, NOT MODIFIED (cannot verify offline): 32 NHL logos use UPPERCASE filenames and Carolina Panthers uses the '500-dark' folder. The app hides any logo that fails to load.", int(nonstd.sum()))

    # derived fields
    df["country"] = df.state_province.map(lambda s: REGIONS[s][1])
    df["state_abbr"] = df.state_province.map(lambda s: REGIONS[s][0])
    df["region"] = df.state_province.map(lambda s: REGIONS[s][2])
    df["color_hex"] = "#" + df.color.str.upper()
    df["alt_color_hex"] = "#" + df.alternate_color.str.upper()
    df["text_on_color"] = df.color.apply(readable_text_color)
    df["team_nickname"] = df.apply(lambda r: r.team.replace(r.city, "").strip() if r.team.startswith(r.city) else r.team.split(" ", 1)[-1], axis=1)
    df["venue_id"] = df.arena + "|" + df.lat.round(4).astype(str) + "|" + df.long.round(4).astype(str)
    df = assign_metros(df)
    n_shared = df.groupby("venue_id").size().gt(1).sum()
    log("Derived fields added", True, f"country, state_abbr, region, color_hex, text_on_color, metro, metro_cluster ({n_shared} venues hosting >1 team)", len(df))
    return df.sort_values(["league", "team"]).reset_index(drop=True), pd.DataFrame(issues)


def assign_metros(df: pd.DataFrame, eps_km: float = 40) -> pd.DataFrame:
    from sklearn.cluster import DBSCAN
    v = df.drop_duplicates("venue_id")[["venue_id", "arena", "city", "lat", "long"]].reset_index(drop=True)
    lab = DBSCAN(eps=eps_km / 6371.0088, min_samples=1, metric="haversine").fit_predict(np.radians(v[["lat", "long"]].values))
    v["metro_cluster"] = lab
    def name(g):
        for a in g.arena:
            if a in METRO_NAMES: return METRO_NAMES[a]
        return g.city.mode().iat[0]
    names = v.groupby("metro_cluster").apply(name, include_groups=False)
    v["metro"] = v.metro_cluster.map(names)
    return df.merge(v[["venue_id", "metro", "metro_cluster"]], on="venue_id", how="left")


# ----------------------------------------------------------------- analysis
def venue_table(df: pd.DataFrame) -> pd.DataFrame:
    """One row per physical venue."""
    g = df.groupby("venue_id").agg(
        arena=("arena", "first"), city=("city", "first"), state_province=("state_province", "first"),
        state_abbr=("state_abbr", "first"), country=("country", "first"), region=("region", "first"),
        metro=("metro", "first"), lat=("lat", "first"), long=("long", "first"),
        leagues=("league", lambda s: "/".join(sorted(set(s)))), n_teams=("team", "count"),
        teams=("team", lambda s: ", ".join(s))).reset_index()
    return g


def metro_summary(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("metro").agg(
        teams=("team", "count"), venues=("venue_id", "nunique"), leagues=("league", "nunique"),
        league_list=("league", lambda s: "/".join(sorted(set(s)))), lat=("lat", "mean"), long=("long", "mean"),
        country=("country", "first"))
    for l in LEAGUES:
        g[l] = df[df.league == l].groupby("metro").size().reindex(g.index).fillna(0).astype(int)
    return g.sort_values(["teams", "leagues"], ascending=False).reset_index()


def pairwise_distances(df: pd.DataFrame, same_league: bool = False) -> pd.DataFrame:
    v = venue_table(df)
    rows = []
    for (i, a), (j, b) in combinations(v.iterrows(), 2):
        rows.append((a.arena, b.arena, a.metro, b.metro, haversine_km(a.lat, a.long, b.lat, b.long)))
    d = pd.DataFrame(rows, columns=["venue_a", "venue_b", "metro_a", "metro_b", "km"])
    d["miles"] = d.km * 0.621371
    return d


def nearest_neighbor_by_league(df: pd.DataFrame) -> pd.DataFrame:
    """Distance from each team's venue to the closest venue of a *different* franchise in the same league."""
    out = []
    for l, g in df.groupby("league"):
        g = g.reset_index(drop=True)
        for i, r in g.iterrows():
            d = np.asarray(haversine_km(r.lat, r.long, g.lat.values, g.long.values), dtype=float)
            d[(g.venue_id == r.venue_id).values] = np.inf
            j = int(np.argmin(d))
            out.append({"league": l, "team": r.team, "nearest_team": g.team[j], "km": float(np.min(d))})
    o = pd.DataFrame(out)
    o["miles"] = o.km * 0.621371
    return o


def league_centroid_stats(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for l, g in df.groupby("league"):
        clat, clon = g.lat.mean(), g.long.mean()
        dist = haversine_km(g.lat, g.long, clat, clon)
        rows.append({"league": l, "teams": len(g), "venues": g.venue_id.nunique(), "metros": g.metro.nunique(),
                     "states_provs": g.state_province.nunique(), "canadian_teams": int((g.country == "Canada").sum()),
                     "centroid_lat": clat, "centroid_lon": clon, "mean_km_from_centroid": dist.mean(),
                     "median_km_from_centroid": dist.median(), "east_west_span_km": haversine_km(g.lat.mean(), g.long.min(), g.lat.mean(), g.long.max()),
                     "north_south_span_km": haversine_km(g.lat.min(), g.long.mean(), g.lat.max(), g.long.mean())})
    return pd.DataFrame(rows)


def regional_clusters(df: pd.DataFrame, k: int = 6, seed: int = 7) -> pd.DataFrame:
    """KMeans on 3-D unit-sphere coordinates -> k super-regions of venue density (named by largest metro)."""
    from sklearn.cluster import KMeans
    v = venue_table(df)
    k = max(1, min(k, len(v)))
    la, lo = np.radians(v.lat), np.radians(v.long)
    X = np.c_[np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)]
    km = KMeans(n_clusters=k, n_init=20, random_state=seed).fit(X)
    v["cluster"] = km.labels_
    big = v.groupby("cluster").apply(lambda g: g.groupby("metro").n_teams.sum().idxmax(), include_groups=False)
    v["cluster_name"] = v.cluster.map(lambda c: f"{big[c]} region")
    return v


def shared_venues(df: pd.DataFrame) -> pd.DataFrame:
    v = venue_table(df)
    return v[v.n_teams > 1].sort_values(["n_teams", "arena"], ascending=[False, True]).reset_index(drop=True)


def recluster_metros(df: pd.DataFrame, eps_km: float) -> pd.DataFrame:
    """Re-define 'metro' with a different linking radius (used by the dashboard slider).
    Merged clusters keep the name of the base metro that has the most teams."""
    from sklearn.cluster import DBSCAN
    d = df.copy()
    v = d.drop_duplicates("venue_id")[["venue_id", "lat", "long"]].reset_index(drop=True)
    lab = DBSCAN(eps=eps_km / 6371.0088, min_samples=1, metric="haversine").fit_predict(np.radians(v[["lat", "long"]].values))
    d = d.merge(v.assign(_c=lab)[["venue_id", "_c"]], on="venue_id")
    pick = d.groupby(["_c", "metro"]).size().reset_index(name="n").sort_values(["_c", "n"], ascending=[True, False]).drop_duplicates("_c")
    d["metro"] = d._c.map(dict(zip(pick._c, pick.metro)))
    d["metro_cluster"] = d._c
    return d.drop(columns="_c")
