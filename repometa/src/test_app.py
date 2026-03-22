from typing import List, Optional
from pydantic import BaseModel

app = "DummyApp"

class User(BaseModel):
    """User data model."""
    id: int
    name: str
    email: Optional[str] = None

class UserService:
    """Business logic for User."""
    def __init__(self, db_conn: str):
        self.db_conn = db_conn

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        # This implementation logic should be DROPPED by PRMG
        if user_id <= 0:
            raise ValueError("Invalid ID")
        print(f"Fetching {user_id} from {self.db_conn}")
        if user_id == 1:
            return User(id=1, name="Alice", email="alice@example.com")
        return None

# The FastAPI Plugin should catch these decorators
@app.get("/users/{user_id}", response_model=User)
async def read_user(user_id: int, q: Optional[str] = None) -> User:
    """
    Fetch a user by ID.
    Returns the user object if found.
    """
    # This logic should also be DROPPED
    service = UserService("sqlite://")
    user = service.get_user_by_id(user_id)
    if not user:
        return User(id=-1, name="Not Found")
    return user

@app.post("/users/")
async def create_user(user: User) -> User:
    # Logic to create user...
    return user
