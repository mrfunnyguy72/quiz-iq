from passlib.context import CryptContext

# Create a CryptContext for hashing and verifying passwords
# We'll use bcrypt as the default hashing algorithm
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hashes a password using the configured context."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)
