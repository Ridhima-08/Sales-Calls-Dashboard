import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(page_title="Call Log Dashboard", layout="wide")

st.title("📞 Call Log Dashboard")

# ==============================
# Utility functions
# ==============================
def to_seconds(x):
    try:
        h, m, s = map(int, str(x).split(":"))
        return h*3600 + m*60 + s
    except:
        return None

def load_excel(file):
    """Read all sheets from Excel and merge into one dataframe"""
    xls = pd.ExcelFile(file)
    all_data = []

    for sheet in xls.sheet_names:
        df = pd.read_excel(file, sheet_name=sheet, header=1)
        df = df.dropna(how="all")

        # Rename columns consistently
        df = df.rename(columns={
            "Call Type": "direction",
            "Call Start": "start",
            "Call End": "end",
            "Total Call Time (H:m:s)": "duration_str",
            "Assigned User": "assigned_to"
        })

        if "start" in df.columns:
            df["date"] = pd.to_datetime(df["start"], errors="coerce").dt.date
        else:
            df["date"] = sheet

        all_data.append(df)

    final_df = pd.concat(all_data, ignore_index=True)
    final_df["duration_sec"] = final_df["duration_str"].astype(str).apply(to_seconds)
    final_df["start"] = pd.to_datetime(final_df["start"], errors="coerce")
    final_df["end"] = pd.to_datetime(final_df["end"], errors="coerce")

    return final_df

# ==============================
# Upload section
# ==============================
uploaded_file = st.file_uploader("Upload Excel file with call logs", type=["xlsx"])

if uploaded_file:
    df = load_excel(uploaded_file)

    st.success(f"✅ Loaded {len(df)} records from {df['date'].min()} to {df['date'].max()}")

    # Sidebar filters
    st.sidebar.header("Filters")
    assigned_options = df["assigned_to"].dropna().unique().tolist()
    assigned_filter = st.sidebar.multiselect("Assigned User(s)", assigned_options, default=assigned_options)

    direction_options = df["direction"].dropna().unique().tolist()
    direction_filter = st.sidebar.multiselect("Direction(s)", direction_options, default=direction_options)

    # Apply filters
    filtered_df = df[
        (df["assigned_to"].isin(assigned_filter)) &
        (df["direction"].isin(direction_filter))
    ]

    # ==============================
    # KPIs
    # ==============================
    total_calls = len(filtered_df)
    total_duration = filtered_df["duration_sec"].sum() / 60
    avg_duration = filtered_df["duration_sec"].mean() / 60 if total_calls > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("📞 Total Calls", total_calls)
    col2.metric("⏱️ Total Talk Time (min)", f"{total_duration:.1f}")
    col3.metric("⚖️ Avg Duration (min)", f"{avg_duration:.1f}")

    # ==============================
    # Charts
    # ==============================
    st.subheader("📊 Calls per Day")
    calls_per_day = filtered_df.groupby("date").size().reset_index(name="count")
    fig = px.bar(calls_per_day, x="date", y="count", title="Calls per Day")
    st.plotly_chart(fig, use_container_width=True)

    # ------------------------------
    # Updated Calls by Hour (30-min slots, 9:30–6:30)
    st.subheader("📈 Calls by Hour")

    # Copy original filtered_df
    df_hour = filtered_df.copy()
    df_hour["hour_slot"] = df_hour["start"].dt.floor("30min").dt.strftime("%I:%M %p")

    # Restrict to business hours
    valid_hours = pd.date_range("09:30", "18:30", freq="30min").strftime("%I:%M %p").tolist()
    df_hour = df_hour[df_hour["hour_slot"].isin(valid_hours)]

    calls_by_hour = df_hour.groupby("hour_slot").size().reset_index(name="count")
    calls_by_hour["hour_slot"] = pd.Categorical(calls_by_hour["hour_slot"], categories=valid_hours, ordered=True)

    fig2 = px.bar(
        calls_by_hour,
        x="hour_slot",
        y="count",
        title="Calls by Hour (Mon–Sat, 9:30 AM–6:30 PM)"
    )
    st.plotly_chart(fig2, use_container_width=True)


    # ==============================
    # Extra Visuals
    # ==============================

    # Incoming vs Outgoing Pie
    st.subheader("📞 Incoming vs Outgoing Split")
    pie_data = filtered_df["direction"].value_counts().reset_index()
    pie_data.columns = ["Direction", "Count"]
    fig4 = px.pie(pie_data, names="Direction", values="Count", title="Incoming vs Outgoing")
    st.plotly_chart(fig4, use_container_width=True)

    # ------------------------------
    # Updated Heatmap (Day × Hour slots, Mon–Sat, 9:30–6:30)
    st.subheader("🔥 Heatmap: Day of Week × Hour")

    # Copy original filtered_df
    df_heat = filtered_df.copy()
    df_heat["dayofweek"] = df_heat["start"].dt.day_name()
    df_heat["hour_slot"] = df_heat["start"].dt.floor("30min").dt.strftime("%I:%M %p")

    # Restrict to Mon–Sat + business hours
    valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    valid_hours = pd.date_range("09:30", "18:30", freq="30min").strftime("%I:%M %p").tolist()
    df_heat = df_heat[df_heat["dayofweek"].isin(valid_days)]
    df_heat = df_heat[df_heat["hour_slot"].isin(valid_hours)]

    heatmap_data = df_heat.groupby(["dayofweek", "hour_slot"]).size().reset_index(name="count")
    heatmap_data["dayofweek"] = pd.Categorical(heatmap_data["dayofweek"], categories=valid_days, ordered=True)

    fig5 = px.density_heatmap(
        heatmap_data,
        x="hour_slot",
        y="dayofweek",
        z="count",
        color_continuous_scale="Viridis",
        title="Calls Heatmap (Mon–Sat, 9:30 AM–6:30 PM)"
    )
    st.plotly_chart(fig5, use_container_width=True)


    # ------------------------------
    # Top 5 Longest Calls
    st.subheader("🏆 Top 5 Longest Calls")
    top_longest = filtered_df.sort_values(by="duration_sec", ascending=False).head(5)
    top_longest_display = top_longest[["assigned_to", "date", "duration_str", "direction"]]
    st.table(top_longest_display)

    # ==============================
    # Data Table + Download
    # ==============================
    st.subheader("📋 Filtered Records")
    st.dataframe(filtered_df)

    csv = filtered_df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download Filtered Data", csv, "filtered_calls.csv", "text/csv")

else:
    st.info("📂 Please upload an Excel file to see the dashboard.")
