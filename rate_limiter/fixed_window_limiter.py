import redis
import time
import json
from datetime import datetime
from base_limiter import BaseLimiter


class FixedWindowRateLimiter(BaseLimiter):
    """
    Fixed Window Rate Limiter implementation using Redis.
    Divides time into fixed windows and limits requests per window.
    Each window resets completely when the time boundary is crossed.

    Algorithm: Fixed Window
    - Time is divided into non-overlapping windows of fixed size
    - Each window has an independent request counter
    - Counter resets to 0 when window expires
    """

    def __init__(self, max_requests, window_size, redis_client=None):
        """
        Initialize the fixed window rate limiter.
        :param max_requests: Maximum number of requests allowed per window.
        :param window_size: Size of the time window in seconds.
        :param redis_client: Redis client instance (optional).
        """
        self.max_requests = max_requests
        self.window_size = window_size
        self.history_key = "fixed_window_history"
        self.redis_client = redis_client or redis.Redis(
            host='redis',
            port=6379,
            db=0,
            decode_responses=True
        )

    def is_allowed(self, client_id):
        """
        Check if a request is allowed.
        Algorithm:
        1. Calculate current window start time
        2. Use Redis atomic operations to increment counter
        3. Set expiration to auto-cleanup old windows
        4. Check if request count exceeds limit

        :param client_id: The client identifier for logging purposes.
        :return: Tuple (allowed: bool, info: dict with window_reset flag).
        """
        current_time = time.time()
        current_window_start = int(current_time // self.window_size) * self.window_size
        window_key = f"fixed_window:{current_window_start}"

        # Atomic Redis operations using pipeline
        pipe = self.redis_client.pipeline()
        pipe.incr(window_key)  # Increment counter (creates key if not exists)
        pipe.expire(window_key, int(self.window_size) + 1)  # Auto-cleanup after window
        results = pipe.execute()

        current_count = results[0]
        allowed = current_count <= self.max_requests
        window_reset = current_count == 1  # First request in new window

        # Record request history
        self._add_history_to_redis(client_id, allowed, current_count, window_reset)

        return allowed, {'window_reset': window_reset}

    def _add_history_to_redis(self, client_id, allowed, count, window_reset):
        """
        Add request history to shared Redis storage.
        :param client_id: Client identifier.
        :param allowed: Whether request was allowed.
        :param count: Current request count in window.
        :param window_reset: Whether this is a new window.
        """
        history_record = {
            'time': datetime.now().strftime('%H:%M:%S'),
            'user': client_id,
            'status': '成功' if allowed else '拒絕',
            'count_after': count,
            'window_reset': window_reset,
            'timestamp': time.time(),
            'algorithm': 'fixed_window'
        }

        # Add to Redis list (newest first)
        self.redis_client.lpush(self.history_key, json.dumps(history_record))

        # Keep only recent 50 records
        self.redis_client.ltrim(self.history_key, 0, 49)

    @property
    def request_history(self):
        """
        Get shared request history from Redis.
        :return: List of recent request records.
        """
        history_data = self.redis_client.lrange(self.history_key, 0, 19)  # Recent 20 records
        history_list = []

        for record_json in history_data:
            try:
                record = json.loads(record_json)
                history_list.append(record)
            except json.JSONDecodeError:
                continue

        return history_list

    def get_status(self):
        """
        Get current rate limiter status.
        :return: Dictionary containing current status information.
        """
        current_time = time.time()
        current_window_start = int(current_time // self.window_size) * self.window_size
        window_key = f"fixed_window:{current_window_start}"

        # Get current count from Redis
        current_count_str = self.redis_client.get(window_key)
        current_count = int(current_count_str) if current_count_str else 0

        # Calculate remaining time in current window
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
        """
        Reset rate limiter state by clearing all data.
        This removes all window counters and history records.
        """
        # Clear history
        self.redis_client.delete(self.history_key)

        # Clear current window counter
        current_time = time.time()
        current_window_start = int(current_time // self.window_size) * self.window_size
        window_key = f"fixed_window:{current_window_start}"
        self.redis_client.delete(window_key)

    def get_window_info(self):
        """
        Get detailed information about current time window.
        :return: Dictionary with window timing information.
        """
        current_time = time.time()
        current_window_start = int(current_time // self.window_size) * self.window_size
        window_end = current_window_start + self.window_size
        time_remaining = max(0, window_end - current_time)
        time_elapsed = current_time - current_window_start

        return {
            'window_start': current_window_start,
            'window_end': window_end,
            'window_size': self.window_size,
            'time_elapsed': time_elapsed,
            'time_remaining': time_remaining,
            'progress_percentage': (time_elapsed / self.window_size) * 100
        }
