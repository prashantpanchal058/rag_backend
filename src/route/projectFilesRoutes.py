from fastapi import APIRouter, HTTPException, Depends
from src.services.supabase_client import supabase
from src.services.clerkAuth import get_current_user_clerk_id
from src.models.index import ProcessingStatus, UrlRequest
from src.utils.index import validate_url
from src.services.tasks import perform_rag_ingestion_task


router = APIRouter(tags=["projectFilesRoutes"])


@router.get("/{project_id}/files")
async def get_project_files(
    project_id: str, current_user_clerk_id: str = Depends(get_current_user_clerk_id)
):
    try:
        project_files_result = (
            supabase.table("project_documents")
            .select("*")
            .eq("project_id", project_id)
            .eq("clerk_id", current_user_clerk_id)
            .order("created_at", desc=True)
            .execute()
        )

        return {
            "message": "Project files retrieved successfully",
            "data": project_files_result.data or [],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/files")
async def create_project_document(
    project_id: str,
    body: dict,
    current_user_clerk_id: str = Depends(get_current_user_clerk_id),
):

    try:
        filename = body.get("filename")

        if not filename:
            raise HTTPException(status_code=400, detail="filename is required")

        document_creation_result = (
            supabase.table("project_documents")
            .insert(
                {
                    "project_id": project_id,
                    "filename": filename,
                    "file_size": body.get("file_size", 0),
                    "file_type": body.get("file_type", "text/plain"),
                    "source_url":body.get("source_url","text/plain"),
                    "source_type":"file",
                    "processing_status": ProcessingStatus.QUEUED,
                    "clerk_id": current_user_clerk_id,
                }
            )
            .execute()
        )

        if not document_creation_result.data:
            raise HTTPException(status_code=422, detail="Failed to create document")

        document_id = document_creation_result.data[0]["id"]
        task_result = perform_rag_ingestion_task.delay(document_id)

        # supabase.table("project_documents").update(
        #     {"task_id": task_result.id}
        # ).eq("id", document_id).execute()

        return {
            "message": "Document created and processing started",
            "data": document_creation_result.data[0],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
from fastapi import UploadFile, File, Form, HTTPException, Depends
from uuid import uuid4

@router.post("/{project_id}/files/stores")
async def create_project_document(
    project_id: str,
    file: UploadFile = File(...),  # 🔥 actual file
    current_user_clerk_id: str = Depends(get_current_user_clerk_id),
):
    try:
        # ---- Validate ----
        if not file.filename:
            raise HTTPException(status_code=400, detail="filename is required")

        if file.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="Only PDF allowed")
        
        # ---- Generate safe filename ----
        unique_filename = f"{uuid4()}_{file.filename}"
        storage_path = f"{project_id}/{unique_filename}"

        # ---- Read file ----
        file_bytes = await file.read()
        # ---- Upload to Supabase Storage ----
        upload_res = supabase.storage.from_("project-files").upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": file.content_type},
        )
        if hasattr(upload_res, "error") and upload_res.error:
            raise HTTPException(status_code=500, detail="Storage upload failed")

        return {
            "message": "File uploaded and processing started",
            # "data": document_creation_result.data[0],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/urls")
async def process_url(
    project_id: str,
    url: UrlRequest,
    current_user_clerk_id: str = Depends(get_current_user_clerk_id),
):


    try:
        url = url.url
        if not url.startswith("http"):
            url = f"https://{url}"

        if not validate_url(url):
            raise HTTPException(status_code=400, detail="Invalid URL")

        document_creation_result = (
            supabase.table("project_documents")
            .insert(
                {
                    "project_id": project_id,
                    "filename": url,
                    "file_size": 0,
                    "file_type": "text/html",
                    "processing_status": ProcessingStatus.QUEUED,
                    "clerk_id": current_user_clerk_id,
                    "source_type": "url",
                    "source_url": url,
                }
            )
            .execute()
        )

        document_id = document_creation_result.data[0]["id"]
        task_result = perform_rag_ingestion_task.delay(document_id)

        return {
            "message": "URL added and processing started",
            "data": document_creation_result.data[0],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{project_id}/files/{file_id}")
async def delete_project_document(
    project_id: str,
    file_id: str,
    current_user_clerk_id: str = Depends(get_current_user_clerk_id),
):

    try:
        result = (
            supabase.table("project_documents")
            .delete()
            .eq("id", file_id)
            .eq("project_id", project_id)
            .eq("clerk_id", current_user_clerk_id)
            .execute()
        )

        if not result.data:
            raise HTTPException(status_code=404, detail="Document not found")

        return {
            "message": "Document deleted successfully",
            "data": result.data[0],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/{project_id}/files/{file_id}/chunks")
async def get_project_document_chunks(
    project_id: str,
    file_id: str,
    current_user_clerk_id: str = Depends(get_current_user_clerk_id),
):
    """
    ! Logic Flow:
    * 1. Verify document exists and belongs to the current user and Take complete project document record
    * 2. Get project document chunks
    * 3. Return project document chunks data
    """
    try:
        # Verify document exists and belongs to the current user and Take complete project document record
        document_ownership_verification_result = (
            supabase.table("project_documents")
            .select("*")
            .eq("id", file_id)
            .eq("project_id", project_id)
            .eq("clerk_id", current_user_clerk_id)
            .execute()
        )

        if not document_ownership_verification_result.data:
            raise HTTPException(
                status_code=404,
                detail="Document not found or you don't have permission to delete this document",
            )

        document_chunks_result = (
            supabase.table("document_chunks")
            .select("*")
            .eq("document_id", file_id)
            .order("chunk_index")
            .execute()
        )

        return {
            "message": "Project document chunks retrieved successfully",
            "data": document_chunks_result.data or [],
        }

    except HTTPException as e:
        raise e

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An internal server error occurred while getting project document chunks for {file_id} for {project_id}: {str(e)}",
        )