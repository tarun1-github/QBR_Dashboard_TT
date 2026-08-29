from app.db import SessionLocal
from sqlalchemy import text

try:
    db = SessionLocal()

    result = db.execute(
        text("SELECT DB_NAME() AS DatabaseName, @@SERVERNAME AS ServerName")
    ).mappings().first()

    print("====================================")
    print("DATABASE CONNECTION SUCCESS")
    print("Server  :", result["ServerName"])
    print("Database:", result["DatabaseName"])
    print("====================================")

    users = db.execute(
        text("""
            SELECT UserID, Username, DisplayName, RoleName,
                   MustSetPassword, IsActive
            FROM qbr.AppUser
            ORDER BY UserID
        """)
    ).mappings().all()

    print("\nQBR USERS:")
    for user in users:
        print(
            user["Username"],
            "|",
            user["DisplayName"],
            "|",
            user["RoleName"],
            "| MustSetPassword:",
            user["MustSetPassword"]
        )

except Exception as e:
    print("\nDATABASE CONNECTION FAILED")
    print(e)

finally:
    try:
        db.close()
    except:
        pass