from fastapi import FastAPI
app = FastAPI()
@app.get("/")
def root():
    return {"ok": True, "msg": "bankers EMERGENCIA - subiu"}
@app.get("/health")
def health():
    return {"status": "alive"}
