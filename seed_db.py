import random
import hashlib
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

# Import the models and the engine from your existing models.py file
from models import (
    engine,
    Base,
    Discipline,
    Theme,
    Item,
    User,
)

# Create a session class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# A simple salt for hashing. In a real application, use a unique salt per user.
SALT = "quiz_iq_super_secret_salt"

def hash_password(password: str) -> str:
    """Hashes a password using SHA-256 with a salt."""
    salted_password = password + SALT
    return hashlib.sha256(salted_password.encode('utf-8')).hexdigest()

def seed_database():
    """
    Seeds the database with sample data for the adaptive testing system.
    """
    # Create a new session
    db = SessionLocal()
    print("Seeding database...")

    try:
        # --- 0. Ensure Users exist ---
        user_names = ["admin", "moderator", "tester"]
        for name in user_names:
            stmt = select(User).where(User.username == name)
            user = db.execute(stmt).scalars().first()

            if not user:
                print(f"Creating user: {name}")
                # The password is the same as the username, then hashed
                password_hash = hash_password(name)
                new_user = User(username=name, password_hash=password_hash)
                db.add(new_user)
            else:
                print(f"User '{name}' already exists.")
        db.commit()


        # --- 1. Ensure Discipline exists ---
        discipline_name = "Mathematics"
        
        # Check if the discipline already exists
        stmt = select(Discipline).where(Discipline.name == discipline_name)
        discipline = db.execute(stmt).scalars().first()

        if not discipline:
            print(f"Creating discipline: {discipline_name}")
            discipline = Discipline(name=discipline_name)
            db.add(discipline)
            db.commit()
            db.refresh(discipline)
        else:
            print(f"Discipline '{discipline_name}' already exists.")

        # --- 2. Ensure Themes exist ---
        theme_names = ["Algebra", "Geometry", "Calculus", "Statistics"]
        themes = []
        for name in theme_names:
            stmt = select(Theme).where(Theme.name == name, Theme.discipline_id == discipline.id)
            theme = db.execute(stmt).scalars().first()

            if not theme:
                print(f"Creating theme: {name} for {discipline_name}")
                theme = Theme(name=name, discipline_id=discipline.id)
                db.add(theme)
                themes.append(theme)
            else:
                print(f"Theme '{name}' already exists.")
                themes.append(theme)
        
        # We need to commit here to get the IDs for the themes
        db.commit()
        for theme in themes:
            db.refresh(theme)


        # --- 3. Create Sample IRT Items ---
        print("Checking for existing items...")
        item_count = db.query(Item).count()

        if item_count >= 10:
            print("Database already contains 10 or more items. Seeding is not required.")
            return

        print("Generating and adding 10000 sample IRT questions...")
        for i in range(10000):
            # Choose a random theme for the question
            selected_theme = random.choice(themes)

            # Generate random IRT parameters within a plausible range
            a_discrim = round(random.uniform(0.5, 2.5), 2)  # Discrimination
            b_diff = round(random.uniform(-2.0, 2.0), 2) # Difficulty
            c_guess = round(random.uniform(0.0, 0.25), 2)  # Guessing factor

            # Create simple math questions
            num1 = random.randint(1, 20)
            num2 = random.randint(1, 20)
            correct_ans_val = num1 + num2
            
            # Create plausible distractors
            options = {
                "A": str(correct_ans_val),
                "B": str(correct_ans_val + random.randint(1, 5)),
                "C": str(abs(correct_ans_val - random.randint(1, 5))),
                "D": str(random.randint(1, 50)),
            }
            # Shuffle options to randomize correct answer position
            shuffled_keys = list(options.keys())
            random.shuffle(shuffled_keys)
            shuffled_options = {key: options[key] for key in shuffled_keys}

            correct_option_key = next(key for key, val in shuffled_options.items() if val == str(correct_ans_val))

            item = Item(
                theme_id=selected_theme.id,
                question_text=f"What is {num1} + {num2}?",
                options=shuffled_options,
                correct_option=correct_option_key,
                a_discrim=a_discrim,
                b_diff=b_diff,
                c_guess=c_guess,
                is_active=True,
            )
            db.add(item)
            print(f"  - Added: Item {i+1} for theme '{selected_theme.name}' (b={b_diff})")

        # Commit all the new items to the database
        db.commit()
        print("\nSuccessfully seeded the database with 10 sample questions.")

    except Exception as e:
        print(f"An error occurred during database seeding: {e}")
        db.rollback()
    finally:
        db.close()
        print("Session closed.")

if __name__ == "__main__":
    # The create_db_and_tables function from models.py will drop and recreate
    # all tables, ensuring the schema is always up-to-date with the models.
    from models import create_db_and_tables
    
    print("Recreating database schema to ensure it is up-to-date...")
    create_db_and_tables()
    
    seed_database()
