from fastapi import APIRouter, Depends, HTTPException
from src.services.supabase_client import supabase
from src.services.clerkAuth import get_current_user_clerk_id
from src.models.index import ProjectSettings

router = APIRouter()

@router.get("/{project_id}/settings")
async def get_project_settings(
    project_id: str,
    current_user_clerk_id: str = Depends(get_current_user_clerk_id)
):
    try:
        # ✅ Step 1: Verify project ownership
        project_check = (
            supabase.table("projects")
            .select("id")
            .eq("id", project_id)
            .eq("user_id", current_user_clerk_id)  # ✅ IMPORTANT
            .limit(1)
            .execute()
        )

        if hasattr(project_check, "error") and project_check.error:
            raise HTTPException(status_code=400, detail=str(project_check.error))

        if not project_check.data:
            raise HTTPException(
                status_code=404,
                detail="Project not found or you don't have permission"
            )

        # ✅ Step 2: Get settings
        response = (
            supabase.table("project_settings")
            .select("*")
            .eq("project_id", project_id)
            .limit(1)
            .execute()
        )

        if hasattr(response, "error") and response.error:
            raise HTTPException(status_code=400, detail=str(response.error))

        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="Project settings not found"
            )

        return {
            "message": "Project settings retrieved successfully",
            "data": response.data[0],
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving project settings: {str(e)}"
        )

@router.put("/{project_id}/settings")
async def update_project_settings(
    project_id: str,
    settings: ProjectSettings,
    current_user_clerk_id: str = Depends(get_current_user_clerk_id),
):
    try:
        # ✅ Step 1: Verify project ownership
        project_check = (
            supabase.table("projects")
            .select("id")
            .eq("id", project_id)
            .eq("user_id", current_user_clerk_id)  # ✅ FIXED
            .limit(1)
            .execute()
        )

        if hasattr(project_check, "error") and project_check.error:
            raise HTTPException(status_code=400, detail=str(project_check.error))

        if not project_check.data:
            raise HTTPException(
                status_code=404,
                detail="Project not found or you don't have permission"
            )

        # ✅ Step 2: Update settings
        update_data = settings.model_dump()

        response = (
            supabase.table("project_settings")
            .update(update_data)
            .eq("project_id", project_id)
            .execute()
        )

        # ✅ Handle Supabase error
        if hasattr(response, "error") and response.error:
            raise HTTPException(status_code=400, detail=str(response.error))

        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="Project settings not found"
            )

        return {
            "message": "Project settings updated successfully",
            "data": response.data[0]
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating project settings: {str(e)}"
        )