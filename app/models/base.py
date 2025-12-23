import enum
from datetime import datetime
from typing import List

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    func,
)
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, relationship

# --- Declarative Base ---
# The base class which our ORM models will inherit from.
Base = declarative_base()


# --- Enums ---

class SessionStatusEnum(enum.Enum):
    """Enum for the status of a test session."""
    started = "started"
    completed = "completed"
    terminated = "terminated"


# --- Model Definitions ---

class User(Base):
    """Represents a user in the system."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # One-to-many relationship with TestSession
    test_sessions: Mapped[List["TestSession"]] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}')>"


class Discipline(Base):
    """Represents a subject or discipline, e.g., 'Mathematics', 'History'."""
    __tablename__ = "disciplines"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # One-to-many relationship
    themes: Mapped[List["Theme"]] = relationship(back_populates="discipline")

    def __repr__(self) -> str:
        return f"<Discipline(id={self.id}, name='{self.name}')>"


class Theme(Base):
    """Represents a specific theme or topic within a discipline, e.g., 'Algebra'."""
    __tablename__ = "themes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    discipline_id: Mapped[int] = mapped_column(ForeignKey("disciplines.id"), nullable=False, index=True)

    # Many-to-one relationship
    discipline: Mapped["Discipline"] = relationship(back_populates="themes")
    
    # One-to-many relationships
    items: Mapped[List["Item"]] = relationship(back_populates="theme")
    test_sessions: Mapped[List["TestSession"]] = relationship(back_populates="theme")

    def __repr__(self) -> str:
        return f"<Theme(id={self.id}, name='{self.name}')>"


class Item(Base):
    """Represents a single IRT question/item in the test bank."""
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    theme_id: Mapped[int] = mapped_column(ForeignKey("themes.id"), nullable=False, index=True)
    
    # Core question components
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[dict] = mapped_column(JSON, nullable=False)
    correct_option: Mapped[str] = mapped_column(String(255), nullable=False)

    # IRT (Item Response Theory) parameters
    a_discrim: Mapped[float] = mapped_column(Float, nullable=False, comment="Item discrimination (a-parameter)")
    b_diff: Mapped[float] = mapped_column(Float, nullable=False, comment="Item difficulty (b-parameter)")
    c_guess: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="Guessing factor (c-parameter)")

    # Metadata
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Many-to-one relationship
    theme: Mapped["Theme"] = relationship(back_populates="items")
    # One-to-many relationship
    responses: Mapped[List["Response"]] = relationship(back_populates="item")

    def __repr__(self) -> str:
        return f"<Item(id={self.id}, b_diff={self.b_diff:.2f})>"


class TestSession(Base):
    """Represents a single adaptive testing session for a user on a specific theme."""
    __tablename__ = "test_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    theme_id: Mapped[int] = mapped_column(ForeignKey("themes.id"), nullable=False, index=True)

    start_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # IRT State
    theta_estimate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    standard_error: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    # Status
    status: Mapped[SessionStatusEnum] = mapped_column(Enum(SessionStatusEnum), default=SessionStatusEnum.started, nullable=False)

    # Many-to-one relationships
    user: Mapped["User"] = relationship(back_populates="test_sessions")
    theme: Mapped["Theme"] = relationship(back_populates="test_sessions")
    
    # One-to-many relationship
    responses: Mapped[List["Response"]] = relationship(back_populates="session", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<TestSession(id={self.id}, user_id={self.user_id}, theta={self.theta_estimate:.3f}, status='{self.status.value}')>"


class Response(Base):
    """Represents a user's response to a single item within a test session."""
    __tablename__ = "responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("test_sessions.id"), nullable=False, index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False, index=True)
    
    user_answer: Mapped[str] = mapped_column(String(255), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    
    theta_after: Mapped[float] = mapped_column(Float, nullable=False, comment="Theta estimate after this response was processed")
    response_time_sec: Mapped[int] = mapped_column(Integer, nullable=False)

    # Many-to-one relationships
    session: Mapped["TestSession"] = relationship(back_populates="responses")
    item: Mapped["Item"] = relationship(back_populates="responses")

    def __repr__(self) -> str:
        return f"<Response(id={self.id}, item_id={self.item_id}, correct={self.is_correct})>"


# --- Database Engine Setup ---
DATABASE_URL = "sqlite:///./test_platform.db"
engine = create_engine(DATABASE_URL, echo=False)


def create_db_and_tables():
    """Creates the database and all necessary tables."""
    print("Dropping all existing tables...")
    Base.metadata.drop_all(engine)
    print("Creating new database and tables...")
    Base.metadata.create_all(engine)
    print("Database and tables created successfully.")


if __name__ == "__main__":
    # This block provides a simple way to initialize the database schema.
    # Running this script directly will drop and recreate the database.
    create_db_and_tables()