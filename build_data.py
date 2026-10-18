"""Builds cleaned data, validation logs, report charts and the findings report.
Run:  python build_data.py <primary.csv> [secondary.csv]
"""
import sys, json, pathlib
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import venue_lib as V

ROOT = pathlib.Path(__file__).parent
DATA, ASSETS = ROOT / "data", ROOT / "report_assets"
DATA.mkdir(exist_ok=True); ASSETS.mkdir(exist_ok=True)
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titleweight": "bold", "figure.dpi": 130, "axes.titlesize": 11})
LC = V.LEAGUE_COLORS
ASPECT = 1 / np.cos(np.radians(38))


def base_map(ax, title):
    ax.set_xlim(-127, -65); ax.set_ylim(24, 55); ax.set_aspect(ASPECT)
    ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude"); ax.set_title(title, loc="left"); ax.grid(alpha=.25)


def main(p1, p2=None):
    raw = V.load_raw(p1)
    df, issues = V.clean_and_validate(raw)
    df.to_csv(DATA / "venues_clean.csv", index=False)
    if p2:
        diff = V.compare_sources(raw, V.load_raw(p2))
        diff.to_csv(DATA / "source_comparison.csv", index=False)
        n_color = diff.field.isin(["color", "alternate_color"]).sum()
        issues.loc[len(issues)] = {"check": "Second file (pro_venues_clean_final_2_0.csv) cross-check",
            "status": "FIXED/FLAGGED", "rows_affected": int(diff[["league", "team"]].drop_duplicates().shape[0]),
            "detail": f"{len(diff)} field differences vs primary: {n_color} are colour codes with leading zeros stripped or turned into scientific notation "
                      f"(e.g. '0E+00', '3831'); 1 is a stale stadium name (Houston Texans 'Reliant Stadium' vs current 'NRG Stadium'). Primary file used."}
    issues.to_csv(DATA / "validation_report.csv", index=False)

    ms = V.metro_summary(df); sv = V.shared_venues(df); vt = V.venue_table(df)
    ls = V.league_centroid_stats(df); nn = V.nearest_neighbor_by_league(df); rc = V.regional_clusters(df, 6)
    ms.to_csv(DATA / "metro_summary.csv", index=False); ls.to_csv(DATA / "league_stats.csv", index=False)
    pw = V.pairwise_distances(df); pw.sort_values("km").head(25).to_csv(DATA / "closest_venue_pairs.csv", index=False)

    # ---------------- numbers for the report
    N = len(df)
    multi = ms[ms.leagues > 1]; four = ms[ms.leagues == 4]
    f = dict(N=N, venues=len(vt), metros=len(ms), multi_metros=len(multi), multi_teams=int(multi.teams.sum()),
             four_metros=len(four), four_teams=int(four.teams.sum()), ny_teams=int(ms.set_index("metro").loc["New York Metro", "teams"]),
             ny_venues=int(ms.set_index("metro").loc["New York Metro", "venues"]),
             la_teams=int(ms.set_index("metro").loc["Los Angeles", "teams"]), single=int((ms.leagues == 1).sum()))
    sh = df[df.venue_id.isin(sv.venue_id)]
    f["shared_venues"] = len(sv); f["shared_nba_nhl"] = int((sv.leagues == "NBA/NHL").sum())
    f["shared_by_league"] = sh.groupby("league").size().reindex(V.LEAGUES).fillna(0).astype(int).to_dict()
    f["can"] = df[df.country == "Canada"].groupby("league").size().reindex(V.LEAGUES).fillna(0).astype(int).to_dict()
    lsi = ls.set_index("league"); f["ls"] = lsi.round(0).to_dict("index")
    bw = df[(df.lat.between(38.5, 42.6)) & (df.long > -77.2)]
    f["boswash"] = len(bw); f["bw_metros"] = bw.metro.nunique()
    f["east90"] = round((df.long > -90).mean() * 100); f["west105"] = round((df.long < -105).mean() * 100)
    f["nn_med"] = nn.groupby("league").miles.median().round(0).to_dict()
    f["nn_max"] = nn.loc[nn.groupby("league").miles.idxmax()].set_index("league")[["team", "miles"]].round(0).to_dict("index")
    sl = ms[ms.leagues == 1]; f["single_by_league"] = {l: sorted(sl[sl.league_list == l].metro) for l in V.LEAGUES}
    f["sens60"] = V.recluster_metros(df, 60).metro.nunique()
    f["sens25"] = V.recluster_metros(df, 25).metro.nunique()
    f["clusters"] = rc.groupby("cluster_name").agg(venues=("arena", "count"), teams=("n_teams", "sum")).sort_values("teams", ascending=False).to_dict("index")
    json.dump(f, open(DATA / "findings_numbers.json", "w"), indent=1, default=str)

    # ---------------- charts
    # Overview map
    fig, ax = plt.subplots(figsize=(10, 6.2))
    for l in V.LEAGUES:
        g = vt[vt.leagues.str.contains(l)]
        ax.scatter(g.long, g.lat, s=60, c=LC[l], alpha=.75, label=f"{l} ({(df.league == l).sum()} teams)", edgecolor="white", lw=.6)
    base_map(ax, "All 124 team venues (111 physical venues)"); ax.legend(loc="lower left", frameon=False)
    fig.tight_layout(); fig.savefig(ASSETS / "00_overview_map.png"); plt.close(fig)

    # F1: co-location
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 5), gridspec_kw={"width_ratios": [1.5, 1]})
    cols = {1: "#BDBDBD", 2: "#9ECAE1", 3: "#3182BD", 4: "#08306B"}
    for k in (1, 2, 3, 4):
        g = ms[ms.leagues == k]
        a.scatter(g.long, g.lat, s=40 + g.teams * 38, c=cols[k], alpha=.85, edgecolor="white", label=f"{k} league{'s' if k > 1 else ''} ({len(g)} metros)")
    for _, r in ms[ms.teams >= 4].iterrows():
        a.annotate(r.metro.split(" (")[0], (r.long, r.lat), fontsize=7, xytext=(4, 4), textcoords="offset points")
    base_map(a, "Metro areas by number of leagues present (bubble = teams)"); a.legend(loc="lower left", frameon=False, fontsize=8)
    cnt = ms.groupby("leagues").teams.sum()
    b.bar([f"{k}" for k in cnt.index], cnt.values, color=[cols[k] for k in cnt.index])
    for i, v in enumerate(cnt.values): b.text(i, v + 1, f"{v} teams\n({v / N:.0%})", ha="center", fontsize=9)
    b.set_xlabel("Leagues present in the metro"); b.set_ylabel("Teams"); b.set_ylim(0, cnt.max() * 1.2)
    b.set_title("Where the 124 teams live", loc="left")
    fig.tight_layout(); fig.savefig(ASSETS / "01_colocation.png"); plt.close(fig)

    # F2: shared venues
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 4.8), gridspec_kw={"width_ratios": [1, 1.3]})
    pct = [f["shared_by_league"][l] / (df.league == l).sum() * 100 for l in V.LEAGUES]
    a.bar(V.LEAGUES, pct, color=[LC[l] for l in V.LEAGUES])
    for i, (p, l) in enumerate(zip(pct, V.LEAGUES)): a.text(i, p + 1, f"{f['shared_by_league'][l]} of {(df.league == l).sum()}", ha="center", fontsize=9)
    a.set_ylabel("% of teams sharing a venue"); a.set_title("Teams that share a building with another team", loc="left"); a.set_ylim(0, max(pct) * 1.25)
    s2 = sv.sort_values("n_teams").copy()
    b.barh(s2.arena, 1, color=[LC["NFL"] if x == "NFL" else LC["NBA"] for x in s2.leagues])
    for i, (_, r) in enumerate(s2.iterrows()): b.text(.03, i, f"{r.metro}: {r.teams}", va="center", color="white", fontsize=7.5)
    b.set_xticks([]); b.spines["bottom"].set_visible(False); b.set_title("The 13 shared venues (red = NBA+NHL, blue = NFL)", loc="left")
    fig.tight_layout(); fig.savefig(ASSETS / "02_shared_venues.png"); plt.close(fig)

    # F3: NHL outlier
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(13, 4.6))
    a.boxplot([df[df.league == l].lat for l in V.LEAGUES], tick_labels=V.LEAGUES, patch_artist=True,
              boxprops=dict(facecolor="#E8EEF4"), medianprops=dict(color="black"))
    for i, l in enumerate(V.LEAGUES): a.scatter(np.random.default_rng(1).normal(i + 1, .05, (df.league == l).sum()), df[df.league == l].lat, s=12, color=LC[l], alpha=.7, zorder=3)
    a.set_ylabel("Venue latitude (°N)"); a.set_title("Latitude spread", loc="left")
    b.bar(V.LEAGUES, ls.set_index("league").loc[V.LEAGUES].mean_km_from_centroid, color=[LC[l] for l in V.LEAGUES])
    for i, l in enumerate(V.LEAGUES): b.text(i, lsi.loc[l, "mean_km_from_centroid"] + 15, f"{lsi.loc[l, 'mean_km_from_centroid']:,.0f}", ha="center", fontsize=9)
    b.set_ylabel("Mean km from league centroid"); b.set_title("Dispersion", loc="left")
    c.bar(V.LEAGUES, [f["can"][l] for l in V.LEAGUES], color=[LC[l] for l in V.LEAGUES])
    for i, l in enumerate(V.LEAGUES): c.text(i, f["can"][l] + .1, str(f["can"][l]), ha="center")
    c.set_ylabel("Canadian teams"); c.set_title("Canadian franchises", loc="left")
    fig.tight_layout(); fig.savefig(ASSETS / "03_nhl_outlier.png"); plt.close(fig)

    # F4: regional clusters
    fig, (a, b) = plt.subplots(1, 2, figsize=(12.5, 5.2), gridspec_kw={"width_ratios": [1.6, 1]})
    pal = plt.cm.tab10(np.arange(6))
    names = sorted(rc.cluster_name.unique())
    for i, n in enumerate(names):
        g = rc[rc.cluster_name == n]
        a.scatter(g.long, g.lat, s=35 + 25 * g.n_teams, color=pal[i], alpha=.8, edgecolor="white", label=f"{n} ({int(g.n_teams.sum())} teams)")
    base_map(a, "Six geographic clusters of venues (k-means on the sphere)"); a.legend(loc="lower left", fontsize=7.5, frameon=False)
    ce = pd.DataFrame(f["clusters"]).T.sort_values("teams")
    b.barh(ce.index, ce.teams, color="#3B6EA5")
    for i, v in enumerate(ce.teams): b.text(v + .5, i, str(int(v)), va="center", fontsize=9)
    b.set_title("Teams per cluster", loc="left"); b.set_xlabel("Teams")
    fig.tight_layout(); fig.savefig(ASSETS / "04_regional_clusters.png"); plt.close(fig)

    # F5: spacing + single-league markets
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 5.8), gridspec_kw={"width_ratios": [1, 1.2]})
    a.boxplot([nn[nn.league == l].miles for l in V.LEAGUES], tick_labels=V.LEAGUES, patch_artist=True,
              boxprops=dict(facecolor="#E8EEF4"), medianprops=dict(color="black"), showfliers=True)
    a.set_ylabel("Miles to nearest other franchise (same league)"); a.set_title("Franchise spacing", loc="left")
    cnts = [len(f["single_by_league"][l]) for l in V.LEAGUES]
    b.bar(V.LEAGUES, cnts, color=[LC[l] for l in V.LEAGUES])
    for i, l in enumerate(V.LEAGUES):
        b.text(i, cnts[i] + .15, str(cnts[i]), ha="center")
        b.text(i, -1.0, "\n".join(f["single_by_league"][l][:6]) + ("\n…" if len(f["single_by_league"][l]) > 6 else ""), ha="center", va="top", fontsize=6.5)
    b.set_ylim(0, max(cnts) + 1.5); b.set_title("Metros where only one league is present", loc="left"); b.set_ylabel("Metros")
    fig.tight_layout(); fig.subplots_adjust(bottom=.30); fig.savefig(ASSETS / "05_spacing_single_league.png"); plt.close(fig)
    print(json.dumps({k: v for k, v in f.items() if k not in ("clusters", "single_by_league", "ls")}, indent=1, default=str))
    print(issues[["check", "status", "rows_affected"]].to_string())


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
