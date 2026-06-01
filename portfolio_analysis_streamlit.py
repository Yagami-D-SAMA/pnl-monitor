from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
TARGET_SCRIPT = PROJECT_ROOT / "portfolio_analysis.py"


def run_portfolio_analysis() -> tuple[int, str]:
    """
    Run portfolio_analysis.py and return (exit_code, combined_output).
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


def main() -> None:
    st.set_page_config(page_title="Portfolio Analysis UI", layout="wide")
    st.title("Portfolio Analysis UI")
    st.caption("该页面通过运行 `portfolio_analysis.py` 展示分析输出，不修改现有脚本逻辑。")

    if not TARGET_SCRIPT.exists():
        st.error(f"未找到目标脚本：{TARGET_SCRIPT}")
        return

    st.markdown("### 运行控制")
    run_clicked = st.button("运行 portfolio_analysis.py", type="primary", use_container_width=True)

    if "last_output" not in st.session_state:
        st.session_state.last_output = ""
        st.session_state.last_code = None
        st.session_state.last_run_at = None

    if run_clicked:
        with st.spinner("正在运行 portfolio_analysis.py ..."):
            code, output = run_portfolio_analysis()
        st.session_state.last_output = output
        st.session_state.last_code = code
        st.session_state.last_run_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    st.markdown("### 运行结果")
    if st.session_state.last_run_at:
        st.write(f"最近运行时间：`{st.session_state.last_run_at}`")
        if st.session_state.last_code == 0:
            st.success(f"脚本执行成功（exit code = {st.session_state.last_code}）。")
        else:
            st.error(f"脚本执行失败（exit code = {st.session_state.last_code}）。")
    else:
        st.info("点击上方按钮开始运行。")

    output = st.session_state.last_output or ""
    st.text_area(
        "输出日志（stdout + stderr）",
        value=output,
        height=520,
    )

    st.download_button(
        "下载本次输出日志",
        data=output.encode("utf-8"),
        file_name="portfolio_analysis_output.txt",
        mime="text/plain",
        use_container_width=True,
        disabled=not bool(output),
    )


if __name__ == "__main__":
    main()
