from __future__ import annotations

import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import streamlit as st

from utils.streamlit_portfolio_helpers import (
    build_number_column_config,
    build_position_options,
    display_holdings_tables,
    display_market_value_messages,
    display_position_price_history_charts,
    display_report_summaries,
    get_expected_pnl_file,
    get_position_trade_history,
    load_historical_pnl_in_process,
    run_followup_step,
    run_portfolio_analysis_in_process,
    save_pending_daily_pnl,
)


PROJECT_ROOT = Path(__file__).resolve().parent
TARGET_SCRIPT = PROJECT_ROOT / "portfolio_analysis.py"


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

    action_cols = st.columns(2)
    with action_cols[0]:
        run_clicked = st.button("Generate Portfolio Report", type="primary", use_container_width=True)
    with action_cols[1]:
        load_history_clicked = st.button("Load Historical Date PnL", use_container_width=True)

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
    if "last_report_mode" not in st.session_state:
        st.session_state.last_report_mode = None
    if "historical_pnl_file" not in st.session_state:
        st.session_state.historical_pnl_file = None

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
        st.session_state.last_report_mode = "generated"
        st.session_state.historical_pnl_file = None

    if load_history_clicked:
        with st.spinner("Loading historical PnL..."):
            code, output, historical_result, historical_pnl_file = load_historical_pnl_in_process(
                target_date=target_date,
                data_source=data_source,
            )
        st.session_state.last_output = output
        st.session_state.last_code = code
        st.session_state.last_run_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state.pending_result = None
        st.session_state.latest_analysis_result = historical_result if code == 0 else None
        st.session_state.pending_pnl_file = None
        st.session_state.followup_output = ""
        st.session_state.followup_images = []
        st.session_state.last_run_target_date = target_date if code == 0 else None
        st.session_state.last_run_data_source = data_source if code == 0 else None
        st.session_state.last_report_mode = "historical"
        st.session_state.historical_pnl_file = historical_pnl_file

    st.markdown("### Report")
    if st.session_state.last_run_at:
        st.write(f"Last run: `{st.session_state.last_run_at}`")
        if st.session_state.last_code == 0:
            if st.session_state.last_report_mode == "historical":
                st.success(f"Historical PnL loaded successfully (exit code = {st.session_state.last_code}).")
                if st.session_state.historical_pnl_file:
                    st.caption(f"Loaded file: `{st.session_state.historical_pnl_file}`")
            else:
                st.success(f"Report generated successfully (exit code = {st.session_state.last_code}).")
        else:
            if st.session_state.last_report_mode == "historical":
                st.error(f"Historical PnL load failed (exit code = {st.session_state.last_code}).")
                if st.session_state.historical_pnl_file:
                    st.caption(f"Expected file: `{st.session_state.historical_pnl_file}`")
            else:
                st.error(f"Report generation failed (exit code = {st.session_state.last_code}).")
    else:
        st.info("Click the button above to generate the report.")

    output = st.session_state.last_output or ""
    display_output = output + ("\n\n" + st.session_state.followup_output if st.session_state.followup_output else "")
    display_market_value_messages(output)
    if st.session_state.last_code == 0 and st.session_state.latest_analysis_result is not None:
        display_holdings_tables(st.session_state.latest_analysis_result)
        display_report_summaries(st.session_state.latest_analysis_result)

    with st.expander("Raw console report", expanded=st.session_state.last_code != 0):
        st.code(display_output or "Report output will appear here after running.", language="text")
    for image_index, image_bytes in enumerate(st.session_state.followup_images, start=1):
        st.image(image_bytes, caption=f"Follow-up chart {image_index}", use_container_width=True)

    if st.session_state.last_code == 0 and st.session_state.latest_analysis_result is not None:
        st.markdown("### Position Zoom-In")
        analysis_result = st.session_state.latest_analysis_result
        position_options = build_position_options(analysis_result)
        if position_options:
            show_position_zoom = st.toggle(
                "Display position zoom-in",
                value=False,
                key="show_position_zoom_in",
            )
            if show_position_zoom:
                selected_market = st.selectbox(
                    "Select position to display",
                    position_options,
                    format_func=lambda market: (
                        f"{market} | {analysis_result['market_ticker_map'].get(market, 'No ticker')}"
                    ),
                )
                selected_position = analysis_result["current_positions"].get(selected_market, {})
                ticker = analysis_result["market_ticker_map"].get(selected_market, "")
                summary_cols = st.columns(4)
                summary_cols[0].metric("Ticker", ticker or "N/A")
                summary_cols[1].metric("Position", f"{selected_position.get('position', 0):,.2f}")
                summary_cols[2].metric("Currency", selected_position.get("ccy", "N/A"))
                summary_cols[3].metric("Strategy", selected_position.get("strategy", "N/A"))

                load_position_zoom = st.button(
                    "Load selected position zoom-in",
                    key="load_selected_position_zoom_in",
                    use_container_width=True,
                )
                if load_position_zoom:
                    st.markdown("#### Price History")
                    chart_end_date = analysis_result.get("target_date") or st.session_state.last_run_target_date or datetime.today()
                    display_position_price_history_charts(
                        ticker=ticker,
                        market=selected_market,
                        analysis_result=analysis_result,
                        end_date=chart_end_date,
                    )

                    trade_history = get_position_trade_history(analysis_result, selected_market)
                    if trade_history is None or trade_history.empty:
                        st.info("No trade history found for this position.")
                    else:
                        st.dataframe(
                            trade_history,
                            use_container_width=True,
                            hide_index=True,
                            column_config=build_number_column_config(trade_history),
                        )
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
