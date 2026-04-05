import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import altair as alt

TEAM_CODE = "SJS"
TEAM_NAME = "San Jose Sharks"
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
        if value <= 1:
            return round(value, 3)
        return round(value, 1)
    except Exception:
        return value


def build_roster_df(roster_json):
    rows = []

    for section, players in roster_json.items():
        if isinstance(players, list):
            for p in players:
                first = p.get("firstName", {}).get("default", "")
                last = p.get("lastName", {}).get("default", "")
                rows.append(
                    {
                        "Player": f"{first} {last}".strip(),
                        "Position": p.get("positionCode"),
                        "Number": p.get("sweaterNumber"),
                        "Shoots/Catches": p.get("shootsCatches"),
                        "Height (in)": p.get("heightInInches"),
                        "Weight": p.get("weightInPounds"),
                        "Birth City": p.get("birthCity", {}).get("default"),
                        "Birth Country": p.get("birthCountry"),
                    }
                )

    df = pd.DataFrame(rows)
    if not df.empty and "Number" in df.columns:
        df = df.sort_values(by=["Position", "Number"], na_position="last")
    return df


def build_schedule_df(schedule_json):
    games = schedule_json.get("games", [])
    rows = []

    for g in games:
        away = g.get("awayTeam", {})
        home = g.get("homeTeam", {})
        venue = g.get("venue", {}).get("default")
        game_date = g.get("gameDate")
        state = g.get("gameState")

        is_sharks_home = home.get("abbrev") == TEAM_CODE
        opponent = (
            away.get("placeName", {}).get("default")
            if is_sharks_home
            else home.get("placeName", {}).get("default")
        )
        matchup = f"{away.get('abbrev')} @ {home.get('abbrev')}"
        goals_for = home.get("score") if is_sharks_home else away.get("score")
        goals_against = away.get("score") if is_sharks_home else home.get("score")

        result = None
        if goals_for is not None and goals_against is not None:
            if goals_for > goals_against:
                result = "Win"
            elif goals_for < goals_against:
                result = "Loss"
            else:
                result = "Tie"

        rows.append(
            {
                "Date": pd.to_datetime(game_date),
                "Matchup": matchup,
                "Opponent": opponent,
                "Home/Away": "Home" if is_sharks_home else "Away",
                "Goals For": goals_for,
                "Goals Against": goals_against,
                "Result": result,
                "State": state,
                "Venue": venue,
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Date")
    return df


def extract_sharks_standing(standings_json):
    standings = standings_json.get("standings", [])
    for team in standings:
        if team.get("teamAbbrev", {}).get("default") == TEAM_CODE:
            return {
                "Points": team.get("points"),
                "Wins": team.get("wins"),
                "Losses": team.get("losses"),
                "OTL": team.get("otLosses"),
                "Games Played": team.get("gamesPlayed"),
                "Goal Diff": team.get("goalDifferential"),
                "Division Rank": team.get("divisionSequence"),
                "Conference Rank": team.get("conferenceSequence"),
                "League Rank": team.get("leagueSequence"),
            }
    return None


def build_team_summary_from_schedule(schedule_df):
    completed = schedule_df.dropna(subset=["Goals For", "Goals Against"]).copy()

    if completed.empty:
        return {
            "Goals For": None,
            "Goals Against": None,
            "Goal Diff": None,
            "Goals/Game": None,
        }

    goals_for = int(completed["Goals For"].sum())
    goals_against = int(completed["Goals Against"].sum())
    games_played = len(completed)
    goals_per_game = round(goals_for / games_played, 2) if games_played else None

    return {
        "Goals For": goals_for,
        "Goals Against": goals_against,
        "Goal Diff": goals_for - goals_against,
        "Goals/Game": goals_per_game,
    }


def build_skaters_df(club_stats_json):
    skaters = club_stats_json.get("skaters", [])
    rows = []

    for p in skaters:
        first = p.get("firstName", {}).get("default", "")
        last = p.get("lastName", {}).get("default", "")
        goals = p.get("goals", 0)
        assists = p.get("assists", 0)

        rows.append(
            {
                "Player": f"{first} {last}".strip(),
                "Player ID": first_present(p, "playerId", "id"),
                "Games": p.get("gamesPlayed"),
                "Goals": goals,
                "Assists": assists,
                "Points": goals + assists,
                "Plus/Minus": p.get("plusMinus"),
                "PIM": p.get("pim"),
                "Shots": p.get("shots"),
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["Points", "Goals"], ascending=False)
    return df


def build_goalies_df(club_stats_json, roster_json):
    roster_goalies = []
    for p in roster_json.get("goalies", []):
        first = p.get("firstName", {}).get("default", "")
        last = p.get("lastName", {}).get("default", "")
        roster_goalies.append(
            {
                "Goalie": f"{first} {last}".strip(),
                "Number": p.get("sweaterNumber"),
                "Catches": p.get("shootsCatches"),
            }
        )

    roster_df = pd.DataFrame(roster_goalies)

    stat_rows = []
    for g in club_stats_json.get("goalies", []):
        first = g.get("firstName", {}).get("default", "")
        last = g.get("lastName", {}).get("default", "")

        otl = first_present(
            g,
            "otLosses",
            "overtimeLosses",
            "otl",
            "lossesOt",
            "lossesInOt",
        )

        save_pct = format_pct(
            first_present(
                g,
                "savePct",
                "savePctg",
                "savePercentage",
                "svPct",
                "svPercentage",
            )
        )

        stat_rows.append(
            {
                "Goalie": f"{first} {last}".strip(),
                "Games": first_present(g, "gamesPlayed", "gp"),
                "Wins": first_present(g, "wins", "w"),
                "Losses": first_present(g, "losses", "l"),
                "OTL": otl,
                "Save %": save_pct,
                "GAA": first_present(g, "goalsAgainstAverage", "gaa"),
                "Shutouts": first_present(g, "shutouts", "so"),
                "Shots Against": first_present(g, "shotsAgainst", "sa"),
                "Saves": first_present(g, "saves", "sv"),
            }
        )

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

        display_cols = [
            "Goalie", "Number", "Catches", "Games", "Wins", "Losses", "OTL",
            "Save %", "GAA", "Shutouts", "Shots Against", "Saves"
        ]
        df = df[[c for c in display_cols if c in df.columns]]
    return df


def extract_regular_season_ids(landing_json):
    season_ids = set()

    if not landing_json:
        return []

    for key in ["seasonTotals", "careerTotals", "regularSeasonStats"]:
        value = landing_json.get(key)
        if isinstance(value, list):
            for row in value:
                game_type = first_present(row, "gameTypeId", "gameType")
                season_id = first_present(row, "season", "seasonId")
                if season_id is not None and (game_type in [None, 2, "2", "R"]):
                    season_ids.add(int(season_id))

    featured = landing_json.get("featuredStats", {})
    if isinstance(featured, dict):
        for subkey in ["regularSeason", "career"]:
            block = featured.get(subkey)
            if isinstance(block, dict):
                season_id = first_present(block, "season", "seasonId")
                if season_id is not None:
                    season_ids.add(int(season_id))
                for nested_key in ["subSeason", "career", "regularSeason"]:
                    nested = block.get(nested_key)
                    if isinstance(nested, dict):
                        season_id = first_present(nested, "season", "seasonId")
                        if season_id is not None:
                            season_ids.add(int(season_id))

    return sorted(season_ids)


def parse_game_log_rows(game_log_json):
    if game_log_json is None:
        return []

    if isinstance(game_log_json, list):
        raw_rows = game_log_json
    else:
        raw_rows = first_present(game_log_json, "gameLog", "games", "playerGameLog")
        if raw_rows is None and isinstance(game_log_json, dict):
            raw_rows = []

    rows = []
    for row in raw_rows or []:
        game_date = first_present(row, "gameDate", "date")
        rows.append(
            {
                "Date": pd.to_datetime(game_date) if game_date else pd.NaT,
                "Goals": first_present(row, "goals", "g", "playerGoals"),
                "Assists": first_present(row, "assists", "a", "playerAssists"),
                "Points": first_present(row, "points", "pts"),
                "Shots": first_present(row, "shots", "sog", "shotsOnGoal"),
                "PIM": first_present(row, "pim", "penaltyMinutes"),
            }
        )
    return rows


def build_first_x_games_stats(player_id, x_games):
    landing = get_player_landing(player_id)
    season_ids = extract_regular_season_ids(landing)

    all_rows = []
    for season_id in season_ids:
        log_json = get_player_game_log(player_id, season_id, 2)
        all_rows.extend(parse_game_log_rows(log_json))

    if not all_rows:
        return None

    df = pd.DataFrame(all_rows)
    if df.empty:
        return None

    df = df.sort_values("Date", na_position="last").head(int(x_games))

    return {
        "Games": int(len(df)),
        "Goals": int(pd.to_numeric(df["Goals"], errors="coerce").fillna(0).sum()),
        "Assists": int(pd.to_numeric(df["Assists"], errors="coerce").fillna(0).sum()),
        "Points": int(pd.to_numeric(df["Points"], errors="coerce").fillna(0).sum()),
        "Shots": int(pd.to_numeric(df["Shots"], errors="coerce").fillna(0).sum()),
        "PIM": int(pd.to_numeric(df["PIM"], errors="coerce").fillna(0).sum()),
        "Window Label": f"First {int(len(df))} NHL games",
        "Games Available": int(len(df)),
    }


def get_current_player_options(skaters_df):
    if skaters_df.empty:
        return {}
    temp = skaters_df.dropna(subset=["Player ID"]).copy()
    return dict(zip(temp["Player"], temp["Player ID"]))


def build_compare_chart(left_name, right_name, left_stats, right_stats):
    rows = []
    for stat in ["Games", "Goals", "Assists", "Points", "Shots", "PIM"]:
        left_val = left_stats.get(stat)
        right_val = right_stats.get(stat)
        if left_val is not None:
            rows.append({"Player": left_name, "Stat": stat, "Value": left_val})
        if right_val is not None:
            rows.append({"Player": right_name, "Stat": stat, "Value": right_val})

    if not rows:
        return None

    chart_df = pd.DataFrame(rows)
    return alt.Chart(chart_df).mark_bar().encode(
        x=alt.X("Stat:N", title="Stat"),
        y=alt.Y("Value:Q", title="Value"),
        color=alt.Color("Player:N", title="Player"),
        xOffset="Player:N",
        tooltip=["Player", "Stat", "Value"],
    )


def render_stat_card(title, stats):
    st.markdown(f"### {title}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Games", stats.get("Games"))
    c2.metric("Goals", stats.get("Goals"))
    c3.metric("Assists", stats.get("Assists"))
    c4, c5, c6 = st.columns(3)
    c4.metric("Points", stats.get("Points"))
    c5.metric("Shots", stats.get("Shots"))
    c6.metric("PIM", stats.get("PIM"))


col1, col2 = st.columns([1, 6])

with col1:
    st.image("https://assets.nhle.com/logos/nhl/svg/SJS_light.svg", width=100)

with col2:
    st.markdown(
        "<h1 style='margin-bottom: 0;'>San Jose Sharks Dashboard</h1>",
        unsafe_allow_html=True
    )

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
    c2.metric("Record", f'{standing["Wins"]}-{standing["Losses"]}-{standing["OTL"]}')
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
        upcoming = schedule_df[schedule_df["Goals For"].isna()].copy()
        upcoming = upcoming.sort_values("Date").head(6)

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

            goals_for_line = alt.Chart(completed).mark_line(
                color="#006D75",
                strokeWidth=3
            ).encode(
                x=alt.X("Date:T", title="Date"),
                y=alt.Y("Goals For:Q", title="Goals"),
            )

            goals_against_line = alt.Chart(completed).mark_line(
                color="#D1D5DB",
                strokeWidth=2
            ).encode(
                x=alt.X("Date:T"),
                y=alt.Y("Goals Against:Q"),
            )

            result_points = alt.Chart(completed).mark_circle(size=95).encode(
                x=alt.X("Date:T"),
                y=alt.Y("Goals For:Q"),
                color=alt.Color(
                    "Result:N",
                    scale=alt.Scale(
                        domain=["Win", "Loss", "Tie"],
                        range=["#22C55E", "#EF4444", "#F59E0B"]
                    ),
                    legend=alt.Legend(title="Result"),
                ),
                tooltip=[
                    alt.Tooltip("Date:T", title="Date"),
                    alt.Tooltip("Opponent:N", title="Opponent"),
                    alt.Tooltip("Goals For:Q", title="Goals For"),
                    alt.Tooltip("Goals Against:Q", title="Goals Against"),
                    alt.Tooltip("Result:N", title="Result"),
                ],
            )

            st.altair_chart(goals_for_line + goals_against_line + result_points, use_container_width=True)
            st.caption("Line colors: teal = Goals For, light gray = Goals Against. Dot colors show Win / Loss / Tie.")
    else:
        st.warning("No schedule data available.")

with tab2:
    st.subheader("Skater Stats")
    if not skaters_df.empty:
        display_skaters = skaters_df.drop(columns=["Player ID"], errors="ignore")
        st.dataframe(display_skaters, use_container_width=True)

        st.subheader("Top 10 Scorers")

        top_df = (
            skaters_df.sort_values(["Points", "Goals"], ascending=False)
            .head(10)
        )

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
    st.subheader("Current Shark vs Sharks Legend")
    st.caption("Comparison mode: first X NHL games vs first X NHL games. X is set to the current Shark's games played.")

    if not current_player_options:
        st.warning("No current skater options available for comparison.")
    else:
        left_col, right_col = st.columns(2)
        with left_col:
            current_name = st.selectbox("Current Shark", list(current_player_options.keys()), index=0)
        with right_col:
            legacy_name = st.selectbox("Sharks Legend", list(LEGACY_PLAYERS.keys()), index=0)

        current_stats_row = skaters_df.loc[skaters_df["Player"] == current_name].iloc[0].to_dict()
        x_games = int(current_stats_row.get("Games") or 0)

        if x_games <= 0:
            st.warning("Selected current player does not have a valid games played value.")
        else:
            current_player_id = int(current_player_options[current_name])
            legacy_player_id = int(LEGACY_PLAYERS[legacy_name])

            current_first_x = build_first_x_games_stats(current_player_id, x_games)
            legacy_first_x = build_first_x_games_stats(legacy_player_id, x_games)

            if current_first_x is None or legacy_first_x is None:
                st.warning("Could not load enough game log data for one of the selected players.")
            else:
                st.markdown(f"#### Comparison Window: First {x_games} NHL Games")

                compare_left, compare_right = st.columns(2)
                with compare_left:
                    render_stat_card(f"{current_name} — First {current_first_x['Games']} NHL Games", current_first_x)
                with compare_right:
                    render_stat_card(f"{legacy_name} — First {legacy_first_x['Games']} NHL Games", legacy_first_x)

                chart = build_compare_chart(
                    f"{current_name}",
                    f"{legacy_name}",
                    current_first_x,
                    legacy_first_x
                )
                if chart is not None:
                    st.subheader("Side-by-Side Comparison")
                    st.altair_chart(chart, use_container_width=True)

                if current_first_x["Games"] != legacy_first_x["Games"]:
                    st.info(
                        f"Requested first {x_games} NHL games, but one player only returned "
                        f"{min(current_first_x['Games'], legacy_first_x['Games'])} games from the endpoint."
                    )
