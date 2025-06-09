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
        self.redis_client = redis_client or redis.Redis(
            host='busy-piglet-47702.upstash.io',
            port=6379,
            password=os.getenv('REDIS_PASSWORD'),  # 從環境變數讀取密碼
            db=0,
            decode_responses=True,
            ssl=True,  # Upstash 需要 SSL
            ssl_cert_reqs=None
        )
        self.lock = threading.Lock()

        # Redis key 用來存歷史紀錄
        self.history_key = "rate_limit_history"

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

        # 🔧 將歷史紀錄也存到 Redis 中
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
                'timestamp': time.time()  # 用於排序和清理舊紀錄
            }

            # 將紀錄推到 Redis list 的左邊（最新的在前面）
            self.redis_client.lpush(self.history_key, json.dumps(history_record))

            # 只保留最近 50 筆紀錄
            self.redis_client.ltrim(self.history_key, 0, 49)

        except Exception as e:
            print(f"⚠️ 保存歷史紀錄到 Redis 失敗: {e}")

    @property
    def request_history(self):
        """從 Redis 獲取共享的歷史紀錄"""
        try:
            # 從 Redis 獲取歷史紀錄
            history_data = self.redis_client.lrange(self.history_key, 0, 19)  # 最近 20 筆

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
            # 計算清除的 keys 數量
            deleted_count = 0
            for key in self.redis_client.scan_iter(match="rate_limit:*"):
                self.redis_client.delete(key)
                deleted_count += 1

            if deleted_count > 0:
                print(f"✅ 清除了 {deleted_count} 個 rate limit keys")
            else:
                print("ℹ️ 沒有找到需要清除的 rate limit keys")

            # 🔧 同時清除共享的歷史紀錄
            self.redis_client.delete(self.history_key)
            print("✅ 清除了共享歷史紀錄")

        except Exception as e:
            print(f"⚠️ Redis reset 失敗: {e}")
