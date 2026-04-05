import json
import base64
from datetime import datetime
from typing import TypedDict
from flask import session
from email.message import EmailMessage

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from langchain_core.tools import tool
from langgraph.types import interrupt

from database import get_user_info

class EventInput(TypedDict):
    summary: str
    start_time: str
    end_time: str

class TaskInput(TypedDict):
    title: str
    notes: str
    due: str

@tool
def add_calendar_events(greeting: str, events: list[EventInput]):
    """
    Create Google Calendar events. This tool must recieve the list of events (details specific below) as an argument.

    Args:
        greeting: A short, concise introduction explaining why these events are being added to the user's roadmap.
        events: A list of EventInput objects. Each object MUST contain:
            1. "summary": (string) The title of the event.
            2. "start_time": (string) The start time in ISO 8601 / RFC 3339 format.
               Example: "2026-04-02T10:00:00Z"
            3. "end_time": (string) The end time in ISO 8601 / RFC 3339 format.
               Example: "2026-04-02T11:00:00Z"

    CRITICAL: The 'start_time' and 'end_time' values must be CLEAN strings. 
    Do NOT include extra text or descriptive labels inside the timestamp values.
    """
    if session.get("cancel_pending_tools", False):
      return {"message": "Adding calendar events skipped because the user cancelled a previous step."}
    
    events_display = ""
    try:
      for event in events:
        start = datetime.fromisoformat(event["start_time"])
        end = datetime.fromisoformat(event["end_time"])

        start_str = start.strftime("%a, %b %d %Y — %I:%M %p")
        end_str = end.strftime("%I:%M %p")

        events_display += f"{event['summary']}\n  {start_str} → {end_str}\n\n"
    except Exception as e:
      return {"error": f"Date formatting error. Please ensure start_time and end_time are strict ISO 8601 strings. Do not add extra text. Error details: {e}"}

    decision = interrupt(f"{greeting}\n\nApprove adding the following event(s)?\n\n{events_display}")
    decision_clean = decision.strip().lower()
    
    affirmatives = ["yes", "sure", "ok", "yeah", "okay", "approve", "go ahead"]
    hesitancies = ['but', 'although', "instead", "no", "stop", "cancel", "quit", "not sure"]
    if not any(word in decision_clean for word in affirmatives) or any(word in decision.strip().lower() for word in hesitancies):
      session['cancel_pending_tools'] = True
      return {"message": f"User denied approval. Adding calendar events cancelled. You may use this tool again if the user asks. Here is the user's message. If the user actually said yes/approve, retry this tool and tell them to try including 'yes' in their response. User's message: {decision.strip()}"}

    try:
      user_details = get_user_info(session['google_id'])
      user_refresh_token = user_details.get("refresh_token", "")

      if not user_refresh_token:
        return {"error": "No valid refresh token found. User must log in again. Adding calendar events cancelled."}
      
      with open("client_secrets.json", "r") as f:
        client_info = json.load(f)["web"]

      creds = Credentials(
            token=None, 
            refresh_token=user_refresh_token,
            token_uri=client_info["token_uri"],
            client_id=client_info["client_id"],
            client_secret=client_info["client_secret"]
      )

      service = build('calendar', 'v3', credentials=creds)

      for eventInput in events:
        event = {
            'summary': eventInput['summary'],
            'start': {
                'dateTime': eventInput['start_time'],
                'timeZone': 'America/Los_Angeles'
            },
            'end': {
                'dateTime': eventInput['end_time'],
                'timeZone': 'America/Los_Angeles'
            },
        }

        event_result = service.events().insert(calendarId='primary', body=event).execute()

      return {"message": f"User explicitly approved with: '{decision}'. Events added to calendar successfully. DO NOT call this tool again for these exact same items (unless the user explicitly asks)."}
    except Exception as e:
      return {"error" : "Failed adding calendar events. Error: " + str(e)}

