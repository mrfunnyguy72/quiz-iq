from rapidfuzz import fuzz

# Define the similarity threshold
SIMILARITY_THRESHOLD = 0.85

def is_answer_correct_fuzzy(user_answer: str, correct_answer: str) -> bool:
    """
    Evaluates if the user's answer is correct for an open-ended question
    using fuzzy string matching.

    Args:
        user_answer: The answer provided by the user.
        correct_answer: The correct answer from the database.

    Returns:
        True if the similarity score is above the threshold, False otherwise.
    """
    if not user_answer or not correct_answer:
        return False

    # Calculate the similarity ratio
    similarity_score = fuzz.ratio(user_answer.lower(), correct_answer.lower()) / 100.0

    # Check if the score exceeds the threshold
    return similarity_score >= SIMILARITY_THRESHOLD
