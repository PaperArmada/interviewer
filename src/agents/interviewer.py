from datetime import datetime
from typing import Dict, List, Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig, RunnableLambda, RunnableSerializable
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, MessagesState, StateGraph

from core import get_model, settings
import json
import logging

logger = logging.getLogger(__name__)

class AgentState(MessagesState, total=False):
    idx: int  # Current question index within a category
    category_idx: int  # Current category index
    questions: Dict[str, Any]  # Structured questions dictionary
    eval_criteria: Dict[str, Any]  # Evaluation criteria
    eval_results: List[Dict[str, Any]]  # Evaluation results for each question
    categories: List[str]  # List of categories
    follow_up_count: int  # Follow-up count tracking
    sufficient_response: bool  # Whether the latest response was sufficient
    user_question: bool  # Whether the user is asking a question
    last_interrupted_node: str  # Track where the graph interrupts for human input

current_date = datetime.now().strftime("%B %d, %Y")

### UTILITY FUNCTIONS ###

PROMPTS = {
    "evaluate_response": """
    Evaluate the following response for the competency "{competency}":
    Question: {question}
    Response: {response}

    Score the response on a scale of 1-5 based on these criteria:
    {criteria}
    """,
    "closing_feedback": """
    Based on the following responses, generate a summary of the candidate's performance:
    Responses: {responses}
    """,
    "follow_up": """
    Generate a follow-up question to clarify or expand on the competency "{competency}".
    Question: {original_question}
    Response: {response}
    """,
    "determine_question": """
    Interpret the user's input to decide whether they are ready to begin the interview or have a question.
    Input: {user_input}

    Respond only with "yes" if they have a question, and "no" if they do not.
    """,
    "respond_to_question": """
    The user has asked a question: {user_input}. Provide a helpful and concise answer to assist them.
    """,
}

def get_prompt(name, **kwargs):
    return PROMPTS[name].format(**kwargs)

def validate_state(state: AgentState):
    if not state.get("questions"):
        raise ValueError("Questions not defined in the state.")
    if not state.get("eval_criteria"):
        raise ValueError("Evaluation criteria not defined.")

async def invoke_model_with_prompt(prompt: str, config: RunnableConfig) -> str:
    model = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
    model_runnable = wrap_model(model)
    try:
        result = await model_runnable.ainvoke({"messages": [HumanMessage(content=prompt)]}, config)
        return result["messages"][-1].content
    except Exception as e:
        logger.error(f"Model invocation failed: {e}")
        raise

def wrap_model(model: BaseChatModel) -> RunnableSerializable[AgentState, AIMessage]:
    return RunnableLambda(lambda state: state["messages"], name="StateModifier") | model

### CORE FUNCTIONS ###

def fetch_question(state: AgentState) -> dict:
    categories = state.get("categories", list(state["questions"].keys()))
    category_idx = state.get("category_idx", 0)
    category = categories[category_idx]
    idx = state.get("idx", 0)

    questions = state["questions"].get(category, [])
    if idx >= len(questions):
        state["category_idx"] += 1
        state["idx"] = 0
        if state["category_idx"] >= len(categories):
            return {"question": "Interview complete.", "competency": None}
        category = categories[state["category_idx"]]
        questions = state["questions"].get(category, [])
    return questions[idx]

async def evaluate_response(state: AgentState, response: str, config: RunnableConfig) -> dict:
    question_info = fetch_question(state)
    competency = question_info["competency"]
    criteria = state["eval_criteria"].get("scoring_criteria", {}).get("competencies", {}).get(competency, {})

    prompt = get_prompt(
        "evaluate_response",
        competency=competency,
        question=question_info["question"],
        response=response,
        criteria=json.dumps(criteria, indent=2),
    )
    try:
        content = await invoke_model_with_prompt(prompt, config)
        score = int([line for line in content.split("\n") if line.strip().isdigit()][0])
    except Exception:
        logger.error("Failed to extract score.")
        score = None

    state.setdefault("eval_results", []).append(
        {
            "question": question_info["question"],
            "competency": competency,
            "score": score,
            "rationale": content,
        }
    )
    return {"score": score, "rationale": content}

async def determine_next_path(state: AgentState) -> str:
    """
    Determine the next path based on the current state.
    """
    last_input = state["messages"][-1].content.lower()

    if state.get("user_question", False):
        return "answer_question"

    if not state.get("sufficient_response", False) and state.get("follow_up_count", 0) < 2:
        return "follow_up_question"

    if state.get("idx", 0) >= len(fetch_question(state)):
        return "closing_remarks"

    return "fetch_question"

async def route_welcome_input(state: AgentState) -> str:
    """
    Routing function to determine the next step after the welcome_input node.

    If the user has a question (state["user_question"] is True), route to "answer_question".
    Otherwise, route to "fetch_question".
    """
    if state.get("user_question", False):
        return "answer_question"
    return "fetch_question"

### NODES ###

async def welcome_node(state: AgentState, config: RunnableConfig) -> AgentState:
    welcome_message = f"""
    Welcome, {state.get('candidate_name', 'Candidate')}, to the interview process. Before we begin, do you have any questions or are you ready to start?
    """
    state["messages"].append(AIMessage(content=welcome_message))
    return state

