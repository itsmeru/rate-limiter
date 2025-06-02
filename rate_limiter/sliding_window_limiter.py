from collections import deque
from datetime import datetime
import threading
import time
from base_limiter import BaseLimiter


class SlidingWindowLimiter(BaseLimiter):
    def __init__(self, max_requests, window_size):
        self.max_requests = max_requests
        self.window_size = window_size
        self.request_timestamps = deque()
        self.request_history = []
        self.lock = threading.Lock()

    def _clean_expired_requests(self, current_time):
        """移除窗口外的過期請求"""
        window_start = current_time - self.window_size

        # 從最舊的請求開始移除，直到遇到未過期的
        while self.request_timestamps and self.request_timestamps[0] <= window_start:
            self.request_timestamps.popleft()

    def is_allowed(self, client_id):
        """檢查請求是否被允許"""
        with self.lock:
            current_time = time.time()

            # 清理過期的請求
            self._clean_expired_requests(current_time)

            # 檢查是否超過限制
            if len(self.request_timestamps) < self.max_requests:
                # 允許請求，記錄時間戳
                self.request_timestamps.append(current_time)
                allowed = True
            else:
                allowed = False

            # 記錄請求歷史
            self.request_history.append({
                'time': datetime.now().strftime('%H:%M:%S'),
                'user': client_id,
                'status': '成功' if allowed else '拒絕',
                'count_after': len(self.request_timestamps),
            })

            # 只保留最近20筆記錄
            if len(self.request_history) > 20:
                self.request_history = self.request_history[-20:]

            return allowed, {}

    def get_status(self):
        """獲取當前狀態"""
        with self.lock:
            current_time = time.time()

            # 清理過期請求
            self._clean_expired_requests(current_time)

            return {
                'current_count': len(self.request_timestamps),
                'max_requests': self.max_requests,
                'remaining': self.max_requests - len(self.request_timestamps),
                'algorithm': 'Sliding Window'
            }

    def reset(self):
        with self.lock:
            self.request_timestamps.clear()
            self.request_history = []
