"""
Locust Load Testing — Performance benchmarks for Mem0 API.

Usage:
    locust -f tests/load_test.py --host=http://localhost:8000
    # Open http://localhost:8089 in browser

    # Headless mode
    locust -f tests/load_test.py --host=http://localhost:8000 --headless -u 100 -r 10 --run-time 60s
"""

from locust import HttpUser, task, between, events
import json
import logging
import time

logger = logging.getLogger(__name__)


class MemoryUser(HttpUser):
    """Simulates a typical Mem0 API user."""
    wait_time = between(0.5, 2.0)
    user_id = "load_test_user"

    def on_start(self):
        """Setup: authenticate if needed."""
        self.headers = {"Content-Type": "application/json"}
        # If JWT is enabled, get a token here
        # token = self._get_token()
        # self.headers["Authorization"] = f"Bearer {token}"

    @task(10)
    def add_memory(self):
        """Add a single memory."""
        payload = {
            "messages": [{"role": "user", "content": f"User likes {self._random_topic()}"}],
            "user_id": self.user_id,
        }
        with self.client.post("/memories", json=payload, headers=self.headers, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                response.success()  # Rate limiting is expected
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(8)
    def search_memories(self):
        """Search for memories."""
        payload = {
            "query": f"tell me about {self._random_topic()}",
            "user_id": self.user_id,
        }
        with self.client.post("/search", json=payload, headers=self.headers, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(5)
    def get_all_memories(self):
        """Get all memories with pagination."""
        with self.client.get(
            f"/memories?user_id={self.user_id}&limit=10",
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(3)
    def health_check(self):
        """Health check endpoint."""
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")

    @task(2)
    def get_single_memory(self):
        """Get a specific memory (requires existing memory)."""
        # First get all to find a memory ID
        resp = self.client.get(f"/memories?user_id={self.user_id}&limit=1", headers=self.headers)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            if items:
                memory_id = items[0].get("id") or items[0].get("memory_id")
                if memory_id:
                    with self.client.get(
                        f"/memories/{memory_id}",
                        headers=self.headers,
                        catch_response=True,
                    ) as response:
                        if response.status_code == 200:
                            response.success()
                        else:
                            response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def bulk_add(self):
        """Bulk add memories."""
        items = [
            {
                "messages": [{"role": "user", "content": f"Bulk memory {i} about {self._random_topic()}"}],
                "user_id": self.user_id,
            }
            for i in range(5)
        ]
        payload = {"items": items}
        with self.client.post("/memories/bulk", json=payload, headers=self.headers, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    def _random_topic(self):
        """Generate random topic for variety."""
        import random
        topics = [
            "pizza", "travel", "music", "coding", "books",
            "movies", "sports", "cooking", "gaming", "art",
            "science", "history", "nature", "technology", "fashion",
        ]
        return random.choice(topics)


class HeavyUser(HttpUser):
    """Simulates a power user with higher request rate."""
    wait_time = between(0.1, 0.5)
    user_id = "heavy_user"

    @task
    def rapid_search(self):
        """Rapid fire searches."""
        import random
        queries = [
            "what do I know about AI",
            "my preferences",
            "recent memories",
            "user profile",
            "conversation history",
        ]
        payload = {
            "query": random.choice(queries),
            "user_id": self.user_id,
        }
        self.client.post("/search", json=payload, headers={"Content-Type": "application/json"})


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    logger.info("Load test starting...")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    logger.info("Load test completed.")
    # Print summary stats
    stats = environment.runner.stats
    logger.info(f"Total requests: {stats.total.num_requests}")
    logger.info(f"Total failures: {stats.total.num_failures}")
    logger.info(f"Average response time: {stats.total.avg_response_time:.0f}ms")
    logger.info(f"95th percentile: {stats.total.get_response_time_percentile(0.95):.0f}ms")
    logger.info(f"99th percentile: {stats.total.get_response_time_percentile(0.99):.0f}ms")
