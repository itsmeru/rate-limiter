import streamlit as st


class RateLimiterUI:
    """可重用的 Rate Limiter UI 組件"""

    @staticmethod
    def render_settings(algorithm_name, default_max_requests=10, default_window_size=60):
        """渲染設定區域"""
        st.subheader("⚙️ 設定")
        col1, col2, col3 = st.columns([2, 2, 1])

        with col1:
            max_requests = st.number_input("最大請求數", 1, 50, default_max_requests, key=f"{algorithm_name}_max")
        with col2:
            window_size = st.number_input("窗口大小 (秒)", 1, 300, default_window_size, key=f"{algorithm_name}_window")
        with col3:
            auto_refresh = st.checkbox("🔄 自動刷新", value=True, key=f"{algorithm_name}_refresh")

        return max_requests, window_size, auto_refresh

    @staticmethod
    def render_status(limiter):
        """渲染狀態顯示區域"""
        status = limiter.get_status()

        st.subheader(f"📊 {status['algorithm']} 狀態")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("已使用", status['current_count'])
        with col2:
            st.metric("總配額", status['max_requests'])
        with col3:
            st.metric("剩餘", status['remaining'])
        with col4:
            if status['algorithm'] == 'Fixed Window':
                st.metric("剩餘時間", f"{status['time_remaining']:.1f}秒")
        # 使用率
        usage_rate = status['current_count'] / status['max_requests']
        st.write(f"**使用率:** {usage_rate*100:.1f}% ({status['current_count']}/{status['max_requests']})")
        st.progress(usage_rate)

        return status

    @staticmethod
    def render_user_testing(limiter, algorithm_name):
        """渲染用戶測試區域"""
        col1, col2 = st.columns([2, 1])

        with col1:
            st.subheader("👥 用戶測試")

            # 用戶選擇和發送請求
            user_col1, user_col2 = st.columns([2, 1])

            with user_col1:
                users = ["Alice", "Bob", "Charlie", "Diana", "Eve"]
                selected_user = st.selectbox("選擇用戶", users, key=f"{algorithm_name}_user")

            with user_col2:
                if st.button("🚀 發送請求", type="primary", key=f"{algorithm_name}_send"):
                    allowed, extra_info = limiter.is_allowed(selected_user)

                    if extra_info.get('window_reset'):
                        st.success("🔄 窗口已重置！")

                    if allowed:
                        st.success(f"✅ {selected_user} 請求成功！")
                    else:
                        st.error(f"❌ {selected_user} 請求被拒絕！")

                    st.rerun()

            # 快速測試按鈕
            st.subheader("⚡ 快速測試")
            test_col1, test_col2, test_col3 = st.columns(3)

            with test_col1:
                if st.button("單用戶連發5次", key=f"{algorithm_name}_test1"):
                    results = []
                    for i in range(5):
                        allowed, _ = limiter.is_allowed(selected_user)
                        results.append("✅" if allowed else "❌")
                    st.write(f"結果: {' '.join(results)}")
                    st.rerun()

            with test_col2:
                if st.button("多用戶各發1次", key=f"{algorithm_name}_test2"):
                    results = []
                    for user in users:
                        allowed, _ = limiter.is_allowed(user)
                        results.append(f"{user}: {'✅' if allowed else '❌'}")
                    for result in results:
                        st.write(result)
                    st.rerun()

            with test_col3:
                if st.button("壓力測試 (10次)", key=f"{algorithm_name}_test3"):
                    import random
                    success_count = 0
                    for i in range(10):
                        user = random.choice(users)
                        allowed, _ = limiter.is_allowed(user)
                        if allowed:
                            success_count += 1
                    st.write(f"成功: {success_count}/10")
                    st.rerun()

        with col2:
            # 控制區域
            st.subheader("🎮 控制")

            if st.button("🗑️ 重置系統", type="secondary", key=f"{algorithm_name}_reset"):
                limiter.reset()
                st.success("系統已重置！")
                st.rerun()

    @staticmethod
    def render_history(limiter):
        """渲染歷史記錄區域"""
        if limiter.request_history:
            st.subheader("📜 請求歷史記錄")

            # 以表格形式顯示
            history_data = []
            for record in reversed(limiter.request_history[-10:]):  # 最近10筆
                status_icon = "✅" if record['status'] == '成功' else "❌"
                reset_info = " (窗口重置)" if record.get('window_reset') else ""
                history_data.append({
                    '時間': record['time'],
                    '用戶': record['user'],
                    '狀態': f"{status_icon} {record['status']}",
                    '系統計數': record['count_after'],
                    '備註': reset_info
                })

            if history_data:
                st.table(history_data)
        else:
            st.info("📝 尚無請求記錄")

    def render_token_bucket_settings(self, algorithm_name):
        """渲染 Token Bucket 專用設定"""
        st.subheader("⚙️ Token Bucket 設定")
        col1, col2, col3 = st.columns([2, 2, 1])

        with col1:
            capacity = st.number_input("桶子容量 (tokens)", 1, 100, 10)
        with col2:
            refill_rate = st.number_input("補充速率 (tokens/秒)", 0.1, 50.0, 2.0)
        with col3:
            auto_refresh = st.checkbox("🔄 自動刷新", value=True)

        return capacity, refill_rate, auto_refresh

    def render_token_bucket_status(self, limiter):
        """渲染 Token Bucket 狀態顯示"""
        status = limiter.get_status()

        st.subheader(f"🪣 {status['algorithm']} 狀態")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("當前 Tokens", f"{status['current_tokens']:.1f}")
        with col2:
            st.metric("桶子容量", status['capacity'])
        with col3:
            st.metric("補充速率", f"{status['refill_rate']}/秒")
        with col4:
            st.metric("填滿時間", f"{status['time_to_fill']:.1f}秒")

        # Token 使用率（反向：tokens 越多使用率越低）
        usage_rate = status['current_tokens'] / status['capacity']
        st.write(f"**Token 存量:** {usage_rate*100:.1f}% ({status['current_tokens']:.1f}/{status['capacity']})")
        st.progress(usage_rate)

        return status

    def render_token_bucket_user_testing(self, limiter, algorithm_name):
        """渲染 Token Bucket 用戶測試區域"""
        col1, col2 = st.columns([2, 1])

        with col1:
            st.subheader("👥 用戶測試")

            # 用戶選擇和發送請求
            user_col1, user_col2, user_col3 = st.columns([2, 1, 1])

            with user_col1:
                users = ["Alice", "Bob", "Charlie", "Diana", "Eve"]
                selected_user = st.selectbox("選擇用戶", users, key=f"{algorithm_name}_user")

            with user_col2:
                tokens_needed = st.number_input("消耗 Tokens", 1, 10, 1, key=f"{algorithm_name}_tokens")

            with user_col3:
                if st.button(f"🚀 消耗 {tokens_needed} Tokens", type="primary", key=f"{algorithm_name}_send"):
                    allowed, extra_info = limiter.is_allowed(selected_user, tokens_needed)

                    if allowed:
                        st.success(f"✅ {selected_user} 成功消耗 {tokens_needed} tokens！")
                    else:
                        st.error(f"❌ {selected_user} 請求被拒絕！Tokens 不足")

                    st.rerun()

            # 快速測試按鈕
            st.subheader("⚡ 快速測試")
            test_col1, test_col2, test_col3 = st.columns(3)

            with test_col1:
                if st.button("突發測試 (5x1)", key=f"{algorithm_name}_burst1"):
                    results = []
                    for i in range(5):
                        allowed, _ = limiter.is_allowed(selected_user, 1)
                        results.append("✅" if allowed else "❌")
                    st.write(f"5次1token: {' '.join(results)}")
                    st.rerun()

            with test_col2:
                if st.button("大額測試 (1x5)", key=f"{algorithm_name}_burst2"):
                    allowed, _ = limiter.is_allowed(selected_user, 5)
                    st.write(f"1次5tokens: {'✅' if allowed else '❌'}")
                    st.rerun()

            with test_col3:
                if st.button("多用戶測試", key=f"{algorithm_name}_multi"):
                    results = []
                    for user in users:
                        allowed, _ = limiter.is_allowed(user, 1)
                        results.append(f"{user}: {'✅' if allowed else '❌'}")
                    for result in results:
                        st.write(result)
                    st.rerun()

        with col2:
            # 控制區域
            st.subheader("🎮 控制")

            if st.button("🗑️ 重置系統", type="secondary", key=f"{algorithm_name}_reset"):
                limiter.reset()
                st.success("系統已重置！")
                st.rerun()
