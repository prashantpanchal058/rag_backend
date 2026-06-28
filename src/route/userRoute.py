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
        response = supabase.table("projects").insert({
            "user_id": user_id,
            "name": data.name,
            "description": data.description
        }).execute()

        print("SUPABASE RESPONSE:", response)

        if hasattr(response, "error") and response.error:
            raise HTTPException(status_code=400, detail=str(response.error))

        return {"data": response.data}

    except Exception as e:
        print("ERROR:", e)
        raise HTTPException(status_code=500, detail=str(e))



@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    current_user_clerk_id: str = Depends(get_current_user_clerk_id)
):
    try:
        response = (
            supabase.table("projects")
            .delete()
            .eq("id", project_id)
            .eq("user_id", current_user_clerk_id)  # ✅ FIXED
            .execute()
        )

        # Handle Supabase error
        if hasattr(response, "error") and response.error:
            raise HTTPException(status_code=400, detail=str(response.error))

        # If nothing deleted → not found OR not owned
        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="Project not found or you don't have permission to delete it"
            )

        return {
            "message": "Project deleted successfully",
            "data": response.data[0]
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting project: {str(e)}"
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