import os
import redis
import threading
import time
import json
from datetime import datetime
from base_limiter import BaseLimiter


class FixedWindowRateLimiter(BaseLimiter):
    def __init__(self, max_requests, window_size, redis_client=None):
        self.max_requests = max_requests
        self.window_size = window_size

        if redis_client:
            self.redis_client = redis_client
            print("✅ 使用提供的 Redis 客戶端")
        else:
            # 詳細診斷 Redis 連接
            self.redis_client = self._create_redis_connection()

        self.lock = threading.Lock()
        self.history_key = "rate_limit_history"

        # 測試連接
        try:
            result = self.redis_client.ping()
            print(f"✅ Redis 連接測試成功: {result}")
        except Exception as e:
            print(f"❌ Redis 連接測試失敗: {e}")
            raise e

    def _create_redis_connection(self):
        """創建 Redis 連接，使用正確的 TLS 設定"""
        print("🔍 開始創建 Redis 連接...")

        # 獲取 REDIS_URL
        redis_url = None
        try:
            import streamlit as st
            if hasattr(st, 'secrets'):
                redis_url = st.secrets.get('REDIS_URL')
        except:
            pass

        if not redis_url:
            redis_url = os.getenv('REDIS_URL')

        if not redis_url:
            raise ValueError("❌ 無法找到 REDIS_URL 配置")

        print(f"Redis URL 前綴: {redis_url[:30]}...")

        # 由於 CLI 需要 --tls，我們需要手動解析 URL 並設定 SSL
        try:
            from urllib.parse import urlparse
            parsed = urlparse(redis_url)

            print(f"解析結果: host={parsed.hostname}, port={parsed.port}")

            # 為 Upstash 創建 Redis 連接，強制使用 SSL
            client = redis.Redis(
                host=parsed.hostname,
                port=parsed.port or 6379,
                password=parsed.password,
                username=parsed.username or 'default',
                ssl=True,                    # 強制使用 SSL，對應 CLI 的 --tls
                ssl_check_hostname=False,    # 對 Upstash 很重要
                ssl_cert_reqs=None,          # 不驗證證書
                decode_responses=True,
                socket_connect_timeout=30,
                socket_timeout=30,
                retry_on_timeout=True
            )

            print("🧪 測試連接...")
            result = client.ping()
            print(f"✅ 連接成功: {result}")
            return client

        except Exception as e:
            print(f"❌ 連接失敗: {e}")
            raise e

    def is_allowed(self, client_id):
        current_time = time.time()
        current_window_start = int(current_time // self.window_size) * self.window_size
        window_key = f"rate_limit:{current_window_start}"

        pipe = self.redis_client.pipeline()
        pipe.incr(window_key)
        pipe.expire(window_key, int(self.window_size) + 1)
        results = pipe.execute()

        current_count = results[0]
        allowed = current_count <= self.max_requests

        # 將歷史紀錄也存到 Redis 中
        self._add_history_to_redis(client_id, allowed, current_count, current_count == 1)

        return allowed, {'window_reset': current_count == 1}

    def _add_history_to_redis(self, client_id, allowed, count, window_reset):
        """將歷史紀錄加到 Redis 中，讓所有客戶端共享"""
        try:
            history_record = {
                'time': datetime.now().strftime('%H:%M:%S'),
                'user': client_id,
                'status': '成功' if allowed else '拒絕',
                'count_after': count,
                'window_reset': window_reset,
                'timestamp': time.time()
            }

            self.redis_client.lpush(self.history_key, json.dumps(history_record))
            self.redis_client.ltrim(self.history_key, 0, 49)

        except Exception as e:
            print(f"⚠️ 保存歷史紀錄到 Redis 失敗: {e}")

    @property
    def request_history(self):
        """從 Redis 獲取共享的歷史紀錄"""
        try:
            history_data = self.redis_client.lrange(self.history_key, 0, 19)
            history_list = []
            for record_json in history_data:
                try:
                    record = json.loads(record_json)
                    history_list.append(record)
                except json.JSONDecodeError:
                    continue
            return history_list
        except Exception as e:
            print(f"⚠️ 從 Redis 讀取歷史紀錄失敗: {e}")
            return []

    def get_status(self):
        current_time = time.time()
        current_window_start = int(current_time // self.window_size) * self.window_size
        window_key = f"rate_limit:{current_window_start}"

        try:
            current_count_str = self.redis_client.get(window_key)
            current_count = int(current_count_str) if current_count_str else 0
        except (ValueError, TypeError):
            current_count = 0

        window_end = current_window_start + self.window_size
        time_remaining = max(0, window_end - current_time)

        return {
            'current_count': current_count,
            'max_requests': self.max_requests,
            'remaining': max(0, self.max_requests - current_count),
            'time_remaining': time_remaining,
            'algorithm': 'Fixed Window'
        }

    def reset(self):
        """重置速率限制器狀態"""
        try:
            deleted_count = 0
            for key in self.redis_client.scan_iter(match="rate_limit:*"):
                self.redis_client.delete(key)
                deleted_count += 1

            if deleted_count > 0:
                print(f"✅ 清除了 {deleted_count} 個 rate limit keys")
            else:
                print("ℹ️ 沒有找到需要清除的 rate limit keys")

            self.redis_client.delete(self.history_key)
            print("✅ 清除了共享歷史紀錄")

        except Exception as e:
            print(f"⚠️ Redis reset 失敗: {e}")


# 獨立測試函數
def test_redis_connection_detailed():
    """詳細的 Redis 連接測試"""
    print("=" * 50)
    print("🧪 Redis 連接詳細診斷")
    print("=" * 50)

    try:
        limiter = FixedWindowRateLimiter(5, 60)
        print("✅ Rate Limiter 創建成功")
        return True
    except Exception as e:
        print(f"❌ 創建失敗: {e}")
        return False
