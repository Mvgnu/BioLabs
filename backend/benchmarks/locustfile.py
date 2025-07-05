from locust import HttpUser, task, between

class LabUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        payload = {"email": "load@lab.com", "password": "password"}
        r = self.client.post("/api/auth/register", json=payload)
        if r.status_code != 200:
            r = self.client.post("/api/auth/login", data={"username": payload["email"], "password": payload["password"]})
        token = r.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {token}"}

    @task(3)
    def list_inventory(self):
        self.client.get("/api/inventory/items", headers=self.headers)

    @task(1)
    def create_item(self):
        data = {"name": "bench item", "type": "sample"}
        self.client.post("/api/inventory/items", json=data, headers=self.headers)
