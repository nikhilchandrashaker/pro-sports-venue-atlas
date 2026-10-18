"""Professional Sports Venue Mapping Dashboard  (NBA · NFL · MLB · NHL)
Run:  streamlit run app.py
"""
import pathlib
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import folium
from folium.plugins import Fullscreen
from streamlit_folium import st_folium
import venue_lib as V

ROOT = pathlib.Path(__file__).parent
DATA = ROOT / "data"
LC = V.LEAGUE_COLORS
MULTI = "#7B2CBF"

st.set_page_config(page_title="Pro Sports Venue Dashboard", page_icon="🏟️", layout="wide")


@st.cache_data
def load_data() -> pd.DataFrame:
    p = DATA / "venues_clean.csv"
    if p.exists():
        df = pd.read_csv(p, dtype=str, keep_default_na=False)
        for c in ("lat", "long", "metro_cluster"):
            df[c] = pd.to_numeric(df[c])
        return df
    raw = V.load_raw(str(DATA / "pro_venues_clean_final.csv"))
    return V.clean_and_validate(raw)[0]


@st.cache_data
def with_radius(radius_km: int) -> pd.DataFrame:
    df = load_data()
    return df if radius_km == 40 else V.recluster_metros(df, radius_km)


@st.cache_data
def read_optional(name: str):
    p = DATA / name
    return pd.read_csv(p, dtype=str, keep_default_na=False) if p.exists() else None


# ------------------------------------------------------------------ sidebar
st.sidebar.title("🏟️ Filters")
radius = st.sidebar.slider("Metro-area linking radius (km)", 20, 80, 40, 5,
                           help="Venues closer than this are treated as one metro market. 40 km is the default.")
ALL = with_radius(radius)
sel_leagues = st.sidebar.multiselect("League", V.LEAGUES, default=V.LEAGUES)
sel_country = st.sidebar.multiselect("Country", ["USA", "Canada"], default=["USA", "Canada"])
pool = ALL[ALL.league.isin(sel_leagues) & ALL.country.isin(sel_country)]
sel_states = st.sidebar.multiselect("State / province", sorted(pool.state_province.unique()))
pool = pool[pool.state_province.isin(sel_states)] if sel_states else pool
sel_cities = st.sidebar.multiselect("City", sorted(pool.city.unique()))
pool = pool[pool.city.isin(sel_cities)] if sel_cities else pool
shared_only = st.sidebar.checkbox("Only venues shared by 2+ teams")
if shared_only:
    pool = pool[pool.groupby("venue_id").team.transform("count") > 1]
F = pool.reset_index(drop=True)
st.sidebar.markdown("---")
st.sidebar.markdown("".join(f"<span style='color:{LC[l]};font-size:20px'>●</span> {l} &nbsp;" for l in V.LEAGUES)
                    + f"<br><span style='color:{MULTI};font-size:20px'>●</span> Venue hosting several leagues", unsafe_allow_html=True)

st.title("Professional Sports Venue Dashboard")
st.caption("NBA · NFL · MLB · NHL — every team's home venue across the United States and Canada")
if F.empty:
    st.warning("No venues match the current filters.")
    st.stop()
VT = V.venue_table(F)
MS = V.metro_summary(F)
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Teams", len(F)); k2.metric("Venues", len(VT)); k3.metric("Metro areas", len(MS))
k4.metric("States / provinces", F.state_province.nunique()); k5.metric("Multi-team venues", int((VT.n_teams > 1).sum()))

tab_map, tab_cmp, tab_dir, tab_geo, tab_dq = st.tabs(
    ["🗺️ Venue map", "📊 League comparison", "🎨 Team directory", "🧭 Geospatial analysis", "✅ Data quality"])


def team_chip(r) -> str:
    return (f"<span style='background:{r.color_hex};color:{r.text_on_color};padding:1px 7px;border-radius:9px;"
            f"border:2px solid {r.alt_color_hex};font-size:12px;font-weight:600'>{r.abbreviation}</span>")