def make_record_interrupted_node(node_name: str):
    async def record_interrupted_node(state: AgentState) -> AgentState:
        """
        Node to record the name of the next user input node in the state.
        """
        state["last_interrupted_node"] = node_name
        return state
    return record_interrupted_node

async def user_input_node(state: AgentState, user_input: str, config: RunnableConfig) -> AgentState:
    """
    Node to facilitate user input.
    """
    pass

async def determine_question_node(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    Node to determine if the user has a question that should be responded to.
    """
    last_input = state["messages"][-1].content
    prompt = get_prompt("determine_question", user_input=last_input)
    content = await invoke_model_with_prompt(prompt, config)
    state["user_question"] = "yes" in content.lower()
    return state

async def fetch_question_node(state: AgentState, config: RunnableConfig) -> AgentState:
    question_info = fetch_question(state)
    state["messages"].append(AIMessage(content=question_info["question"]))
    state["current_competency"] = question_info["competency"]
    state["idx"] += 1
    return state

async def follow_up_question_node(state: AgentState, config: RunnableConfig) -> AgentState:
    prompt = get_prompt(
        "follow_up",
        original_question=state["messages"][-2].content,
        response=state["messages"][-1].content,
        competency=state["current_competency"],
    )
    follow_up = await invoke_model_with_prompt(prompt, config)
    state["messages"].append(AIMessage(content=follow_up))
    return state

async def update_response_sufficiency_node(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    Node to update the "sufficient_response" field in the state based on evaluation criteria.
    """
    last_response = state["messages"][-1].content
    competency = state.get("current_competency", "")
    prompt = f"""
    Evaluate if the following response sufficiently addresses the competency "{competency}". 
    Response: {last_response}

    Answer only with either "yes" or "no".
    """
    content = await invoke_model_with_prompt(prompt, config)
    state["sufficient_response"] = "yes" in content.lower()
    return state

async def closing_remarks_node(state: AgentState, config: RunnableConfig) -> AgentState:
    responses = [m.content for m in state["messages"] if isinstance(m, HumanMessage)]
    prompt = get_prompt("closing_feedback", responses=json.dumps(responses, indent=2))
    feedback = await invoke_model_with_prompt(prompt, config)
    closing_message = f"""
    Thank you for your time. Here is our feedback:
    {feedback}
    """
    state["messages"].append(AIMessage(content=closing_message))
    return state

async def final_evaluation_node(state: AgentState, config: RunnableConfig) -> AgentState:
    final_scores = {
        competency: sum(r["score"] for r in state["eval_results"] if r["competency"] == competency)
        for competency in set(r["competency"] for r in state["eval_results"])
    }
    summary = {
        k: v / len(state["eval_results"])
        for k, v in final_scores.items()
    }
    prompt = f"Final evaluation: {json.dumps(summary, indent=2)}"
    evaluation = await invoke_model_with_prompt(prompt, config)
    state["final_evaluation"] = evaluation
    return state

async def answer_question_node(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    Node to handle providing professional and appropriate answers to user questions.
    """
    last_input = state["messages"][-1].content
    prompt = get_prompt("respond_to_question", user_input=last_input)
    response = await invoke_model_with_prompt(prompt, config)
    state["messages"].append(AIMessage(content=response))
    return state


### GRAPH DEFINITION ###

agent = StateGraph(AgentState)

agent.add_node("welcome", welcome_node)
agent.add_node("lead_welcome", make_record_interrupted_node("welcome_input"))
agent.add_node("welcome_input", user_input_node)
agent.add_node("welcome_question", determine_question_node)
agent.add_node("answer_welcome_question", answer_question_node)
agent.add_node("fetch_question", fetch_question_node)
agent.add_node("lead_interview", make_record_interrupted_node("interview_input"))
agent.add_node("interview_input", user_input_node)
agent.add_node("interview_question", determine_question_node)
agent.add_node("update_response_sufficiency", update_response_sufficiency_node)
agent.add_node("follow_up_question", follow_up_question_node)
agent.add_node("answer_question", answer_question_node)
agent.add_node("closing_remarks", closing_remarks_node)
agent.add_node("final_evaluation", final_evaluation_node)

agent.set_entry_point("welcome")
agent.add_edge("welcome", "lead_welcome")
agent.add_edge("lead_welcome", "welcome_input")
agent.add_edge("welcome_input", "welcome_question")
agent.add_edge("answer_welcome_question", "lead_welcome")
agent.add_edge("fetch_question", "lead_interview")
agent.add_edge("lead_interview", "interview_input")
agent.add_edge("interview_input", "interview_question")
agent.add_edge("interview_question", "update_response_sufficiency")
agent.add_edge("answer_question", "lead_interview")
agent.add_edge("follow_up_question","lead_interview")

agent.add_conditional_edges(
    source="welcome_question",
    path=route_welcome_input,
    path_map={
        "answer_question": "answer_welcome_question",
        "fetch_question": "fetch_question",
    },
)
agent.add_conditional_edges(
    source="update_response_sufficiency",
    path=determine_next_path,
    path_map={
        "follow_up_question": "follow_up_question",
        "fetch_question": "fetch_question",
        "closing_remarks": "closing_remarks",
        "answer_question": "answer_question",
    },
)

### COMPILE ###

interviewer = agent.compile(checkpointer=MemorySaver())