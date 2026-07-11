from __future__ import annotations

import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime
from io import StringIO
from pathlib import Path

import streamlit as st


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
        st.session_state.pending_pnl_file = get_expected_pnl_file(data_source, target_date) if code == 0 else None

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
    st.code(output or "Report output will appear here after running.", language="text")

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

    st.download_button(
        "Download report",
        data=output.encode("utf-8"),
        file_name="portfolio_analysis_report.txt",
        mime="text/plain",
        use_container_width=True,
        disabled=not bool(output),
    )


if __name__ == "__main__":
    main()
