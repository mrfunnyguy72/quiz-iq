import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from main import app, get_db
from models import Base, Discipline, Theme, User, TestSession as DBTestSession, Response as DBResponse # Renamed to avoid conflicts
import pytest
from password_utils import hash_password # Import the hashing utility
from fastapi import status # Import status for HTTP status codes
from bs4 import BeautifulSoup # Import BeautifulSoup for robust HTML parsing

@pytest.fixture(scope="function")
def db_session(monkeypatch):
    """
    This fixture sets up a completely isolated, temporary, file-based SQLite database
    for each test function. It creates the database and tables, seeds them with data,
    patches the application's engine and dependencies, and tears everything down afterward.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_url = f"sqlite:///{db_path}"
        
        # Create a new engine and session for the temporary database
        test_engine = create_engine(db_url, connect_args={"check_same_thread": False})
        TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

        # Patch the engine in the models module
        monkeypatch.setattr("models.engine", test_engine)
        
        # Create tables
        Base.metadata.create_all(bind=test_engine)
        db = TestSessionLocal()
        
        # Override the app's get_db dependency
        app.dependency_overrides[get_db] = lambda: db

        try:
            # Pre-populate the database with test data
            # Hash the password for the test user
            hashed_password = hash_password("testpassword")
            user1 = User(id=1, username="testuser", password_hash=hashed_password)
            
            discipline1 = Discipline(id=1, name="Math")
            discipline2 = Discipline(id=2, name="Science")
            theme1 = Theme(id=1, name="Algebra", discipline_id=1)
            theme2 = Theme(id=2, name="Geometry", discipline_id=1)
            theme3 = Theme(id=3, name="Physics", discipline_id=2)

            db.add_all([user1, discipline1, discipline2, theme1, theme2, theme3])
            db.commit()
            
            # Add a test session for user1
            test_session = DBTestSession(
                user_id=user1.id,
                theme_id=theme1.id,
                theta_estimate=0.5,
                standard_error=0.2,
                status="completed"
            )
            db.add(test_session)
            db.commit()
            db.refresh(test_session)


            yield db
        finally:
            db.close()
            Base.metadata.drop_all(bind=test_engine)
            app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(db_session):
    """
    Provides a TestClient configured to use the isolated, temporary database.
    """
    with TestClient(app) as c:
        yield c


def test_read_root_unauthenticated(client):
    """Test the main page loads and shows login/register for unauthenticated users."""
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert "Login" in response.text
    assert "Register" in response.text
    assert "Welcome, testuser!" not in response.text # Should not see welcome message


def test_register_user_success(client):
    """Test successful user registration."""
    response = client.post("/register", data={"username": "newuser", "password": "newpassword"}, follow_redirects=False)
    assert response.status_code == status.HTTP_303_SEE_OTHER # Expect redirect
    assert response.headers["location"] == "/"
    
    # Follow redirect and check message
    followed_response = client.get(response.headers["location"], cookies=response.cookies)
    assert followed_response.status_code == status.HTTP_200_OK
    assert "Registration successful! Please log in." in followed_response.text

    # Verify user actually created
    db = app.dependency_overrides[get_db]()
    new_user = db.execute(select(User).where(User.username == "newuser")).scalars().first()
    assert new_user is not None
    assert new_user.check_password("newpassword")


def test_register_user_duplicate(client):
    """Test registration with an existing username fails."""
    # First user registration
    response = client.post("/register", data={"username": "existinguser", "password": "password"}, follow_redirects=False)
    assert response.status_code == status.HTTP_303_SEE_OTHER # Expect redirect
    
    # Attempt to register with the same username
    response = client.post("/register", data={"username": "existinguser", "password": "anotherpassword"}, follow_redirects=False)
    assert response.status_code == status.HTTP_303_SEE_OTHER # Expect redirect with error message
    
    followed_response = client.get(response.headers["location"], cookies=response.cookies)
    assert followed_response.status_code == status.HTTP_200_OK
    assert "Registration failed: Username already exists." in followed_response.text


def test_login_user_success(client):
    """Test successful user login."""
    response = client.post("/login", data={"username": "testuser", "password": "testpassword"}, follow_redirects=False)
    assert response.status_code == status.HTTP_303_SEE_OTHER # Expect redirect
    assert response.headers["location"] == "/"
    assert "session_id" in response.cookies # Check for session cookie
    
    # Follow redirect and check welcome message
    followed_response = client.get(response.headers["location"], cookies=response.cookies)
    assert followed_response.status_code == status.HTTP_200_OK
    assert "Welcome, testuser!" in followed_response.text
    # The session_id cookie is a httponly cookie, so it won't be visible in followed_response.cookies
    # We assert its presence in the initial redirect response.


def test_login_user_invalid_password(client):
    """Test login fails with invalid password."""
    response = client.post("/login", data={"username": "testuser", "password": "wrongpassword"}, follow_redirects=False)
    assert response.status_code == status.HTTP_303_SEE_OTHER # Expect redirect
    assert response.headers["location"] == "/"
    assert "session_id" not in response.cookies # No session cookie set
    
    followed_response = client.get(response.headers["location"], cookies=response.cookies)
    assert followed_response.status_code == status.HTTP_200_OK
    assert "Invalid username or password." in followed_response.text


def test_login_user_non_existent(client):
    """Test login fails for a non-existent user."""
    response = client.post("/login", data={"username": "nonexistent", "password": "anypassword"}, follow_redirects=False)
    assert response.status_code == status.HTTP_303_SEE_OTHER # Expect redirect
    assert response.headers["location"] == "/"
    assert "session_id" not in response.cookies # No session cookie set
    
    followed_response = client.get(response.headers["location"], cookies=response.cookies)
    assert followed_response.status_code == status.HTTP_200_OK
    assert "Invalid username or password." in followed_response.text


def test_logout_user(client):
    """Test successful user logout."""
    # First, log in the user to get a session
    login_response = client.post("/login", data={"username": "testuser", "password": "testpassword"}, follow_redirects=False)
    assert login_response.status_code == status.HTTP_303_SEE_OTHER
    assert "session_id" in login_response.cookies
    
    # Then, log out using the session cookie
    response = client.post("/logout", cookies=login_response.cookies, follow_redirects=False)
    assert response.status_code == status.HTTP_303_SEE_OTHER # Expect redirect
    assert response.headers["location"] == "/"
    assert "session_id" not in response.cookies # Session cookie should be deleted

    # Follow redirect and check logout message
    followed_response = client.get(response.headers["location"], cookies=response.cookies)
    assert followed_response.status_code == status.HTTP_200_OK
    assert "You have been logged out." in followed_response.text


def test_read_root_authenticated(client):
    """Test the main page loads and shows welcome message for authenticated users."""
    login_response = client.post("/login", data={"username": "testuser", "password": "testpassword"}, follow_redirects=False)
    assert login_response.status_code == status.HTTP_303_SEE_OTHER
    
    # Get the root page with the session cookie
    response = client.get("/", cookies=login_response.cookies)
    assert response.status_code == status.HTTP_200_OK
    assert "Welcome, testuser!" in response.text
    assert "Login" not in response.text # Should not see login form
    assert "Register" not in response.text # Should not see register form


def test_start_test_authenticated(client):
    """Test that an authenticated user can start a test."""
    login_response = client.post("/login", data={"username": "testuser", "password": "testpassword"}, follow_redirects=False)
    assert login_response.status_code == status.HTTP_303_SEE_OTHER

    # Start the test with the session cookie
    response = client.post("/start-test", data={"theme_id": "1"}, cookies=login_response.cookies)
    assert response.status_code == status.HTTP_200_OK # Returns the test.html page directly


def test_start_test_unauthenticated(client):
    """Test that an unauthenticated user cannot start a test."""
    response = client.post("/start-test", data={"theme_id": "1"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED # Unauthorized


def test_user_profile_access(client):
    """Test that a logged-in user can access their profile."""
    login_response = client.post("/login", data={"username": "testuser", "password": "testpassword"}, follow_redirects=False)
    assert login_response.status_code == status.HTTP_303_SEE_OTHER

    # Access the profile page with the session cookie
    response = client.get("/profile/1", cookies=login_response.cookies) # Assuming testuser has id 1
    assert response.status_code == status.HTTP_200_OK
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Check for user profile header
    h1_tag = soup.find("h1", string=lambda text: text and "User Profile: testuser" in text)
    assert h1_tag is not None
    
    # Check for test session theme (using more flexible search)
    # Find the p tag that contains the text "Theme: Algebra"
    theme_p_tag = None
    for p_tag in soup.find_all("p"):
        if "Theme: Algebra" in p_tag.get_text():
            theme_p_tag = p_tag
            break
    assert theme_p_tag is not None, "Did not find 'Theme: Algebra' in any paragraph tag."
    
    # Check for final theta, using a more robust approach
    # Find the p tag that contains the text "Final Theta: 0.500"
    theta_p_tag = None
    for p_tag in soup.find_all("p"):
        if "Final Theta: 0.500" in p_tag.get_text():
            theta_p_tag = p_tag
            break
    assert theta_p_tag is not None, "Did not find 'Final Theta: 0.500' in any paragraph tag."