from data_access_layer.database import Database

db = Database()
db.reset_database()
print("✓ Tables dropped and public schema recreated")
