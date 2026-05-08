from fastapi import APIRouter, Depends, HTTPException
from src.services.supabase_client import supabase
from src.services.clerkAuth import get_current_user_clerk_id
from src.models.index import ChatCreate
from typing import Dict, List
from src.models.index import MessageCreate, MessageRole
from src.agents.simple_agent.agent import create_rag_agent

router = APIRouter()

def get_chat_history(
    chat_id: str,
    user_id: str,
    exclude_message_id: str = None
) -> List[Dict[str, str]]:
    try:
        query = (
            supabase.table("messages")
            .select("id, role, content")
            .eq("chat_id", chat_id)
            .eq("user_id", user_id)  # ✅ security
            .order("created_at", desc=True)  # latest first
            .limit(10)  # ✅ fetch only what you need
        )

        if exclude_message_id:
            query = query.neq("id", exclude_message_id)

        response = query.execute()

        # Handle Supabase error
        if hasattr(response, "error") and response.error:
            raise Exception(response.error)

        if not response.data:
            return []

        # Reverse to chronological order (old → new)
        messages = list(reversed(response.data))

        return [
            {
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            }
            for msg in messages
        ]

    except Exception as e:
        # 🔥 Don't silently ignore
        return []


@router.post("/{project_id}/chats/{chat_id}/messages")
async def send_message(
    project_id: str,
    chat_id: str,
    message: MessageCreate,
    current_user_clerk_id: str = Depends(get_current_user_clerk_id),
):
    try:
        # ─────────────────────────────────────────
        # Step 0: Verify chat belongs to user + project
        # ─────────────────────────────────────────
        chat_check = (
            supabase.table("chats")
            .select("id")
            .eq("id", chat_id)
            .eq("project_id", project_id)
            .eq("user_id", current_user_clerk_id)
            .limit(1)
            .execute()
        )

        if not chat_check.data:
            raise HTTPException(404, "Chat not found or you don't have permission")

        # ─────────────────────────────────────────
        # Step 1: Insert user message
        # ─────────────────────────────────────────
        user_msg = {
            "content": message.content,
            "chat_id": chat_id,
            "user_id": current_user_clerk_id,
            "role": MessageRole.USER.value,
        }
        user_res = supabase.table("messages").insert(user_msg).execute()

        if not user_res.data:
            raise HTTPException(422, "Failed to create user message")

        current_message_id = user_res.data[0]["id"]

        # ─────────────────────────────────────────
        # Step 2: Get chat history (excluding current message)
        # ─────────────────────────────────────────
        chat_history = get_chat_history(
            chat_id,
            current_user_clerk_id,
            exclude_message_id=current_message_id,
        )

        # ─────────────────────────────────────────
        # Step 3: Create RAG agent and invoke
        # ─────────────────────────────────────────
        agent = create_rag_agent(
            project_id=project_id,
            chat_history=chat_history,
        )
        result = agent.invoke({
            "messages": [{"role": "user", "content": message.content}]
        })

        # Last message in the graph is always the final AI
        final_response = result["messages"][-1].content[0]["text"]
        # ─────────────────────────────────────────
        # Step 4: Insert AI response
        # ─────────────────────────────────────────
        ai_msg = {
            "content": final_response,
            "chat_id": chat_id,
            "user_id": current_user_clerk_id,
            "role": MessageRole.ASSISTANT.value,
        }

        ai_res = supabase.table("messages").insert(ai_msg).execute()

        if not ai_res.data:
            raise HTTPException(422, "Failed to save AI response")

        return {
            "message": "Message created successfully",
            "data": {
                "userMessage": user_res.data[0],
                "aiMessage": ai_res.data[0],
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))