import logging

from rich.logging import RichHandler

from lib.database_manager import DatabaseManager

logging.basicConfig(
    level=logging.INFO, format="%(message)s", datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True)]
)
log = logging.getLogger("rich")

db_manager = DatabaseManager(log=log)
