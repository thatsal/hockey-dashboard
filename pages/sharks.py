import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import altair as alt

TEAM_CODE = "SJS"
BASE_URL = "https://api-web.nhle.com/v1"
FULL_SCHEDULE_URL = "https://www.nhl.com/sharks/schedule"

LEGACY_PLAYERS = {
    "Patrick Marleau": 8466139,
    "Joe Thornton": 8466138,
    "Joe Pavelski": 8470794,
    "Logan Couture": 8471709,
}

st.set_page_config(page_title="San Jose Sharks", page_icon="🦈", layout="wide")


@st.cache_data(ttl=900)
def fetch_json(url: str):
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=900)
def fetch_json_safe(url: str):
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


@st.cache_data(ttl=3600)
def get_roster():
    return fetch_json(f"{BASE_URL}/roster/{TEAM_CODE}/current")


@st.cache_data(ttl=900)
def get_schedule_now():
    return fetch_json(f"{BASE_URL}/club-schedule-season/{TEAM_CODE}/now")


@st.cache_data(ttl=900)
def get_standings():
    return fetch_json(f"{BASE_URL}/standings/now")


@st.cache_data(ttl=900)
def get_club_stats():
    return fetch_json(f"{BASE_URL}/club-stats/{TEAM_CODE}/now")


@st.cache_data(ttl=3600)
def get_player_landing(player_id: int):
    return fetch_json_safe(f"{BASE_URL}/player/{player_id}/landing")


@st.cache_data(ttl=3600)
def get_player_game_log(player_id: int, season_id: int, game_type: int = 2):
    return fetch_json_safe(f"{BASE_URL}/player/{player_id}/game-log/{season_id}/{game_type}")


def first_present(d, *keys):
    for key in keys:
        if isinstance(d, dict) and key in d and d.get(key) is not None:
            return d.get(key)
    return None


def format_pct(value):
    if value is None or value == "":
        return None
    try:
        value = float(value)
        return round(value, 3) if value <= 1 else round(value, 1)
    except Exception:
        return value


def season_label(season_id):
    if season_id is None:
        return "Unknown"
    try:
        season_id = str(int(float(season_id)))
    except Exception:
        season_id = str(season_id).strip()
    if len(season_id) == 8 and season_id.isdigit():
        return f"{season_id[:4]}-{season_id[4:6]}"
    return season_id or "Unknown"


def build_roster_df(roster_json):
    rows = []
    for section, players in roster_json.items():
        if isinstance(players, list):
            for p in players:
                rows.append({
                    "Player": f"{p.get('firstName', {}).get('default', '')} {p.get('lastName', {}).get('default', '')}".strip(),
                    "Position": p.get("positionCode"),
                    "Number": p.get("sweaterNumber"),
                    "Shoots/Catches": p.get("shootsCatches"),
                    "Height (in)": p.get("heightInInches"),
                    "Weight": p.get("weightInPounds"),
                    "Birth City": p.get("birthCity", {}).get("default"),
                    "Birth Country": p.get("birthCountry"),
                })
    df = pd.DataFrame(rows)
    if not df.empty and "Number" in df.columns:
        df = df.sort_values(by=["Position", "Number"], na_position="last")
    return df


def build_schedule_df(schedule_json):
    rows = []
    for g in schedule_json.get("games", []):
        away = g.get("awayTeam", {})
        home = g.get("homeTeam", {})
        is_sharks_home = home.get("abbrev") == TEAM_CODE
        goals_for = home.get("score") if is_sharks_home else away.get("score")
        goals_against = away.get("score") if is_sharks_home else home.get("score")
        result = None
        if goals_for is not None and goals_against is not None:
            result = "Win" if goals_for > goals_against else ("Loss" if goals_for < goals_against else "Tie")
        rows.append({
            "Date": pd.to_datetime(g.get("gameDate")),
            "Matchup": f"{away.get('abbrev')} @ {home.get('abbrev')}",
            "Opponent": away.get("placeName", {}).get("default") if is_sharks_home else home.get("placeName", {}).get("default"),
            "Home/Away": "Home" if is_sharks_home else "Away",
            "Goals For": goals_for,
            "Goals Against": goals_against,
            "Result": result,
            "Venue": g.get("venue", {}).get("default"),
        })
    df = pd.DataFrame(rows)
    return df.sort_values("Date") if not df.empty else df


