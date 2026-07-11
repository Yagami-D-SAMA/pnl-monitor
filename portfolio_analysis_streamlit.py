from __future__ import annotations

import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime
from io import BytesIO, StringIO
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
TARGET_SCRIPT = PROJECT_ROOT / "portfolio_analysis.py"
TRADE_DISPLAY_COLUMNS = [
    "TextDate",
    "Time",
    "Activity",
    "Market",
    "Direction",
    "Quantity",
    "Price",
    "Currency",
    "Consideration",
    "Commission",
    "Charges",
    "Cost/Proceeds",
    "Conversion rate",
    "Order type",
    "Venue ID",
    "Settlement date",
    "Order ID",
    "AssetType",
    "Region",
    "Strategy",
]


def run_portfolio_analysis() -> tuple[int, str]:
    """
    Run portfolio_analysis.py and return (exit_code, combined_output).
    This is kept as a fallback if you want to compare with the command-line script.
    """
    process = subprocess.run(
        [sys.executable, str(TARGET_SCRIPT)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    combined = (process.stdout or "") + ("\n" if process.stdout and process.stderr else "") + (process.stderr or "")
    return process.returncode, combined


def get_expected_pnl_file(data_source: str, target_date: object) -> Path:
    source_map = {
        "ALL": "SXAFI_SX9Q9",
        "SXAFI": "SXAFI",
        "SX9Q9": "SX9Q9",
    }
    source_prefix = source_map[data_source]
    date_tag = target_date.strftime("%Y%m%d")
    return PROJECT_ROOT / "investment" / "Daily Pnl" / f"daily_pnl_{source_prefix}_{date_tag}.pkl"


def run_portfolio_analysis_in_process(
    target_date: object,
    data_source: str = "ALL",
    asset_type: bool = True,
    save_results: bool = False,
) -> tuple[int, str, object | None]:
    """
    Run analyze_portfolio() inside Streamlit and capture everything printed by
    generate_report(), plus the surrounding analyzer output.
    """
    buffer = StringIO()
    try:
        from utils.analyzer import analyze_portfolio

        with redirect_stdout(buffer), redirect_stderr(buffer):
            result = analyze_portfolio(
                target_date.strftime("%Y-%m-%d"),
                data_source=data_source,
                asset_type=asset_type,
                prompt_for_constituents=False,
                save_results=save_results,
            )
        return 0, buffer.getvalue(), result
    except Exception as exc:
        print(f"Streamlit wrapper error: {exc}", file=buffer)
        return 1, buffer.getvalue(), None


def save_pending_daily_pnl(pending_result: object, overwrite_existing: bool) -> tuple[int, str]:
    buffer = StringIO()
    try:
        with redirect_stdout(buffer), redirect_stderr(buffer):
            pending_result["data_loader"].save_results(
                pending_result["daily_pnl_result"],
                pending_result["trade_history_paths"],
                overwrite_existing=overwrite_existing,
            )
        return 0, buffer.getvalue()
    except Exception as exc:
        print(f"Streamlit save error: {exc}", file=buffer)
        return 1, buffer.getvalue()


def build_position_options(pending_result: object) -> list[str]:
    daily_pnl_result = pending_result.get("daily_pnl_result") or {}
    market_details = daily_pnl_result.get("market_details") or []
    return [row["market"] for row in market_details if row.get("market")]


def get_position_trade_history(pending_result: object, market: str):
    trades_df = pending_result.get("trades_df")
    if trades_df is None or trades_df.empty:
        return None

    position_trades = trades_df[trades_df["Market"] == market].copy()
    if position_trades.empty:
        return position_trades

    position_trades = position_trades.sort_values(["TextDate", "Time"], ascending=[False, False])
    display_columns = [column for column in TRADE_DISPLAY_COLUMNS if column in position_trades.columns]
    position_trades = position_trades[display_columns]
    if "TextDate" in position_trades.columns:
        position_trades["TextDate"] = position_trades["TextDate"].dt.strftime("%Y-%m-%d")
    return position_trades


def run_followup_step(
    step_name: str,
    target_date: object,
    data_source: str,
    lookback_period: int,
    cumulative_start_date: object,
    cumulative_end_date: object,
) -> tuple[int, str, list[bytes]]:
    buffer = StringIO()
    images: list[bytes] = []
    try:
        import matplotlib.pyplot as plt

        from utils.analyzer import (
            analyze_portfolio_industry_percentiles,
            calculate_cumulative_contribution,
            display_index_top_constituents_performance,
            display_upcoming_dividends,
            portfolio_drawdown_monitor,
        )

        target_date_str = target_date.strftime("%Y-%m-%d")
        with redirect_stdout(buffer), redirect_stderr(buffer):
            if step_name == "prompt_for_constituents":
                display_index_top_constituents_performance(top_n=10)
            elif step_name == "run_portfolio_drawdown_monitor":
                portfolio_drawdown_monitor(
                    running_date=target_date_str,
                    lookback_period=lookback_period,
                    data_source=data_source,
                )
            elif step_name == "run_dividend_display":
                display_upcoming_dividends(
                    running_date=target_date_str,
                    data_source=data_source,
                )
            elif step_name == "analyze_portfolio_industry_percentiles":
                analyze_portfolio_industry_percentiles(
                    target_date=target_date_str,
                    data_source=data_source,
                )
            elif step_name == "calculate_cumulative_contribution":
                calculate_cumulative_contribution(
                    cumulative_start_date.strftime("%Y-%m-%d"),
                    cumulative_end_date.strftime("%Y-%m-%d"),
                    data_source=data_source,
                )
            else:
                raise ValueError(f"Unknown follow-up step: {step_name}")

        for figure_number in plt.get_fignums():
            figure = plt.figure(figure_number)
            image_buffer = BytesIO()
            figure.savefig(image_buffer, format="png", bbox_inches="tight")
            image_buffer.seek(0)
            images.append(image_buffer.getvalue())
        plt.close("all")
        return 0, buffer.getvalue(), images
    except Exception as exc:
        print(f"Streamlit follow-up error: {exc}", file=buffer)
        return 1, buffer.getvalue(), images


def parse_target_date(raw_value: str) -> date | None:
    raw_value = raw_value.strip()
    if not raw_value:
        return datetime.today().date()
    try:
        return datetime.strptime(raw_value, "%Y-%m-%d").date()
    except ValueError:
        return None


def main() -> None:
    st.set_page_config(page_title="Portfolio Analysis UI", layout="wide")
    st.title("Portfolio Analysis UI")
    st.caption("Capture and display the report text printed by generate_report().")

    if not TARGET_SCRIPT.exists():
        st.error(f"Target script not found: {TARGET_SCRIPT}")
        return

    st.markdown("### Run Controls")
    left_col, right_col = st.columns([2, 1])
    with left_col:
        data_source = st.selectbox("Data source", ["ALL", "SXAFI", "SX9Q9"], index=0)
    with right_col:
        asset_type = st.checkbox("Show asset type table", value=True)
    target_date_input = st.text_input(
        "Target date override",
        value=datetime.today().strftime("%Y-%m-%d"),
        help="Use YYYY-MM-DD, for example 2026-07-10.",
    )
    target_date = parse_target_date(target_date_input)
    if target_date is None:
        st.error("Invalid target date. Please use YYYY-MM-DD, for example 2026-07-10.")
        return

    run_clicked = st.button("Generate Portfolio Report", type="primary", use_container_width=True)

    if "last_output" not in st.session_state:
        st.session_state.last_output = ""
        st.session_state.last_code = None
        st.session_state.last_run_at = None
    if "pending_result" not in st.session_state:
        st.session_state.pending_result = None
    if "pending_pnl_file" not in st.session_state:
        st.session_state.pending_pnl_file = None
    if "latest_analysis_result" not in st.session_state:
        st.session_state.latest_analysis_result = None
    if "followup_output" not in st.session_state:
        st.session_state.followup_output = ""
    if "followup_images" not in st.session_state:
        st.session_state.followup_images = []
    if "last_run_target_date" not in st.session_state:
        st.session_state.last_run_target_date = None
    if "last_run_data_source" not in st.session_state:
        st.session_state.last_run_data_source = None

    if run_clicked:
        with st.spinner("Generating portfolio report..."):
            code, output, pending_result = run_portfolio_analysis_in_process(
                target_date=target_date,
                data_source=data_source,
                asset_type=asset_type,
            )
        st.session_state.last_output = output
        st.session_state.last_code = code
        st.session_state.last_run_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state.pending_result = pending_result if code == 0 else None
        st.session_state.latest_analysis_result = pending_result if code == 0 else None
        st.session_state.pending_pnl_file = get_expected_pnl_file(data_source, target_date) if code == 0 else None
        st.session_state.followup_output = ""
        st.session_state.followup_images = []
        st.session_state.last_run_target_date = target_date if code == 0 else None
        st.session_state.last_run_data_source = data_source if code == 0 else None

    st.markdown("### Report")
    if st.session_state.last_run_at:
        st.write(f"Last run: `{st.session_state.last_run_at}`")
        if st.session_state.last_code == 0:
            st.success(f"Report generated successfully (exit code = {st.session_state.last_code}).")
        else:
            st.error(f"Report generation failed (exit code = {st.session_state.last_code}).")
    else:
        st.info("Click the button above to generate the report.")

    output = st.session_state.last_output or ""
    display_output = output + ("\n\n" + st.session_state.followup_output if st.session_state.followup_output else "")
    st.code(display_output or "Report output will appear here after running.", language="text")
    for image_index, image_bytes in enumerate(st.session_state.followup_images, start=1):
        st.image(image_bytes, caption=f"Follow-up chart {image_index}", use_container_width=True)

    if st.session_state.last_code == 0 and st.session_state.latest_analysis_result is not None:
        st.markdown("### Position Zoom-In")
        analysis_result = st.session_state.latest_analysis_result
        position_options = build_position_options(analysis_result)
        if position_options:
            selected_market = st.selectbox(
                "Position",
                position_options,
                format_func=lambda market: (
                    f"{market} | {analysis_result['market_ticker_map'].get(market, 'No ticker')}"
                ),
            )
            selected_position = analysis_result["current_positions"].get(selected_market, {})
            ticker = analysis_result["market_ticker_map"].get(selected_market, "")
            summary_cols = st.columns(4)
            summary_cols[0].metric("Ticker", ticker or "N/A")
            summary_cols[1].metric("Position", f"{selected_position.get('position', 0):,.0f}")
            summary_cols[2].metric("Currency", selected_position.get("ccy", "N/A"))
            summary_cols[3].metric("Strategy", selected_position.get("strategy", "N/A"))

            trade_history = get_position_trade_history(analysis_result, selected_market)
            if trade_history is None or trade_history.empty:
                st.info("No trade history found for this position.")
            else:
                st.dataframe(trade_history, use_container_width=True, hide_index=True)
        else:
            st.info("No current positions are available for zoom-in.")

    if st.session_state.last_code == 0 and st.session_state.pending_result is not None:
        st.markdown("### Save Daily PnL")
        pending_pnl_file = Path(st.session_state.pending_pnl_file)
        pnl_file_exists = pending_pnl_file.exists()
        if pnl_file_exists:
            st.warning(f"Daily PnL file already exists: {pending_pnl_file}")
            save_label = "Overwrite Daily PnL file"
            overwrite_existing = True
        else:
            st.info(f"Daily PnL file will be saved to: {pending_pnl_file}")
            save_label = "Save Daily PnL file"
            overwrite_existing = False

        if st.button(save_label, use_container_width=True):
            code, save_output = save_pending_daily_pnl(
                st.session_state.pending_result,
                overwrite_existing=overwrite_existing,
            )
            st.session_state.last_output = output + "\n\n" + save_output
            st.session_state.pending_result = None if code == 0 else st.session_state.pending_result
            if code == 0:
                st.success("Daily PnL file saved.")
            else:
                st.error("Daily PnL file save failed.")
            st.rerun()

    if st.session_state.last_code == 0:
        workflow_target_date = st.session_state.last_run_target_date or target_date
        workflow_data_source = st.session_state.last_run_data_source or data_source
        st.markdown("### Follow-up Workflow")
        st.caption("Run these in the same order as run_portfolio_daily_workflow after analyze_portfolio.")
        st.write(f"Workflow date: `{workflow_target_date.strftime('%Y-%m-%d')}`, data source: `{workflow_data_source}`")
        lookback_period = st.number_input("Drawdown lookback period", min_value=1, value=90, step=1)
        date_cols = st.columns(2)
        with date_cols[0]:
            cumulative_start_date = st.date_input(
                "Cumulative contribution start date",
                value=date(2025, 12, 31),
            )
        with date_cols[1]:
            cumulative_end_date = st.date_input(
                "Cumulative contribution end date",
                value=workflow_target_date,
            )

        followup_steps = [
            ("prompt_for_constituents", "Display index top constituents"),
            ("run_portfolio_drawdown_monitor", "Run portfolio drawdown monitor"),
            ("run_dividend_display", "Run dividend display"),
            ("analyze_portfolio_industry_percentiles", "Run industry percentiles"),
            ("calculate_cumulative_contribution", "Run cumulative contribution"),
        ]
        for step_name, button_label in followup_steps:
            if st.button(button_label, key=f"followup_{step_name}", use_container_width=True):
                with st.spinner(f"Running {button_label}..."):
                    code, step_output, step_images = run_followup_step(
                        step_name=step_name,
                        target_date=workflow_target_date,
                        data_source=workflow_data_source,
                        lookback_period=int(lookback_period),
                        cumulative_start_date=cumulative_start_date,
                        cumulative_end_date=cumulative_end_date,
                    )
                section_output = f"\n\n===== {button_label} =====\n{step_output}"
                st.session_state.followup_output += section_output
                st.session_state.followup_images.extend(step_images)
                if code == 0:
                    st.success(f"{button_label} completed.")
                else:
                    st.error(f"{button_label} failed.")
                st.rerun()


    st.download_button(
        "Download report",
        data=display_output.encode("utf-8"),
        file_name="portfolio_analysis_report.txt",
        mime="text/plain",
        use_container_width=True,
        disabled=not bool(output),
    )


if __name__ == "__main__":
    main()
