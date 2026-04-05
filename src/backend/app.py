"""
- python -m venv .venv
- source .venv/bin/activate
- pip install flask flask-cors python-dotenv google-api-python-client google-auth-oauthlib google-auth-httplib2 langchain langchain-core langchain-google-genai langgraph langgraph-checkpoint-sqlite
- npm install react-bootstrap bootstrap react-markdown
"""
import uuid
from flask import Flask, redirect, request, session, jsonify
from flask_cors import CORS

from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests
from langgraph.types import Command

from config import SECRET_APP_KEY, FRONTEND_CALLBACK_URL, CLIENT_SECRETS_FILE, SCOPES
from database import conn, get_user_info, addMessage
from graph import graph

app = Flask(__name__)
app.config["DEBUG"] = True
CORS(app)

app.secret_key = SECRET_APP_KEY

@app.route('/getLoginData')
def getDetails():
  if 'google_id' in session:
    user_details = get_user_info(session['google_id'])
    return jsonify({
      "loggedIn" : True,
      "user_google_id": session['google_id'],
      "user_name": user_details.get("name", "")
    })
  else:
    return jsonify({
      "loggedIn" : False,
      "user_google_id": "",
      "user_name": ""
    })

@app.route('/login')
def login():
  flow = Flow.from_client_secrets_file(
    CLIENT_SECRETS_FILE,
    scopes=SCOPES,
    redirect_uri=FRONTEND_CALLBACK_URL,
  )

  authorization_url, browser_id = flow.authorization_url(
    access_type="offline",
    include_granted_scopes="true",
    prompt="consent"
  )

  session["browser_id"] = browser_id
  session["code_verifier"] = flow.code_verifier
  return redirect(authorization_url)

@app.route('/callback')
def callback():
  flow = Flow.from_client_secrets_file(
    CLIENT_SECRETS_FILE,
    scopes=SCOPES,
    state=session["browser_id"],
    redirect_uri=FRONTEND_CALLBACK_URL
  )
  flow.code_verifier = session.get("code_verifier")
  flow.fetch_token(authorization_response=request.url)
  credentials = flow.credentials

  access_token = credentials.token
  refresh_token = credentials.refresh_token

  session['access_token'] = access_token
  session['refresh_token'] = refresh_token

  user_info = id_token.verify_oauth2_token(
    credentials.id_token, requests.Request(), flow.client_config["client_id"]
  )

  session['google_id'] = user_info['sub']
  session['name'] = user_info.get('name')
  session['user_email'] = user_info.get('email')

  local_cursor = conn.cursor()
  local_cursor.execute("""
      INSERT INTO user_sessions (google_id, access_token, refresh_token, name, user_email)
      VALUES (?, ?, ?, ?, ?)
      ON CONFLICT(google_id) DO UPDATE SET
          access_token = excluded.access_token,
          refresh_token = excluded.refresh_token,
          name = excluded.name,
          user_email = excluded.user_email
  """, (session['google_id'], access_token, refresh_token, session['name'], session['user_email']))

  conn.commit()
  local_cursor.close()

  return redirect('http://localhost:5173/')

@app.route('/logout')
def logout():
  session.clear()
  return redirect('http://localhost:5173/')

@app.route('/updateSettings', methods=['POST'])
def updateSettings():
  data = request.get_json(silent=True)
  if data is None: 
    return jsonify({"error": "Invalid JSON payload"}), 400
  
  google_id = session.get("google_id", "")
  if not google_id:
    return jsonify({"error" : "User not logged in."}), 400
  
  try:
    gemini_api_key = data.get("gemini_api_key", "")
    local_cursor = conn.cursor()
    local_cursor.execute("""
        UPDATE user_sessions 
        SET gemini_api_key = ? 
        WHERE google_id = ?
    """, (gemini_api_key, google_id))
    conn.commit()
    local_cursor.close()
    return jsonify({"success": True})
  except Exception as e:
    print(e)
    return jsonify({"error": "Error updating database"}), 500

@app.route('/create_chat', methods=['POST'])
def create_chat():
  google_id = session.get("google_id", "")
  if not google_id:
    return jsonify({"error" : "User not logged in."}), 400

  data = request.get_json(silent=True)
  chat_name = data.get("chat_name", "New Chat")

  thread_id = str(uuid.uuid4())

  local_cursor = conn.cursor()
  local_cursor.execute(
    "INSERT INTO chats (thread_id, google_id, chat_name) VALUES (?, ?, ?)",
    (thread_id, google_id, chat_name)
  )
  conn.commit()
  local_cursor.close()

  addMessage(thread_id, "AI", "Hi there! How can I help you?")

  return jsonify({"message": thread_id})

