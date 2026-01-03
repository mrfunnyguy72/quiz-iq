import logging
from typing import List

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, sessionmaker

from app.core import irt as irt_engine
from app.core.evaluation import is_answer_correct_fuzzy
from app.core.security import get_password_hash
from app.models.base import (
    Base,
    Item,
    ItemTypeEnum,
    Response,
    SessionStatusEnum,
    TestSession,
    Theme,
    User,
    engine,
)

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

# --- FastAPI Application ---
app = FastAPI(
    title="QuizIQ - Adaptive Testing API",
    description="An API for managing adaptive testing sessions using IRT.",
)
logger.info("main.py: FastAPI app initialized.")

# --- HTML Serving Endpoints ---

@app.get("/", response_class=HTMLResponse, tags=["Frontend"])
async def read_root(request: Request, db: Session = Depends(get_db)):
    """Serves the main landing page."""
    # In a real app, you'd fetch all users and themes here to populate the form
    users = db.execute(select(User)).scalars().all()
    themes = db.execute(select(Theme)).scalars().all()
    return templates.TemplateResponse("index.html", {"request": request, "users": users, "themes": themes})

@app.post("/start-test", response_class=HTMLResponse, tags=["Frontend"])
async def start_test(
    request: Request,
    user_id: int = Form(...),
    theme_id: int = Form(...),
    db: Session = Depends(get_db)
):
    """
    Starts a new session from the form post and returns the test page,
    ready for HTMX to load the first question.
    """
    # Validate user and theme existence
    if not db.get(User, user_id):
        raise HTTPException(status_code=404, detail=f"User with id {user_id} not found.")
    if not db.get(Theme, theme_id):
        raise HTTPException(status_code=404, detail=f"Theme with id {theme_id} not found.")

    # Create new session
    new_session = TestSession(
        user_id=user_id,
        theme_id=theme_id,
        theta_estimate=0.0,
        standard_error=1.0,
        status=SessionStatusEnum.started,
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    # Return the test page, which will then use HTMX to fetch the first question
    return templates.TemplateResponse("test.html", {"request": request, "session_id": new_session.id})


@app.get("/register", response_class=HTMLResponse, tags=["Frontend"])
async def register_form(request: Request):
    """Serves the user registration page."""
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register", response_class=HTMLResponse, tags=["Frontend"])
async def register_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Creates a new user and returns a confirmation message."""
    # Check if user already exists
    user = db.execute(select(User).where(User.username == username)).scalars().first()
    if user:
        return HTMLResponse("<div class='text-red-500'>Username already exists.</div>")

    # Create new user
    hashed_password = get_password_hash(password)
    new_user = User(username=username, password_hash=hashed_password)
    db.add(new_user)
    db.commit()

    response = HTMLResponse("<div class='text-green-500'>User created successfully! Redirecting...</div>")
    response.headers["HX-Redirect"] = "/"
    return response


# --- HTMX Partial Endpoints ---

@app.get("/sessions/{session_id}/next-question", response_class=HTMLResponse, tags=["HTMX"])
async def get_next_question_htmx(session_id: int, request: Request, db: Session = Depends(get_db)):
    """
    Finds the next best question and returns it as an HTML fragment.
    """
    session = db.get(TestSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if session.status != SessionStatusEnum.started:
        return templates.TemplateResponse("partials/results.html", {
            "request": request,
            "final_theta": session.current_theta,
        })

    answered_item_ids = db.execute(select(Response.item_id).where(Response.session_id == session_id)).scalars().all()
    available_items = db.execute(select(Item).where(
        Item.theme_id == session.theme_id,
        Item.is_active,
        Item.id.notin_(answered_item_ids)
    )).scalars().all()

    if not available_items:
        session.status = SessionStatusEnum.completed
        db.commit()
        return templates.TemplateResponse("partials/results.html", {
            "request": request,
            "final_theta": session.theta_estimate, # Corrected: current_theta -> theta_estimate
        })

    next_item = irt_engine.select_next_item(session.theta_estimate, available_items) # Corrected: current_theta -> theta_estimate
    if not next_item:
        raise HTTPException(status_code=500, detail="IRT engine failed to select an item.")

    question_data = {
        "item_id": next_item.id,
        "text": next_item.question_text,
        "options": next_item.options,
        "type": next_item.type,
        "media_type": next_item.media_type,
        "media_url": next_item.media_url,
        "correct_option": next_item.correct_option,
    }
    return templates.TemplateResponse("partials/question_card.html", {
        "request": request,
        "session_id": session_id,
        "question": question_data
    })


@app.post("/sessions/{session_id}/answer", response_class=HTMLResponse, tags=["HTMX"])
async def submit_answer_htmx(
    session_id: int,
    request: Request,
    item_id: int = Form(...),
    user_answer: List[str] = Form(...),
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

    # Evaluation logic based on question type
    if item.type == ItemTypeEnum.OPEN_ENDED:
        is_correct = is_answer_correct_fuzzy(user_answer[0], item.correct_option[0])
    else:  # Default to multiple choice
        is_correct = (sorted(user_answer) == sorted(item.correct_option))
    
    previous_responses = db.execute(select(Response).options(joinedload(Response.item)).where(Response.session_id == session_id)).scalars().all()
    
    response_history_for_irt = [(
        {"a_discrim": r.item.a_discrim, "b_diff": r.item.b_diff, "c_guess": r.item.c_guess},
        r.is_correct
    ) for r in previous_responses]
    response_history_for_irt.append((
        {"a_discrim": item.a_discrim, "b_diff": item.b_diff, "c_guess": item.c_guess},
        is_correct
    ))

    new_theta = irt_engine.estimate_theta(response_history_for_irt)
    new_se = irt_engine.calculate_standard_error(new_theta, response_history_for_irt)

    db.add(Response(
        session_id=session.id,
        item_id=item.id,
        user_answer=", ".join(user_answer), # Store as comma-separated string
        is_correct=is_correct,
        theta_after=new_theta,
        response_time_sec=0,
    ))
    
    session.theta_estimate = new_theta # Corrected: current_theta -> theta_estimate
    session.standard_error = new_se

    num_responses = len(response_history_for_irt)
    if new_se < 0.3 or num_responses >= 20:
        session.status = SessionStatusEnum.completed
        session.end_time = func.now()
        db.commit()
        return templates.TemplateResponse("partials/results.html", {
            "request": request,
            "final_theta": new_theta,
        })
    else:
        db.commit()
        # If the test is not finished, immediately fetch the next question to send back
        return await get_next_question_htmx(session_id, request, db)

# To run the app:
# uvicorn main:app --reload
