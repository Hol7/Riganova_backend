import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
import time

SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://livraison_user:livraison_pass@db:5440/livraison_db"
)

def create_retry_engine(url, max_retries=5, delay=3):
    retries = 0
    while retries < max_retries:
        try:
            engine = create_engine(url)
            with engine.connect():
                print("Database connection established.")
            return engine
        except OperationalError:
            retries += 1
            print(f"Database connection failed, retrying {retries}/{max_retries}...")
            time.sleep(delay)
    raise OperationalError("Could not connect to the database after retries.")

engine = create_retry_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()




# from sqlalchemy import create_engine
# from sqlalchemy.ext.declarative import declarative_base
# from sqlalchemy.orm import sessionmaker
# from sqlalchemy.exc import OperationalError
# import time 

# # SQLALCHEMY_DATABASE_URL = "postgresql://user:password@localhost/dbname"  # Update with your actual database credentials

# #production
# SQLALCHEMY_DATABASE_URL = "postgresql://postgres:1234@localhost:5432/postgres"
# # SQLALCHEMY_DATABASE_URL="postgresql://livraison_user:livraison_pass@db:5432/livraison_db"

# #use localy
# # SQLALCHEMY_DATABASE_URL = "postgresql://postgres:1234@192.168.1.159:5438/postgres"


# # SQLALCHEMY_DATABASE_URL = "postgresql://postgres:1234@http://80.241.211.172:5438/postgres"
# # SQLALCHEMY_DATABASE_URL = "postgresql://postgres:1234@80.241.211.172:5438/postgres"
# # SQLALCHEMY_DATABASE_URL = "postgresql://postgres:1234@192.168.1.159:5438/postgres"


# # Create engine with retry mechanism
# def create_retry_engine(url, max_retries=5, delay=3):
#     retries = 0
#     while retries < max_retries:
#         try:
#             engine = create_engine(url)
#             # Test the connection
#             with engine.connect():
#                 print("Database connection established.")
#             return engine
#         except OperationalError:
#             retries += 1
#             print(f"Database connection failed, retrying {retries}/{max_retries}...")
#             time.sleep(delay)
#     raise OperationalError("Could not connect to the database after retries.")

# engine = create_retry_engine(SQLALCHEMY_DATABASE_URL)
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Base = declarative_base()

# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()


# from sqlalchemy import create_engine
# from sqlalchemy.ext.declarative import declarative_base
# from sqlalchemy.orm import sessionmaker
# import os

# # Récupération de l'URL de la base de données
# DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./test.db")

# # Création du moteur SQLAlchemy
# connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
# engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)

# # Session locale
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# # Base pour les modèles
# Base = declarative_base()

# # Fonction pour obtenir une session de base de données
# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()