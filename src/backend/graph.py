from typing import TypedDict, Annotated
from datetime import datetime
from flask import session

from langchain_core.messages import SystemMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.sqlite import SqliteSaver

from database import conn, get_gemini_api_key
from tools import tools

class State(TypedDict):
  messages: Annotated[list, add_messages]

memory = SqliteSaver(conn)

def call_llm(state: State):
  GEMINI_API_KEY = get_gemini_api_key()

  if not GEMINI_API_KEY:
    return {"messages": [AIMessage(content="Please add your Gemini API key in the settings to continue!")]}

  session['cancel_pending_tools'] = False

  llm = ChatGoogleGenerativeAI(
    #model = 'gemini-3-flash-preview',
    model = 'gemini-3.1-flash-lite-preview',
    temperature = 0.7,
    google_api_key = GEMINI_API_KEY
  )
  llm_with_tools = llm.bind_tools(tools)

  system_prompt = (
    f"Today's date: {datetime.now().strftime('%A, %B %d, %Y')}. "
    "You are a helpful, optimistic, knowledgeable, encouraging Personal Goal Planning Assistant. Your job is to help the user achieve their goals by creating roadmaps using their Google Calendar, Tasks, and Gmail. "
    "\n\n"
    "STRATEGIC RULES:"
    "\n1. Propose a structured plan first and ask for confirmation before calling tools (you may call tools like retrieving events and tasks first to adjust that plan). Summarize suggested actions in a clear, concise format."
    "\n2. If a tool action is CANCELLED (user says 'No'), do not stop. Acknowledge the feedback, suggest the necessary changes, and ask for permission to try again with a corrected version."
    "\n3. If a tool executes SUCCESSFULLY, provide a brief success message. If it fails or is cancelled, explicitly tell the user it was not completed."
    "\n4. Ideally (unless the user has special requests), use google tasks and google calendar to create checkpoints and things to do and use gmail to send a roadmap. First check calendar / tasks for potential schedule conflicts. Add events and tasks. Finish a conversation with a roadmap summary of the goal(s) emailed to the user."
    "\n5. CRITICAL: When adding events or tasks for multiple weeks, you MUST batch them into a single tool call. Do NOT make separate tool calls for Week 1, Week 2, etc. Pass the entire list of events/tasks into one execution. After the user approves and the tools execute, you must call the send_email tool to send a summary."
    "\n\n"
    "FORMATTING RULES:"
    "\n- Do NOT use markdown (bolding, headers, etc.) in your regular chat responses. Use plain text only."
    "\n- You MAY use standard line breaks and simple characters (like • or -) for lists in email content."
    "\n- When providing a greeting for a tool, keep it to one or two sentences maximum to ensure the approval display remains compact."
    "Do NOT answer questions regarding unrelated queries."
  )
  try:
    response = llm_with_tools.invoke([SystemMessage(system_prompt)] + state['messages'][-20:])
    return {"messages": [response]}
  except Exception as e:
    print(f"LLM API Error: {e}")
    return {"messages": [AIMessage(content="I encountered a connection error or your API key is invalid. Please check your settings and try again.")]}


builder = StateGraph(State)

builder.add_node("llm_node", call_llm)
builder.add_node("tools", ToolNode(tools))

builder.add_edge(START, "llm_node")
builder.add_conditional_edges("llm_node", tools_condition)
builder.add_edge("tools", "llm_node")
builder.add_edge("llm_node", END)

graph = builder.compile(checkpointer=memory)