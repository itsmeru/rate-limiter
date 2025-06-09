import time
from fixed_window_limiter import FixedWindowRateLimiter
from leaky_bucket_limiter import LeakyBucketLimiter
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
    elif algorithm == "Leaky Bucket":
        render_leaky_bucket_page()


def render_fixed_window_page():
    """渲染 Fixed Window 頁面"""
    st.markdown("**原理：** 將時間劃分為固定大小的視窗期，每個視窗內維護一個請求計數器。當視窗時間到達時，計數器重置為0，開始新的計數週期。")
    st.markdown("**優點：** 容易實施、記憶體使用空間小。")
    st.markdown("**缺點：** 1. 突發流量問題：窗口邊界可能出現雙倍流量,2. 不夠平滑：在窗口重置瞬間大量請求通過")

    # 🔧 簡化設定 - 移除自動刷新選項
    st.subheader("⚙️ 設定")
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        max_requests = st.number_input("最大請求數", 1, 50, 10, key="fixed_window_max")
    with col2:
        window_size = st.number_input("窗口大小 (秒)", 1, 300, 60, key="fixed_window_window")
    with col3:
        if st.button("🔄 刷新", key="fixed_manual_refresh"):
            st.rerun()

    # 初始化 limiter
    if 'fixed_limiter' not in st.session_state:
        st.session_state.fixed_limiter = FixedWindowRateLimiter(max_requests, window_size)
    else:
        st.session_state.fixed_limiter.max_requests = max_requests
        st.session_state.fixed_limiter.window_size = window_size

    limiter = st.session_state.fixed_limiter

    # 使用簡化的 UI 組件
    ui = RateLimiterUI()

    # 狀態顯示
    status = ui.render_status(limiter)

    st.markdown("---")

    # 用戶測試
    ui.render_user_testing(limiter, "fixed_window")

    # 歷史記錄
    ui.render_history(limiter)


def render_sliding_window_page():
    """渲染 Sliding Window 頁面"""
    st.markdown("**原理：** 滑動時間窗口，動態移除過期請求")

    # 🔧 簡化設定
    st.subheader("⚙️ 設定")
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        max_requests = st.number_input("最大請求數", 1, 50, 10, key="sliding_window_max")
    with col2:
        window_size = st.number_input("窗口大小 (秒)", 1, 300, 60, key="sliding_window_window")
    with col3:
        if st.button("🔄 刷新", key="sliding_manual_refresh"):
            st.rerun()

    # 初始化 limiter
    if 'sliding_limiter' not in st.session_state:
        st.session_state.sliding_limiter = SlidingWindowLimiter(max_requests, window_size)
    else:
        st.session_state.sliding_limiter.max_requests = max_requests
        st.session_state.sliding_limiter.window_size = window_size

    limiter = st.session_state.sliding_limiter

    ui = RateLimiterUI()

    # 狀態顯示
    status = ui.render_status(limiter)

    st.markdown("---")

    # 用戶測試
    ui.render_user_testing(limiter, "sliding_window")

    # 歷史記錄
    ui.render_history(limiter)


def render_token_bucket_page():
    """渲染 Token Bucket 頁面"""
    st.markdown("**原理：** 令牌桶，以固定速率補充 tokens，允許突發流量")

    # 🔧 簡化 Token Bucket 設定
    st.subheader("⚙️ Token Bucket 設定")
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        capacity = st.number_input("桶子容量 (tokens)", 1, 100, 10, key="token_bucket_capacity")
    with col2:
        refill_rate = st.number_input("補充速率 (tokens/秒)", 0.1, 50.0, 2.0, key="token_bucket_rate")
    with col3:
        if st.button("🔄 刷新", key="token_manual_refresh"):
            st.rerun()

    if 'token_limiter' not in st.session_state:
        st.session_state.token_limiter = TokenBucketLimiter(capacity, refill_rate)
    else:
        st.session_state.token_limiter.capacity = capacity
        st.session_state.token_limiter.refill_rate = refill_rate

    limiter = st.session_state.token_limiter
    ui = RateLimiterUI()
    status = ui.render_token_bucket_status(limiter)
    st.markdown("---")
    ui.render_token_bucket_user_testing(limiter, "token_bucket")
    ui.render_history(limiter)


def render_leaky_bucket_page():
    """渲染 Leaky Bucket 頁面"""
    st.markdown("**原理：** 漏桶，請求排隊，以固定速率處理，平滑流量")

    # 🔧 簡化 Leaky Bucket 設定
    st.subheader("⚙️ Leaky Bucket 設定")
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        capacity = st.number_input("桶子容量 (請求)", 1, 100, 10, key="leaky_bucket_capacity")
    with col2:
        leak_rate = st.number_input("漏出速率 (請求/秒)", 0.1, 50.0, 2.0, step=0.1, key="leaky_bucket_rate")
    with col3:
        if st.button("🔄 手動刷新", key="leaky_manual_refresh"):
            st.rerun()

    if 'leaky_limiter' not in st.session_state:
        st.session_state.leaky_limiter = LeakyBucketLimiter(capacity, leak_rate)
    else:
        st.session_state.leaky_limiter.capacity = capacity
        st.session_state.leaky_limiter.leak_rate = leak_rate

    limiter = st.session_state.leaky_limiter
    ui = RateLimiterUI()
    status = ui.render_leaky_bucket_status(limiter)
    st.markdown("---")
    ui.render_leaky_bucket_user_testing(limiter, "leaky_bucket")
    ui.render_history(limiter)


if __name__ == "__main__":
    main()
