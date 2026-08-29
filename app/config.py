import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

APP_TITLE = "QBR Ticket Alert Dashboard"

DATABASE_SERVER = os.getenv("DATABASE_SERVER")
DATABASE_NAME = os.getenv("DATABASE_NAME")
DATABASE_USER = os.getenv("DATABASE_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")

connection_string = (
    f"DRIVER={{{DB_DRIVER}}};"
    f"SERVER={DATABASE_SERVER};"
    f"DATABASE={DATABASE_NAME};"
    f"UID={DATABASE_USER};"
    f"PWD={DB_PASSWORD};"
    "TrustServerCertificate=yes;"
)

DATABASE_URL = (
    "mssql+pyodbc:///?odbc_connect="
    + quote_plus(connection_string)
)