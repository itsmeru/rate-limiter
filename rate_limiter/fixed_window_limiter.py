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

        # 調試環境變數
        redis_url = os.getenv('REDIS_URL')
        redis_password = os.getenv('REDIS_PASSWORD')
        try:
            if redis_client:
                self.redis_client = redis_client
                print("✅ 使用提供的 Redis 客戶端")
            elif redis_url:
                print("🔗 使用 REDIS_URL 連接...")
                # 顯示隱藏密碼的 URL 格式用於調試
                safe_url = redis_url.split('@')[0].split(':')[:-1] + ['***@'] + \
                    redis_url.split('@')[1:] if '@' in redis_url else redis_url
                print(f"連接格式: {''.join(safe_url) if isinstance(safe_url, list) else safe_url}")

                self.redis_client = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_timeout=10,
                    socket_connect_timeout=10,
                    retry_on_timeout=True,
                    ssl_cert_reqs=None
                )
            else:
                print("🔗 使用個別參數連接...")
                if not redis_password:
                    raise ValueError("❌ REDIS_PASSWORD 環境變數未設定")

                self.redis_client = redis.Redis(
                    host='busy-piglet-47702.upstash.io',
                    port=6379,
                    password=redis_password,
                    db=0,
                    decode_responses=True,
                    ssl=True,
                    ssl_cert_reqs=None,
                    socket_timeout=10,
                    socket_connect_timeout=10,
                    retry_on_timeout=True
                )

            # 測試連接
            print("🧪 測試 Redis 連接...")
            result = self.redis_client.ping()
            print(f"✅ Redis 連接成功: {result}")

        except redis.AuthenticationError as e:
            print(f"❌ Redis 認證失敗: {e}")
            print("💡 請檢查:")
            print("   1. REDIS_PASSWORD 是否正確")
            print("   2. 或使用完整的 REDIS_URL")
            print("   3. Upstash 控制台的連接資訊")
            raise e
        except Exception as e:
            print(f"❌ Redis 連接失敗: {type(e).__name__}: {e}")
            raise e

        self.lock = threading.Lock()
        self.history_key = "rate_limit_history"

    def is_allowed(self, client_id):
        try:
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

        except Exception as e:
            print(f"⚠️ is_allowed 操作失敗: {e}")
            # 如果 Redis 操作失敗，返回允許但記錄錯誤
            return True, {'window_reset': False, 'error': str(e)}

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
        try:
            current_time = time.time()
            current_window_start = int(current_time // self.window_size) * self.window_size
            window_key = f"rate_limit:{current_window_start}"

            current_count_str = self.redis_client.get(window_key)
            current_count = int(current_count_str) if current_count_str else 0

            window_end = current_window_start + self.window_size
            time_remaining = max(0, window_end - current_time)

            return {
                'current_count': current_count,
                'max_requests': self.max_requests,
                'remaining': max(0, self.max_requests - current_count),
                'time_remaining': time_remaining,
                'algorithm': 'Fixed Window'
            }
        except Exception as e:
            print(f"⚠️ get_status 失敗: {e}")
            return {
                'current_count': 0,
                'max_requests': self.max_requests,
                'remaining': self.max_requests,
                'time_remaining': 0,
                'algorithm': 'Fixed Window (Error)',
                'error': str(e)
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


# 測試連接的輔助函數
def test_redis_connection():
    """測試 Redis 連接的獨立函數"""
    print("🧪 開始測試 Redis 連接...")

    redis_url = os.getenv('REDIS_URL')
    redis_password = os.getenv('REDIS_PASSWORD')

    print(f"REDIS_URL: {'已設定' if redis_url else '未設定'}")
    print(f"REDIS_PASSWORD: {'已設定' if redis_password else '未設定'}")

    if redis_url:
        try:
            client = redis.from_url(redis_url, decode_responses=True, ssl_cert_reqs=None)
            result = client.ping()
            print(f"✅ 使用 REDIS_URL 連接成功: {result}")
            return True
        except Exception as e:
            print(f"❌ 使用 REDIS_URL 連接失敗: {e}")

    if redis_password:
        try:
            client = redis.Redis(
                host='busy-piglet-47702.upstash.io',
                port=6379,
                password=redis_password,
                ssl=True,
                ssl_cert_reqs=None,
                decode_responses=True
            )
            result = client.ping()
            print(f"✅ 使用個別參數連接成功: {result}")
            return True
        except Exception as e:
            print(f"❌ 使用個別參數連接失敗: {e}")

    print("❌ 所有連接方式都失敗")
    return False
