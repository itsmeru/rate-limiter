from abc import ABC, abstractmethod


class BaseLimiter(ABC):

    @abstractmethod
    def is_allowed(self, client_id: str, cost: int = 1):
        pass

    @abstractmethod
    def get_status(self):
        pass

    @abstractmethod
    def reset(self):
        pass
