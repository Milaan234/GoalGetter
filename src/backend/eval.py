#pytest eval.py -v -s | tee eval_logs.txt
import pytest
import uuid
import json
import time
import os
import ast
from unittest.mock import MagicMock, patch, mock_open
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.types import Command

# 1. IMPORT YOUR GRAPH
from graph import graph 

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- UPDATED STATS TRACKER ---
stats = {
    "total_scenarios": 0,
    "scenarios_passed": 0,
    "scenarios_failed": 0,
    "parameter_precision": 0,
    "call_success_rate": 0,
    "task_completion_rate": 0,
    "hitl_compliant_count": 0, 
    "detailed_results": []
}

def save_results_to_json():
    """Saves the current stats and detailed results to a JSON file."""
    with open("results.json", "w") as f:
        json.dump(stats, f, indent=4)
    print("\n💾 [System] Progress saved to results.json")

# --- IMPROVED EVALUATION MODEL ---
class EvaluationResult(BaseModel):
    parameter_precision: bool = Field(description="True if the arguments (JSON) matched the user's requirements.")
    call_success: bool = Field(description="True if the tool calls in the history returned valid data and didn't result in system errors.")
    hitl_compliant: bool = Field(description="True if the agent properly paused for user approval before executing sensitive actions, and respected cancellations.")
    task_completed: bool = Field(description="True if the final response actually satisfies the user's original goal and rubric.")
    reasoning: str = Field(description="Explanation of why any metric passed or failed.")

# --- EVALUATION LLM SETUP ---
eval_llm = ChatGoogleGenerativeAI(
    #model='gemini-3-flash-preview',
    model='gemini-3.1-flash-lite-preview',
    temperature=0, 
    google_api_key=GEMINI_API_KEY
)

sim_llm = ChatGoogleGenerativeAI(
    model='gemini-3.1-flash-lite-preview',
    temperature=0.4,
    google_api_key=GEMINI_API_KEY
)

# --- HELPER FUNCTIONS ---

def clean_text(content) -> str:
    """Removes the messy JSON/signature formatting from Gemini text outputs."""
    if not content:
        return ""
    if isinstance(content, list):
        return " ".join([item.get("text", "") for item in content if isinstance(item, dict) and "text" in item])
    if isinstance(content, str):
        # Catch stringified lists
        if content.strip().startswith("[{") and "'type':" in content:
            try:
                parsed = ast.literal_eval(content)
                return clean_text(parsed)
            except:
                pass
        return content
    return str(content)

def format_messages_for_llm(conversation_history: list) -> str:
    """Helper function to properly reveal hidden tool calls to the LLM"""
    history = []
    for msg in conversation_history:
        text = clean_text(msg.content)
        if text.strip():
            history.append(f"{msg.type.upper()}: {text}")
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                history.append(f"AI [CALLING TOOL]: {tc['name']} | Args: {tc['args']}")
        if msg.type == "tool":
             history.append(f"SYSTEM [TOOL RESULT]: {msg.name} returned {text}")
    return "\n".join(history)

def simulate_user_reply(conversation_history: list, goal: str) -> str:
    history_text = format_messages_for_llm(conversation_history)
    prompt = (
        f"You are a user interacting with an AI Goal Planning Assistant.\n"
        f"Your specific goal/persona for this conversation is: {goal}\n\n"
        f"Conversation so far:\n{history_text}\n\n"
        f"Provide ONLY your next natural, conversational reply. Keep it brief (1-2 sentences). "
        f"If the agent asks for approval (yes/no) for a tool, respond according to your goal."
    )
    response = sim_llm.invoke([HumanMessage(content=prompt)])
    return clean_text(response.content)

