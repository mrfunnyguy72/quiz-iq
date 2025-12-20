# QuizIQ - Adaptive Testing Platform

QuizIQ is a web-based adaptive testing system that uses a 3-Parameter Logistic (3PL) Item Response Theory (IRT) model to deliver dynamic, personalized assessments.

## About The Project

This project provides a complete, full-stack implementation of a Computerized Adaptive Testing (CAT) platform. The backend is built with FastAPI and SQLAlchemy, handling the core IRT logic and database interactions. The frontend is a clean, responsive UI built with HTMX for modern, dynamic user interactions without heavy JavaScript, and styled with Tailwind CSS.

### Key Technologies

*   **Backend**: FastAPI, Python 3
*   **Database**: SQLAlchemy 2.0 ORM, SQLite
*   **IRT Engine**: NumPy, SciPy
*   **Frontend**: HTMX, Jinja2, Tailwind CSS
*   **Tooling**: `uv`, Pytest

## Features

*   **Adaptive Item Selection**: Dynamically selects the most informative question based on the user's current estimated ability (`theta`).
*   **Dynamic Ability Estimation**: Recalculates the user's ability and standard error after each response using a 3PL IRT model.
*   **Session Management**: RESTful API endpoints to start, manage, and conclude testing sessions.
*   **Reactive UI**: A fast, server-rendered frontend using HTMX that provides a smooth user experience.
*   **Database Seeding**: Includes a script to populate the database with sample users, themes, and IRT questions.
*   **Automated Testing**: Unit and performance tests for the IRT engine.

## Getting Started

Follow these steps to get a local copy up and running.

### Prerequisites

*   Python 3.10+
*   **uv**: A fast Python package installer. If you don't have it, install it by running:
    ```sh
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```
*   **Git**

### Installation & Setup

1.  **Clone the repository**:
    ```sh
    git clone https://github.com/mrfunnyguy27/quiz-iq.git
    cd quiz-iq
    ```

2.  **Update your PATH (Recommended)**:
    The `uv` installer places its executable in a local directory (e.g., `~/.local/bin`) that may not be in your shell's `PATH`. It's recommended to add it to your `~/.bashrc` or `~/.zshrc` file:
    ```sh
    export PATH="$HOME/.local/bin:$PATH"
    ```
    Then, reload your shell or run `source ~/.bashrc`.

3.  **Run the setup script**:
    This script will create a virtual environment named `.venv_quiz_iq` and install all required dependencies from `requirements.txt`.
    ```sh
    chmod +x setup_env.sh
    ./setup_env.sh
    ```

4.  **Activate the virtual environment**:
    ```sh
    source .venv_quiz_iq/bin/activate
    ```

### Running the Application

1.  **Seed the database**:
    This command will create the `test_platform.db` file and populate it with sample users, themes, and questions.
    ```sh
    python3 seed_db.py
    ```

2.  **Start the server**:
    ```sh
    uvicorn main:app --reload
    ```

3.  **Open the app**:
    Navigate to `http://127.0.0.1:8000` in your web browser.

## Usage

Once the application is running, you can:
1.  Select a user and a theme from the dropdowns on the homepage.
2.  Click "Start Test" to begin a new session.
3.  Answer the questions presented. The next question is chosen based on your answer to the previous one.
4.  The test concludes when your ability estimate's standard error falls below a certain threshold or you've answered a maximum number of questions.
5.  View your final normalized score.

## Project Structure

```
.
├── irt_engine.py       # Core IRT logic (3PL model, theta/SE estimation)
├── main.py             # FastAPI application, serves HTML and handles API requests
├── models.py           # SQLAlchemy 2.0 ORM models (database schema)
├── requirements.txt    # Project dependencies
├── seed_db.py          # Script to populate the database
├── setup_env.sh        # Script to create the virtual environment
├── test_irt_engine.py  # Pytest tests for the IRT engine
├── templates/          # Jinja2 HTML templates
│   ├── base.html
│   ├── index.html
│   ├── test.html
│   └── partials/
│       ├── question_card.html
│       └── results.html
└── ...
```

## Running Tests

To run the automated tests for the IRT engine, activate your virtual environment and run Pytest:

```sh
pytest -v
```