@tool
def get_calendar_events(timeMin: str, timeMax: str):
  """
  Retrieve Google Calendar events. This tool must recieve the start time range and end time range as arguments (details below).

  Args:
        timeMin: (string) The start of the time range in ISO 8601 / RFC 3339 format.
                 Example: "2026-04-01T00:00:00Z"
        timeMax: (string) The end of the time range in ISO 8601 / RFC 3339 format.
                 Example: "2026-04-01T23:59:59Z"

    CRITICAL: The 'timeMin' and 'timeMax' values must be CLEAN strings. 
    Do NOT include extra text, labels, or variable names (like 'timeMax:') inside the timestamp values.
  """
  try:
    user_details = get_user_info(session['google_id'])
    user_refresh_token = user_details.get("refresh_token", "")

    if not user_refresh_token:
      return {"error": "No valid refresh token found. User must log in again."}
    
    with open("client_secrets.json", "r") as f:
      client_info = json.load(f)["web"]

    creds = Credentials(
          token=None, 
          refresh_token=user_refresh_token,
          token_uri=client_info["token_uri"],
          client_id=client_info["client_id"],
          client_secret=client_info["client_secret"]
    )

    service = build('calendar', 'v3', credentials=creds)

    raw_events = service.events().list(
        calendarId = 'primary',
        timeMin = timeMin,
        timeMax = timeMax,
        singleEvents = True,
        orderBy = 'startTime'
    ).execute()

    cleaned_events = [
        {
          "Summary": event.get("summary", ""),
          "Start Time": event.get("start", {}),
          "End Time": event.get("end", {})
        }
        for event in raw_events.get('items', [])
    ]

    return {"events" : cleaned_events}
  except Exception as e:
    return {"error" : str(e)}

@tool
def send_email(greeting: str, subject: str, content: str):
    """
    Send an email to the user. Make sure you provide the subject and content. You ONLY need to provide the subject and content, no other parameters.
    The system automatically handles the recipient's email address in the background, so DO NOT ask the user for an email address.

    Args:
        greeting: greeting: A short, concise introduction explaining why the email is about to be send to the user.
        subject: Subject of the email
        content: Content of the email
    """
    if session.get("cancel_pending_tools", False):
      return {"message": "Sending email skipped because the user cancelled a previous step."}

    content += "\n\nThis email was generated by AI."

    decision = interrupt(f"{greeting}\n\nApprove sending the following email?\n\nSubject: {subject}\nContent:\n{content}\n\nApprove? (yes/no)")
    decision_clean = decision.strip().lower()
    
    affirmatives = ["yes", "sure", "ok", "yeah", "okay", "approve", "go ahead"]
    hesitancies = ['but', 'although', "instead", "no", "stop", "cancel", "quit", "not sure"]
    if not any(word in decision_clean for word in affirmatives) or any(word in decision.strip().lower() for word in hesitancies):
      session['cancel_pending_tools'] = True
      return {"message": f"User denied approval. Sending email cancelled. You may use this tool again if the user asks. Here is the user's message. If the user actually said yes/approve, retry this tool and tell them to try including 'yes' in their response. User's message: {decision.strip()}"}

    try:
      user_details = get_user_info(session['google_id'])
      user_refresh_token = user_details.get("refresh_token", "")
        
      if not user_refresh_token:
          return {"error": "No valid refresh token found. User must log in again. Cancelled sending email."}

      with open("client_secrets.json", "r") as f:
          client_info = json.load(f)["web"]

      creds = Credentials(
          token=None, 
          refresh_token=user_refresh_token,
          token_uri=client_info["token_uri"],
          client_id=client_info["client_id"],
          client_secret=client_info["client_secret"]
      )

      service = build('gmail', 'v1', credentials=creds)

      user_email = user_details.get('user_email')

      msg = EmailMessage()
      msg.set_content(content)
      msg['Subject'] = subject
      msg['From'] = user_email
      msg['To'] = user_email

      encoded_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()
      create_message = {'raw': encoded_message}

      service.users().messages().send(userId="me", body=create_message).execute()

      return {"message": f"User explicitly approved with: '{decision}'. Email sent successfully. DO NOT call this tool again for sending the exact same email (unless the user explicitly asks)."}
    except Exception as e:
      return {"error" : "Failed sending email. Error: " + str(e)}