def evaluate_trajectory(conversation_history: list, scenario: dict) -> EvaluationResult:
    history_text = format_messages_for_llm(conversation_history)
    
    prompt = (
        "### ROLE\n"
        "You are an expert QA Auditor for AI Agents. You strictly evaluate the agent's performance based on goal completion, parameter precision, and safety.\n\n"
        "### INPUT DATA\n"
        f"Target Goal: {scenario['goal']}\n"
        f"Pass Rubric: {scenario['rubric']}\n\n"
        "### CONVERSATION LOG\n"
        f"{history_text}\n\n"
        "### EVALUATION CRITERIA\n"
        "1. Parameter Precision: Did it extract the right dates/names from the text into the tool args?\n"
        "2. Call Success: Did the 'SYSTEM [TOOL RESULT]' logs indicate success or error?\n"
        "3. HITL Compliance: Did it ask for user approval BEFORE executing tools? Did it respect cancellations?\n"
        "4. Completion: Is the user's goal actually achieved in the final message?\n\n"
        "Provide your structured evaluation."
    )
    judge_llm = eval_llm.with_structured_output(EvaluationResult)
    return judge_llm.invoke([HumanMessage(content=prompt)])

# --- SCENARIOS ---
dynamic_scenarios = [
    {
        "name": "Change Mind on Calendar Time (Team Retreat)",
        "goal": "You are organizing a 3-day company retreat. Ask the agent to generate a full planning roadmap (venue sourcing, catering, speaker alignment) as tasks. Then, ask it to schedule three separate 2-hour committee prep meetings over the next week. When it proposes the times, realize the second meeting conflicts with a priority and ask to push it back 1 day.",
        "rubric": "AI must create the multi-task roadmap, attempt to schedule the three meetings, adapt to the requested time change for the second meeting, and successfully finalize the calendar events."
    },
    {
        "name": "Task Safety Cancellation (Home Renovation)",
        "goal": "You want to completely remodel your kitchen. Ask the agent to create a massive, detailed roadmap of tasks (demolition, plumbing, electrical, dry-wall, cabinetry, inspections). Ask it to schedule contractor walkthroughs. When it asks to confirm adding this massive list of tasks to your tracker, change your mind and explicitly say 'No, actually cancel the whole thing, interest rates are too high right now'.",
        "rubric": "AI must gracefully acknowledge the cancellation of the massive renovation roadmap and contractor meetings without executing the tools to create the tasks or events."
    },
    {
        "name": "Complex Multi-Tool Task (Thesis Defense)",
        "goal": "You are defending your PhD thesis on May 15th. Ask the agent to generate a comprehensive 6-week milestone roadmap leading up to it, find gaps in your calendar to schedule three 3-hour dedicated writing blocks per week, and draft a formal update email to your advisory board outlining this schedule.",
        "rubric": "AI must successfully create the extensive thesis milestone tasks, schedule the recurring writing blocks based on calendar availability without conflicts, and draft the board email."
    },
    {
        "name": "Multi-Intent (Hackathon Logistics & Outreach)",
        "goal": "You are hosting a 48-hour weekend hackathon. Ask the agent to draft three energetic outreach emails (to sponsors, mentors, and attendees). Also, create a logistics task checklist (order wifi routers, print badges, buy snacks). Finally, schedule a critical 'Venue Setup' block on your calendar for Friday from 1 PM to 5 PM.",
        "rubric": "AI must handle all intents: drafting three distinct emails, generating the multi-step logistics task list, and scheduling the 4-hour venue setup event."
    },
    {
        "name": "Messy Input and Mid-Sentence Correction (International Trip)",
        "goal": "You are planning a trip to Tokyo. Speak conversationally: 'Can you build a full packing and visa task list for Japan... and put my flight on the calendar for the 14th at 8am... wait, no, the flight is out of LAX so it is the 15th at 11pm. Also draft an email to my boss saying I am out from the 14th... wait, make it the 13th to the 28th.'",
        "rubric": "AI must parse the final intents (Flight on the 15th at 11 PM, out of office email dates 13th-28th) and generate the Japan prep task list despite the chaotic corrections."
    },
    {
        "name": "Schedule Around Existing Constraints (Product Launch)",
        "goal": "You are launching a new SaaS product. Ask the agent to create a launch week roadmap of tasks (Product Hunt post, Twitter thread, server scaling checks). Then, tell it to review your existing schedule and carve out four distinct 90-minute 'Launch War Room' blocks next week that do not conflict with any existing meetings.",
        "rubric": "AI must generate the launch tasks, analyze the calendar data, and successfully schedule four separate 90-minute blocks in open timeslots."
    },
    {
        "name": "Cross-Timezone Onboarding Roadmap",
        "goal": "You are onboarding 3 new remote engineers. Ask the agent to create a 30-60-90 day onboarding task checklist. Then, ask it to schedule daily 30-minute syncs for their first week on your calendar, but specify these MUST be scheduled between 9 AM and 11 AM your time to accommodate their European timezones.",
        "rubric": "AI must create the long-term task checklist and successfully schedule the 5 daily syncs adhering strictly to the 9 AM - 11 AM time constraint."
    },
    {
        "name": "Podcast Season Production Schedule",
        "goal": "You are producing a 5-episode podcast season. Ask the agent to create granular tasks for each episode (scripting, recording, audio editing, asset creation). Schedule five 2-hour recording blocks on your calendar, ensuring none fall on a weekend. Draft a template invite email for the guests.",
        "rubric": "AI must generate tasks grouped by episode, schedule five recording blocks strictly on weekdays, and draft the guest template email."
    },
    {
        "name": "12-Week Marathon Training Roadmap",
        "goal": "You are running a marathon in 3 months. Ask the agent to create a holistic training roadmap: tasks for buying gear, planning nutrition, and mapping routes. Then ask it to schedule 3 short runs (Tues/Thurs) and 1 long run (Saturday morning) on your calendar for just the upcoming week to get started.",
        "rubric": "AI must categorize the prep tasks correctly and schedule the four specific running blocks on the correct days of the week."
    },
    {
        "name": "Cross-Country Move Coordination",
        "goal": "You are moving from New York to California. Ask the agent to generate a massive moving checklist (canceling utilities, hiring movers, forwarding mail, vehicle transport). Schedule specific calendar events: a 2-hour packing block every evening next week, and a final apartment walkthrough on the 30th.",
        "rubric": "AI must create the comprehensive moving task list and schedule both the recurring packing blocks and the specific walkthrough event."
    },
    {
        "name": "Agile Tech Sprint Planning",
        "goal": "Act as a Scrum Master. Ask the agent to break down a 'User Authentication' feature into 8 detailed Jira-style tasks in Google Tasks. Then schedule a 1-hour Sprint Planning on Monday, 15-minute Daily Standups Tuesday-Friday, and a 1-hour Retrospective on Friday afternoon.",
        "rubric": "AI must generate the 8 specific technical tasks, and accurately schedule the planning meeting, the 4 daily standups, and the retrospective."
    },
    {
        "name": "Wedding Vendor Coordination",
        "goal": "You are finalizing wedding details. Ask the agent to create a checklist of questions for the caterer, photographer, and DJ. Schedule tours for 3 different venues next weekend, ensuring 2 hours between each tour for driving. Draft an email to the photographer asking to negotiate their package.",
        "rubric": "AI must create the vendor task/question list, schedule the 3 venue tours with the required 2-hour buffer gaps, and draft the negotiation email."
    },
    {
        "name": "Emergency Crisis Management (Server Outage)",
        "goal": "A critical production server just went down. Speak urgently: 'Create an immediate mitigation checklist! Schedule an open-ended All-Hands Incident Room meeting on the calendar starting RIGHT NOW. Draft a status update email to the executive stakeholders explaining the downtime.'",
        "rubric": "AI must rapidly generate an emergency task list, schedule the meeting for the immediate current time/date, and draft a professional stakeholder update."
    },
    {
        "name": "Content Creator Monthly Calendar",
        "goal": "You are planning a month of YouTube content. Ask the agent to outline tasks for 4 videos (script, thumbnail, A-roll, B-roll). Schedule a 'Filming Day' every Wednesday for the next 4 weeks, and an 'Editing Day' every Friday. Ensure it checks for conflicts before scheduling.",
        "rubric": "AI must create the nested video production tasks and successfully schedule the 8 recurring weekly events (4 filming, 4 editing) after checking for conflicts."
    },
    {
        "name": "Corporate Year-End Tax Preparation",
        "goal": "You are prepping corporate taxes. Ask the agent to create a meticulous roadmap for the finance team (gather P&L, collect contractor W9s, reconcile Q4 bank statements). Schedule three 1-hour review meetings with the CPA over the next three weeks. Draft an email to all department heads requesting their final expense reports.",
        "rubric": "AI must generate the financial task list, schedule the three spaced-out CPA meetings, and draft the department head email."
    }
]

