# Agent 2 (Backend & DB)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import residents, verify, logs, ws, camera

app = FastAPI(title="AI Security Access Control")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
                   allow_methods=["*"], allow_headers=["*"])
for r in (residents.router, verify.router, logs.router, ws.router, camera.router):
    app.include_router(r)

@app.get("/api/health")
def health():
    return {"status": "ok"}
