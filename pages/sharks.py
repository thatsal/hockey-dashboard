import streamlit as st
import pandas as pd
import requests
from datetime import datetime

TEAM_CODE = "SJS"
TEAM_NAME = "San Jose Sharks"
BASE_URL = "https://api-web.nhle.com/v1"


st.set_page_config(page_title="San Jose Sharks", page_icon="🦈", layout="wide")


@st.cache_data(ttl=900)
def fetch_json(url: str):
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json()


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
        opponent = away.get("placeName", {}).get("default") if is_sharks_home else home.get("placeName", {}).get("default")
        matchup = f"{away.get('abbrev')} @ {home.get('abbrev')}"
        sharks_score = home.get("score") if is_sharks_home else away.get("score")
        opp_score = away.get("score") if is_sharks_home else home.get("score")

        rows.append(
            {
                "Date": game_date,
                "Matchup": matchup,
                "Opponent": opponent,
                "Home/Away": "Home" if is_sharks_home else "Away",
                "Sharks Score": sharks_score,
                "Opponent Score": opp_score,
                "State": state,
                "Venue": venue,
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"])
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


def build_goalies_df(club_stats_json):
    goalies = club_stats_json.get("goalies", [])
    rows = []

    for g in goalies:
        first = g.get("firstName", {}).get("default", "")
        last = g.get("lastName", {}).get("default", "")
        rows.append(
            {
                "Goalie": f"{first} {last}".strip(),
                "Games": g.get("gamesPlayed"),
                "Wins": g.get("wins"),
                "Losses": g.get("losses"),
                "OTL": g.get("otLosses"),
                "Save %": g.get("savePct"),
                "GAA": g.get("goalsAgainstAverage"),
                "Shutouts": g.get("shutouts"),
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["Wins", "Save %"], ascending=False)
    return df


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
skaters_df = build_skaters_df(club_stats_json)
goalies_df = build_goalies_df(club_stats_json)

if standing:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Points", standing["Points"])
    c2.metric("Record", f'{standing["Wins"]}-{standing["Losses"]}-{standing["OTL"]}')
    c3.metric("Division Rank", standing["Division Rank"])
    c4.metric("Conference Rank", standing["Conference Rank"])
    c5.metric("League Rank", standing["League Rank"])

tab1, tab2, tab3, tab4 = st.tabs(["Schedule", "Skaters", "Goalies", "Roster"])

with tab1:
    st.subheader("Season Schedule")
    if not schedule_df.empty:
        st.dataframe(schedule_df, use_container_width=True)

        completed = schedule_df.dropna(subset=["Sharks Score", "Opponent Score"]).copy()
        if not completed.empty:
            completed["Result"] = completed.apply(
                lambda x: "Win" if x["Sharks Score"] > x["Opponent Score"] else "Loss",
                axis=1
            )
            st.subheader("Sharks Goals by Game")
            chart_df = completed.set_index("Date")[["Sharks Score", "Opponent Score"]]
            import altair as alt

            chart_data = completed.set_index("Date").reset_index()

            chart = alt.Chart(chart_data).transform_fold(
                ["Sharks Score", "Opponent Score"],
                as_=["Team", "Goals"]
            ).mark_line(point=True).encode(
                x=alt.X("Date:T", title="Date"),
                y=alt.Y("Goals:Q", title="Goals"),
                color=alt.Color(
                    "Team:N",
                    scale=alt.Scale(
                        domain=["Sharks Score", "Opponent Score"],
                        range=["#006D75", "#999999"]  # 🦈 teal + gray
                    ),
                    legend=alt.Legend(title="Team")
                )
            )

            st.line_chart  # remove this line if still there
            st.altair_chart(chart, use_container_width=True)
    else:
        st.warning("No schedule data available.")

with tab2:
    st.subheader("Skater Stats")
    if not skaters_df.empty:
        st.dataframe(skaters_df, use_container_width=True)

        import altair as alt

        st.subheader("Top 10 Scorers")

        top_df = (
            skaters_df.sort_values(["Points", "Goals"], ascending=False)
            .head(10)
        )

        chart = alt.Chart(top_df).mark_bar().encode(
            x=alt.X("Points:Q", title="Points"),
            y=alt.Y("Player:N", sort="-x", title="Player")  # 🔥 forces correct order
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

st.caption(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
