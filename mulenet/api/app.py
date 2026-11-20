"""FastAPI app: REST + WebSocket. Thin layer over mulenet.runtime.Runtime. WRITTEN, NOT EXECUTED in the build sandbox
(fastapi not installed there). SYNTHETIC DATA ONLY."""
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from ..config import load_config, ROOT
from ..runtime import Runtime


class AttackReq(BaseModel):
    pattern: Optional[str] = None
    size: Optional[int] = Field(None, ge=3, le=30)
    depth: Optional[int] = Field(None, ge=2, le=6)
    hop_gap_min: Optional[float] = Field(None, gt=0)
    hop_gap_max: Optional[float] = Field(None, gt=0)
    split_ratio: Optional[float] = Field(None, gt=0, lt=1)


class ThresholdReq(BaseModel):
    flag_at: Optional[float] = None
    hold_at: Optional[float] = None
    freeze_at: Optional[float] = None


class ControlReq(BaseModel):
    speed: Optional[float] = Field(None, gt=0, le=200)
    paused: Optional[bool] = None


def create_app(cfg=None, runtime=None) -> FastAPI:
    cfg = cfg or load_config(); rt = runtime or Runtime(cfg); token = os.environ.get("MULENET_ADMIN_TOKEN")

    @asynccontextmanager
    async def lifespan(app):
        rt.start(); yield; await rt.stop()

    app = FastAPI(title="MuleNet-Graph (SYNTHETIC DATA)", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=cfg["api"]["cors_origins"], allow_methods=["*"], allow_headers=["*"])
    app.state.rt = rt

    def admin(x_admin_token: Optional[str] = Header(None)):     # optional shared secret for public demos
        if token and x_admin_token != token:
            raise HTTPException(401, "admin token required (X-Admin-Token)")

    @app.get("/api/health")
    def health(): return {"status": "ok", "synthetic": True, "scorer": rt.scorer_name, "stream_backend": cfg["stream"]["backend"]}

    @app.get("/api/state")
    def state(): return rt.snapshot()

    @app.get("/api/metrics")
    def metrics(): return rt.metrics()

    @app.get("/api/thresholds")
    def get_th(): return rt.decision.th

    @app.post("/api/thresholds", dependencies=[Depends(admin)])
    def set_th(r: ThresholdReq):
        try: rt.decision.set_thresholds(**r.model_dump())
        except ValueError as e: raise HTTPException(400, str(e))
        return rt.decision.th

    @app.post("/api/attack", dependencies=[Depends(admin)])
    def attack(r: AttackReq):
        gap = None
        if r.hop_gap_min is not None or r.hop_gap_max is not None:
            gap = [r.hop_gap_min or 2.0, r.hop_gap_max or max((r.hop_gap_min or 2.0) + 1, 30.0)]
        try: return rt.launch_attack(pattern=r.pattern, size=r.size, depth=r.depth, hop_gap=gap, split_ratio=r.split_ratio)
        except ValueError as e: raise HTTPException(400, str(e))

    @app.post("/api/control", dependencies=[Depends(admin)])
    def control(r: ControlReq):
        if r.speed is not None: rt.speed = r.speed
        if r.paused is not None: rt.paused = r.paused
        return {"speed": rt.speed, "paused": rt.paused}

    @app.post("/api/reset", dependencies=[Depends(admin)])
    async def reset():
        await rt.reset(); return {"ok": True}

    @app.get("/api/explain/{node}")
    def explain(node: str):
        from ..explain.explain import explain_node
        return explain_node(rt, node)

    @app.post("/api/release/{node}", dependencies=[Depends(admin)])
    def release(node: str): return rt.release(node)

    @app.websocket("/ws")
    async def ws(sock: WebSocket):
        await sock.accept(); q = rt.hub.subscribe()
        try:
            await sock.send_json({"type": "snapshot", "data": rt.snapshot()})
            while True: await sock.send_json(await q.get())
        except (WebSocketDisconnect, RuntimeError): pass
        finally: rt.hub.unsubscribe(q)

    static = ROOT / cfg["api"]["static_dir"]
    if (static / "index.html").exists():                        # serve built dashboard (Phase 5) from the same origin
        app.mount("/", StaticFiles(directory=static, html=True), name="ui")
    return app


app = create_app()