def extract_sharks_standing(standings_json):
    for team in standings_json.get("standings", []):
        if team.get("teamAbbrev", {}).get("default") == TEAM_CODE:
            return {
                "Points": team.get("points"),
                "Wins": team.get("wins"),
                "Losses": team.get("losses"),
                "OTL": team.get("otLosses"),
                "Division Rank": team.get("divisionSequence"),
                "Conference Rank": team.get("conferenceSequence"),
                "League Rank": team.get("leagueSequence"),
            }
    return None


def build_team_summary_from_schedule(schedule_df):
    completed = schedule_df.dropna(subset=["Goals For", "Goals Against"]).copy()
    if completed.empty:
        return {"Goals For": None, "Goals Against": None, "Goal Diff": None, "Goals/Game": None}
    gf = int(completed["Goals For"].sum())
    ga = int(completed["Goals Against"].sum())
    gp = len(completed)
    return {
        "Goals For": gf,
        "Goals Against": ga,
        "Goal Diff": gf - ga,
        "Goals/Game": round(gf / gp, 2) if gp else None,
    }


def build_skaters_df(club_stats_json):
    rows = []
    for p in club_stats_json.get("skaters", []):
        goals = p.get("goals", 0)
        assists = p.get("assists", 0)
        games = p.get("gamesPlayed", 0)
        points = goals + assists
        rows.append({
            "Player": f"{p.get('firstName', {}).get('default', '')} {p.get('lastName', {}).get('default', '')}".strip(),
            "Player ID": first_present(p, "playerId", "id"),
            "Games": games,
            "Goals": goals,
            "Assists": assists,
            "Points": points,
            "PPG": round(points / games, 2) if games else None,
            "Plus/Minus": p.get("plusMinus"),
            "PIM": p.get("pim"),
            "Shots": p.get("shots"),
        })
    df = pd.DataFrame(rows)
    return df.sort_values(["Points", "Goals"], ascending=False) if not df.empty else df


def build_goalies_df(club_stats_json, roster_json):
    roster_goalies = []
    for p in roster_json.get("goalies", []):
        roster_goalies.append({
            "Goalie": f"{p.get('firstName', {}).get('default', '')} {p.get('lastName', {}).get('default', '')}".strip(),
            "Number": p.get("sweaterNumber"),
            "Catches": p.get("shootsCatches"),
        })

    stat_rows = []
    for g in club_stats_json.get("goalies", []):
        stat_rows.append({
            "Goalie": f"{g.get('firstName', {}).get('default', '')} {g.get('lastName', {}).get('default', '')}".strip(),
            "Games": first_present(g, "gamesPlayed", "gp"),
            "Wins": first_present(g, "wins", "w"),
            "Losses": first_present(g, "losses", "l"),
            "OTL": first_present(g, "otLosses", "overtimeLosses", "otl", "lossesOt", "lossesInOt"),
            "Save %": format_pct(first_present(g, "savePct", "savePctg", "savePercentage", "svPct", "svPercentage")),
            "GAA": first_present(g, "goalsAgainstAverage", "gaa"),
            "Shutouts": first_present(g, "shutouts", "so"),
            "Shots Against": first_present(g, "shotsAgainst", "sa"),
            "Saves": first_present(g, "saves", "sv"),
        })

    roster_df = pd.DataFrame(roster_goalies)
    stats_df = pd.DataFrame(stat_rows)

    if not roster_df.empty and not stats_df.empty:
        df = roster_df.merge(stats_df, on="Goalie", how="outer")
    elif not roster_df.empty:
        df = roster_df.copy()
    else:
        df = stats_df.copy()

    if not df.empty:
        if "OTL" in df.columns:
            df["OTL"] = df["OTL"].fillna(0)
        if "Goalie" in df.columns:
            df = df.drop_duplicates(subset=["Goalie"], keep="first")
        if "Wins" in df.columns:
            df = df.sort_values(["Wins", "Games", "Save %"], ascending=False, na_position="last")
        cols = ["Goalie", "Number", "Catches", "Games", "Wins", "Losses", "OTL", "Save %", "GAA", "Shutouts", "Shots Against", "Saves"]
        df = df[[c for c in cols if c in df.columns]]
    return df


def get_current_player_options(skaters_df):
    if skaters_df.empty:
        return {}
    temp = skaters_df.dropna(subset=["Player ID"]).copy()
    return dict(zip(temp["Player"], temp["Player ID"]))


