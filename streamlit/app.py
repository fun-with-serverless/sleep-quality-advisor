from datetime import date as date_cls, datetime, time, timezone, timedelta
from typing import List

import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
import pandas as pd

from src.data import (
    fetch_env_readings,
    fetch_env_readings_days,
    fetch_sleep_segments,
    fetch_sleep_summary,
)
from src.stats import (
    BucketSize,
    Percentile,
    aggregate_buckets,
    summarize_timeframe,
)


def _bucket_label(bucket: BucketSize) -> str:
    return "5 minutes" if bucket == BucketSize.FIVE_MINUTES else "1 hour"


def _percentile_label(p: Percentile) -> str:
    mapping = {
        Percentile.P50: "P50",
        Percentile.P90: "P90",
        Percentile.P99: "P99",
        Percentile.MAX: "Max",
    }
    return mapping[p]


@st.cache_data(show_spinner=False)
def _load_day(day_str: str):
    return fetch_env_readings(day_str)


@st.cache_data(show_spinner=False)
def _load_sleep_segments_cached(day_str: str):
    return fetch_sleep_segments(day_str)


@st.cache_data(show_spinner=False)
def _load_sleep_summary_cached(day_str: str):
    return fetch_sleep_summary(day_str)


def main() -> None:
    load_dotenv()
    st.set_page_config(page_title="Sleep QA - Environment Dashboard", layout="wide")
    st.title("Environment Dashboard")

    # Time window controls (local timezone)
    local_tz = datetime.now().astimezone().tzinfo
    local_now = datetime.now(tz=local_tz)
    if "window_end" not in st.session_state:
        st.session_state.window_end = local_now
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("◀ Previous 24h"):
            st.session_state.window_end = st.session_state.window_end - timedelta(hours=24)
    with col_b:
        if st.button("Now"):
            st.session_state.window_end = local_now
    with col_c:
        disable_next = (st.session_state.window_end + timedelta(hours=24)) > local_now
        if st.button("Next 24h ▶", disabled=disable_next):
            st.session_state.window_end = min(st.session_state.window_end + timedelta(hours=24), local_now)

    # Never allow moving the window past 'now'
    if st.session_state.window_end > local_now:
        st.session_state.window_end = local_now
    window_end_local = st.session_state.window_end
    window_start_local = window_end_local - timedelta(hours=24)

    bucket_choice = st.radio(
        "Bucket size",
        options=[BucketSize.FIVE_MINUTES, BucketSize.ONE_HOUR],
        format_func=_bucket_label,
        horizontal=True,
    )

    pct_options: List[Percentile] = [Percentile.P50, Percentile.P90, Percentile.P99, Percentile.MAX]
    selected_pcts = st.multiselect(
        "Percentiles to show (Average always shown)",
        options=pct_options,
        default=[Percentile.P50],
        format_func=_percentile_label,
    )

    # Determine which UTC day partitions to read
    start_utc = window_start_local.astimezone(timezone.utc)
    end_utc = window_end_local.astimezone(timezone.utc)
    day_list: List[str] = []
    cur_date = start_utc.date()
    end_date = end_utc.date()
    while True:
        day_list.append(cur_date.strftime("%Y-%m-%d"))
        if cur_date == end_date:
            break
        cur_date = (datetime.combine(cur_date, time.min, tzinfo=timezone.utc) + timedelta(days=1)).date()
    try:
        if len(day_list) == 1:
            df = _load_day(day_list[0])
        else:
            df = fetch_env_readings_days(day_list)
    except Exception as exc:  # surface helpful errors (e.g., table not found)
        st.error(str(exc))
        return

    if df is None or df.empty:
        st.info("No data for the selected window.")
        return

    # Filter DF to local-time window
    ts_local = pd.to_datetime(df["ts_min"] * 60, unit="s", utc=True).dt.tz_convert(local_tz)
    mask = (ts_local >= window_start_local) & (ts_local <= window_end_local)
    df = df.loc[mask].reset_index(drop=True)

    agg = aggregate_buckets(df, bucket_choice, local_tz)
    summary = summarize_timeframe(df)

    # X-axis as local datetimes
    x_vals = agg["bucket_time"]

    # Label above the chart to avoid legend/title overlap
    st.caption(f"Last 24 hours ending {window_end_local.strftime('%Y-%m-%d %H:%M %Z')} — {_bucket_label(bucket_choice)}")

    # Prepare figure
    fig = go.Figure()

    # Always include averages
    fig.add_trace(
        go.Scatter(
            x=x_vals,
            y=agg["temp_avg"],
            mode="lines",
            name="Temp Avg (°C)",
            line=dict(color="#d62728"),
            yaxis="y1",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x_vals,
            y=agg["humidity_avg"],
            mode="lines",
            name="Humidity Avg (%)",
            line=dict(color="#1f77b4"),
            yaxis="y2",
        )
    )

    # Add selected percentiles
    def maybe_add(col: str, name: str, color: str, axis: str) -> None:
        if col in agg.columns:
            fig.add_trace(
                go.Scatter(x=x_vals, y=agg[col], mode="lines", name=name, line=dict(dash="dot", color=color), yaxis=axis)
            )

    if Percentile.P50 in selected_pcts:
        maybe_add("temp_p50", "Temp P50 (°C)", "#ff9896", "y1")
        maybe_add("humidity_p50", "Humidity P50 (%)", "#aec7e8", "y2")
    if Percentile.P90 in selected_pcts:
        maybe_add("temp_p90", "Temp P90 (°C)", "#ff7f0e", "y1")
        maybe_add("humidity_p90", "Humidity P90 (%)", "#2ca02c", "y2")
    if Percentile.P99 in selected_pcts:
        maybe_add("temp_p99", "Temp P99 (°C)", "#9467bd", "y1")
        maybe_add("humidity_p99", "Humidity P99 (%)", "#17becf", "y2")
    if Percentile.MAX in selected_pcts:
        maybe_add("temp_max", "Temp Max (°C)", "#8c564b", "y1")
        maybe_add("humidity_max", "Humidity Max (%)", "#7f7f7f", "y2")

    # Initial ranges: 24h on x; keep y ranges reasonable
    temp_vals = df["temp_c"].dropna()
    if not temp_vals.empty:
        t_min = float(temp_vals.min())
        t_max = float(temp_vals.max())
    else:
        t_min, t_max = 0.0, 40.0
    pad = 1.0
    y1_range = [max(-10.0, t_min - pad), min(50.0, t_max + pad)]

    # Optional: overlay sleep stages as translucent bands
    show_overlay = st.checkbox("Overlay sleep stages", value=False)
    if show_overlay:
        stage_colors = {"Deep": "#1f77b4", "Light": "#ff7f0e", "REM": "#2ca02c", "Awake": "#d62728"}
        added_proxy: set[str] = set()

        def _to_local(ts_sec: int) -> datetime:
            return datetime.fromtimestamp(int(ts_sec), tz=timezone.utc).astimezone(local_tz)

        # Load segments for all UTC days in the window
        seg_frames: list[pd.DataFrame] = []
        for d in day_list:
            try:
                df_seg = _load_sleep_segments_cached(d)
                if df_seg is not None and not df_seg.empty:
                    seg_frames.append(df_seg)
            except Exception:
                pass
        seg_all = pd.concat(seg_frames, ignore_index=True) if seg_frames else None

        if seg_all is not None and not seg_all.empty:
            for _, r in seg_all.iterrows():
                stage_name = str(r.get("stage"))
                x0 = _to_local(r.get("start_ts"))
                x1 = _to_local(r.get("end_ts"))
                # Clip to window
                x0c = x0 if x0 > window_start_local else window_start_local
                x1c = x1 if x1 < window_end_local else window_end_local
                if x0c >= x1c:
                    continue
                fig.add_vrect(
                    x0=x0c,
                    x1=x1c,
                    y0=0,
                    y1=1,
                    yref="y",
                    fillcolor=stage_colors.get(stage_name, "#cccccc"),
                    opacity=0.15,
                    line_width=0,
                    layer="below",
                )
                if stage_name not in added_proxy:
                    fig.add_trace(
                        go.Scatter(
                            x=[None],
                            y=[None],
                            mode="lines",
                            line=dict(color=stage_colors.get(stage_name, "#cccccc"), width=10),
                            name=stage_name,
                            showlegend=True,
                        )
                    )
                    added_proxy.add(stage_name)

        # Bedtime/risetime markers if available in summaries for days in range
        for d in day_list:
            try:
                ssum = _load_sleep_summary_cached(d)
            except Exception:
                ssum = None
            if not ssum:
                continue
            bt = ssum.get("bedtime")
            rt = ssum.get("risetime")
            if isinstance(bt, int):
                fig.add_vline(x=_to_local(bt), line_dash="dash", line_color="#999", opacity=0.6)
            if isinstance(rt, int):
                fig.add_vline(x=_to_local(rt), line_dash="dash", line_color="#999", opacity=0.6)

    fig.update_layout(
        xaxis=dict(title="Time", range=[window_start_local, window_end_local], rangeslider=dict(visible=False), fixedrange=True),
        yaxis=dict(title="Temperature (°C)", side="left", range=y1_range, fixedrange=True),
        yaxis2=dict(title="Humidity (%)", side="right", overlaying="y", range=[0, 100], fixedrange=True),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=40, r=40, t=30, b=60),
        height=500,
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "scrollZoom": False,
            "displaylogo": False,
            "modeBarButtonsToRemove": [
                "zoom2d",
                "zoomIn2d",
                "zoomOut2d",
                "select2d",
                "lasso2d",
                "pan2d",
            ],
        },
    )

    # Summary panel
    st.subheader("Summary (selected timeframe)")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Temp Min (°C)", f"{summary['temperature']['min']:.2f}" if summary["temperature"]["min"] is not None else "—")
    c2.metric("Temp Max (°C)", f"{summary['temperature']['max']:.2f}" if summary["temperature"]["max"] is not None else "—")
    c3.metric("Temp Std (°C)", f"{summary['temperature']['std']:.2f}" if summary["temperature"]["std"] is not None else "—")
    c4.metric("Hum Min (%)", f"{summary['humidity']['min']:.2f}" if summary["humidity"]["min"] is not None else "—")
    c5.metric("Hum Max (%)", f"{summary['humidity']['max']:.2f}" if summary["humidity"]["max"] is not None else "—")
    c6.metric("Hum Std (%)", f"{summary['humidity']['std']:.2f}" if summary["humidity"]["std"] is not None else "—")

    # Sleep session section
    st.header("Sleep Session")
    default_sleep_date = (local_now - timedelta(days=1)).date()
    sleep_date = st.date_input("Sleep date", value=default_sleep_date, format="YYYY-MM-DD")
    sleep_date_str = sleep_date.strftime("%Y-%m-%d") if hasattr(sleep_date, "strftime") else str(sleep_date)

    try:
        seg_df = _load_sleep_segments_cached(sleep_date_str)
        summary_row = _load_sleep_summary_cached(sleep_date_str)
    except Exception as exc:
        st.error(str(exc))
        return

    if (seg_df is None or seg_df.empty) and not summary_row:
        st.info("No sleep data for the selected date.")
        return

    # KPIs (with fallback when summary is missing)
    k1, k2, k3, k4, k5 = st.columns(5)
    if summary_row:
        score_val = summary_row.get("score")
        eff_val = summary_row.get("efficiency")
        total_min = summary_row.get("total_min") or 0
        bedtime = summary_row.get("bedtime")
        risetime = summary_row.get("risetime")
        total_hours = (total_min or 0) / 60.0
        k1.metric("Sleep Score", f"{score_val}" if score_val is not None else "—")
        k2.metric("Efficiency", f"{eff_val:.0%}" if isinstance(eff_val, float) else "—")
        k3.metric("Total (h)", f"{total_hours:.2f}")
        if isinstance(bedtime, int):
            k4.metric("Bedtime", datetime.fromtimestamp(bedtime, tz=timezone.utc).astimezone(local_tz).strftime("%H:%M"))
        else:
            k4.metric("Bedtime", "—")
        if isinstance(risetime, int):
            k5.metric("Risetime", datetime.fromtimestamp(risetime, tz=timezone.utc).astimezone(local_tz).strftime("%H:%M"))
        else:
            k5.metric("Risetime", "—")

        # Stage composition donut
        st.subheader("Stage Composition")
        stage_labels = ["Deep", "Light", "REM", "Awake"]
        rem_min = summary_row.get("rem_min") or 0
        deep_min = summary_row.get("deep_min") or 0
        light_min = summary_row.get("light_min") or 0
        total_min = summary_row.get("total_min") or 0
        asleep_min = rem_min + deep_min + light_min
        awake_min = max(total_min - asleep_min, 0)
        pie_fig = go.Figure(
            data=[
                go.Pie(
                    labels=stage_labels,
                    values=[deep_min, light_min, rem_min, awake_min],
                    hole=0.4,
                    sort=False,
                )
            ]
        )
        pie_fig.update_layout(margin=dict(l=20, r=20, t=0, b=0), height=300)
        st.plotly_chart(pie_fig, use_container_width=True, config={"scrollZoom": False, "displaylogo": False})
    else:
        # Derive minimal KPIs from segments if summary is unavailable
        if seg_df is not None and not seg_df.empty:
            total_seconds_asleep = int(seg_df.loc[seg_df["stage"].isin(["Deep", "Light", "REM"]), "duration_s"].sum())
            total_hours = total_seconds_asleep / 3600.0
            st_min = int(seg_df["start_ts"].min())
            en_max = int(seg_df["end_ts"].max())
            k1.metric("Sleep Score", "—")
            k2.metric("Efficiency", "—")
            k3.metric("Total (h)", f"{total_hours:.2f}")
            k4.metric("Bedtime", datetime.fromtimestamp(st_min, tz=timezone.utc).astimezone(local_tz).strftime("%H:%M"))
            k5.metric("Risetime", datetime.fromtimestamp(en_max, tz=timezone.utc).astimezone(local_tz).strftime("%H:%M"))

            st.subheader("Stage Composition")
            stage_labels = ["Deep", "Light", "REM", "Awake"]
            deep_s = int(seg_df.loc[seg_df["stage"] == "Deep", "duration_s"].sum())
            light_s = int(seg_df.loc[seg_df["stage"] == "Light", "duration_s"].sum())
            rem_s = int(seg_df.loc[seg_df["stage"] == "REM", "duration_s"].sum())
            total_s = int(seg_df["duration_s"].sum())
            awake_s = max(total_s - (deep_s + light_s + rem_s), 0)
            pie_fig = go.Figure(
                data=[
                    go.Pie(
                        labels=stage_labels,
                        values=[deep_s / 60.0, light_s / 60.0, rem_s / 60.0, awake_s / 60.0],
                        hole=0.4,
                        sort=False,
                    )
                ]
            )
            pie_fig.update_layout(margin=dict(l=20, r=20, t=0, b=0), height=300)
            st.plotly_chart(pie_fig, use_container_width=True, config={"scrollZoom": False, "displaylogo": False})

    # Hypnogram
    if seg_df is not None and not seg_df.empty:
        st.subheader("Hypnogram")
        # Stage ordering and colors
        stage_order = {"Deep": 0, "Light": 1, "REM": 2, "Awake": 3}
        stage_colors = {"Deep": "#1f77b4", "Light": "#ff7f0e", "REM": "#2ca02c", "Awake": "#d62728"}

        def _to_local(ts: int) -> datetime:
            return datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone(local_tz)

        hyp_fig = go.Figure()
        x_min = None
        x_max = None
        for stage_name, idx in stage_order.items():
            times: list[datetime | None] = []
            vals: list[int | None] = []
            for _, row in seg_df.iterrows():
                if row.get("stage") != stage_name:
                    continue
                s = _to_local(row.get("start_ts"))
                e = _to_local(row.get("end_ts"))
                x_min = s if x_min is None or s < x_min else x_min
                x_max = e if x_max is None or e > x_max else x_max
                times.extend([s, e, None])
                vals.extend([idx, idx, None])
            if times:
                hyp_fig.add_trace(
                    go.Scatter(
                        x=times,
                        y=vals,
                        mode="lines",
                        name=stage_name,
                        line=dict(color=stage_colors[stage_name], width=8),
                        line_shape="hv",
                        hoverinfo="x+name",
                    )
                )

        # Set x-range to sleep window if available, else from segments
        if summary_row and isinstance(summary_row.get("bedtime"), int) and isinstance(summary_row.get("risetime"), int):
            x0 = _to_local(summary_row.get("bedtime"))
            x1 = _to_local(summary_row.get("risetime"))
        else:
            x0 = x_min or window_start_local
            x1 = x_max or window_end_local

        hyp_fig.update_layout(
            xaxis=dict(title="Time", range=[x0, x1], fixedrange=True),
            yaxis=dict(
                title="Stage",
                tickmode="array",
                tickvals=[0, 1, 2, 3],
                ticktext=["Deep", "Light", "REM", "Awake"],
                autorange="reversed",
                fixedrange=True,
            ),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            margin=dict(l=40, r=40, t=30, b=60),
            height=300,
        )
        st.plotly_chart(
            hyp_fig,
            use_container_width=True,
            config={
                "scrollZoom": False,
                "displaylogo": False,
                "modeBarButtonsToRemove": [
                    "zoom2d",
                    "zoomIn2d",
                    "zoomOut2d",
                    "select2d",
                    "lasso2d",
                    "pan2d",
                ],
            },
        )


if __name__ == "__main__":
    main()


