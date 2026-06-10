from __future__ import annotations

from locust import HttpUser, between, task


class ImperialCarsUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def ask_chatbot(self):
        self.client.post(
            "/api/ask",
            json={"question": "What is the MSRP of a Toyota Camry?"},
            name="POST /api/ask",
        )

    @task(2)
    def decode_vin(self):
        self.client.get(
            "/api/vin/decode/5FNRL6H79LB123456",
            name="GET /api/vin/decode/{vin}",
        )

    @task(1)
    def health(self):
        self.client.get("/api/health", name="GET /api/health")
