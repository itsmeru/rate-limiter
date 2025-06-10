import redis
import time
import json
from datetime import datetime
from base_limiter import BaseLimiter


class LeakyBucketLimiter(BaseLimiter):
    """
    Leaky Bucket Rate Limiter implementation using Redis.

    Models a bucket with a hole at the bottom that leaks at a constant rate.
    Incoming requests fill the bucket, and requests leak out at a steady pace.
    Provides smooth, consistent output rate regardless of input bursts.

    Algorithm: Leaky Bucket
    - Bucket has a maximum capacity for queued requests
    - Requests "leak out" at a constant rate (processed)
    - New requests fill the bucket up to capacity
    - Overflow requests are rejected
    - Output rate is always smooth and predictable
    """

    def __init__(self, capacity, leak_rate, redis_client=None):
        """
        Initialize the leaky bucket rate limiter.
        :param capacity: Maximum capacity of the bucket (queue size).
        :param leak_rate: Number of requests that leak out per second.
        :param redis_client: Redis client instance (optional).
        """
        self.capacity = capacity
        self.leak_rate = leak_rate
        self.redis_client = redis_client or redis.Redis(
            host='redis',
            port=6379,
            db=0,
            decode_responses=True
        )

        self.queue_size_key = "leaky_bucket_queue_size"
        self.last_leak_key = "leaky_bucket_last_leak"
        self.history_key = "leaky_bucket_history"

        self._initialize_bucket()

    def _initialize_bucket(self):
        """
        Initialize Leaky Bucket state in Redis.
        Sets bucket to empty state if no previous state exists.
        """
        if not self.redis_client.exists(self.queue_size_key):
            self.redis_client.set(self.queue_size_key, 0.0)
            self.redis_client.set(self.last_leak_key, time.time())

    def _leak_requests(self):
        """
        Leak requests from bucket based on elapsed time.

        Algorithm:
        1. Calculate time passed since last leak
        2. Calculate requests to leak (time_passed * leak_rate)
        3. Reduce queue size by leaked requests (minimum 0)
        4. Update Redis with new state

        This simulates the constant "dripping" of the leaky bucket.

        :return: Current queue size after leaking.
        """
        current_time = time.time()

        current_queue_size = float(self.redis_client.get(self.queue_size_key) or 0)
        last_leak_time = float(self.redis_client.get(self.last_leak_key) or current_time)

        time_passed = current_time - last_leak_time
        requests_to_leak = time_passed * self.leak_rate

        new_queue_size = max(0, current_queue_size - requests_to_leak)

        self.redis_client.set(self.queue_size_key, new_queue_size)
        self.redis_client.set(self.last_leak_key, current_time)

        return new_queue_size

    def is_allowed(self, client_id, cost=1):
        """
        Check if a request is allowed to enter the leaky bucket.

        Algorithm:
        1. Leak requests based on elapsed time
        2. Check if bucket has space for new request
        3. If yes, add request to queue (increase queue size)
        4. If no, reject request (bucket overflow)
        5. Record request history

        :param client_id: The client identifier for logging.
        :param cost: Queue space required for this request.
        :return: Tuple (allowed: bool, info: dict with queue info).
        """
        current_time = time.time()
        current_queue_size = self._leak_requests()

        if current_queue_size + cost <= self.capacity:
            new_queue_size = current_queue_size + cost
            self.redis_client.set(self.queue_size_key, new_queue_size)
            allowed = True
            final_queue_size = new_queue_size
        else:
            allowed = False
            final_queue_size = current_queue_size

        self._add_history_to_redis(client_id, allowed, final_queue_size, cost, current_time)

        return allowed, {
            'queue_position': final_queue_size if allowed else None,
            'queue_size': final_queue_size
        }

    def _add_history_to_redis(self, client_id, allowed, queue_size_after, cost, request_time):
        """
        Add request history to shared Redis storage.
        :param client_id: Client identifier.
        :param allowed: Whether request was allowed.
        :param queue_size_after: Queue size after processing request.
        :param cost: Queue space requested.
        :param request_time: Timestamp of the request.
        """
        history_record = {
            'time': datetime.fromtimestamp(request_time).strftime('%H:%M:%S.%f')[:-3],
            'user': client_id,
            'status': '成功' if allowed else '拒絕',
            'count_after': round(queue_size_after, 2),
            'cost': cost,
            'timestamp': request_time,
            'algorithm': 'leaky_bucket'
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
        Get current leaky bucket status.

        Automatically leaks requests and returns current state.

        :return: Dictionary containing current status information.
        """
        current_queue_size = self._leak_requests()
        time_to_empty = current_queue_size / self.leak_rate if self.leak_rate > 0 else 0

        return {
            'current_count': round(current_queue_size, 2),
            'max_requests': self.capacity,
            'remaining': round(self.capacity - current_queue_size, 2),
            'time_remaining': round(time_to_empty, 2),
            'algorithm': 'Leaky Bucket',
            'queue_size': round(current_queue_size, 2),
            'capacity': self.capacity,
            'leak_rate': self.leak_rate,
            'time_to_empty': round(time_to_empty, 2)
        }

    def reset(self):
        """
        Reset leaky bucket state to empty.
        Clears queue and resets leak timing.
        """
        # Reset queue size to empty
        self.redis_client.set(self.queue_size_key, 0.0)
        self.redis_client.set(self.last_leak_key, time.time())

        # Clear history records
        self.redis_client.delete(self.history_key)

    def get_bucket_visualization(self):
        """
        Get visual representation of current bucket state.
        :return: Dictionary with visualization data.
        """
        current_queue_size = self._leak_requests()
        fill_percentage = (current_queue_size / self.capacity) * 100

        # Create simple text visualization
        filled_blocks = int((current_queue_size / self.capacity) * 10)
        empty_blocks = 10 - filled_blocks

        visual = "🟦" * filled_blocks + "⬜" * empty_blocks

        return {
            'visual': visual,
            'percentage': round(fill_percentage, 1),
            'queue_size': round(current_queue_size, 2),
            'capacity': self.capacity
        }
