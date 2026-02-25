"""
Centralized logger configuration to avoid circular imports.
"""
import os
import logging

# Get application directory
__APP_DIR__ = os.path.dirname(__file__)
__log_filename__ = os.path.join(__APP_DIR__, "../log/polygon.log")

# Configure logging
logging.basicConfig(
    filename=__log_filename__,
    level=logging.INFO,  # Changed from ERROR to INFO to show info messages
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create logger instance
logger = logging.getLogger(__name__)
