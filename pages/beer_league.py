import streamlit as st
import pandas as pd

st.title("🍺 Beer League")

data = {
    "Player": ["Alex", "Chris", "Jordan"],
    "Goals": [10, 7, 5],
    "Assists": [8, 6, 9]
}

df = pd.DataFrame(data)
df["Points"] = df["Goals"] + df["Assists"]

st.dataframe(df)

st.bar_chart(df.set_index("Player")["Points"])
