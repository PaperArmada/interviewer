from langgraph.graph.state import CompiledStateGraph

from agents.bg_task_agent.bg_task_agent import bg_task_agent
from agents.chatbot import chatbot
from agents.research_assistant import research_assistant
from agents.human_demo import human_demo

DEFAULT_AGENT = "research-assistant"


agents: dict[str, CompiledStateGraph] = {
    "chatbot": chatbot,
    "research-assistant": research_assistant,
    "bg-task-agent": bg_task_agent,
    "human_demo": human_demo,
}
