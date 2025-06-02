from datetime import datetime
import threading
import time
from base_limiter import BaseLimiter


class LeakyBucketLimiter(BaseLimiter):
    def __init__(self, capacity, leak_rate):

        self.capacity = capacity
        self.leak_rate = leak_rate
        self.queue_size = 0.0  # 當前排隊數量（使用浮點數）
        self.last_leak_time = time.time()
        self.lock = threading.Lock()
        self.request_history = []

    def _leak_requests(self):
        current_time = time.time()
        time_passed = current_time - self.last_leak_time

        # 計算可以漏出多少請求
        requests_to_leak = time_passed * self.leak_rate

        # 更新排隊數量（不能小於 0）
        self.queue_size = max(0, self.queue_size - requests_to_leak)

        # 更新漏出時間
        self.last_leak_time = current_time

    def is_allowed(self, client_id, cost=1):
        with self.lock:
            # 先漏出一些請求
            self._leak_requests()

            # 檢查桶子是否還有空間
            if self.queue_size + cost <= self.capacity:
                # 請求進入桶子排隊
                self.queue_size += cost
                allowed = True
            else:
                # 桶子滿了，請求溢出
                allowed = False

            # 記錄請求歷史
            self.request_history.append({
                'time': datetime.now().strftime('%H:%M:%S'),
                'user': client_id,
                'status': '成功' if allowed else '拒絕',
                'count_after': self.queue_size,
                'cost': cost
            })

            if len(self.request_history) > 20:
                self.request_history = self.request_history[-20:]

            return allowed, {'queue_position': self.queue_size if allowed else None}

    def get_status(self):
        """獲取當前狀態"""
        with self.lock:
            # 更新排隊狀態
            self._leak_requests()

            # 計算排隊清空需要多長時間
            time_to_empty = self.queue_size / self.leak_rate if self.leak_rate > 0 else 0

            return {
                'current_count': self.queue_size,
                'max_requests': self.capacity,
                'remaining': self.capacity - self.queue_size,
                'time_remaining': time_to_empty,
                'algorithm': 'Leaky Bucket',
                'queue_size': self.queue_size,
                'capacity': self.capacity,
                'leak_rate': self.leak_rate,
                'time_to_empty': time_to_empty,
            }

    def reset(self):
        """重置桶子"""
        with self.lock:
            self.queue_size = 0
            self.last_leak_time = time.time()
            self.request_history = []
