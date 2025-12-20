import numpy as np
from scipy.optimize import minimize_scalar
from typing import List, Dict, Tuple, Any

# Define the scaling constant for the 3PL model
D = 1.702

def probability_correct(theta: float, a_discrim: float, b_diff: float, c_guess: float) -> float:
    """
    Calculates the probability of a correct response using the 3PL IRT model.

    P(theta) = c + (1 - c) / (1 + exp(-D * a * (theta - b)))

    Args:
        theta: The ability estimate of the user (θ).
        a_discrim: The item's discrimination parameter (a).
        b_diff: The item's difficulty parameter (b).
        c_guess: The item's guessing parameter (c).

    Returns:
        The probability of a correct response (float).
    """
    val = -D * a_discrim * (theta - b_diff)
    # Clamp the value to avoid overflow in np.exp
    val = np.clip(val, -500, 500)
    return c_guess + (1 - c_guess) / (1 + np.exp(val))

def log_likelihood(theta: float, responses: List[Tuple[Dict[str, float], bool]]) -> float:
    """
    Calculates the log-likelihood of a theta estimate given a series of responses.

    The log-likelihood is the sum of the logs of the probabilities of each observed
    response (correct or incorrect).

    Args:
        theta: The ability estimate (θ) to evaluate.
        responses: A list of tuples, where each tuple contains:
                   - A dictionary with the item's IRT parameters ('a_discrim', 'b_diff', 'c_guess').
                   - A boolean indicating if the response was correct (True) or not (False).

    Returns:
        The total log-likelihood value (float).
    """
    total_log_likelihood = 0.0
    for item_params, is_correct in responses:
        p_correct = probability_correct(theta, **item_params)
        
        # To avoid log(0) errors, use a small epsilon
        epsilon = 1e-9
        p_correct = np.clip(p_correct, epsilon, 1 - epsilon)

        if is_correct:
            total_log_likelihood += np.log(p_correct)
        else:
            total_log_likelihood += np.log(1 - p_correct)
            
    return total_log_likelihood

def estimate_theta(responses: List[Tuple[Dict[str, float], bool]]) -> float:
    """
    Estimates the user's ability (theta) that maximizes the log-likelihood.

    This function uses scipy's scalar minimizer to find the theta that minimizes
    the *negative* log-likelihood, which is equivalent to maximizing the
    log-likelihood.

    Args:
        responses: A list of response tuples (item_params_dict, is_correct_bool).

    Returns:
        The estimated theta value (float). Returns 0.0 if estimation fails.
    """
    if not responses:
        return 0.0

    # Objective function to minimize (negative log-likelihood)
    def neg_log_likelihood(theta: float):
        return -log_likelihood(theta, responses)

    # Use minimize_scalar to find the theta that maximizes likelihood
    result = minimize_scalar(
        neg_log_likelihood,
        bounds=(-4.0, 4.0),
        method='bounded'
    )

    if result.success:
        return float(result.x)
    
    # Return a default value if optimization fails
    print(f"Warning: Theta estimation did not converge. Reason: {result.message}")
    return 0.0

def item_information(theta: float, a_discrim: float, b_diff: float, c_guess: float) -> float:
    """
    Calculates the information function for a single item at a given theta.

    I(θ) = (D*a)² * ((P(θ) - c) / (1 - c))² * ((1 - P(θ)) / P(θ))

    Args:
        theta: The ability estimate (θ).
        a_discrim: The item's discrimination parameter (a).
        b_diff: The item's difficulty parameter (b).
        c_guess: The item's guessing parameter (c).

    Returns:
        The information value for the item (float).
    """
    p = probability_correct(theta, a_discrim, b_diff, c_guess)

    # Avoid division by zero if p is 0 or 1
    if p <= 0 or p >= 1:
        return 0.0

    # First part of the equation: ((P(θ) - c) / (1 - c))^2
    p_minus_c = p - c_guess
    one_minus_c = 1 - c_guess
    
    # Avoid division by zero if c_guess is 1
    if one_minus_c == 0:
        return 0.0
        
    term1 = (p_minus_c / one_minus_c) ** 2
    
    # Second part: (1 - P(θ)) / P(θ)
    term2 = (1 - p) / p

    information = (D * a_discrim) ** 2 * term1 * term2
    return information

def test_information(theta: float, responses: List[Tuple[Dict[str, float], bool]]) -> float:
    """
    Calculates the total test information for all answered items at a given theta.
    
    This is the sum of the information from each individual item.

    Args:
        theta: The ability estimate (θ).
        responses: A list of response tuples containing item parameters.

    Returns:
        The total test information value (float).
    """
    total_info = 0.0
    for item_params, _ in responses:
        total_info += item_information(theta, **item_params)
    return total_info

def calculate_standard_error(theta: float, responses: List[Tuple[Dict[str, float], bool]]) -> float:
    """
    Calculates the Standard Error (SE) of the theta estimate.

    SE(θ) = 1 / sqrt(I(θ)), where I(θ) is the total test information.

    Args:
        theta: The ability estimate (θ).
        responses: A list of response tuples containing item parameters.

    Returns:
        The standard error of the estimate (float). Returns a large value if info is zero.
    """
    info = test_information(theta, responses)
    if info <= 0:
        # Return a large SE if information is zero or negative to indicate high uncertainty
        return 10.0
    return 1.0 / np.sqrt(info)

def select_next_item(current_theta: float, available_items: List[Any]) -> Any:
    """
    Selects the next item that provides the maximum information at the current theta.

    Args:
        current_theta: The user's current ability estimate (θ).
        available_items: A list of available items. These can be ORM objects or dicts,
                         as long as they have 'a_discrim', 'b_diff', and 'c_guess' attributes.

    Returns:
        The item object/dict that has the highest information value. Returns None
        if no items are available.
    """
    if not available_items:
        return None

    best_item = None
    max_info = -1.0

    for item in available_items:
        info = item_information(
            theta=current_theta,
            a_discrim=item.a_discrim,
            b_diff=item.b_diff,
            c_guess=item.c_guess
        )
        if info > max_info:
            max_info = info
            best_item = item
            
    return best_item
