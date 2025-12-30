
import os
import logging

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

def setup_logging():
    """Configure centralized logging for the application"""
    logging.basicConfig(
        filename="logs/app_errors.log",
        level=logging.ERROR,
        format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
    )
