from fastapi import FastAPI
from app.db import c

app = FastAPI()

@app.get("/")
def root():
    return {"status": "running"}

@app.get("/stats")
def stats():
    c.execute("SELECT COUNT(*) FROM users")
    users = c.fetchone()[0]
    return {"users": users}