def parse_game_log_rows(game_log_json):
    if not game_log_json:
        return []
    raw_rows = first_present(game_log_json, "gameLog", "games", "playerGameLog")
    if raw_rows is None and isinstance(game_log_json, list):
        raw_rows = game_log_json
    if raw_rows is None:
        raw_rows = []

    rows = []
    for row in raw_rows:
        game_type = first_present(row, "gameTypeId", "gameType")
        if game_type not in [2, "2"]:
            continue
        rows.append({
            "Date": pd.to_datetime(first_present(row, "gameDate", "date"), errors="coerce"),
            "Goals": pd.to_numeric(first_present(row, "goals", "g", "playerGoals"), errors="coerce"),
            "Assists": pd.to_numeric(first_present(row, "assists", "a", "playerAssists"), errors="coerce"),
            "Points": pd.to_numeric(first_present(row, "points", "pts"), errors="coerce"),
            "Shots": pd.to_numeric(first_present(row, "shots", "sog", "shotsOnGoal"), errors="coerce"),
            "PIM": pd.to_numeric(first_present(row, "pim", "penaltyMinutes"), errors="coerce"),
        })
    return rows


def season_ids_from_landing(landing_json):
    ids = []
    for row in landing_json.get("seasonTotals", []) if landing_json else []:
        if not isinstance(row, dict):
            continue
        game_type = first_present(row, "gameTypeId", "gameType")
        if game_type not in [2, "2"]:
            continue
        season_id = first_present(row, "season", "seasonId")
        if season_id is not None:
            ids.append(int(season_id))
    return sorted(set(ids))


def progression_from_landing_totals(landing_json):
    season_rows = []
    for row in landing_json.get("seasonTotals", []) if landing_json else []:
        if not isinstance(row, dict):
            continue

        game_type = first_present(row, "gameTypeId", "gameType")
        if game_type not in [2, "2"]:
            continue

        league_abbrev = first_present(row, "leagueAbbrev", "league")
        if league_abbrev not in [None, "NHL"]:
            continue

        season_id = first_present(row, "season", "seasonId")
        if season_id is None:
            continue

        games = pd.to_numeric(first_present(row, "gamesPlayed", "games", "gp"), errors="coerce")
        goals = pd.to_numeric(first_present(row, "goals", "g"), errors="coerce")
        assists = pd.to_numeric(first_present(row, "assists", "a"), errors="coerce")
        points = pd.to_numeric(first_present(row, "points", "pts"), errors="coerce")
        shots = pd.to_numeric(first_present(row, "shots", "sog", "shotsOnGoal"), errors="coerce")
        pim = pd.to_numeric(first_present(row, "pim", "penaltyMinutes"), errors="coerce")

        if pd.isna(games) and pd.isna(points) and pd.isna(goals) and pd.isna(assists):
            continue

        games = int(0 if pd.isna(games) else games)
        goals = int(0 if pd.isna(goals) else goals)
        assists = int(0 if pd.isna(assists) else assists)
        points = int(goals + assists if pd.isna(points) else points)
        shots = int(0 if pd.isna(shots) else shots)
        pim = int(0 if pd.isna(pim) else pim)

        season_rows.append({
            "Season ID": int(season_id),
            "Season": season_label(season_id),
            "Games": games,
            "Goals": goals,
            "Assists": assists,
            "Points": points,
            "PPG": round(points / games, 2) if games else None,
            "Shots": shots,
            "PIM": pim,
        })

    if not season_rows:
        return pd.DataFrame()

    df = pd.DataFrame(season_rows).drop_duplicates(subset=["Season ID"])
    df = df.sort_values("Season ID").reset_index(drop=True)
    df["Career Year"] = range(1, len(df) + 1)
    return df


