import logging
from fastapi import FastAPI, Depends, HTTPException, Request, Form, status, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from typing import List, Dict, Optional

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import database engine, models, and IRT logic
from models import (
    engine,
    Base,
    User,
    Theme,
    Item,
    TestSession,
    Response as DBResponse, # Alias to avoid conflict with FastAPI Response
    SessionStatusEnum,
    Discipline,
)
from sqlalchemy import select, func
from sqlalchemy.orm import sessionmaker
import irt_engine
from password_utils import hash_password, verify_password


# --- Pydantic Schemas for API requests ---
from pydantic import BaseModel

class UserCreate(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

logger.info("main.py: Starting module import and global execution...")

# --- Template Setup ---
try:
    templates = Jinja2Templates(directory="templates")
    logger.info("main.py: Jinja2Templates initialized.")
except Exception as e:
    logger.error(f"main.py: ERROR during Jinja2Templates initialization: {e}")
    raise # Re-raise to ensure Uvicorn sees the error

# --- Database Setup ---
try:
    Base.metadata.create_all(bind=engine)
    logger.info("main.py: Database tables ensured.")
except Exception as e:
    logger.error(f"main.py: ERROR during Base.metadata.create_all: {e}")
    raise # Re-raise to ensure Uvicorn sees the error

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
logger.info("main.py: SessionLocal initialized.")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Helper function to get a user by username
def get_user_by_username(db: Session, username: str):
    return db.execute(select(User).where(User.username == username)).scalars().first()

# --- FastAPI Application ---
app = FastAPI(
    title="QuizIQ - Adaptive Testing API",
    description="An API for managing adaptive testing sessions using IRT.",
)
logger.info("main.py: FastAPI app initialized.")

# --- Authentication Dependencies ---

async def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Dependency to get the current logged-in user."""
    session_id = request.cookies.get("session_id")
    if session_id:
        user = db.get(User, int(session_id))
        return user
    return None

# --- HTML Serving Endpoints ---

@app.get("/", response_class=HTMLResponse, tags=["Frontend"])
async def read_root(request: Request, db: Session = Depends(get_db), current_user: Optional[User] = Depends(get_current_user)):
    """Serves the main landing page."""
    users = db.execute(select(User)).scalars().all() # Still pass all users for admin/selection purposes
    disciplines = db.execute(select(Discipline)).scalars().all()
    
    message = request.cookies.get("msg")
    
    response = templates.TemplateResponse(request, "index.html", {
        "request": request, # Pass request directly for Jinja2
        "users": users, 
        "disciplines": disciplines,
        "message": message,
        "current_user": current_user
    })
    
    if message:
        response.delete_cookie("msg")
    
    return response

@app.post("/register", response_class=RedirectResponse, tags=["Authentication"])
async def register_user(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    """Handles user registration."""
    logger.info(f"Register attempt for username: {username}")
    if get_user_by_username(db, username):
        logger.warning(f"Registration failed: Username '{username}' already exists.")
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="msg", value="Registration failed: Username already exists.")
        return response
    
    hashed_password = hash_password(password)
    new_user = User(username=username, password_hash=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    logger.info(f"User '{username}' registered successfully with ID: {new_user.id}")
    
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="msg", value="Registration successful! Please log in.")
    return response

@app.post("/login", response_class=RedirectResponse, tags=["Authentication"])
async def login_user(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    """Handles user login."""
    logger.info(f"Login attempt for username: {username}")
    user = get_user_by_username(db, username)
    if not user or not user.check_password(password):
        logger.warning(f"Login failed for username: {username}")
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="msg", value="Invalid username or password.")
        return response
    
    logger.info(f"User '{username}' logged in successfully.")
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="session_id", value=str(user.id), httponly=True) # Secure the cookie
    response.set_cookie(key="msg", value=f"Welcome, {user.username}!")
    return response

@app.post("/logout", response_class=RedirectResponse, tags=["Authentication"])
async def logout_user(request: Request):
    """Handles user logout."""
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key="session_id")
    response.set_cookie(key="msg", value="You have been logged out.")
    logger.info("User logged out.")
    return response

@app.get("/profile/{user_id}", response_class=HTMLResponse, tags=["Frontend"])
async def show_user_profile(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Displays the profile page for a specific user."""
    if not current_user or current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only view your own profile.")

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Fetch test sessions for the user, eager-loading theme and responses
    test_sessions = db.execute(
        select(TestSession)
        .options(joinedload(TestSession.theme), joinedload(TestSession.responses))
        .where(TestSession.user_id == user_id)
        .order_by(TestSession.start_time.desc())
    ).scalars().unique().all()
    
    return templates.TemplateResponse(
        request,
        "profile.html",
        {"request": request, "user": user, "test_sessions": test_sessions, "current_user": current_user}
    )

@app.post("/start-test", response_class=HTMLResponse, tags=["Frontend"])
async def start_test(
    request: Request,
    theme_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) # Ensure user is logged in
):
    """
    Starts a new session from the form post and returns the test page,
    ready for HTMX to load the first question.
    """
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated to start a test.")

    user_id = current_user.id # Use ID from authenticated user
    
    # Validate user and theme existence
    # Note: user existence is implicitly checked by get_current_user.
    # We still check theme existence.
    theme = db.get(Theme, theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail=f"Theme with id {theme_id} not found.")

    # Create new session
    new_session = TestSession(
        user_id=user_id,
        theme_id=theme_id,
        status=SessionStatusEnum.started,
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    # Return the test page, which will then use HTMX to fetch the first question
    return templates.TemplateResponse(request, "test.html", {"session_id": new_session.id, "theme_name": theme.name})

# --- HTMX Partial Endpoints ---

@app.get("/themes/", response_class=HTMLResponse, tags=["HTMX"])
async def get_themes_for_discipline_htmx(request: Request, discipline_id: int = None, db: Session = Depends(get_db)):
    """
    Given a discipline_id, returns an HTML fragment of a <select>
    element with the themes for that discipline.
    """
    if not discipline_id:
        # Return an empty, disabled select if no discipline is chosen, matching the initial state in index.html
        return HTMLResponse('<label for="theme_id" class="block text-sm font-medium text-gray-300 mb-2">Select Theme</label><select id="theme_id" name="theme_id" class="w-full bg-gray-700 text-white border-gray-600 rounded-md p-2 focus:ring-blue-500 focus:border-blue-500" disabled><option>-- Select a Discipline First --</option></select>')

    themes = db.execute(select(Theme).where(Theme.discipline_id == discipline_id)).scalars().all()
    # This assumes you will create a 'partials/theme_select.html' template
    return templates.TemplateResponse(request, "partials/theme_select.html", {"themes": themes})

@app.get("/sessions/{session_id}/next-question", response_class=HTMLResponse, tags=["HTMX"])
async def get_next_question_htmx(session_id: int, request: Request, db: Session = Depends(get_db)):
    """
    Finds the next best question and returns it as an HTML fragment.
    """
    session = db.get(TestSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
		
    # Eager load the theme to get its name
    session = db.query(TestSession).options(joinedload(TestSession.theme)).filter(TestSession.id == session_id).one()


    if session.status != SessionStatusEnum.started:
        return templates.TemplateResponse(
            request,
            "partials/results.html",
            {"final_theta": session.theta_estimate, "theme_name": session.theme.name},
        )

    answered_item_ids = db.execute(select(DBResponse.item_id).where(DBResponse.session_id == session_id)).scalars().all()
    available_items = db.execute(select(Item).where(
        Item.theme_id == session.theme_id,
        Item.is_active == True,
        Item.id.notin_(answered_item_ids)
    )).scalars().all()

    if not available_items:
        session.status = SessionStatusEnum.completed
        db.commit()
        return templates.TemplateResponse(
            request,
            "partials/results.html",
            {"final_theta": session.theta_estimate, "theme_name": session.theme.name},
        )

    next_item = irt_engine.select_next_item(session.theta_estimate, available_items)
    if not next_item:
        session.status = SessionStatusEnum.completed # No more items to select
        db.commit()
        logger.warning(f"Session {session.id} completed because IRT engine could not select a next item.")
        return templates.TemplateResponse(
            request,
            "partials/results.html",
            {"final_theta": session.theta_estimate, "theme_name": session.theme.name},
        )

    question_data = {
        "item_id": next_item.id,
        "text": next_item.question_text,
        "options": next_item.options,
    }
    return templates.TemplateResponse(
        request,
        "partials/question_card.html",
        {
            "session_id": session_id,
            "question": question_data,
            "theme_name": session.theme.name,
        },
    )


@app.post("/sessions/{session_id}/answer", response_class=HTMLResponse, tags=["HTMX"])
async def submit_answer_htmx(
    session_id: int,
    request: Request,
    item_id: int = Form(...),
    user_answer: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Processes an answer and returns either the next question card or the results page.
    """
    session = db.get(TestSession, session_id)
    if not session or session.status != SessionStatusEnum.started:
        raise HTTPException(status_code=400, detail="Invalid or finished session.")

    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found.")

    is_correct = (user_answer == item.correct_option)
    
    previous_responses = db.execute(select(DBResponse).options(joinedload(DBResponse.item)).where(DBResponse.session_id == session_id)).scalars().all()
    
    response_history_for_irt = [(
        {"a_discrim": item.a_discrim, "b_diff": item.b_diff, "c_guess": item.c_guess},
        r.is_correct
    ) for r in previous_responses]
    response_history_for_irt.append((
        {"a_discrim": item.a_discrim, "b_diff": item.b_diff, "c_guess": item.c_guess},
        is_correct
    ))

    new_theta = irt_engine.estimate_theta(response_history_for_irt)
    new_se = irt_engine.calculate_standard_error(new_theta, response_history_for_irt)

    db.add(DBResponse(
        session_id=session.id,
        item_id=item.id,
        user_answer=user_answer,
        is_correct=is_correct,
        theta_after=new_theta,
        response_time_sec=0,
    ))
    
    session.theta_estimate = new_theta
    session.standard_error = new_se

    num_responses = len(response_history_for_irt)
    if new_se < 0.3 or num_responses >= 20:
        session.status = SessionStatusEnum.completed
        session.end_time = func.now()
        db.commit()
        return templates.TemplateResponse(request, "partials/results.html", {"final_theta": new_theta})
    else:
        db.commit()
        # If the test is not finished, immediately fetch the next question to send back
        return await get_next_question_htmx(session_id, request, db)

# To run the app:
# uvicorn main:app --reload