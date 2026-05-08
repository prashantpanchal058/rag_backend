"""
LangGraph RAG Agent Implementation
"""

from typing import Any, List, Dict, Optional
from langchain.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from langgraph.prebuilt import create_react_agent
from typing_extensions import Annotated

from src.rag.retrieval.index import retrieve_context
from src.rag.retrieval.utils import prepare_prompt_and_invoke_llm
from src.services.llm import gemini


# =============================================================================
# PROMPTS
# =============================================================================

BASE_SYSTEM_PROMPT = """You are a helpful AI assistant with access to a RAG (Retrieval-Augmented Generation) tool that searches project-specific documents.

For every user question:

1. Do not assume any question is purely conceptual or general.  
2. Use the `rag_search` tool immediately with a clear and relevant query derived from the user's question. 
3. Use the chat history to understand the context and references in the current question. 
4. Carefully review the retrieved documents and base your entire answer on the RAG results.  
5. If the retrieved information fully answers the user's question, respond clearly and completely using that information.  
6. If the retrieved information is insufficient or incomplete, explicitly state that and provide helpful suggestions or guidance based on what you found.  
7. Always present answers in a clear, well-structured, and conversational manner.

**Make sure to call the rag_search tool correctly**
**Never answer without first querying the RAG tool. This ensures every response is grounded in project-specific context and documentation.**
"""


def format_chat_history(chat_history: List[Dict[str, str]]) -> str:
    if not chat_history:
        return ""
    formatted_messages = []
    for msg in chat_history:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        role_label = "User Message" if role.lower() == "user" else "AI Message"
        formatted_messages.append(f"{role_label}: {content}")
    return "\n\n".join(formatted_messages)


def get_system_prompt(chat_history: Optional[List[Dict[str, str]]] = None) -> str:
    prompt = BASE_SYSTEM_PROMPT
    if chat_history:
        formatted_history = format_chat_history(chat_history)
        if formatted_history:
            prompt += "\n\n### Previous Conversation Context\n"
            prompt += "The following is the recent conversation history for context:\n\n"
            prompt += formatted_history
            prompt += "\n\nUse this conversation history to understand context and references in the current question."
    return prompt


# =============================================================================
# TOOLS
# =============================================================================

def create_rag_tool(project_id: str):
    """Create a RAG search tool bound to a specific project."""

    @tool
    def rag_search(
        query: str,
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command:
        """
        Search through project documents using RAG.
        Use this tool for every user question to retrieve relevant context.

        Args:
            query: The search query to find relevant information
            tool_call_id: Injected tool call ID for message tracking
        """
        try:
            texts, images, tables, citations = retrieve_context(project_id, query)

            if not texts:
                return Command(
                    update={
                        "messages": [
                            ToolMessage(
                                "No relevant information found in the project documents for this query.",
                                tool_call_id=tool_call_id,
                            )
                        ]
                    }
                )
            response = prepare_prompt_and_invoke_llm(
                user_query=query,
                texts=texts,
                images=images,
                tables=tables,
            )

            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=response,
                            tool_call_id=tool_call_id,
                        )
                    ],
                }
            )

        except Exception as e:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            f"Error retrieving information: {str(e)}",
                            tool_call_id=tool_call_id,
                        )
                    ]
                }
            )

    return rag_search


# =============================================================================
# AGENT CREATION
# =============================================================================

def create_rag_agent(
    project_id: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
):
    """
    Create a simple RAG agent for a specific project.

    Args:
        project_id: The UUID of the project to search documents from
        chat_history: Optional previous conversation messages for context

    Returns:
        A compiled LangGraph agent ready to invoke

    Example:
        >>> agent = create_rag_agent(project_id="abc-123")
        >>> result = agent.invoke({
        ...     "messages": [{"role": "user", "content": "What is X?"}]
        ... })
        >>> print(result["messages"][-1].content)
    """
    tools = [create_rag_tool(project_id)]
    system_prompt = get_system_prompt(chat_history=chat_history)

    agent = create_react_agent(
        model=gemini["mini_llm"],
        tools=tools,
        prompt=system_prompt,
    )

    return agent