# ------------------------------------------------------------------ 1. map
with tab_map:
    c1, c2, c3 = st.columns([1, 1, 2])
    tiles = c1.selectbox("Basemap", ["CartoDB positron", "OpenStreetMap", "CartoDB dark_matter"])
    color_by = c2.radio("Colour markers by", ["League", "Team colour"], horizontal=True)
    c3.caption("Click a marker for the venue, city and every team that plays there. Toggle leagues in the layer control (top right).")
    m = folium.Map(location=[F.lat.mean(), F.long.mean()], zoom_start=4, tiles=tiles, control_scale=True)
    Fullscreen().add_to(m)
    groups = {k: folium.FeatureGroup(name=k) for k in V.LEAGUES + ["Multi-league venue"]}
    for _, v in VT.iterrows():
        tms = F[F.venue_id == v.venue_id]
        multi = tms.league.nunique() > 1
        lg = "Multi-league venue" if multi else tms.league.iloc[0]
        fill = (MULTI if multi else LC[lg]) if color_by == "League" else tms.color_hex.iloc[0]
        rows = "".join(f"<div style='margin-top:3px'>{team_chip(t)} {t.team} <span style='color:#777'>({t.league})</span></div>"
                       for _, t in tms.iterrows())
        html = (f"<div style='font-family:sans-serif;min-width:200px'><b style='font-size:14px'>{v.arena}</b><br>"
                f"{v.city}, {v.state_province}<br><span style='color:#777'>{v.metro}</span>{rows}</div>")
        folium.CircleMarker([v.lat, v.long], radius=6 + 2 * min(v.n_teams, 3), color=MULTI if multi else LC[lg],
                            weight=3, fill=True, fill_color=fill, fill_opacity=.9,
                            popup=folium.Popup(html, max_width=320), tooltip=f"{v.arena} — {v.leagues}").add_to(groups[lg])
    for g in groups.values():
        g.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    if len(VT) > 1:
        m.fit_bounds([[VT.lat.min(), VT.long.min()], [VT.lat.max(), VT.long.max()]], padding=(30, 30))
    st_folium(m, height=620, use_container_width=True, returned_objects=[])
    st.subheader("Venues in view")
    st.dataframe(VT[["arena", "city", "state_province", "country", "metro", "leagues", "teams", "lat", "long"]]
                 .sort_values(["state_province", "city"]), use_container_width=True, hide_index=True)

# ------------------------------------------------------------------ 2. league comparison
with tab_cmp:
    LS = V.league_centroid_stats(F)
    st.subheader("League scorecard")
    st.dataframe(LS.rename(columns={"states_provs": "states/provs", "centroid_lat": "centroid lat", "centroid_lon": "centroid lon",
                                    "mean_km_from_centroid": "mean km from centroid", "median_km_from_centroid": "median km",
                                    "east_west_span_km": "E–W span km", "north_south_span_km": "N–S span km"}).round(1),
                 use_container_width=True, hide_index=True)
    a, b = st.columns(2)
    long = LS.melt(id_vars="league", value_vars=["teams", "venues", "metros"], var_name="measure", value_name="count")
    fig = px.bar(long, x="league", y="count", color="measure", barmode="group", title="Teams, physical venues and metro markets",
                 color_discrete_sequence=["#1f4e79", "#5b9bd5", "#a5c8e4"])
    a.plotly_chart(fig, use_container_width=True)
    reg = F.groupby(["league", "region"]).size().reset_index(name="teams")
    fig = px.bar(reg, x="league", y="teams", color="region", title="Teams by region", barmode="stack",
                 color_discrete_sequence=px.colors.qualitative.Safe)
    b.plotly_chart(fig, use_container_width=True)
    a, b = st.columns(2)
    fig = px.box(F, x="league", y="lat", color="league", points="all", color_discrete_map=LC, hover_name="team",
                 title="Latitude distribution (north–south spread)")
    fig.update_layout(showlegend=False); a.plotly_chart(fig, use_container_width=True)
    fig = px.box(F, x="league", y="long", color="league", points="all", color_discrete_map=LC, hover_name="team",
                 title="Longitude distribution (east–west spread)")
    fig.update_layout(showlegend=False); b.plotly_chart(fig, use_container_width=True)
    st.subheader("Where each league plays — teams per state / province")
    piv = F.pivot_table(index="state_province", columns="league", values="team", aggfunc="count", fill_value=0)
    piv = piv.reindex(columns=[l for l in V.LEAGUES if l in piv.columns])
    piv = piv.loc[piv.sum(axis=1).sort_values(ascending=False).index]
    fig = px.imshow(piv, text_auto=True, aspect="auto", color_continuous_scale="Blues", height=max(380, 22 * len(piv)))
    st.plotly_chart(fig, use_container_width=True)
    st.subheader("Shared markets between leagues")
    mk = {l: set(F[F.league == l].metro) for l in V.LEAGUES if l in set(F.league)}
    mat = pd.DataFrame([[len(mk[x] & mk[y]) for y in mk] for x in mk], index=list(mk), columns=list(mk))
    fig = px.imshow(mat, text_auto=True, color_continuous_scale="Purples", title="Metro areas in common (diagonal = metros per league)")
    st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------ 3. team directory
