from datetime import datetime
from typing import Literal, Dict, List, Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig, RunnableLambda, RunnableSerializable
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.managed import RemainingSteps
from langgraph.prebuilt import ToolNode

from agents.tools import calculator
from core import get_model, settings
import json

class AgentState(MessagesState, total=False):
    """`total=False` is PEP589 specs.

    documentation: https://typing.readthedocs.io/en/latest/spec/typeddict.html#totality
    """

    idx: int  # Current question index within a category
    category_idx: int  # Current category index
    questions: Dict[str, Any]  # Structured questions dictionary
    eval_criteria: Dict[str, Any]  # Evaluation criteria
    eval_results: List[dict[str, Any]]  # Evaluation results for each question
    categories: List[str]  # List of categories (e.g., ["behavioral", "technical"])
    follow_up_count: int  # Tracking how many times the system elects to follow up on a given question

tools = [calculator]
current_date = datetime.now().strftime("%B %d, %Y")

### FUNCTIONS ###

def wrap_model(model: BaseChatModel) -> RunnableSerializable[AgentState, AIMessage]:
    model = model.bind_tools(tools)
    preprocessor = RunnableLambda(
        lambda state: state["messages"],
        name="StateModifier",
    )
    return preprocessor | model

def fetch_next_question(state: AgentState) -> dict:
    """
    Fetch the next question based on the current state.
    Dynamically handles categories and question indices.
    """
    categories = state.get("categories", list(state["questions"]["interview_questions"].keys()))
    category_idx = state.get("category_idx", 0)
    category = categories[category_idx]
    idx = state.get("idx", 0)

    # Get the list of questions for the current category
    questions_by_category = state["questions"]["interview_questions"].get(category, [])

    # Check if we've exhausted all questions in this category
    if idx >= len(questions_by_category):
        # Move to the next category
        state["category_idx"] += 1
        state["idx"] = 0
        if state["category_idx"] >= len(categories):
            return {"question": "Interview complete. Thank you for your time!", "competency": None}

        # Update category and fetch the first question in the new category
        category = categories[state["category_idx"]]
        questions_by_category = state["questions"]["interview_questions"].get(category, [])
        return questions_by_category[0]

    # Return the current question in the category
    return questions_by_category[idx]

def determine_next_path(state: AgentState) -> str:
    """
    Determine the next path based on the current state of the interview.

    Returns:
        str: The name of the next node.
    """
    # Check if a follow-up question is warranted and within the allowed limit
    if state.get("follow_up_count", 0) < 2 and not state.get("sufficient_response", False):
        return "follow_up_question"
    
    # Check if all questions in the current category have been asked
    current_category = state.get("category", "behavioral")
    questions = state["questions"]["interview_questions"].get(current_category, [])
    if state.get("idx", 0) + 1 >= len(questions):
        return "end_interview"
    
    # Default to fetching the next question
    return "fetch_question"

async def acall_model(state: AgentState, config: RunnableConfig) -> AgentState:
    m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
    model_runnable = wrap_model(m)
    response = await model_runnable.ainvoke(state, config)

    if state["remaining_steps"] < 2 and response.tool_calls:
        return {
            "messages": [
                AIMessage(
                    id=response.id,
                    content="Sorry, need more steps to process this request.",
                )
            ]
        }
    # We return a list, because this will get added to the existing list
    return {"messages": [response]}



async def evaluate_response(state: AgentState, response: str, config: RunnableConfig) -> dict:
    """
    Evaluate a candidate's response and assign a score based on evaluation criteria.
    """
    question_info = fetch_next_question(state)
    competency = question_info["competency"]
    criteria = state["eval_criteria"]["scoring_criteria"]["competencies"].get(competency, {})

    prompt = f"""
    Evaluate the following response for the competency "{competency}":
    Question: {question_info["question"]}
    Response: {response}

    Score the response on a scale of 1-5 based on these criteria:
    {json.dumps(criteria, indent=2)}
    """
    m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
    model_runnable = wrap_model(m)
    result = await model_runnable.ainvoke({"messages": [HumanMessage(content=prompt)]}, config)
    content = result["messages"][-1].content

    # Extract score and rationale
    score = None
    try:
        score = int([line for line in content.split("\n") if line.strip().isdigit()][0])
    except Exception:
        pass
    rationale = content

    # Store evaluation results
    state.setdefault("eval_results", []).append({
        "question": question_info["question"],
        "competency": competency,
        "score": score,
        "rationale": rationale
    })

    # Advance to the next question
    state["idx"] += 1
    return {"score": score, "rationale": rationale}

