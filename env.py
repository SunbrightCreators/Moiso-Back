from pathlib import Path
import environ
import os

env = environ.Env(DEBUG=(bool, False))

BASE_DIR = Path(__file__).resolve().parent

environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

DEBUG = env('DEBUG')
SECRET_KEY = env('SECRET_KEY')
DATABASE_DEFAULT = env.db()