def progression_from_game_logs(player_id: int):
    landing = get_player_landing(player_id)

    if not landing:
        return pd.DataFrame()

    season_ids = season_ids_from_landing(landing)
    if not season_ids:
        return progression_from_landing_totals(landing)

    season_rows = []

    for season_id in season_ids:
        log_json = get_player_game_log(player_id, season_id, 2)
        if not log_json:
            continue

        rows = parse_game_log_rows(log_json)
        if not rows:
            continue

        df = pd.DataFrame(rows)
        games = int(len(df))
        goals = int(df["Goals"].fillna(0).sum())
        assists = int(df["Assists"].fillna(0).sum())
        points = int(df["Points"].fillna(0).sum())
        shots = int(df["Shots"].fillna(0).sum()) if "Shots" in df.columns else 0
        pim = int(df["PIM"].fillna(0).sum()) if "PIM" in df.columns else 0

        season_rows.append({
            "Season ID": season_id,
            "Season": season_label(season_id),
            "Games": games,
            "Goals": goals,
            "Assists": assists,
            "Points": points,
            "PPG": round(points / games, 2) if games else None,
            "Shots": shots,
            "PIM": pim,
        })

    if not season_rows:
        return progression_from_landing_totals(landing)

    df = pd.DataFrame(season_rows).drop_duplicates(subset=["Season ID"])
    df = df.sort_values("Season ID").reset_index(drop=True)
    df["Career Year"] = range(1, len(df) + 1)
    return df


def fallback_career_from_landing(player_id: int):
    landing = get_player_landing(player_id)
    if not landing:
        return None

    career_totals = landing.get("careerTotals") or {}
    regular = career_totals.get("regularSeason") or career_totals
    if not isinstance(regular, dict) or not regular:
        return None

    games = first_present(regular, "gamesPlayed", "games")
    goals = first_present(regular, "goals", "g")
    assists = first_present(regular, "assists", "a")
    points = first_present(regular, "points", "pts")
    shots = first_present(regular, "shots", "sog", "shotsOnGoal")
    pim = first_present(regular, "pim", "penaltyMinutes")

    if games is None and points is None:
        return None

    try:
        games_num = int(pd.to_numeric(games, errors="coerce")) if games is not None else 0
    except Exception:
        games_num = 0

    try:
        points_num = int(pd.to_numeric(points, errors="coerce")) if points is not None else 0
    except Exception:
        points_num = 0

    return {
        "Games": games_num if games is not None else None,
        "Goals": int(pd.to_numeric(goals, errors="coerce")) if goals is not None and pd.notna(pd.to_numeric(goals, errors="coerce")) else None,
        "Assists": int(pd.to_numeric(assists, errors="coerce")) if assists is not None and pd.notna(pd.to_numeric(assists, errors="coerce")) else None,
        "Points": points_num if points is not None else None,
        "Shots": int(pd.to_numeric(shots, errors="coerce")) if shots is not None and pd.notna(pd.to_numeric(shots, errors="coerce")) else None,
        "PIM": int(pd.to_numeric(pim, errors="coerce")) if pim is not None and pd.notna(pd.to_numeric(pim, errors="coerce")) else None,
        "PPG": round(points_num / games_num, 2) if games_num else None,
    }


def career_totals_from_progression(progress_df):
    if progress_df.empty:
        return None
    totals = {
        "Games": int(progress_df["Games"].fillna(0).sum()),
        "Goals": int(progress_df["Goals"].fillna(0).sum()),
        "Assists": int(progress_df["Assists"].fillna(0).sum()),
        "Points": int(progress_df["Points"].fillna(0).sum()),
        "Shots": int(progress_df["Shots"].fillna(0).sum()) if "Shots" in progress_df.columns else None,
        "PIM": int(progress_df["PIM"].fillna(0).sum()) if "PIM" in progress_df.columns else None,
    }
    totals["PPG"] = round(totals["Points"] / totals["Games"], 2) if totals["Games"] else None
    return totals


def build_progression_chart(current_df, legacy_df, current_name, legacy_name):
    plot_parts = []
    if not current_df.empty:
        left = current_df[["Career Year", "Points"]].copy()
        left["Player"] = current_name
        plot_parts.append(left)
    if not legacy_df.empty:
        right = legacy_df[["Career Year", "Points"]].copy()
        right["Player"] = legacy_name
        plot_parts.append(right)

    if not plot_parts:
        return None

    plot_df = pd.concat(plot_parts, ignore_index=True)
    return alt.Chart(plot_df).mark_line(point=True).encode(
        x=alt.X("Career Year:Q", title="Career Year"),
        y=alt.Y("Points:Q", title="Points"),
        color=alt.Color("Player:N", title="Player"),
        tooltip=["Player", "Career Year", "Points"],
    )