### NODE DEFINITIONS ###

async def welcome_node(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    Deliver the welcome message to the candidate.
    """
    # Scripted welcome message
    scripted_welcome = f"""
    Welcome, {state.get('candidate_name', 'Candidate')}, and thank you for taking the time to interview
    with us today for the {state.get('position', 'role')} position at {state.get('company', 'our company')}.

    We\'re excited to learn more about your background, experience, and how you might contribute
    to our mission of {state.get('company_mission', 'driving innovation')}.

    Here\'s what to expect during today\'s interview:
    1. You\'ll be asked a series of questions designed to explore your:
       - Technical expertise,
       - Problem-solving abilities,
       - Adaptability,
       - Collaboration skills, and
       - Alignment with our company values.
    2. Feel free to take your time with each question, and don\'t hesitate to ask for clarification
       or additional context if needed.
    3. At the end of the interview, you\'ll receive information about the next steps, and you\'ll also have
       an opportunity to share any final remarks or questions.

    Before we begin, do you have any questions about the process, or are you ready to get started?

    When you\'re ready, just let me know!
    """

    # Add the welcome message to the conversation
    state["messages"].append(AIMessage(content=scripted_welcome))
    return state


async def fetch_question_node(state: AgentState, config: RunnableConfig) -> AgentState:
    question_info = fetch_next_question(state)
    state["messages"].append(AIMessage(content=question_info["question"]))
    state["current_competency"] = question_info["competency"]
    return state

async def routing_node(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    A simplified routing node that prepares the state for the next transition.
    The conditional logic for routing is now handled by `determine_next_path`.
    """
    # Ensure follow-up count is initialized
    state["follow_up_count"] = state.get("follow_up_count", 0)
    
    # No direct routing logic here; state preparation only
    return state

async def follow_up_question_node(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    Generate a follow-up question based on the original question,
    response, and evaluation.
    """
    original_question = state["messages"][-2].content
    response = state["messages"][-1].content
    competency = state["current_competency"]

    prompt = f"""
    Based on the following question and response, generate a follow-up question
    that will clarify or expand on the competency "{competency}".

    Question: {original_question}
    Response: {response}
    """
    m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
    model_runnable = wrap_model(m)
    result = await model_runnable.ainvoke({"messages": [HumanMessage(content=prompt)]}, config)
    follow_up = result["messages"][-1].content

    state["messages"].append(AIMessage(content=follow_up))
    return state

async def closing_remarks_node(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    Generate closing remarks that include:
    - LLM-generated appreciation comments based on the candidate's responses.
    - Scripted information about next steps.
    - An invitation for the candidate's closing remarks.
    """
    # Extract candidate responses for LLM evaluation
    responses = [m.content for m in state["messages"] if m.type == "human"]

    # Generate LLM feedback
    prompt = f"""
    Based on the following interview responses, generate a summary of what was 
    most impressive or appreciated about the candidate's performance. Provide a 
    professional and encouraging tone.

    Candidate Responses:
    {json.dumps(responses, indent=2)}

    Summary:
    """
    m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
    model_runnable = wrap_model(m)
    llm_feedback_result = await model_runnable.ainvoke({"messages": [HumanMessage(content=prompt)]}, config)
    llm_feedback = llm_feedback_result["messages"][-1].content

    # Scripted closing remarks
    scripted_closing = f"""
    Thank you, {state.get('candidate_name', 'Candidate')}, for your time and thoughtful responses today.
    We truly appreciate the effort you put into sharing your experiences and perspectives.

    {llm_feedback}

    Next steps: Our team will review your interview responses in detail, and you can
    expect to hear back within the next few days. If you have any final remarks or 
    questions, feel free to share them now.
    """

    # Add the closing remarks to the conversation
    state["messages"].append(AIMessage(content=scripted_closing))
    return state


async def end_interview_node(state: AgentState, config: RunnableConfig) -> AgentState:
    state["messages"].append(AIMessage(content="Thank you for completing the interview!"))
    return state

async def evaluate_response_node(state: AgentState, config: RunnableConfig) -> AgentState:
    response = state["messages"][-1].content  # Last user message
    evaluation = await evaluate_response(state, response, config)

    # If we've exhausted the questions, move to the end node
    categories = state.get("categories", list(state["questions"]["interview_questions"].keys()))
    if state["category_idx"] >= len(categories):
        return state  # Stay in this node until transitioned

    return state

async def final_evaluation_node(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    Perform automated evaluation of the candidate based on their interview performance.
    Generate a final recommendation and rationale.
    """
    # Aggregate scores for each competency
    final_scores = {}
    for result in state["eval_results"]:
        competency = result["competency"]
        score = result["score"]
        if competency not in final_scores:
            final_scores[competency] = []
        final_scores[competency].append(score)

    # Calculate average scores for each competency
    summary_scores = {k: sum(v) / len(v) for k, v in final_scores.items()}

    # Generate a professional evaluation summary using the LLM
    prompt = f"""
    Based on the following competency scores and the candidate's interview responses, 
    provide a professional evaluation summary. Include strengths, areas for improvement, 
    and a final recommendation (e.g., Highly Recommended, Recommended, or Not Recommended).

    Competency Scores:
    {json.dumps(summary_scores, indent=2)}

    Candidate Responses:
    {json.dumps([m.content for m in state["messages"] if m.type == "human"], indent=2)}

    Evaluation Summary:
    """
    m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
    model_runnable = wrap_model(m)
    evaluation_result = await model_runnable.ainvoke({"messages": [HumanMessage(content=prompt)]}, config)
    evaluation_summary = evaluation_result["messages"][-1].content

    # Store the evaluation summary in the state
    state["final_evaluation"] = {
        "scores": summary_scores,
        "summary": evaluation_summary,
    }

    # Add a message summarizing the evaluation for logging or debugging
    state["messages"].append(AIMessage(content="Final evaluation completed."))
    return state


# Define the graph
agent = StateGraph(AgentState)

# Add Nodes
agent.add_node("welcome", welcome_node)
agent.add_node("fetch_question", fetch_question_node)
agent.add_node("evaluate_response", evaluate_response_node)
agent.add_node("routing", routing_node)
agent.add_node("follow_up_question", follow_up_question_node)
agent.add_node("closing_remarks", closing_remarks_node)
agent.add_node("final_evaluation", final_evaluation_node)

# Add Edges
agent.set_entry_point("welcome")
agent.add_edge("welcome", "fetch_question")
agent.add_edge("fetch_question", "evaluate_response")
agent.add_edge("evaluate_response", "routing")

# Use `add_conditional_edges` for routing logic
agent.add_conditional_edges(
    source="routing",
    path=determine_next_path,  # Callable to determine the next node
    path_map={
        "follow_up_question": "follow_up_question",
        "fetch_question": "fetch_question",
        "end_interview": "closing_remarks",
    },
)

agent.add_edge("closing_remarks", "final_evaluation")


# After "model", if there are tool calls, run "tools". Otherwise END.
def pending_tool_calls(state: AgentState) -> Literal["tools", "done"]:
    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage):
        raise TypeError(f"Expected AIMessage, got {type(last_message)}")
    if last_message.tool_calls:
        return "tools"
    return "done"


agent.add_conditional_edges("model", pending_tool_calls, {"tools": "tools", "done": END})

interviewer = agent.compile(checkpointer=MemorySaver())