with tab_dir:
    q1, q2 = st.columns([2, 1])
    query = q1.text_input("Search team, city, abbreviation or venue", "")
    sort = q2.selectbox("Sort by", ["Team", "League", "City", "Venue"])
    D = F
    if query:
        ql = query.lower()
        D = F[F[["team", "city", "abbreviation", "arena", "state_province"]].apply(lambda s: s.str.lower().str.contains(ql, regex=False)).any(axis=1)]
    D = D.sort_values({"Team": "team", "League": "league", "City": "city", "Venue": "arena"}[sort])
    st.caption(f"{len(D)} teams")
    cards = []
    for _, r in D.iterrows():
        cards.append(
            f"<div style='border:1px solid #ddd;border-radius:12px;overflow:hidden;font-family:sans-serif;background:#fff'>"
            f"<div style='background:{r.color_hex};color:{r.text_on_color};padding:10px 12px;display:flex;justify-content:space-between;align-items:center'>"
            f"<div><div style='font-size:22px;font-weight:800;letter-spacing:1px'>{r.abbreviation}</div>"
            f"<div style='font-size:12px;opacity:.9'>{r.league}</div></div>"
            f"<img src='{r.logo}' height='44' style='background:rgba(255,255,255,.85);border-radius:8px;padding:3px' onerror=\"this.style.display='none'\"></div>"
            f"<div style='height:6px;background:{r.alt_color_hex}'></div>"
            f"<div style='padding:10px 12px;color:#222'><b>{r.team}</b><br><span style='color:#555;font-size:13px'>🏟️ {r.arena}</span><br>"
            f"<span style='color:#777;font-size:12px'>{r.city}, {r.state_abbr}</span><br>"
            f"<span style='font-size:11px;font-family:monospace'>{r.color_hex} · {r.alt_color_hex}</span></div></div>")
    st.markdown("<div style='display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px'>" + "".join(cards) + "</div>",
                unsafe_allow_html=True)
    st.markdown("---")
    st.subheader("Team detail")
    if len(D):
        pick = st.selectbox("Choose a team", D.team.tolist())
        t = D[D.team == pick].iloc[0]
        co = ALL[(ALL.venue_id == t.venue_id) & (ALL.team != t.team)]
        d1, d2 = st.columns([1, 1.4])
        d1.markdown(f"### {team_chip(t)} {t.team}", unsafe_allow_html=True)
        d1.write(f"**Venue:** {t.arena}  \n**Location:** {t.city}, {t.state_province}, {t.country}  \n**Metro:** {t.metro}  \n"
                 f"**Coordinates:** {t.lat:.4f}, {t.long:.4f}  \n**Primary / alternate colour:** {t.color_hex} / {t.alt_color_hex}")
        d1.write("**Shares venue with:** " + (", ".join(co.team) if len(co) else "— (sole tenant)"))
        local = ALL[(ALL.metro == t.metro) & (ALL.team != t.team)]
        d1.write("**Other teams in this metro:** " + (", ".join(f"{x.team} ({x.league})" for _, x in local.iterrows()) or "—"))
        dd = ALL.assign(km=V.haversine_km(t.lat, t.long, ALL.lat.values, ALL.long.values))
        near = dd[(dd.team != t.team) & (dd.venue_id != t.venue_id)].nsmallest(5, "km")
        d1.write("**Five nearest other teams:**")
        d1.dataframe(near[["team", "league", "arena"]].assign(miles=(near.km * .621371).round(1)), hide_index=True, use_container_width=True)
        fig = go.Figure(go.Scattermap(lat=[t.lat], lon=[t.long], mode="markers", marker=dict(size=16, color=t.color_hex), text=[t.arena]))
        fig.update_layout(map=dict(style="carto-positron", center=dict(lat=t.lat, lon=t.long), zoom=9),
                          margin=dict(l=0, r=0, t=0, b=0), height=380)
        d2.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------ 4. geospatial