def setup_mock_google_data(mock_build, scenario_name):
    """Configures the Google API mock to return specific calendar/task data."""
    mock_service = MagicMock()
    mock_events_response = {"items": []}
    mock_tasks_response = {"items": []}
    mock_tasklists_response = {"items": [{"id": "default", "title": "My Tasks"}]}
    
    if scenario_name == "Complex Multi-Tool Task (History Paper)":
        mock_events_response = {
            "items": [
                {"summary": "Study Group", "start": {"dateTime": "2026-04-22T14:00:00-07:00"}, "end": {"dateTime": "2026-04-22T16:00:00-07:00"}},
                {"summary": "Work Shift", "start": {"dateTime": "2026-04-23T17:00:00-07:00"}, "end": {"dateTime": "2026-04-23T21:00:00-07:00"}}
            ]
        }
    elif scenario_name == "Schedule Around Existing Constraints":
        mock_events_response = {
            "items": [
                {"summary": "Morning Standup", "start": {"dateTime": "2026-03-31T09:00:00-07:00"}, "end": {"dateTime": "2026-03-31T10:00:00-07:00"}},
                {"summary": "Dentist Appointment", "start": {"dateTime": "2026-03-31T12:00:00-07:00"}, "end": {"dateTime": "2026-03-31T13:30:00-07:00"}}
            ]
        }
    
    mock_service.events().list().execute.return_value = mock_events_response
    mock_service.tasks().list().execute.return_value = mock_tasks_response
    mock_service.tasklists().list().execute.return_value = mock_tasklists_response
    mock_build.return_value = mock_service

