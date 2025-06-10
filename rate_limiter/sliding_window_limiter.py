import redis
import time
import json
from datetime import datetime
from base_limiter import BaseLimiter


class SlidingWindowLimiter(BaseLimiter):
    """
    Sliding Window Rate Limiter implementation using Redis.

    Uses a truly sliding window that moves continuously with time.
    Maintains precise request timestamps and removes expired ones dynamically.

    Algorithm: Sliding Window
    - Stores timestamps of all requests in a sorted set
    - Continuously slides the window as time progresses
    - More precise than fixed window but requires more memory
    """

    def __init__(self, max_requests, window_size, redis_client=None):
        """
        Initialize the sliding window rate limiter.
        :param max_requests: Maximum number of requests allowed per window.
        :param window_size: Size of the sliding window in seconds.
        :param redis_client: Redis client instance (optional).
        """
        self.max_requests = max_requests
        self.window_size = window_size
        self.redis_client = redis_client or redis.Redis(
            host='redis',
            port=6379,
            db=0,
            decode_responses=True
        )

        self.timestamps_key = "sliding_window_timestamps"
        self.history_key = "sliding_window_history"

    def _remove_old_requests(self):
        """
        Remove requests that are outside the current sliding window.

        Uses Redis ZREMRANGEBYSCORE to efficiently remove timestamps
        older than (current_time - window_size).

        :return: Number of removed requests.
        """
        current_time = time.time()
        clean_threshold = current_time - self.window_size

        # Remove all timestamps older than the window
        removed_count = self.redis_client.zremrangebyscore(
            self.timestamps_key, 0, clean_threshold
        )

        # Set expiration to prevent data accumulation
        if self.redis_client.exists(self.timestamps_key):
            self.redis_client.expire(self.timestamps_key, int(self.window_size * 2))

        return removed_count

    def is_allowed(self, client_id):
        """
        Check if a request is allowed based on sliding window rate limiting.

        Algorithm:
        1. Remove expired requests from the sliding window
        2. Check current request count in window
        3. If under limit, add current request timestamp
        4. Record request history

        :param client_id: The client identifier for logging.
        :return: Tuple (allowed: bool, info: dict with window info).
        """
        current_time = time.time()
        removed_count = self._remove_old_requests()
        current_count = self.redis_client.zcard(self.timestamps_key)

        if current_count < self.max_requests:
            unique_timestamp = f"{current_time:.6f}_{client_id}_{time.time_ns()}"
            self.redis_client.zadd(self.timestamps_key, {unique_timestamp: current_time})

            allowed = True
            final_count = self.redis_client.zcard(self.timestamps_key)
        else:
            allowed = False
            final_count = current_count

        self._add_history_to_redis(client_id, allowed, final_count, current_time)

        return allowed, {
            'window_requests': final_count,
            'removed_requests': removed_count
        }

    def _add_history_to_redis(self, client_id, allowed, count, request_time):
        """
        Add request history to shared Redis storage.
        :param client_id: Client identifier.
        :param allowed: Whether request was allowed.
        :param count: Current request count in window.
        :param request_time: Timestamp of the request.
        """
        history_record = {
            'time': datetime.fromtimestamp(request_time).strftime('%H:%M:%S'),
            'user': client_id,
            'status': '成功' if allowed else '拒絕',
            'count_after': count,
            'timestamp': request_time,
            'algorithm': 'sliding_window'
        }

        # Add to Redis list (newest first)
        self.redis_client.lpush(self.history_key, json.dumps(history_record))

        self.redis_client.ltrim(self.history_key, 0, 49)

    @property
    def request_history(self):
        """
        Get shared request history from Redis.
        :return: List of recent request records.
        """
        history_data = self.redis_client.lrange(self.history_key, 0, 19)
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
        Get current sliding window status.

        Always returns up-to-date information by cleaning expired
        requests before calculating current state.

        :return: Dictionary containing current status information.
        """
        current_time = time.time()

        clean_threshold = current_time - self.window_size
        self.redis_client.zremrangebyscore(self.timestamps_key, 0, clean_threshold)

        total_requests = self.redis_client.zcard(self.timestamps_key)

        return {
            'current_count': total_requests,
            'max_requests': self.max_requests,
            'remaining': max(0, self.max_requests - total_requests),
            'algorithm': 'Sliding Window',
            'window_size': self.window_size,
            'time_remaining': 0
        }

    def get_client_status(self, client_id):
        """
        Get global status (since this is a global rate limiter).
        All clients share the same sliding window.
        :param client_id: Client identifier (ignored in global limiter).
        :return: Same as get_status() since all clients share global limit.
        """
        return self.get_status()

    def reset(self):
        """
        Reset sliding window rate limiter state.
        Clears all stored timestamps and history records.
        """
        self.redis_client.delete(self.timestamps_key)
        self.redis_client.delete(self.history_key)