@app.route('/get_all_chats')
def get_all_chats():
  google_id = session.get("google_id", "")
  if not google_id:
    return jsonify({"error" : "User not logged in."}), 400

  local_cursor = conn.cursor()
  local_cursor.execute(
    "SELECT thread_id, chat_name, created_at FROM chats WHERE google_id = ? ORDER BY created_at DESC",
    (google_id,)
  )
  rows = local_cursor.fetchall()
  local_cursor.close()

  chats = [{"thread_id": row[0], "chat_name": row[1], "created_at": row[2]} for row in rows]
  return jsonify({"message": chats})

@app.route('/get_chat_messages', methods=['POST'])
def get_chat_messages():
  google_id = session.get("google_id", "")
  thread_id = request.get_json(silent=True).get("thread_id", "")
  if not google_id:
    return jsonify({"error": "User not logged in."}), 400

  if not thread_id:
    return jsonify({"error": "No thread_id found."}), 400
  
  local_cursor = conn.cursor()
  local_cursor.execute(
    "SELECT role, content, message_type, created_at FROM messages WHERE thread_id = ? ORDER BY created_at ASC",
    (thread_id,)
  )
  rows = local_cursor.fetchall()
  local_cursor.close()

  messages = [{
      "role": row[0],
      "content": row[1],
      "message_type": row[2],
      "created_at": row[3]
    } for row in rows
  ]
  return jsonify({"message": messages})

@app.route('/ask_ai', methods=['POST'])
def run_graph():
  data = request.get_json(silent=True)
  user_query = data.get("user_query", "")
  thread_id = data.get("thread_id", "")
  google_id = session.get("google_id", "")

  if not google_id:
    return jsonify({"role": "AI", "content" : "Google Account not found! Are you signed in?", "message_type": "error", "thread_id" : thread_id}), 200

  if not user_query:
    return jsonify({"role": "AI", "content" : "Please enter a valid query.", "message_type": "error", "thread_id" : thread_id}), 200

  if not thread_id:
    return jsonify({"role": "AI", "content" : "No chat id found! Try creating a new chat.", "message_type": "error", "thread_id" : thread_id}), 200

  config = {"configurable": {"thread_id": thread_id}}

  response = None

  addedMessageSuccessfully = addMessage(thread_id=thread_id, role="user", content=user_query)

  if not addedMessageSuccessfully:
    return jsonify({"role": "AI", "content" : "Unable to save chat message to database.", "message_type": "error", "thread_id" : thread_id}), 200

  try:
    print("Calling graph...")
    if graph.get_state(config).next:
      response = graph.invoke(Command(resume=user_query), config=config)
    else:
      response = graph.invoke({"messages": [{"role": "user", "content": user_query}]}, config=config)
    print("Done calling graph.")
    # print(response)
    # -------------------------------------------
    last_msg = response["messages"][-1]

    # Check for and print tool calls (or explicitly print "None")
    if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
        for tool in last_msg.tool_calls:
            print(f"\n🛠️ [TOOL CALL] Name: {tool['name']} | Parameters: {tool['args']}\n")
    else:
        print("\n🛠️ [TOOL CALL] None\n")
    # -------------------------------------------

    if response.get("__interrupt__"):
      message = (
          f'{response["__interrupt__"][0].value}'
      )
      addMessage(thread_id=thread_id, role="AI", content=message, message_type="approval")
      return jsonify({"role": "AI", "content" : message, "message_type" : "approval", "thread_id" : thread_id})

    last_message_content = response['messages'][-1].content
    
    if isinstance(last_message_content, str):
        ai_text = last_message_content
    elif isinstance(last_message_content, list) and len(last_message_content) > 0 and 'text' in last_message_content[0]:
        ai_text = str(last_message_content[0]['text'])
    else:
        ai_text = str(last_message_content)
    addMessage(thread_id=thread_id, role="AI", content=str(ai_text), message_type="regular")
    return jsonify({"role": "AI", "content": str(ai_text), "message_type" : "regular", "thread_id" : thread_id})

  except Exception as e:
    print(e)
    message = "Error: " + str(e)
    addMessage(thread_id=thread_id, role="AI", content=message, message_type="error")
    return jsonify({"role": "AI", "content" : message, "message_type": "error", "thread_id" : thread_id}), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)