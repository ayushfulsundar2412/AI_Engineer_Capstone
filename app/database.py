import os

from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()  # reads DATABASE_URL from your .env file

engine = create_engine(os.environ["DATABASE_URL"])


def get_conn():
    """Give each request its own connection, then clean up.

    engine.begin() commits if the request succeeds
    and rolls back if an error happens.
    """
    with engine.begin() as conn:
        yield conn