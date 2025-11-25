from utils.security import hash_password, verify_password
h = hash_password("admin123")
print(h)                        # should start with $pbkdf2-sha256$
print(verify_password("admin123", h))  # True
