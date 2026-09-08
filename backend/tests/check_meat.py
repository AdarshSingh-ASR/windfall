import sqlite3

c = sqlite3.connect("gleaner.db")
rows = c.execute(
    "SELECT side,intent,message,created_at FROM turns WHERE event_id='evt-be7954faa7' ORDER BY created_at"
).fetchall()
for r in rows:
    print(r[3][11:19], f"[{r[0]}|{r[1]}]", r[2][:110])
