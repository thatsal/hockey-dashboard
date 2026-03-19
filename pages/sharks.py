import streamlit as st
import pandas as pd

st.title("🦈 San Jose Sharks")

data = {
    "Player": ["Player A", "Player B", "Player C"],
    "Goals": [20, 15, 10],
    "Assists": [25, 18, 12]
}

df = pd.DataFrame(data)
df["Points"] = df["Goals"] + df["Assists"]

st.dataframe(df)

st.bar_chart(df.set_index("Player")["Points"])
