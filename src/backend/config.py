import os
from dotenv import load_dotenv

load_dotenv()

SECRET_APP_KEY = os.getenv('SECRET_APP_KEY')

# REMOVE BEFORE DEPLOYMENT
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1" 

FRONTEND_CALLBACK_URL = "https://5173-firebase-goal-planner-1772916885143.cluster-247htgozabfwetjtf5m4n5737o.cloudworkstations.dev/callback"
CLIENT_SECRETS_FILE = "client_secrets.json"
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email", # See user email address
    "https://www.googleapis.com/auth/gmail.send",     # Send emails
    "https://www.googleapis.com/auth/calendar",       # Read/Edit calendar
    "https://www.googleapis.com/auth/tasks"           # Read/Edit tasks
]