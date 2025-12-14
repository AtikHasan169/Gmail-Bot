from fastapi import FastAPI
from app.db import c

app = FastAPI()

@app.get("/dashboard")
def dashboard():
    c.execute("SELECT COUNT(*) FROM users")
    users = c.fetchone()[0]
    return {"total_users": users}