import sqlite3

conn = sqlite3.connect("mes.db")
cursor = conn.cursor()

cursor.execute("SELECT * FROM events limit 10")

rows = cursor.fetchall()

for row in rows:
    print(row)

conn.close()