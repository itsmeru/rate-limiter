import time
from fixed_window_limiter import FixedWindowRateLimiter
from token_bucket_limiter import TokenBucketLimiter
from sliding_window_limiter import SlidingWindowLimiter
from rate_limiter_ui import RateLimiterUI
import streamlit as st


def main():
    st.set_page_config(
        page_title="Rate Limiter Dashboard",
        page_icon="🚦",
        layout="wide"
    )

    st.title("🚦 Rate Limiter 演算法比較")

    # 演算法選擇
    algorithm = st.sidebar.selectbox(
        "選擇演算法",
        ["Fixed Window", "Sliding Window", "Token Bucket", "Leaky Bucket"]
    )

    # 根據選擇的演算法創建對應的 limiter
    if algorithm == "Fixed Window":
        render_fixed_window_page()
    elif algorithm == "Sliding Window":
        render_sliding_window_page()
    elif algorithm == "Token Bucket":
        render_token_bucket_page()
    # elif algorithm == "Leaky Bucket":
    #     st.info("🚧 Leaky Bucket 即將推出...")


def render_fixed_window_page():
    """渲染 Fixed Window 頁面"""
    st.markdown("**原理：** 將時間切分成固定窗口，所有用戶共享同一個請求配額")

    # 使用 UI 組件
    ui = RateLimiterUI()

    # 設定
    max_requests, window_size, auto_refresh = ui.render_settings("fixed_window")

    # 初始化 limiter
    if 'fixed_limiter' not in st.session_state:
        st.session_state.fixed_limiter = FixedWindowRateLimiter(max_requests, window_size)
    else:
        st.session_state.fixed_limiter.max_requests = max_requests
        st.session_state.fixed_limiter.window_size = window_size

    limiter = st.session_state.fixed_limiter

    # 狀態顯示
    status = ui.render_status(limiter)

    st.markdown("---")

    # 用戶測試
    ui.render_user_testing(limiter, "fixed_window")

    # 歷史記錄
    ui.render_history(limiter)

    # 自動刷新
    if auto_refresh and status['time_remaining'] > 0:
        time.sleep(1)
        st.rerun()


def render_sliding_window_page():
    """渲染 Sliding Window 頁面"""
    st.markdown("**原理：** 滑動時間窗口，動態移除過期請求")

    # 使用 UI 組件
    ui = RateLimiterUI()

    # 設定
    max_requests, window_size, auto_refresh = ui.render_settings("sliding_window")

    # 初始化 limiter
    if 'sliding_limiter' not in st.session_state:
        st.session_state.sliding_limiter = SlidingWindowLimiter(max_requests, window_size)
    else:
        st.session_state.sliding_limiter.max_requests = max_requests
        st.session_state.sliding_limiter.window_size = window_size

    limiter = st.session_state.sliding_limiter

    # 狀態顯示
    status = ui.render_status(limiter)

    st.markdown("---")

    # 用戶測試
    ui.render_user_testing(limiter, "sliding_window")

    # 歷史記錄
    ui.render_history(limiter)

    # 自動刷新（Sliding Window 每秒刷新清理過期請求）
    if auto_refresh:
        time.sleep(1)
        st.rerun()


def render_token_bucket_page():
    """渲染 Token Bucket 頁面"""
    st.markdown("**原理：** 令牌桶，以固定速率補充 tokens，允許突發流量")

    ui = RateLimiterUI()
    capacity, refill_rate, auto_refresh = ui.render_token_bucket_settings("token_bucket")

    if 'token_limiter' not in st.session_state:
        st.session_state.token_limiter = TokenBucketLimiter(capacity, refill_rate)
    else:
        st.session_state.token_limiter.capacity = capacity
        st.session_state.token_limiter.refill_rate = refill_rate

    limiter = st.session_state.token_limiter
    status = ui.render_token_bucket_status(limiter)
    st.markdown("---")
    ui.render_token_bucket_user_testing(limiter, "token_bucket")
    ui.render_history(limiter)

    if auto_refresh:
        time.sleep(1)
        st.rerun()


if __name__ == "__main__":
    main()
