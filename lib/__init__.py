import logging
import logging.handlers
from rich.logging import RichHandler
from rich.traceback import install

# Install rich traceback handling
install(show_locals=True)


# Configure logging
log_format = "%(asctime)s | %(levelname)8s | %(name)s | %(message)s"
date_format = "%Y-%m-%d %H:%M:%S"

# Create handlers
console_handler = RichHandler(
    rich_tracebacks=True,
    markup=True,
    show_time=False
)

# Configure handlers
console_handler.setFormatter(logging.Formatter("%(message)s", datefmt="[%X]"))

# Setup root logger
logging.basicConfig(
    level=logging.INFO,
    handlers=[console_handler]
)

# Create logger
log = logging.getLogger("cyberflix-server")