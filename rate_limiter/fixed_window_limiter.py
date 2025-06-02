import threading
import time
from datetime import datetime
from base_limiter import BaseLimiter


class FixedWindowRateLimiter(BaseLimiter):
    def __init__(self, max_requests, window_size):
        self.max_requests = max_requests
        self.window_size = window_size
        self.current_count = 0
        self.window_start = 0
        self.request_history = []
        self.lock = threading.Lock()

    def is_allowed(self, client_id):
        current_time = time.time()
        current_window_start = int(current_time // self.window_size) * self.window_size

        window_reset = False
        if current_window_start > self.window_start:
            self.current_count = 0
            self.window_start = current_window_start
            window_reset = True

        if self.current_count < self.max_requests:
            self.current_count += 1
            allowed = True
        else:
            allowed = False

        self.request_history.append({
            'time': datetime.now().strftime('%H:%M:%S'),
            'user': client_id,
            'status': '成功' if allowed else '拒絕',
            'count_after': self.current_count,
            'window_reset': window_reset
        })

        if len(self.request_history) > 20:
            self.request_history = self.request_history[-20:]

        return allowed, {'window_reset': window_reset}

    def get_status(self):
        with self.lock:
            current_time = time.time()
            window_end = self.window_start + self.window_size
            time_remaining = max(0, window_end - current_time)

            return {
                'current_count': self.current_count,
                'max_requests': self.max_requests,
                'remaining': self.max_requests - self.current_count,
                'time_remaining': time_remaining,
                'algorithm': 'Fixed Window'
            }

    def reset(self):
        with self.lock:
            self.current_count = 0
            self.request_history = []
