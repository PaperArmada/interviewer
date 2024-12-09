from langchain_core.tools import tool
from langgraph.graph import MessagesState, StateGraph, END, START
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from langgraph.checkpoint.memory import MemorySaver


# Define the tools
@tool
def search(query: str):
    """Perform a simple search."""
    return f"Search result for query '{query}': Example result."


class AskHuman(BaseModel):
    """Ask a human a clarifying question."""
    question: str


tools = [search]
tool_node = ToolNode(tools)

# Set up the model
model = ChatOpenAI(model="gpt-4o-mini")
model = model.bind_tools(tools + [AskHuman])

# Define the decision function
def should_continue(state):
    messages = state["messages"]
    last_message = messages[-1]
    if not last_message.tool_calls:
        return "end"
    elif last_message.tool_calls[0]["name"] == "AskHuman":
        return "ask_human"
    else:
        return "continue"

# Define the model node function
def call_model(state):
    messages = state["messages"]
    response = model.invoke(messages)
    return {"messages": [response]}

# Define the ask_human node
def ask_human(state):
    return {"messages": [{"type": "human", "content": "What should I do next?"}]}

# Build the workflow
workflow = StateGraph(MessagesState)
workflow.add_node("agent", call_model)
workflow.add_node("action", tool_node)
workflow.add_node("ask_human", ask_human)

workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", should_continue, {
    "continue": "action",
    "ask_human": "ask_human",
    "end": END,
})
workflow.add_edge("action", "agent")
workflow.add_edge("ask_human", "agent")

# Compile the workflow with a memory saver
memory = MemorySaver()
human_demo = workflow.compile(checkpointer=memory, interrupt_before=["ask_human"])