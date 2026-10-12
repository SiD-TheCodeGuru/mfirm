import httpx
from typing import Optional, Dict, Any, List

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
    def _get_headers() -> Dict[str, str]:
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

            # If user is firm_admin, assign their firm statically
            if AppSession.user["role"] == "firm_admin":
                AppSession.active_firm_id = AppSession.user.get("firm_id")
                AppSession.active_firm_name = f"Firm: {AppSession.active_firm_id}"

            return data

    @classmethod
    async def fetch_available_firms(cls) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{API_BASE_URL}/api/v1/auth/available-firms",
                headers=cls._get_headers(),
            )
            if resp.status_code == 200:
                return resp.json()
            return []