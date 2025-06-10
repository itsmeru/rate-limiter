import redis
import time
import json
from datetime import datetime
from base_limiter import BaseLimiter


class TokenBucketLimiter(BaseLimiter):
    """
    Token Bucket Rate Limiter implementation using Redis.

    Models a bucket that holds tokens which are consumed by requests.
    Tokens are continuously refilled at a constant rate.
    Allows burst traffic up to bucket capacity.

    Algorithm: Token Bucket
    - Bucket has a maximum capacity of tokens
    - Tokens are added at a constant refill rate
    - Each request consumes one or more tokens
    - Requests are allowed if sufficient tokens are available
    - Supports burst traffic when bucket is full
    """

    def __init__(self, capacity, refill_rate, redis_client=None):
        """
        Initialize the token bucket rate limiter.
        :param capacity: Maximum number of tokens in the bucket.
        :param refill_rate: Number of tokens added per second.
        :param redis_client: Redis client instance (optional).
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.redis_client = redis_client or redis.Redis(
            host='redis',
            port=6379,
            db=0,
            decode_responses=True
        )

        self.tokens_key = "token_bucket_tokens"
        self.last_refill_key = "token_bucket_last_refill"
        self.history_key = "token_bucket_history"

        self._initialize_bucket()

    def _initialize_bucket(self):
        """
        Initialize Token Bucket state in Redis.
        Sets bucket to full capacity if no previous state exists.
        """
        if not self.redis_client.exists(self.tokens_key):
            self.redis_client.set(self.tokens_key, self.capacity)
            self.redis_client.set(self.last_refill_key, time.time())

    def _refill_tokens(self):
        """
        Refill tokens based on time elapsed since last refill.

        Algorithm:
        1. Calculate time passed since last refill
        2. Calculate tokens to add (time_passed * refill_rate)
        3. Add tokens up to bucket capacity
        4. Update Redis with new token count and refill time

        :return: Current number of tokens after refill.
        """
        current_time = time.time()

        current_tokens = float(self.redis_client.get(self.tokens_key) or 0)
        last_refill_time = float(self.redis_client.get(self.last_refill_key) or current_time)

        time_passed = current_time - last_refill_time
        tokens_to_add = time_passed * self.refill_rate
        new_tokens = min(self.capacity, current_tokens + tokens_to_add)

        self.redis_client.set(self.tokens_key, new_tokens)
        self.redis_client.set(self.last_refill_key, current_time)

        return new_tokens

    def is_allowed(self, client_id, cost=1):
        """
        Check if a request is allowed based on available tokens.

        Algorithm:
        1. Refill tokens based on elapsed time
        2. Check if sufficient tokens are available
        3. If yes, consume tokens and allow request
        4. If no, reject request (tokens remain unchanged)
        5. Record request history

        :param client_id: The client identifier for logging.
        :param cost: Number of tokens required for this request.
        :return: Tuple (allowed: bool, info: dict with token info).
        """
        current_time = time.time()
        current_tokens = self._refill_tokens()

        if current_tokens >= cost:
            new_tokens = current_tokens - cost
            self.redis_client.set(self.tokens_key, new_tokens)
            allowed = True
            final_tokens = new_tokens
        else:
            allowed = False
            final_tokens = current_tokens

        self._add_history_to_redis(client_id, allowed, final_tokens, cost, current_time)

        return allowed, {
            'cost': cost if allowed else 0,
            'tokens_remaining': final_tokens
        }

    def _add_history_to_redis(self, client_id, allowed, tokens_after, cost, request_time):
        """
        Add request history to shared Redis storage.
        :param client_id: Client identifier.
        :param allowed: Whether request was allowed.
        :param tokens_after: Number of tokens remaining after request.
        :param cost: Number of tokens requested.
        :param request_time: Timestamp of the request.
        """
        history_record = {
            'time': datetime.fromtimestamp(request_time).strftime('%H:%M:%S'),
            'user': client_id,
            'status': '成功' if allowed else '拒絕',
            'count_after': round(tokens_after, 2),
            'cost': cost,
            'timestamp': request_time,
            'algorithm': 'token_bucket'
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
        Get current token bucket status.
        Automatically refills tokens and returns current state.

        :return: Dictionary containing current status information.
        """
        current_tokens = self._refill_tokens()
        tokens_needed_to_fill = self.capacity - current_tokens
        time_to_fill = tokens_needed_to_fill / self.refill_rate if self.refill_rate > 0 else 0

        return {
            'current_tokens': round(current_tokens, 2),
            'capacity': self.capacity,
            'refill_rate': self.refill_rate,
            'time_to_fill': round(time_to_fill, 2),
            'algorithm': 'Token Bucket'
        }

    def reset(self):
        """
        Reset Token Bucket state to full capacity.
        Clears all stored tokens and history records.
        """
        self.redis_client.set(self.tokens_key, self.capacity)
        self.redis_client.set(self.last_refill_key, time.time())
        self.redis_client.delete(self.history_key)

    def get_bucket_visualization(self):
        """
        Get visual representation of current bucket state.
        :return: Dictionary with visualization data.
        """
        current_tokens = self._refill_tokens()
        fill_percentage = (current_tokens / self.capacity) * 100

        filled_blocks = int((current_tokens / self.capacity) * 10)
        empty_blocks = 10 - filled_blocks

        visual = "🟦" * filled_blocks + "⬜" * empty_blocks

        return {
            'visual': visual,
            'percentage': round(fill_percentage, 1),
            'tokens': round(current_tokens, 2),
            'capacity': self.capacity
        }
