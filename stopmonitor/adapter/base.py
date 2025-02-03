from abc import ABC, abstractmethod


class AdapterInterface(ABC):

    @abstractmethod
    def find_stops(self, lookup_name: str) -> dict:
        pass

    @abstractmethod
    async def find_departures(self, stop_id: str, num_results: int, order_type: str = 'estimated_time', offset_seconds: int = 0) -> dict:
        pass