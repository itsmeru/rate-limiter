from datetime import datetime
import threading
import time
from base_limiter import BaseLimiter


class TokenBucketLimiter(BaseLimiter):
    def __init__(self, capacity, refill_rate):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill_time = time.time()
        self.lock = threading.Lock()
        self.request_history = []

    def _refill_tokens(self):
        current_time = time.time()
        time_passed = current_time - self.last_refill_time

        tokens_to_add = time_passed * self.refill_rate
        self.tokens = min(self.capacity, tokens_to_add + self.tokens)

        self.last_refill_time = current_time

    def is_allowed(self, client_id, cost=1):
        with self.lock:
            self._refill_tokens()

            if self.tokens >= cost:
                self.tokens -= cost
                allowed = True
            else:
                allowed = False

            self.request_history.append({
                'time': datetime.now().strftime('%H:%M:%S'),
                'user': client_id,
                'status': '成功' if allowed else '拒絕',
                'count_after': self.tokens,
                'cost': cost
            })

            if len(self.request_history) > 20:
                self.request_history = self.request_history[-20:]

            return allowed, {'cost': cost if allowed else 0}

    def get_status(self):
        with self.lock:
            self._refill_tokens()

            tokens_needed_to_fill = self.capacity - self.tokens
            time_to_fill = tokens_needed_to_fill / self.refill_rate if self.refill_rate > 0 else 0

            return {
                'current_tokens': self.tokens,
                'capacity': self.capacity,
                'refill_rate': self.refill_rate,
                'time_to_fill': time_to_fill,
                'algorithm': 'Token Bucket'
            }

    def reset(self):
        with self.lock:
            self.tokens = self.capacity
            self.last_refill_time = time.time()
            self.request_history = []
