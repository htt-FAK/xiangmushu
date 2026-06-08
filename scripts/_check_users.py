import sqlite3, os

db = "data/auth.sqlite3"
if not os.path.exists(db):
    print(f"No {db} found")
else:
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cur.fetchall()
    print("Tables:", [t[0] for t in tables])
    for t in tables:
        tname = t[0]
        cur.execute(f"SELECT * FROM [{tname}] LIMIT 5")
        cols = [d[0] for d in cur.description]
        print(f"\n{tname}: cols={cols}")
        for r in cur.fetchall():
            # mask password_hash
            row = []
            for i, v in enumerate(r):
                if cols[i] == "password_hash":
                    row.append(str(v)[:20] + "...")
                else:
                    row.append(v)
            print(f"  {row}")
    conn.close()