def render_stat_card(title, subtitle, stats):
    st.markdown(f"### {title}")
    st.caption(subtitle)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Games", stats.get("Games"))
    c2.metric("Goals", stats.get("Goals"))
    c3.metric("Assists", stats.get("Assists"))
    c4.metric("Points", stats.get("Points"))
    c5, c6, c7 = st.columns(3)
    c5.metric("PPG", stats.get("PPG"))
    c6.metric("Shots", stats.get("Shots"))
    c7.metric("PIM", stats.get("PIM"))


col1, col2 = st.columns([1, 6])
with col1:
    st.image("https://assets.nhle.com/logos/nhl/svg/SJS_light.svg", width=100)
with col2:
    st.markdown("<h1 style='margin-bottom: 0;'>San Jose Sharks Dashboard</h1>", unsafe_allow_html=True)

with st.spinner("Loading Sharks data..."):
    roster_json = get_roster()
    schedule_json = get_schedule_now()
    standings_json = get_standings()
    club_stats_json = get_club_stats()

roster_df = build_roster_df(roster_json)
schedule_df = build_schedule_df(schedule_json)
standing = extract_sharks_standing(standings_json)
team_summary = build_team_summary_from_schedule(schedule_df)
skaters_df = build_skaters_df(club_stats_json)
goalies_df = build_goalies_df(club_stats_json, roster_json)
current_player_options = get_current_player_options(skaters_df)

if standing:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Points", standing["Points"])
    c2.metric("Record", f"{standing['Wins']}-{standing['Losses']}-{standing['OTL']}")
    c3.metric("Division Rank", standing["Division Rank"])
    c4.metric("Conference Rank", standing["Conference Rank"])
    c5.metric("League Rank", standing["League Rank"])

c6, c7, c8, c9 = st.columns(4)
c6.metric("Goals For", team_summary["Goals For"])
c7.metric("Goals Against", team_summary["Goals Against"])
c8.metric("Goal Diff", team_summary["Goal Diff"])
c9.metric("Goals/Game", team_summary["Goals/Game"])

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Schedule", "Skaters", "Goalies", "Roster", "Compare"])

with tab1:
    st.subheader("Upcoming Games")
    if not schedule_df.empty:
        upcoming = schedule_df[schedule_df["Goals For"].isna()].copy().sort_values("Date").head(6)
        if not upcoming.empty:
            display_upcoming = upcoming[["Date", "Matchup", "Opponent", "Home/Away", "Venue"]].copy()
            display_upcoming["Date"] = display_upcoming["Date"].dt.strftime("%Y-%m-%d")
            st.dataframe(display_upcoming, use_container_width=True)
        else:
            st.info("No upcoming games found.")

        st.markdown(f"👉 [View Full Schedule]({FULL_SCHEDULE_URL})")

        completed = schedule_df.dropna(subset=["Goals For", "Goals Against"]).copy()
        if not completed.empty:
            st.subheader("Goals For vs Goals Against")
            gf = alt.Chart(completed).mark_line(color="#006D75", strokeWidth=3).encode(
                x=alt.X("Date:T", title="Date"),
                y=alt.Y("Goals For:Q", title="Goals")
            )
            ga = alt.Chart(completed).mark_line(color="#D1D5DB", strokeWidth=2).encode(
                x=alt.X("Date:T"),
                y=alt.Y("Goals Against:Q")
            )
            pts = alt.Chart(completed).mark_circle(size=95).encode(
                x=alt.X("Date:T"),
                y=alt.Y("Goals For:Q"),
                color=alt.Color(
                    "Result:N",
                    scale=alt.Scale(domain=["Win", "Loss", "Tie"], range=["#22C55E", "#EF4444", "#F59E0B"]),
                    legend=alt.Legend(title="Result")
                ),
                tooltip=[
                    alt.Tooltip("Date:T", title="Date"),
                    alt.Tooltip("Opponent:N", title="Opponent"),
                    alt.Tooltip("Goals For:Q", title="Goals For"),
                    alt.Tooltip("Goals Against:Q", title="Goals Against"),
                    alt.Tooltip("Result:N", title="Result"),
                ],
            )
            st.altair_chart(gf + ga + pts, use_container_width=True)
            st.caption("Line colors: teal = Goals For, light gray = Goals Against. Dot colors show Win / Loss / Tie.")
    else:
        st.warning("No schedule data available.")

