from datetime import datetime
import streamlit as st


class RateLimiterUI:
    """可重用的 Rate Limiter UI 組件（簡化版）"""

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
            if 'time_remaining' in status and status['time_remaining'] > 0:
                time_remaining = status['time_remaining']
                if time_remaining > 60:
                    time_display = f"{time_remaining/60:.1f}分"
                else:
                    time_display = f"{time_remaining:.0f}秒"
                st.metric("窗口重置", time_display)
            else:
                st.metric("窗口狀態", "✅ 可重置")

        # 使用率計算和進度條
        usage_rate = status['current_count'] / status['max_requests']
        usage_percentage = usage_rate * 100

        # 限制進度條值在 0.0-1.0 之間
        progress_value = min(usage_rate, 1.0)

        st.write(f"**使用率:** {usage_percentage:.1f}% ({status['current_count']}/{status['max_requests']})")
        st.progress(progress_value)

        # 如果超過限制，顯示警告
        if usage_rate > 1.0:
            st.error(f"⚠️ 已超出限制！超出 {(usage_rate - 1.0) * 100:.1f}%")
        elif usage_rate > 0.8:
            st.warning("⚠️ 接近限制")

        # 倒數計時視覺化（靜態顯示）
        if 'time_remaining' in status and status['time_remaining'] > 0:
            st.write("⏰ **窗口重置倒數:**")

            # 計算倒數進度
            window_size = getattr(limiter, 'window_size', 60)
            countdown_progress = 1 - (status['time_remaining'] / window_size)
            countdown_progress = max(0.0, min(1.0, countdown_progress))

            st.progress(countdown_progress)

            # 倒數數字顯示
            if status['time_remaining'] > 60:
                time_text = f"還有 {status['time_remaining']/60:.1f} 分鐘後重置"
            elif status['time_remaining'] > 10:
                time_text = f"還有 {status['time_remaining']:.0f} 秒後重置"
            else:
                time_text = f"還有 {status['time_remaining']:.1f} 秒後重置"

            st.caption(time_text)

            # 提示用戶手動刷新
            if status['time_remaining'] < 10:
                st.info("🔄 接近重置時間，點擊手動刷新查看最新狀態")

        else:
            if status.get('remaining', 0) <= 0:
                st.success("✅ 窗口已可重置！")
            else:
                st.info("ℹ️ 窗口內還有可用請求")

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
            for record in limiter.request_history[:10]:  # 最近10筆，最新在前
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

        # Token 使用率計算
        usage_rate = status['current_tokens'] / status['capacity']
        usage_percentage = usage_rate * 100

        # 確保進度條值在 0.0-1.0 之間
        progress_value = max(0.0, min(usage_rate, 1.0))

        st.write(f"**Token 存量:** {usage_percentage:.1f}% ({status['current_tokens']:.1f}/{status['capacity']})")
        st.progress(progress_value)

        # Token 補充狀態
        if status['current_tokens'] < status['capacity']:
            st.write("🔄 **Token 補充狀態:**")

            # 計算補充進度
            refill_progress = status['current_tokens'] / status['capacity']
            st.progress(refill_progress)

            if status['time_to_fill'] > 60:
                fill_text = f"完全填滿還需 {status['time_to_fill']/60:.1f} 分鐘"
            else:
                fill_text = f"完全填滿還需 {status['time_to_fill']:.1f} 秒"

            st.caption(fill_text)
            st.info("💡 點擊手動刷新查看 Token 補充狀態")
        else:
            st.success("✅ Token 桶已滿！")

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

    def render_leaky_bucket_status(self, limiter):
        """渲染 Leaky Bucket 狀態顯示"""
        status = limiter.get_status()

        st.subheader(f"🕳️ {status['algorithm']} 狀態")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("排隊數量", f"{status['queue_size']:.1f}")
        with col2:
            st.metric("桶子容量", status['capacity'])
        with col3:
            st.metric("漏出速率", f"{status['leak_rate']}/秒")
        with col4:
            st.metric("清空時間", f"{status['time_to_empty']:.1f}秒")

        # 桶子使用率計算
        usage_rate = status['queue_size'] / status['capacity']
        usage_percentage = usage_rate * 100

        # 確保進度條值在 0.0-1.0 之間
        progress_value = max(0.0, min(usage_rate, 1.0))

        st.write(f"**桶子使用率:** {usage_percentage:.1f}% ({status['queue_size']:.1f}/{status['capacity']})")
        st.progress(progress_value)

        # 如果超過容量，顯示警告
        if usage_rate > 1.0:
            st.error(f"⚠️ 桶子溢出！超出 {(usage_rate - 1.0) * 100:.1f}%")

        # 漏出進度條
        if status['queue_size'] > 0 and status['leak_rate'] > 0:
            st.write("💧 **漏出進度:**")

            # 基於剩餘時間的倒數進度條
            max_wait_time = status['capacity'] / status['leak_rate']

            if max_wait_time > 0 and status['time_to_empty'] <= max_wait_time:
                progress = 1 - (status['time_to_empty'] / max_wait_time)
                progress = max(0.0, min(1.0, progress))

                st.progress(progress)

                # 倒數計時文字
                if status['time_to_empty'] > 60:
                    time_text = f"⏰ 還需等待 {status['time_to_empty']/60:.1f} 分鐘清空"
                else:
                    time_text = f"⏰ 還需等待 {status['time_to_empty']:.1f} 秒清空"

                st.caption(f"{time_text} (進度: {progress*100:.1f}%)")
                st.info("💡 點擊手動刷新查看漏出進度")
            else:
                st.progress(1.0)
                st.caption("✅ 即將清空")
        else:
            st.write("💧 **漏出狀態:** 桶子空閒")

        return status

    def render_leaky_bucket_user_testing(self, limiter, algorithm_name):
        """渲染 Leaky Bucket 用戶測試區域"""
        col1, col2 = st.columns([2, 1])

        with col1:
            st.subheader("👥 用戶測試")

            # 用戶選擇和發送請求
            user_col1, user_col2, user_col3 = st.columns([2, 1, 1])

            with user_col1:
                users = ["Alice", "Bob", "Charlie", "Diana", "Eve"]
                selected_user = st.selectbox("選擇用戶", users, key=f"{algorithm_name}_user")

            with user_col2:
                queue_cost = st.number_input("排隊數量", 1, 10, 1, key=f"{algorithm_name}_cost")

            with user_col3:
                if st.button(f"🚰 排隊 {queue_cost} 個", type="primary", key=f"{algorithm_name}_send"):
                    allowed, extra_info = limiter.is_allowed(selected_user, queue_cost)

                    if allowed:
                        st.success(f"✅ {selected_user} 成功排隊 {queue_cost} 個請求！")
                    else:
                        st.error(f"❌ {selected_user} 排隊失敗！桶子已滿")

                    st.rerun()

            # 快速測試按鈕
            st.subheader("⚡ 快速測試")
            test_col1, test_col2, test_col3 = st.columns(3)

            with test_col1:
                if st.button("連續排隊測試", key=f"{algorithm_name}_queue1"):
                    results = []
                    for i in range(5):
                        allowed, _ = limiter.is_allowed(selected_user, 1)
                        results.append("✅" if allowed else "❌")
                    st.write(f"5次排隊: {' '.join(results)}")
                    st.rerun()

            with test_col2:
                if st.button("大量排隊測試", key=f"{algorithm_name}_queue2"):
                    allowed, _ = limiter.is_allowed(selected_user, 5)
                    st.write(f"一次排隊5個: {'✅' if allowed else '❌'}")
                    st.rerun()

            with test_col3:
                if st.button("多用戶排隊", key=f"{algorithm_name}_multi"):
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

            # 桶子狀態可視化
            st.subheader("🪣 桶子狀態")
            status = limiter.get_status()

            # 簡單的文字可視化
            if status['capacity'] > 0:
                filled_slots = int((status['queue_size'] / status['capacity']) * 10)
                filled_slots = max(0, min(10, filled_slots))
                empty_slots = 10 - filled_slots

                bucket_visual = "🟦" * filled_slots + "⬜" * empty_slots
                st.write("桶子狀態:")
                st.write(bucket_visual)
                st.caption(f"排隊: {status['queue_size']:.1f}/{status['capacity']}")
