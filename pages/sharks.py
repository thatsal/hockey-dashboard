import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import altair as alt

TEAM_CODE = "SJS"
BASE_URL = "https://api-web.nhle.com/v1"

st.set_page_config(page_title="San Jose Sharks", page_icon="🦈", layout="wide")

@st.cache_data(ttl=900)
def fetch_json(url: str):
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=900)
def get_schedule_now():
    return fetch_json(f"{BASE_URL}/club-schedule-season/{TEAM_CODE}/now")

@st.cache_data(ttl=900)
def get_standings():
    return fetch_json(f"{BASE_URL}/standings/now")

@st.cache_data(ttl=900)
def get_club_stats():
    return fetch_json(f"{BASE_URL}/club-stats/{TEAM_CODE}/now")

def build_schedule_df(schedule_json):
    games = schedule_json.get("games", [])
    rows = []

    for g in games:
        away = g.get("awayTeam", {})
        home = g.get("homeTeam", {})
        venue = g.get("venue", {}).get("default")
        game_date = g.get("gameDate")

        is_sharks_home = home.get("abbrev") == TEAM_CODE
        opponent = away.get("placeName", {}).get("default") if is_sharks_home else home.get("placeName", {}).get("default")

        sharks_score = home.get("score") if is_sharks_home else away.get("score")
        opp_score = away.get("score") if is_sharks_home else home.get("score")

        result = None
        if sharks_score is not None and opp_score is not None:
            result = "Win" if sharks_score > opp_score else "Loss"

        rows.append(
            {
                "Date": pd.to_datetime(game_date),
                "Matchup": f"{away.get('abbrev')} @ {home.get('abbrev')}",
                "Opponent": opponent,
                "Home/Away": "Home" if is_sharks_home else "Away",
                "Sharks Score": sharks_score,
                "Opponent Score": opp_score,
                "Result": result,
                "Venue": venue,
            }
        )

    df = pd.DataFrame(rows)
    return df.sort_values("Date") if not df.empty else df

def extract_standing(data):
    for team in data.get("standings", []):
        if team.get("teamAbbrev", {}).get("default") == TEAM_CODE:
            return team
    return None

# Header
col1, col2 = st.columns([1, 6])
with col1:
    st.image("https://assets.nhle.com/logos/nhl/svg/SJS_light.svg", width=100)
with col2:
    st.markdown("<h1>San Jose Sharks Dashboard</h1>", unsafe_allow_html=True)

# Load data
schedule_df = build_schedule_df(get_schedule_now())
standing = extract_standing(get_standings())
club_stats = get_club_stats()

# Top metrics
if standing:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Points", standing.get("points"))
    c2.metric("Record", f"{standing.get('wins')}-{standing.get('losses')}-{standing.get('otLosses')}")
    c3.metric("Division Rank", standing.get("divisionSequence"))
    c4.metric("Conference Rank", standing.get("conferenceSequence"))
    c5.metric("League Rank", standing.get("leagueSequence"))

# Second row stats
team = club_stats.get("team", {})
c6, c7, c8, c9 = st.columns(4)
c6.metric("Goals For", team.get("goalsFor"))
c7.metric("Goals Against", team.get("goalsAgainst"))
c8.metric("Goal Diff", team.get("goalDifferential"))
c9.metric("Shots/Game", team.get("shotsPerGame"))

# Tabs
tab1 = st.tabs(["Schedule"])[0]

with tab1:
    st.subheader("Upcoming Games")

    upcoming = schedule_df[schedule_df["Sharks Score"].isna()].copy()
    upcoming = upcoming.sort_values("Date").head(6)

    if not upcoming.empty:
        st.dataframe(upcoming, use_container_width=True)

    st.markdown("👉 [View Full Schedule](https://www.nhl.com/sharks/schedule)")

    completed = schedule_df.dropna(subset=["Sharks Score", "Opponent Score"])

    if not completed.empty:
        st.subheader("Sharks Goals by Game")

        # Lines
        base = alt.Chart(completed).transform_fold(
            ["Sharks Score", "Opponent Score"],
            as_=["Team", "Goals"]
        ).mark_line().encode(
            x="Date:T",
            y="Goals:Q",
            color=alt.Color(
                "Team:N",
                scale=alt.Scale(
                    domain=["Sharks Score", "Opponent Score"],
                    range=["#006D75", "#999999"]
                )
            )
        )

        # Points colored by win/loss (Sharks only)
        points = alt.Chart(completed).mark_circle(size=80).encode(
            x="Date:T",
            y="Sharks Score:Q",
            color=alt.Color(
                "Result:N",
                scale=alt.Scale(
                    domain=["Win", "Loss"],
                    range=["#00FF7F", "#FF4C4C"]
                )
            ),
            tooltip=["Date:T", "Opponent:N", "Sharks Score", "Opponent Score", "Result"]
        )

        st.altair_chart(base + points, use_container_width=True)

st.caption(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.image("https://assets.nhle.com/logos/nhl/svg/SJS_light.svg", width=100)
with col2:
    st.markdown("<h1>San Jose Sharks Dashboard</h1>", unsafe_allow_html=True)

# Load data
schedule_df = build_schedule_df(get_schedule_now())
standing = extract_standing(get_standings())
club_stats = get_club_stats()

# Top metrics
if standing:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Points", standing.get("points"))
    c2.metric("Record", f"{standing.get('wins')}-{standing.get('losses')}-{standing.get('otLosses')}")
    c3.metric("Division Rank", standing.get("divisionSequence"))
    c4.metric("Conference Rank", standing.get("conferenceSequence"))
    c5.metric("League Rank", standing.get("leagueSequence"))

# Second row stats
team = club_stats.get("team", {})
c6, c7, c8, c9 = st.columns(4)
c6.metric("Goals For", team.get("goalsFor"))
c7.metric("Goals Against", team.get("goalsAgainst"))
c8.metric("Goal Diff", team.get("goalDifferential"))
c9.metric("Shots/Game", team.get("shotsPerGame"))

# Tabs
tab1 = st.tabs(["Schedule"])[0]

with tab1:
    st.subheader("Upcoming Games")

    upcoming = schedule_df[schedule_df["Sharks Score"].isna()].copy()
    upcoming = upcoming.sort_values("Date").head(6)

    if not upcoming.empty:
        st.dataframe(upcoming, use_container_width=True)

    st.markdown("👉 [View Full Schedule](https://www.nhl.com/sharks/schedule)")

    completed = schedule_df.dropna(subset=["Sharks Score", "Opponent Score"])

    if not completed.empty:
        chart = alt.Chart(completed).transform_fold(
            ["Sharks Score", "Opponent Score"],
            as_=["Team", "Goals"]
        ).mark_line(point=True).encode(
            x="Date:T",
            y="Goals:Q",
            color=alt.Color(
                "Team:N",
                scale=alt.Scale(
                    domain=["Sharks Score", "Opponent Score"],
                    range=["#006D75", "#999999"]
                )
            )
        )
        st.subheader("Sharks Goals by Game")
        st.altair_chart(chart, use_container_width=True)

st.caption(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
