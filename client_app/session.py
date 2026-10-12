from typing import Optional, Dict, Any, List
import httpx

API_BASE_URL = "http://127.0.0.1:8000"


class AppSession:
    token: Optional[str] = None
    user: Optional[Dict[str, Any]] = None
    active_firm_id: Optional[str] = None
    active_firm_name: Optional[str] = None

    @classmethod
    def is_logged_in(cls) -> bool:
        return cls.token is not None

    @classmethod
    def get_role(cls) -> Optional[str]:
        return cls.user.get("role") if cls.user else None

    @classmethod
    def clear(cls):
        cls.token = None
        cls.user = None
        cls.active_firm_id = None
        cls.active_firm_name = None


class ApiClient:
    @staticmethod
    def _headers() -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if AppSession.token:
            headers["Authorization"] = f"Bearer {AppSession.token}"
        if AppSession.active_firm_id:
            headers["X-Active-Firm-ID"] = AppSession.active_firm_id
        return headers

    @classmethod
    async def login(cls, username_or_email: str, password: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{API_BASE_URL}/api/v1/auth/login",
                json={"username_or_email": username_or_email, "password": password},
            )
            if resp.status_code != 200:
                detail = resp.json().get("detail", "Login failed")
                raise ValueError(detail)

            data = resp.json()
            AppSession.token = data["access_token"]
            AppSession.user = data["user"]

            if AppSession.user["role"] == "firm_admin":
                AppSession.active_firm_id = AppSession.user.get("firm_id")
                AppSession.active_firm_name = f"Firm: {AppSession.active_firm_id}"

            return data

    @classmethod
    async def fetch_available_firms(cls) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{API_BASE_URL}/api/v1/auth/available-firms",
                headers=cls._headers(),
            )
            if resp.status_code == 200:
                return resp.json()
            return []

    @classmethod
    async def register_user(cls, user_payload: Dict[str, Any]) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{API_BASE_URL}/api/v1/auth/register",
                json=user_payload,
                headers=cls._headers(),
            )
            if resp.status_code not in (200, 201):
                detail = resp.json().get("detail", "Registration failed")
                raise ValueError(detail)
            return resp.json()
    @classmethod
    async def fetch_items_by_firm(cls, firm_id: str) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{API_BASE_URL}/api/v1/items/by-firm/{firm_id}",
                headers=cls._headers(),
            )
            if resp.status_code == 200:
                return resp.json()
            return []

    @classmethod
    async def create_item(cls, payload: Dict[str, Any], firm_id: Optional[str] = None) -> Dict[str, Any]:
        params = {"firm_id": firm_id} if firm_id else {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{API_BASE_URL}/api/v1/items/register",
                json=payload,
                params=params,
                headers=cls._headers(),
            )
            if resp.status_code not in (200, 201):
                detail = resp.json().get("detail", "Failed to create item")
                raise ValueError(detail)
            return resp.json()

    @classmethod
    async def update_item(cls, item_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.put(
                f"{API_BASE_URL}/api/v1/items/{item_id}",
                json=payload,
                headers=cls._headers(),
            )
            if resp.status_code != 200:
                detail = resp.json().get("detail", "Failed to update item")
                raise ValueError(detail)
            return resp.json()

    @classmethod
    async def fetch_stock_by_firm(cls, firm_id: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {"category": category} if category else {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{API_BASE_URL}/api/v1/stocks/by-firm/{firm_id}",
                params=params,
                headers=cls._headers(),
            )
            if resp.status_code == 200:
                return resp.json()
            return []

    @classmethod
    async def adjust_stock(cls, payload: Dict[str, Any], firm_id: Optional[str] = None) -> Dict[str, Any]:
        params = {"firm_id": firm_id} if firm_id else {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{API_BASE_URL}/api/v1/stocks/adjust",
                json=payload,
                params=params,
                headers=cls._headers(),
            )
            if resp.status_code != 200:
                detail = resp.json().get("detail", "Stock adjustment failed")
                raise ValueError(detail)
            return resp.json()

    @classmethod
    async def fetch_purchases_by_firm(cls, firm_id: str) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{API_BASE_URL}/api/v1/purchases/by-firm/{firm_id}",
                headers=cls._headers(),
            )
            if resp.status_code == 200:
                return resp.json()
            return []

    @classmethod
    async def record_purchase(cls, payload: Dict[str, Any], firm_id: Optional[str] = None) -> Dict[str, Any]:
        params = {"firm_id": firm_id} if firm_id else {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{API_BASE_URL}/api/v1/purchases/record",
                json=payload,
                params=params,
                headers=cls._headers(),
            )
            if resp.status_code not in (200, 201):
                detail = resp.json().get("detail", "Failed to record purchase")
                raise ValueError(detail)
            return resp.json()

    @classmethod
    async def fetch_expenses_by_firm(cls, firm_id: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {"category": category} if category else {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{API_BASE_URL}/api/v1/expenses/by-firm/{firm_id}",
                params=params,
                headers=cls._headers(),
            )
            if resp.status_code == 200:
                return resp.json()
            return []

    @classmethod
    async def record_expense(cls, payload: Dict[str, Any], firm_id: Optional[str] = None) -> Dict[str, Any]:
        params = {"firm_id": firm_id} if firm_id else {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{API_BASE_URL}/api/v1/expenses/record",
                json=payload,
                params=params,
                headers=cls._headers(),
            )
            if resp.status_code not in (200, 201):
                detail = resp.json().get("detail", "Failed to record expense")
                raise ValueError(detail)
            return resp.json()

    @classmethod
    async def fetch_batches_by_firm(cls, firm_id: str) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{API_BASE_URL}/api/v1/batches/by-firm/{firm_id}",
                headers=cls._headers(),
            )
            if resp.status_code == 200:
                return resp.json()
            return []

    @classmethod
    async def create_batch(cls, payload: Dict[str, Any], firm_id: Optional[str] = None) -> Dict[str, Any]:
        params = {"firm_id": firm_id} if firm_id else {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{API_BASE_URL}/api/v1/batches/create",
                json=payload,
                params=params,
                headers=cls._headers(),
            )
            if resp.status_code not in (200, 201):
                detail = resp.json().get("detail", "Failed to create batch")
                raise ValueError(detail)
            return resp.json()

    @classmethod
    async def log_harvest(cls, payload: Dict[str, Any], firm_id: Optional[str] = None) -> Dict[str, Any]:
        params = {"firm_id": firm_id} if firm_id else {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{API_BASE_URL}/api/v1/batches/harvest/log",
                json=payload,
                params=params,
                headers=cls._headers(),
            )
            if resp.status_code not in (200, 201):
                detail = resp.json().get("detail", "Failed to log harvest")
                raise ValueError(detail)
            return resp.json()

    @classmethod
    async def fetch_harvest_logs(cls, batch_id: str) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{API_BASE_URL}/api/v1/batches/harvest/logs/{batch_id}",
                headers=cls._headers(),
            )
            if resp.status_code == 200:
                return resp.json()
            return []

    @classmethod
    async def fetch_farm_reports(
            cls,
            firm_id: str,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
            year: Optional[int] = None,
            batch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        params = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if year:
            params["year"] = year
        if batch_id and batch_id != "ALL":
            params["batch_id"] = batch_id

        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(
                f"{API_BASE_URL}/api/v1/reports/summary/{firm_id}",
                params=params,
                headers=cls._headers(),
            )
            if resp.status_code == 200:
                return resp.json()
            return {}