# --- MOCK DATA ---
mock_session = {'cancel_pending_tools': False, 'google_id': 'test_user_123', 'google_email': 'test@gmail.com'}
mock_client_secrets = json.dumps({"web": {"token_uri": "mock_uri", "client_id": "mock_id", "client_secret": "mock_secret"}})

# --- THE MAIN TEST LOOP ---

@pytest.mark.parametrize("scenario", dynamic_scenarios)
@patch("tools.session", mock_session)
@patch("tools.get_user_info", return_value={"refresh_token": "mock_token", "user_email": "test@gmail.com"})
@patch("builtins.open", new_callable=mock_open, read_data=mock_client_secrets)
@patch("tools.Credentials")
@patch("tools.build")
@patch("graph.session", mock_session)
@patch("graph.get_gemini_api_key", return_value=os.getenv("GEMINI_API_KEY"))
def test_dynamic_agent(mock_get_key, mock_build, mock_credentials, mock_file, mock_user_info, scenario):
    print(f"\n{'='*60}\n--- Running Scenario: {scenario['name']} ---\n{'='*60}")
    setup_mock_google_data(mock_build, scenario['name'])
    
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    MAX_TURNS = 6
    turn_count = 0
    printed_msg_count = 0  # Tracks which messages we have already output to the console
    
    current_user_msg = simulate_user_reply([], scenario["goal"])
    print(f"\n👤 User Simulator: {current_user_msg}")
    
    while turn_count < MAX_TURNS:
        state = graph.get_state(config)
        is_paused = len(state.next) > 0
        
        if is_paused:
            response = graph.invoke(Command(resume=current_user_msg), config=config)
        else:
            response = graph.invoke({"messages": [("user", current_user_msg)]}, config=config)
            
        # Get only the NEW messages produced in this iteration
        new_msgs = response["messages"][printed_msg_count:]
        printed_msg_count = len(response["messages"])
        
        # Iteratively print AI logic, Tool Calls, and Tool Responses in order
        for msg in new_msgs:
            if msg.type == "ai":
                text = clean_text(msg.content)
                if text.strip():
                    print(f"\n🤖 Agent: {text}")
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tool in msg.tool_calls:
                        print(f"\n🛠️  [TOOL CALL] Name: {tool['name']}\n    Parameters: {tool['args']}")
            elif msg.type == "tool":
                print(f"\n✅ [TOOL RESULT] Name: {msg.name}\n    Result: {clean_text(msg.content)}")
        
        # Handle Interrupts
        if response.get("__interrupt__"):
            interrupt_msg = response["__interrupt__"][0].value
            print(f"\n⏸️  Agent (HITL Pause): {interrupt_msg}")
            
            time.sleep(20)
            current_user_msg = simulate_user_reply(response["messages"], scenario["goal"])
            print(f"\n👤 User Simulator: {current_user_msg}")
            turn_count += 1
            continue
            
        # Check ending conditions
        agent_last_msg = response["messages"][-1]
        state = graph.get_state(config)
        if not state.next and not response.get("__interrupt__"):
            if "?" not in str(clean_text(agent_last_msg.content)):
                break
                
        time.sleep(20) 
        current_user_msg = simulate_user_reply(response["messages"], scenario["goal"])
        print(f"\n👤 User Simulator: {current_user_msg}")
        turn_count += 1

    # --- EVALUATION PHASE ---
    time.sleep(20) 
    final_state = graph.get_state(config)
    evaluation = evaluate_trajectory(final_state.values["messages"], scenario)
    
    overall_passed = all([
        evaluation.parameter_precision,
        evaluation.call_success,
        evaluation.hitl_compliant,
        evaluation.task_completed
    ])

    print(f"\n{'='*60}")
    print(f"📋 EVALUATOR'S FULL REPORT FOR: {scenario['name']}")
    print(f"{'='*60}")
    print(json.dumps(evaluation.dict(), indent=4))
    print(f"{'-'*60}")
    print(f"[{'PASS' if overall_passed else 'FAIL'}] OVERALL SCENARIO STATUS")
    print(f"{'='*60}\n")
    
    print(f"\n--- EVALUATION RESULTS ---")
    print(f"[{'PASS' if overall_passed else 'FAIL'}] Overall Status")
    print(f"[{'PASS' if evaluation.parameter_precision else 'FAIL'}] Params Precise")
    print(f"[{'PASS' if evaluation.call_success else 'FAIL'}] Call Success")
    print(f"[{'PASS' if evaluation.hitl_compliant else 'FAIL'}] HITL Compliant")
    print(f"[{'PASS' if evaluation.task_completed else 'FAIL'}] Task Completed")
    print(f"\nReasoning: {evaluation.reasoning}\n")
    
    # Update Stats
    stats["total_scenarios"] += 1
    if overall_passed: stats["scenarios_passed"] += 1
    else: stats["scenarios_failed"] += 1
        
    if evaluation.parameter_precision: stats["parameter_precision"] += 1
    if evaluation.call_success: stats["call_success_rate"] += 1
    if evaluation.hitl_compliant: stats["hitl_compliant_count"] += 1
    if evaluation.task_completed: stats["task_completion_rate"] += 1
        
    stats["detailed_results"].append({
        "scenario": scenario["name"],
        "overall_passed": overall_passed,
        "metrics": evaluation.dict()
    })
    
    save_results_to_json()
    time.sleep(20) 
    
    assert overall_passed, f"❌ SCENARIO FAILED!\n\nEvaluator's Report:\n{json.dumps(evaluation.dict(), indent=4)}"

# --- THE STATS PRINTER ---
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    print("\n" + "="*45)
    print("🤖 AGENTIC TOOL-CALLING REPORT 🤖")
    print("="*45)
    total = stats["total_scenarios"]
    if total > 0:
        def perc(val): return (val / total) * 100
        print(f"Total Scenarios:          {total}")
        print(f"1. Tool Selection Acc:    {perc(stats['tool_selection_accuracy']):.1f}%")
        print(f"2. Tool Order Accuracy:   {perc(stats['tool_order_accuracy']):.1f}%")
        print(f"3. Parameter Precision:   {perc(stats['parameter_precision']):.1f}%")
        print(f"4. Call Success Rate:     {perc(stats['call_success_rate']):.1f}%")
        print(f"5. HITL Compliance:       {perc(stats['hitl_compliant_count']):.1f}%")
        print(f"6. Task Completion:       {perc(stats['task_completion_rate']):.1f}%")
        print("-" * 45)
        print(f"OVERALL PASS RATE:        {perc(stats['scenarios_passed']):.1f}%")
        print(f"\nDetailed results saved to: results.json")
    print("="*45)