with tab2:
    st.subheader("Skater Stats")
    if not skaters_df.empty:
        st.dataframe(skaters_df.drop(columns=["Player ID"], errors="ignore"), use_container_width=True)
        st.subheader("Top 10 Scorers")
        top_df = skaters_df.sort_values(["Points", "Goals"], ascending=False).head(10)
        chart = alt.Chart(top_df).mark_bar().encode(
            x=alt.X("Points:Q", title="Points"),
            y=alt.Y("Player:N", sort="-x", title="Player")
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.warning("No skater stats available.")

with tab3:
    st.subheader("Goalie Stats")
    if not goalies_df.empty:
        st.dataframe(goalies_df, use_container_width=True)
    else:
        st.warning("No goalie stats available.")

with tab4:
    st.subheader("Roster")
    if not roster_df.empty:
        st.dataframe(roster_df, use_container_width=True)
    else:
        st.warning("No roster data available.")

with tab5:
    st.subheader("Career Card + Year-by-Year Comparison")
    st.caption("Top cards show NHL regular-season career totals only. Compare data is rebuilt from season game logs.")

    if not current_player_options:
        st.warning("No current skater options available for comparison.")
    else:
        left_col, right_col = st.columns(2)
        with left_col:
            current_name = st.selectbox("Current Shark", list(current_player_options.keys()), index=0)
        with right_col:
            legacy_name = st.selectbox("Legend", list(LEGACY_PLAYERS.keys()), index=0)

        current_player_id = int(current_player_options[current_name])
        legacy_player_id = int(LEGACY_PLAYERS[legacy_name])

        current_progression = progression_from_game_logs(current_player_id)
        legacy_progression = progression_from_game_logs(legacy_player_id)

        current_career = career_totals_from_progression(current_progression)
        legacy_career = career_totals_from_progression(legacy_progression)

        current_progression_ok = not current_progression.empty
        legacy_progression_ok = not legacy_progression.empty

        if current_career is None:
            current_career = fallback_career_from_landing(current_player_id)
        if legacy_career is None:
            legacy_career = fallback_career_from_landing(legacy_player_id)

        if current_career is None:
            st.warning(f"Could not load NHL regular-season data for {current_name}.")
        if legacy_career is None:
            st.warning(f"Could not load NHL regular-season data for {legacy_name}.")

        if current_career is not None or legacy_career is not None:
            a, b = st.columns(2)
            with a:
                if current_career is not None:
                    render_stat_card(current_name, "NHL regular-season career totals so far", current_career)
                else:
                    st.info(f"No career totals available for {current_name}.")
            with b:
                if legacy_career is not None:
                    render_stat_card(legacy_name, "NHL regular-season full career totals", legacy_career)
                else:
                    st.info(f"No career totals available for {legacy_name}.")

        chart = build_progression_chart(current_progression, legacy_progression, current_name, legacy_name)
        if chart is not None:
            st.subheader("Year-by-Year Points by Career Year")
            st.altair_chart(chart, use_container_width=True)

            display_frames = []
            if current_progression_ok:
                current_display = current_progression[["Career Year", "Season", "Games", "Goals", "Assists", "Points", "PPG"]].copy()
                current_display["Player"] = current_name
                display_frames.append(current_display)
            if legacy_progression_ok:
                legacy_display = legacy_progression[["Career Year", "Season", "Games", "Goals", "Assists", "Points", "PPG"]].copy()
                legacy_display["Player"] = legacy_name
                display_frames.append(legacy_display)

            if display_frames:
                combined = pd.concat(display_frames, ignore_index=True)
                combined = combined[["Player", "Career Year", "Season", "Games", "Goals", "Assists", "Points", "PPG"]]
                st.subheader("Season-by-Season Breakdown")
                st.dataframe(combined, use_container_width=True)

            if not (current_progression_ok and legacy_progression_ok):
                st.info("One player is using fallback season totals, so the chart may be missing some game-log detail. The graph still shows whatever valid year-by-year data was returned.")
        else:
            st.info("No season-by-season NHL regular-season data was returned for either player.")

        with st.expander("Compare debug (optional)"):
            st.write("Current progression rows:", current_progression)
            st.write("Legacy progression rows:", legacy_progression)
            st.write("Current progression source:", "game logs / season totals" if current_progression_ok else "career totals fallback only")
            st.write("Legacy progression source:", "game logs / season totals" if legacy_progression_ok else "career totals fallback only")
            st.write("Current career totals:", current_career)
            st.write("Legacy career totals:", legacy_career)

st.caption(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
