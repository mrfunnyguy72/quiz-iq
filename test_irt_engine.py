import pytest
import time
import random
import numpy as np
from irt_engine import estimate_theta, probability_correct

# Re-using the existing test for directional correctness
def test_theta_estimation_responds_directionally():
    """
    Tests that the theta estimate responds logically to different response patterns,
    avoiding the "ceiling effect" of a perfect score.
    """
    # Use constant, moderate item parameters for predictability
    item_params = {
        "a_discrim": 1.0,
        "b_diff": 0.0,
        "c_guess": 0.1,
    }

    # --- Test 1: A single correct answer should yield a positive theta ---
    # A correct answer to a medium-difficulty question (b=0.0)
    responses_1 = [(item_params, True)]
    theta_1 = estimate_theta(responses_1)
    print(f"\nScenario 1 (1 Correct): Theta = {theta_1:.4f}")
    assert theta_1 > 0, "A single correct answer to a medium item should result in a positive theta."

    # --- Test 2: A single incorrect answer should yield a negative theta ---
    # An incorrect answer to the same question
    responses_2 = [(item_params, False)]
    theta_2 = estimate_theta(responses_2)
    print(f"Scenario 2 (1 Incorrect): Theta = {theta_2:.4f}")
    assert theta_2 < 0, "A single incorrect answer to a medium item should result in a negative theta."

    # --- Test 3: Test a mixed response pattern and ensure theta moves logically ---
    # Start with a baseline: 1 correct, 1 incorrect on items of medium difficulty
    responses_3 = [
        (item_params, True),
        (item_params, False),
    ]
    # With one correct and one incorrect, theta should be near 0
    theta_3 = estimate_theta(responses_3)
    print(f"Scenario 3 (1 Correct, 1 Incorrect): Theta = {theta_3:.4f}")
    assert -0.5 < theta_3 < 0.5, "With a balanced response pattern, theta should be close to zero."

    # --- Test 4: Add a correct answer to a hard item, theta should increase ---
    hard_item = {"a_discrim": 1.0, "b_diff": 2.0, "c_guess": 0.1}
    responses_4 = responses_3 + [(hard_item, True)]
    theta_4 = estimate_theta(responses_4)
    print(f"Scenario 4 (Add Correct on Hard Item): Theta = {theta_4:.4f}")
    assert theta_4 > theta_3, "Theta should increase after a correct answer on a hard item."

    # --- Test 5: Add an incorrect answer to an easy item, theta should decrease ---
    easy_item = {"a_discrim": 1.0, "b_diff": -2.0, "c_guess": 0.1}
    responses_5 = responses_4 + [(easy_item, False)]
    theta_5 = estimate_theta(responses_5)
    print(f"Scenario 5 (Add Incorrect on Easy Item): Theta = {theta_5:.4f}")
    assert theta_5 < theta_4, "Theta should decrease after an incorrect answer on an easy item."


def test_estimate_theta_performance():
    """
    Tests that the estimate_theta function runs within an acceptable time limit (e.g., 100ms).
    """
    # --- 1. Setup a realistic (but not excessively large) set of responses ---
    num_responses = 20 # A typical number of items answered in an adaptive test
    responses = []
    
    # Simulate a user with a true ability (theta) around 0.5
    true_theta = 0.5

    for _ in range(num_responses):
        # Generate random item parameters
        a_discrim = round(random.uniform(0.8, 1.5), 2)
        b_diff = round(random.uniform(-1.0, 1.0), 2)
        c_guess = round(random.uniform(0.0, 0.2), 2)
        
        item_params = {
            "a_discrim": a_discrim,
            "b_diff": b_diff,
            "c_guess": c_guess,
        }
        
        # Simulate correctness based on the true_theta and item parameters
        prob_correct = probability_correct(true_theta, **item_params)
        is_correct = random.random() < prob_correct
        
        responses.append((item_params, is_correct))

    # --- 2. Measure performance ---
    start_time = time.perf_counter() # Use perf_counter for more precise timing
    estimated_theta = estimate_theta(responses)
    end_time = time.perf_counter()

    elapsed_time_ms = (end_time - start_time) * 1000
    
    print(f"\nestimate_theta with {num_responses} responses took: {elapsed_time_ms:.2f} ms")

    # --- 3. Assert against the time limit ---
    time_limit_ms = 100
    assert elapsed_time_ms < time_limit_ms, (
        f"estimate_theta took {elapsed_time_ms:.2f} ms, "
        f"which exceeds the {time_limit_ms} ms limit."
    )

# To run this test:
# 1. Make sure you have pytest installed: pip install pytest
# 2. Activate your virtual environment.
# 3. Run pytest from your terminal in the project directory:
#    pytest -v