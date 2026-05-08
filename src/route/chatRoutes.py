from fastapi import APIRouter, Depends, HTTPException
from src.services.supabase_client import supabase
from src.services.clerkAuth import get_current_user_clerk_id
from src.models.index import ChatCreate

router = APIRouter()

@router.get("/{project_id}/chats")
async def get_project_chats(
    project_id: str,
    current_user_clerk_id: str = Depends(get_current_user_clerk_id)
):
    try:
        response = (
            supabase.table("chats")
            .select("*")
            .eq("project_id", project_id)
            .order("created_at", desc=True)
            .execute()
        )

        if hasattr(response, "error") and response.error:
            raise HTTPException(status_code=400, detail=str(response.error))

        return {
            "message": "Chats retrieved successfully",
            "data": response.data or []
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/")
async def create_chat(
    chat: ChatCreate,
    current_user_clerk_id: str = Depends(get_current_user_clerk_id)
):
    try:
        # ✅ Step 1: Verify project belongs to user
        project_check = (
            supabase.table("projects")
            .select("id")
            .eq("id", chat.project_id)
            .eq("user_id", current_user_clerk_id)
            .limit(1)
            .execute()
        )

        if hasattr(project_check, "error") and project_check.error:
            raise HTTPException(status_code=400, detail=str(project_check.error))

        if not project_check.data:
            raise HTTPException(
                status_code=404,
                detail="Project not found or you don't have access"
            )

        # ✅ Step 2: Insert chat
        chat_insert_data = {
            "title": chat.title,
            "project_id": chat.project_id,
            "user_id": current_user_clerk_id,  # ✅ FIXED
        }

        response = (
            supabase.table("chats")
            .insert(chat_insert_data)
            .execute()
        )

        # ✅ Handle Supabase error
        if hasattr(response, "error") and response.error:
            raise HTTPException(status_code=400, detail=str(response.error))

        if not response.data:
            raise HTTPException(
                status_code=422,
                detail="Failed to create chat"
            )

        return {
            "message": "Chat created successfully",
            "data": response.data[0]
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error creating chat: {str(e)}"
        )

@router.get("/{chat_id}")
async def get_chat(
    chat_id: str,
    current_user_clerk_id: str = Depends(get_current_user_clerk_id)
):
    try:
        # ✅ Step 1: Verify ownership + get chat
        chat_response = (
            supabase.table("chats")
            .select("*")
            .eq("id", chat_id)
            .eq("user_id", current_user_clerk_id)  # ✅ FIXED
            .limit(1)
            .execute()
        )

        if hasattr(chat_response, "error") and chat_response.error:
            raise HTTPException(status_code=400, detail=str(chat_response.error))

        if not chat_response.data:
            raise HTTPException(
                status_code=404,
                detail="Chat not found or you don't have permission"
            )

        chat = chat_response.data[0]

        # ✅ Step 2: Fetch messages
        messages_response = (
            supabase.table("messages")
            .select("*")
            .eq("chat_id", chat_id)
            .order("created_at", desc=False)
            .execute()
        )

        if hasattr(messages_response, "error") and messages_response.error:
            raise HTTPException(status_code=400, detail=str(messages_response.error))

        chat["messages"] = messages_response.data or []

        return {
            "message": "Chat retrieved successfully",
            "data": chat
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting chat {chat_id}: {str(e)}"
        )
        

@router.delete("/{chat_id}")
async def delete_chat(
    chat_id: str, current_user_clerk_id: str = Depends(get_current_user_clerk_id)
):
    """
    ! Logic Flow
    * 1. Get current user clerk_id
    * 2. Verify if the chat exists and belongs to the current user
    * 3. Delete chat
    * 4. Return successfully deleted chat data
    """

    try:
        # First get the chat to retrieve project_id
        chat_result = (
            supabase.table("chats")
            .select("project_id")
            .eq("id", chat_id)
            .eq("user_id", current_user_clerk_id)
            .execute()
        )
        
        if not chat_result.data:
            raise HTTPException(
                status_code=404,
                detail="Chat not found or you don't have permission to delete it",
            )

        chat_deletion_result = (
            supabase.table("chats")
            .delete()
            .eq("id", chat_id)
            .eq("user_id", current_user_clerk_id)
            .execute()
        )
        if not chat_deletion_result.data:
            raise HTTPException(
                status_code=404,
                detail="Chat not found or you don't have permission to delete it",
            )

        return {
            "message": "Chat deleted successfully",
            "data": chat_deletion_result.data[0],
        }

    except HTTPException as e:
        raise e

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An internal server error occurred while deleting chat {chat_id}: {str(e)}",
        )