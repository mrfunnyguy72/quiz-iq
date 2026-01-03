import random

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

# Import the models and the engine from your existing models.py file
from app.core.security import get_password_hash
from app.models.base import (
    Discipline,
    Item,
    ItemTypeEnum,
    MediaTypeEnum,
    Theme,
    User,
    UserRoleEnum,
    engine,
)

# Create a session class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def seed_database():
    """
    Seeds the database with sample data for the adaptive testing system.
    """
    # Create a new session
    db = SessionLocal()
    print("Seeding database...")

    try:
        # --- 0. Ensure Users exist ---
        users_to_create = {
            "admin": UserRoleEnum.ADMIN,
            "moderator": UserRoleEnum.MODERATOR,
            "tester": UserRoleEnum.STUDENT,
        }
        for name, role in users_to_create.items():
            stmt = select(User).where(User.username == name)
            user = db.execute(stmt).scalars().first()

            if not user:
                print(f"Creating user: {name} with role {role.value}")
                # The password is the same as the username, then hashed
                password_hash = get_password_hash(name)
                new_user = User(username=name, password_hash=password_hash, role=role)
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

        if item_count > 0:
            print("Database already contains items. Skipping seeding.")
            return

        print("Generating and adding special and random sample IRT questions...")
        
        # --- Add a few specific, interesting questions ---

        # 1. Open-ended algebra question (existing)
        db.add(Item(
            theme_id=themes[0].id, # Algebra
            question_text="Solve for x in the equation: 2x + 10 = 20",
            type=ItemTypeEnum.OPEN_ENDED,
            correct_option=["5"],
            a_discrim=1.2, b_diff=0.5, c_guess=0.1, is_active=True
        ))
        print("  - Added: Open-ended algebra question.")

        # 2. HTML Formatted geometry question (single correct answer)
        db.add(Item(
            theme_id=themes[1].id, # Geometry
            question_text="What is the area of a circle with radius <i>r</i>?",
            type=ItemTypeEnum.MULTIPLE_CHOICE,
            media_type=MediaTypeEnum.HTML,
            options={"A": "&pi;r<sup>2</sup>", "B": "2&pi;r", "C": "r<sup>2</sup>"},
            correct_option=["A"],
            a_discrim=1.0, b_diff=-0.5, c_guess=0.2, is_active=True
        ))
        print("  - Added: HTML-formatted geometry question.")

        # 3. Multiple Choice Calculus Question (single correct answer)
        db.add(Item(
            theme_id=themes[2].id, # Calculus
            question_text="What is the derivative of x<sup>2</sup>?",
            type=ItemTypeEnum.MULTIPLE_CHOICE,
            options={"A": "x", "B": "2x", "C": "x<sup>3</sup>/3", "D": "2"},
            correct_option=["B"],
            a_discrim=1.5, b_diff=1.0, c_guess=0.15, is_active=True
        ))
        print("  - Added: Multiple Choice Calculus question.")

        # 4. Open-ended Statistics Question
        db.add(Item(
            theme_id=themes[3].id, # Statistics
            question_text="What is the median of the following set of numbers: 10, 5, 20, 15, 30?",
            type=ItemTypeEnum.OPEN_ENDED,
            correct_option=["15"],
            a_discrim=1.0, b_diff=0.8, c_guess=0.05, is_active=True
        ))
        print("  - Added: Open-ended Statistics question.")

        # 5. Multiple Choice Algebra Question (single correct answer)
        db.add(Item(
            theme_id=themes[0].id, # Algebra
            question_text="If 3x - 5 = 10, what is x?",
            type=ItemTypeEnum.MULTIPLE_CHOICE,
            options={"A": "3", "B": "5", "C": "10", "D": "15"},
            correct_option=["B"],
            a_discrim=1.1, b_diff=0.2, c_guess=0.0, is_active=True
        ))
        print("  - Added: Another Multiple Choice Algebra question.")

        # 6. Open-ended Geometry Question
        db.add(Item(
            theme_id=themes[1].id, # Geometry
            question_text="How many degrees are in a triangle?",
            type=ItemTypeEnum.OPEN_ENDED,
            correct_option=["180"],
            a_discrim=0.9, b_diff=0.0, c_guess=0.0, is_active=True
        ))
        print("  - Added: Another Open-ended Geometry question.")

        # 7. New Question with Multiple Correct Answers
        db.add(Item(
            theme_id=themes[3].id, # Statistics
            question_text="Which of the following numbers are prime? (Select all that apply)",
            type=ItemTypeEnum.MULTIPLE_CHOICE,
            options={"A": "2", "B": "4", "C": "7", "D": "9"},
            correct_option=["A", "C"],
            a_discrim=1.7, b_diff=1.2, c_guess=0.1, is_active=True
        ))
        print("  - Added: Multiple choice question with multiple correct answers.")
        
        # --- Generate a larger set of random questions (increased from 50 to 100) ---
        print("\nGenerating 100 random questions (50 multiple choice, 50 open-ended)...")
        for i in range(100): 
            selected_theme = random.choice(themes)
            a_discrim = round(random.uniform(0.5, 2.5), 2)
            b_diff = round(random.uniform(-2.0, 2.0), 2)
            c_guess = round(random.uniform(0.0, 0.25), 2)

            if i % 2 == 0: # 50% chance for multiple choice
                # Multiple Choice Question
                num1 = random.randint(1, 20)
                num2 = random.randint(1, 20)
                operator = random.choice(['+', '-', '*'])
                correct_ans_val = eval(f"{num1} {operator} {num2}")

                options = {
                    "A": str(correct_ans_val),
                    "B": str(correct_ans_val + random.randint(1, 5)),
                    "C": str(correct_ans_val - random.randint(1, 5)),
                    "D": str(random.randint(1, 50)),
                }
                
                # Ensure options are unique
                while len(set(options.values())) != len(options):
                    options["B"] = str(correct_ans_val + random.randint(1, 5))
                    options["C"] = str(correct_ans_val - random.randint(1, 5))
                    options["D"] = str(random.randint(1, 50))
                
                options_list = list(options.items())
                random.shuffle(options_list)
                shuffled_options = dict(options_list)
                
                correct_option_keys = [key for key, val in shuffled_options.items() if val == str(correct_ans_val)]

                item = Item(
                    theme_id=selected_theme.id,
                    question_text=f"What is {num1} {operator} {num2}?",
                    type=ItemTypeEnum.MULTIPLE_CHOICE,
                    options=shuffled_options,
                    correct_option=correct_option_keys,
                    a_discrim=a_discrim,
                    b_diff=b_diff,
                    c_guess=c_guess,
                    is_active=True,
                )
            else:
                # Open-Ended Question
                num = random.randint(1, 10)
                item = Item(
                    theme_id=selected_theme.id,
                    question_text=f"What is {num} squared?",
                    type=ItemTypeEnum.OPEN_ENDED,
                    correct_option=[str(num * num)],
                    a_discrim=a_discrim,
                    b_diff=b_diff,
                    c_guess=c_guess,
                    is_active=True,
                )
            db.add(item)

        # Commit all the new items
        db.commit()
        print("\nSuccessfully seeded the database with special and random questions.")

    except Exception as e:
        print(f"An error occurred during database seeding: {e}")
        db.rollback()
    finally:
        db.close()
        print("Session closed.")

if __name__ == "__main__":
    # The create_db_and_tables function from models.py will drop and recreate
    # all tables, ensuring the schema is always up-to-date with the models.
    from app.models.base import create_db_and_tables
    
    print("Recreating database schema to ensure it is up-to-date...")
    create_db_and_tables()
    
    seed_database()

