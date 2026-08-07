import sqlite3

conn = sqlite3.connect("mes.db")
cursor = conn.cursor()

# Print tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", cursor.fetchall())

try:
    cursor.execute("SELECT * FROM liveupdate_stream LIMIT 5")
    rows = cursor.fetchall()
    print("liveupdate_stream rows:")
    for row in rows:
        print(row)
except Exception as e:
    print("Error querying liveupdate_stream:", e)

try:
    cursor.execute("SELECT * FROM events LIMIT 5")
    rows = cursor.fetchall()
    print("events rows:")
    for row in rows:
        print(row)
except Exception as e:
    print("Error querying events:", e)

conn.close()