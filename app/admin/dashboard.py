from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from app.db.models import all_users

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def dashboard():
    rows = ""
    for u in all_users():
        rows += f"""
        <tr>
        <td>{u['telegram_id']}</td>
        <td>{u['email']}</td>
        <td>{u['banned']}</td>
        </tr>
        """

    return f"""
    <html>
    <head>
    <title>Admin Dashboard</title>
    <style>
    body{{background:#111;color:#eee;font-family:Arial}}
    table{{border-collapse:collapse;width:100%}}
    td,th{{border:1px solid #444;padding:8px}}
    </style>
    </head>
    <body>
    <h2>📊 Gmail Platform Admin</h2>
    <table>
    <tr><th>Telegram ID</th><th>Email</th><th>Banned</th></tr>
    {rows}
    </table>
    </body>
    </html>
    """