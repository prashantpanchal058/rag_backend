from fastapi import APIRouter, Depends, HTTPException
from src.services.supabase_client import supabase
from src.models.index import ProjectCreate
from src.services.clerkAuth import get_current_user_clerk_id

router = APIRouter()

@router.get("/")
async def get_projects(
    current_user_clerk_id: str = Depends(get_current_user_clerk_id)
):
    try:
        # IMPORTANT: match column name with DB
        response = (
            supabase.table("projects")
            .select("*")
            .eq("user_id", current_user_clerk_id)   # <-- FIXED (was clerk_id)
            .execute()
        )

        # Handle Supabase-level errors
        if hasattr(response, "error") and response.error:
            raise HTTPException(status_code=400, detail=str(response.error))

        return {
            "message": "Projects retrieved successfully",
            "data": response.data or []
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching projects: {str(e)}"
        )

@router.post("/")
async def create_project(
    data: ProjectCreate,
    user_id: str = Depends(get_current_user_clerk_id)
):
    try:
        project_creation_result = supabase.table("projects").insert({
            "user_id": user_id,
            "name": data.name,
            "description": data.description
        }).execute()

        if hasattr(project_creation_result, "error") and project_creation_result.error:
            raise HTTPException(status_code=400, detail=str(project_creation_result.error))
        
        newly_created_project = project_creation_result.data[0]

        # Create default project settings for the new project
        project_settings_data = {
            "project_id": newly_created_project["id"],
            "embedding_model": "text-embedding-3-large",
            "rag_strategy": "basic",
            "agent_type": "agentic",
            "chunks_per_search": 10,
            "final_context_size": 5,
            "similarity_threshold": 0.3,
            "number_of_queries": 5,
            "reranking_enabled": True,
            "reranking_model": "reranker-english-v3.0",
            "vector_weight": 0.7,
            "keyword_weight": 0.3,
        }

        project_settings_creation_result = (
            supabase.table("project_settings").insert(project_settings_data).execute()
        )

        if not project_settings_creation_result.data:
            # Rollback: Delete the project if settings creation fails
            supabase.table("projects").delete().eq(
                "id", newly_created_project["id"]
            ).execute()
            raise HTTPException(
                status_code=422,
                detail="Failed to create project settings - project creation rolled back",
            )

        return {
            "message": "Project created successfully",
            "data": newly_created_project,
        }


        # return {"data": project_creation_result.data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    current_user_clerk_id: str = Depends(get_current_user_clerk_id)
):
    try:

        # Delete project
        project_response = (
            supabase.table("projects")
            .delete()
            .eq("id", project_id)
            .eq("user_id", current_user_clerk_id)
            .execute()
        )

        if hasattr(project_response, "error") and project_response.error:
            raise HTTPException(status_code=400, detail=str(project_response.error))

        if not project_response.data:
            raise HTTPException(
                status_code=404,
                detail="Project not found or you don't have permission"
            )

        return {
            "message": "Project deleted successfully",
            "data": project_response.data[0]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/settings")
async def get_project_settings(
    project_id: str, current_user_clerk_id: str = Depends(get_current_user_clerk_id)
):
    """
    ! Logic Flow
    * 1. Get current user clerk_id
    * 2. Verify if the project exists and belongs to the current user
    * 3. Check if the project settings exists for the project
    * 4. Return project settings data
    """
    # set_project_id(project_id)
    # set_user_id(current_user_clerk_id)
    try:
        
        # logger.info("fetching_project_settings")
        project_settings_result = (
            supabase.table("project_settings")
            .select("*")
            .eq("project_id", project_id)
            .execute()
        )

        if not project_settings_result.data:
            # logger.warning("project_settings_not_found")
            raise HTTPException(
                status_code=404,
                detail="Project settings not found or you don't have permission to access it",
            )

        settings_data = project_settings_result.data[0]
        # logger.info("project_settings_retrieved",
        #            rag_strategy=settings_data.get("rag_strategy"),
        #            agent_type=settings_data.get("agent_type"),
        #            embedding_model=settings_data.get("embedding_model"),
        #            final_context_size=settings_data.get("final_context_size"),
        #            reranking_enabled=settings_data.get("reranking_enabled"))
        return {
            "message": "Project settings retrieved successfully",
            "data": project_settings_result.data[0],
        }

    except HTTPException as e:
        raise e

    except Exception as e:
        # logger.error("project_settings_retrieval_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"An internal server error occurred while retrieving project {project_id} settings: {str(e)}",
        )


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    current_user_clerk_id: str = Depends(get_current_user_clerk_id)
):
    try:
        response = (
            supabase.table("projects")
            .select("*")
            .eq("id", project_id)
            .eq("user_id", current_user_clerk_id)  # ✅ FIXED
            .limit(1)  # optional but cleaner
            .execute()
        )

        # Handle Supabase-level errors
        if hasattr(response, "error") and response.error:
            raise HTTPException(status_code=400, detail=str(response.error))

        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="Project not found or you don't have permission to access it",
            )

        return {
            "message": "Project retrieved successfully",
            "data": response.data[0],
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving project: {str(e)}",
        )

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