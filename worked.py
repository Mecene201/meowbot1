# worked.py
import random

# Define the job list with unlock levels, wage ranges, and XP gain ranges.
jobs = {
    "fast_food_worker": {
        "level_requirement": 1,
        "wage_range": (50, 100),
        "xp_range": (20, 40)
    },
    "barista": {
        "level_requirement": 5,
        "wage_range": (150, 250),
        "xp_range": (45, 50)
    },
    "freelance_writer": {
        "level_requirement": 10,
        "wage_range": (300, 500),
        "xp_range": (55, 65)
    },
    "software_developer": {
        "level_requirement": 15,
        "wage_range": (600, 1000),
        "xp_range": (65, 75)
    },
    "business_owner": {
        "level_requirement": 20,
        "wage_range": (1500, 3000),
        "xp_range": (80, 85)
    }
}

def do_work(job_key: str, user_level: int):
    """
    Perform a work action for a given job, returning coins and XP earned.
    
    Parameters:
      - job_key: Identifier for the job (e.g., "fast_food_worker").
      - user_level: The user's current level.
      
    Returns:
      - A tuple ((coins, xp), None) if the work action is valid.
      - If the job does not exist or the user level is too low, returns (None, error_message).
    """
    if job_key not in jobs:
        return None, "Job not found."
    
    job = jobs[job_key]
    if user_level < job["level_requirement"]:
        return None, f"You need to be level {job['level_requirement']} to work as a {job_key.replace('_', ' ').title()}."
    
    coins = random.randint(*job["wage_range"])
    xp = random.randint(*job["xp_range"])
    return (coins, xp), None