@tool
def add_google_tasks(greeting: str, tasks: list[TaskInput]):
  """
  Create Google Tasks. This tool must receive the list of tasks as an argument.

    Args:
        greeting: A short, concise introduction explaining why these specific tasks are being added to the user's roadmap.
        tasks: A list of TaskInput objects. Each object MUST contain:
            1. "title": (string) The title of the task.
            2. "notes": (string, optional) Additional description or context for the task.
            3. "due": (string, optional) The due date in ISO 8601 / RFC 3339 format.
               Example: "2026-04-02T12:00:00Z"

    CRITICAL: The 'due' date value must be a CLEAN string. 
    Do NOT include extra text, key names (like 'notes:'), or descriptive labels inside the timestamp values.
  """
  if session.get("cancel_pending_tools", False):
    return {"message": "Adding to google tasks skipped because the user cancelled a previous step."}

  tasks_display = ""
  try:
    for task in tasks:
      due_str = datetime.fromisoformat(task['due'].replace('Z', '+00:00')).strftime('%a, %b %d %Y') if task.get('due') else ""
      tasks_display += f"- {task['title']} (Due: {due_str})\n"
  except Exception as e:
    return {"error": f"Invalid date format for 'due'. Do not append notes to the date string. Use strict ISO format. Error: {e}"}

  decision = interrupt(f"{greeting}\n\nApprove adding the following task(s)?\n\n{tasks_display}\n\nApprove? (yes/no)")
  decision_clean = decision.strip().lower()
    
  affirmatives = ["yes", "sure", "ok", "yeah", "okay", "approve", "go ahead"]
    hesitancies = ['but', 'although', "instead", "no", "stop", "cancel", "quit", "not sure"]
  if not any(word in decision_clean for word in affirmatives) or any(word in decision.strip().lower() for word in hesitancies):
    session['cancel_pending_tools'] = True
    return {"message": f"User denied approval. Adding to google tasks cancelled. You may use this tool again if the user asks. Here is the user's message. If the user actually said yes/approve, retry this tool and tell them to try including 'yes' in their response. User's message: {decision.strip()}"}

  try:
    user_details = get_user_info(session['google_id'])
    user_refresh_token = user_details.get("refresh_token")
    
    if not user_refresh_token:
      return {"error": "No valid refresh token found. User must log in again. Addin to google tasks cancelled."}

    with open("client_secrets.json", "r") as f:
      client_info = json.load(f)["web"]

    creds = Credentials(
          token=None, 
          refresh_token=user_refresh_token,
          token_uri=client_info["token_uri"],
          client_id=client_info["client_id"],
          client_secret=client_info["client_secret"]
    )

    service = build('tasks', 'v1', credentials=creds)

    for task_input in tasks:
      body = {
          'title': task_input['title'],
          'notes': task_input.get('notes', '')
      }
      if task_input.get('due'):
          body['due'] = task_input['due']

      service.tasks().insert(tasklist='@default', body=body).execute()

    return {"message": f"User explicitly approved with: '{decision}'. Google tasks items added successfully. DO NOT call this tool again for these exact same items (unless the user explicitly asks to repeat these)."}

  except Exception as e:
    return {"error" : "Failed adding to google tasks. Error: " + str(e)}

@tool
def get_google_tasks():
  """
  Retrieve incomplete tasks from the user's default Google Tasks list.
  """
  try:
    user_details = get_user_info(session['google_id'])
    user_refresh_token = user_details.get("refresh_token")
    
    if not user_refresh_token:
      return {"error": "No valid refresh token found. User must log in again."}

    with open("client_secrets.json", "r") as f:
      client_info = json.load(f)["web"]

    creds = Credentials(
          token=None, 
          refresh_token=user_refresh_token,
          token_uri=client_info["token_uri"],
          client_id=client_info["client_id"],
          client_secret=client_info["client_secret"]
    )

    service = build('tasks', 'v1', credentials=creds)

    raw_tasks = service.tasks().list(
        tasklist='@default', 
        showCompleted=False
    ).execute()

    cleaned_tasks = [
        {
            "Title": task.get("title", ""),
            "Notes": task.get("notes", ""),
            "Due": task.get("due", "No due date")
        }
        for task in raw_tasks.get('items', [])
    ]

    return {"tasks" : cleaned_tasks}

  except Exception as e:
    return {"error" : str(e)}

tools = [send_email, add_calendar_events, get_calendar_events, add_google_tasks, get_google_tasks]