with tab_geo:
    st.subheader("Regional clusters")
    kmax = min(10, len(VT))
    k = st.slider("Number of geographic clusters", 2, kmax, min(6, kmax)) if kmax > 2 else kmax
    RC = V.regional_clusters(F, k)
    fig = px.scatter_map(RC, lat="lat", lon="long", color="cluster_name", size="n_teams", size_max=18, zoom=3, height=560,
                         hover_name="arena", hover_data={"teams": True, "metro": True, "lat": False, "long": False, "n_teams": False},
                         map_style="carto-positron")
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), legend_title_text="Cluster (named by largest metro)")
    st.plotly_chart(fig, use_container_width=True)
    cs = RC.groupby("cluster_name").agg(venues=("arena", "count"), teams=("n_teams", "sum"), states=("state_province", "nunique")).sort_values("teams", ascending=False)
    cs["share_of_teams_%"] = (cs.teams / cs.teams.sum() * 100).round(1)
    st.dataframe(cs, use_container_width=True)

    st.subheader("Metro markets and multi-league cities")
    top = MS.head(20)[["metro"] + [l for l in V.LEAGUES if l in MS.columns]].melt(id_vars="metro", var_name="league", value_name="n")
    fig = px.bar(top[top.n > 0], y="metro", x="n", labels={"n": "teams"}, color="league", orientation="h", color_discrete_map=LC,
                 title="Largest 20 metro markets by team count", height=560)
    fig.update_yaxes(categoryorder="total ascending")
    st.plotly_chart(fig, use_container_width=True)
    multi = MS[MS.leagues > 1]
    st.write(f"**{len(multi)}** of {len(MS)} metros host teams from two or more leagues; "
             f"**{int((MS.leagues == len(set(F.league))).sum())}** host every league currently selected.")
    st.dataframe(multi[["metro", "teams", "venues", "leagues", "league_list"]], use_container_width=True, hide_index=True)

    st.subheader("Distances between venues")
    names = VT.sort_values("arena").arena.tolist()
    e1, e2 = st.columns(2)
    A = e1.selectbox("From venue", names, index=0)
    B = e2.selectbox("To venue", names, index=min(1, len(names) - 1))
    va, vb = VT[VT.arena == A].iloc[0], VT[VT.arena == B].iloc[0]
    km = float(V.haversine_km(va.lat, va.long, vb.lat, vb.long))
    st.metric("Great-circle distance", f"{km * .621371:,.0f} mi  /  {km:,.0f} km")
    fig = go.Figure(go.Scattermap(lat=[va.lat, vb.lat], lon=[va.long, vb.long], mode="lines+markers+text", text=[A, B],
                                  marker=dict(size=11, color="#C9082A"), line=dict(width=3, color="#1f4e79")))
    fig.update_layout(map=dict(style="carto-positron", center=dict(lat=(va.lat + vb.lat) / 2, lon=(va.long + vb.long) / 2), zoom=3),
                      margin=dict(l=0, r=0, t=0, b=0), height=380)
    st.plotly_chart(fig, use_container_width=True)

    r1, r2 = st.columns(2)
    miles = r1.slider(f"Venues within … miles of {A}", 10, 500, 100, 10)
    dd = VT.assign(miles=V.haversine_km(va.lat, va.long, VT.lat.values, VT.long.values) * .621371)
    near = dd[(dd.miles <= miles) & (dd.arena != A)].sort_values("miles")
    r2.write(f"**{len(near)}** other venues within {miles} miles")
    st.dataframe(near[["arena", "city", "leagues", "miles"]].round(1), use_container_width=True, hide_index=True)

    st.subheader("Franchise spacing within each league")
    NN = V.nearest_neighbor_by_league(F)
    a, b = st.columns([1, 1.2])
    fig = px.box(NN, x="league", y="miles", color="league", color_discrete_map=LC, points="all", hover_name="team",
                 title="Miles to nearest other franchise (excludes co-tenants)")
    fig.update_layout(showlegend=False); a.plotly_chart(fig, use_container_width=True)
    b.dataframe(NN.sort_values("miles", ascending=False)[["league", "team", "nearest_team", "miles"]].round(0), use_container_width=True, hide_index=True, height=400)
    if len(VT) > 1:
        st.subheader("Closest venue pairs")
        pw = V.pairwise_distances(F).sort_values("km").head(15)
        st.dataframe(pw[["venue_a", "venue_b", "metro_a", "metro_b", "miles"]].round(2), use_container_width=True, hide_index=True)

# ------------------------------------------------------------------ 5. data quality
with tab_dq:
    st.subheader("Validation checks")
    vr = read_optional("validation_report.csv")
    if vr is not None:
        st.dataframe(vr, use_container_width=True, hide_index=True)
    else:
        st.info("Run `python build_data.py <csv>` to generate the validation report.")
    sc = read_optional("source_comparison.csv")
    if sc is not None:
        st.subheader("Differences between the two uploaded files")
        st.caption("The primary file (pro_venues_clean_final.csv) is used. The _2_0 file has colour codes that lost leading zeros "
                   "or became scientific notation, and the Texans' stadium under its pre-2014 name.")
        st.dataframe(sc, use_container_width=True, hide_index=True)
    st.subheader("Missing values (current data)")
    miss = ALL.replace({"": np.nan}).isna().sum().rename("missing").to_frame()
    st.dataframe(miss.T, use_container_width=True)
    st.download_button("⬇️ Download cleaned data (CSV)", ALL.to_csv(index=False).encode(), "venues_clean.csv", "text/csv")
    st.download_button("⬇️ Download current filtered view (CSV)", F.to_csv(index=False).encode(), "venues_filtered.csv", "text/csv")
