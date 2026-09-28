import sqlite3

conn = sqlite3.connect("data/pokerlab.db")
conn.execute(
    "UPDATE tournament_results SET currency = 'SAT' WHERE tournament_id = ?",
    (240582474,),
)
conn.commit()
conn.close()
print("ok")