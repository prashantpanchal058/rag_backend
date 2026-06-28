from src.services.supabase_client import supabase
import os
import time
from src.rag.ingestion.utils import partition_document, analyze_elements, separate_content_types, get_page_number, create_ai_summary
from src.models.index import ProcessingStatus
from unstructured.chunking.title import chunk_by_title
from src.services.scraping import scrape_url
import requests
from src.services.llm import gemini
import sys
sys.stdout.reconfigure(encoding='utf-8')


def process_document(document_id: str):
    """
    * Step 1 : Download from S3 (file) or Crawl the URL (url) and Extract text, tables, and images from the PDF (using Unstructured Library) from the AWS S3 document.
    * Step 2 : Split the extracted content into chunks.
    * Step 3 : Generate AI summaries for each chunk.
    * Step 4 : Create vector embeddings of chunk and store in PostgreSQL.
    * Update the project document record with the processing_status and processing_details as needed.
    *   - `processing_details` : What type of elements or metadata did we retrieve from the document to show in the UI.
    """
    try:
        update_status_in_database(document_id, ProcessingStatus.PROCESSING)

        document_result = supabase.table("project_documents").select("*").eq("id", int(document_id)).execute()
        if not document_result.data:
            raise Exception(f"Failed to get project document record with id: {document_id}")
        document = document_result.data[0]

        # Step 1 : Download from S3 (file) or Crawl the URL (url) and Extract content.
        update_status_in_database(document_id, ProcessingStatus.PARTITIONING)
        elements_summary, elements = download_content_and_partition(document_id, document)

        update_status_in_database(document_id, ProcessingStatus.CHUNKING)

        # Step 2 : Split the extracted content into chunks.
        chunks, chunking_metrics = chunk_elements_by_title(elements)
        update_status_in_database(document_id, ProcessingStatus.SUMMARISING)

        # Step 3 : Generate AI summaries for chunk which are Having images and tables.
        processed_chunks = summarise_chunks(chunks, document_id)
        update_status_in_database(document_id, ProcessingStatus.VECTORIZATION)

        # Step 4 : Create vector embeddings (1536 dimensions per chunk).
        chunk_ids = vectorize_chunks_summary_and_store_in_database(processed_chunks, document_id)

        update_status_in_database(document_id, ProcessingStatus.COMPLETED)

        return {"success": True, "document_id": document_id, "chunks_created": len(processed_chunks)}
    except Exception as e:
        raise Exception(f"Failed to process document {document_id}: {str(e)}")


def update_status_in_database(
    document_id: str, status: ProcessingStatus, details: dict = None
):
    """
    Update the project document record with the new status and details.
    """

    try:
        # Get the project document record
        document_result = (
            supabase.table("project_documents")
            .select("processing_details")
            .eq("id", int(document_id))
            .execute()
        )
        if not document_result.data:
            raise Exception(
                f"Failed to get project document record with id: {document_id}"
            )

        # Add processing details to the project document record if there are any
        current_details = {}
        if document_result.data[0]["processing_details"]:
            current_details = document_result.data[0]["processing_details"]

        # Add new details if provided
        if details:
            current_details.update(
                details
            )

        # Update the project document record with the new details
        document_update_result = (
            supabase.table("project_documents")
            .update(
                {
                    "processing_status": status.value,
                    "processing_details": current_details,
                }
            )
            .eq("id", int(document_id))
            .execute()
        )

        if not document_update_result.data:
            raise Exception(
                f"Failed to update project document record with id: {document_id}"
            )


    except Exception as e:
        raise Exception(f"Failed to update status in database: {str(e)}")


def download_content_and_partition(document_id: str, document: dict):
    """
    Content either a file or a url.
    if :  Document - Download from S3
    else : URL - Crawl the URL
    Partition into elements like text, tables, images, etc. and analyze the elements summary and upload to db.
    """
    try:
        document_source_type = document["source_type"]
        elements = None
        temp_file_path = None

        if document_source_type == "file":
            file_url = document["source_url"]  # ✅ Supabase public URL
            filename = document["filename"]
            file_type = filename.split(".")[-1].lower()

            temp_file_path = f"{document_id}.{file_type}"

            # 🔥 Download from Supabase
            response = requests.get(file_url)
            if response.status_code != 200:
                raise Exception(f"Failed to download file: {response.status_code}")
            
            # Write to file
            with open(temp_file_path, "wb") as file:
                file.write(response.content)
                
            elements = partition_document(temp_file_path, file_type)

        if document_source_type == "url":
            url = document["source_url"]
            response = scrape_url(url)
            temp_file_path = f"{document_id}.html"
            with open(temp_file_path, "w", encoding="utf-8") as f:  # "w" not "wb", string not bytes
                f.write(response)
            elements = partition_document(temp_file_path, "html", source_type="url")

        elements_summary = analyze_elements(elements)
        os.remove(temp_file_path)

        return elements_summary, elements

    except Exception as e:
        raise Exception(f"Failed in Step 1 to download content and partition elements: {str(e)}")


def chunk_elements_by_title(elements):
    try:
        chunks = chunk_by_title(
            elements,  # The parsed PDF elements from previous step
            max_characters=3000,  # Hard limit - never exceed 3000 characters per chunk
            new_after_n_chars=2400,  # Try to start a new chunk after 2400 characters
            combine_text_under_n_chars=500,  # Merge tiny chunks under 500 chars with neighbors
        )

        # Collect chunking metrics
        total_chunks = len(chunks)

        chunking_metrics = {"total_chunks": total_chunks}

        return chunks, chunking_metrics
    except Exception as e:
        raise Exception(f"Failed to chunk elements by title: {str(e)}")


def summarise_chunks(chunks, document_id, source_type="file"):
    """
    Create user-friendly, searchable chunks.

    For each chunk we optionally generate an AI summary (useful for mixed content like
    tables/images) and update the UI to better UX as each chunk will take at least 5 seconds to process.
    """

    try:
        processed_chunks = []
        total_chunks = len(chunks)

        for i, chunk in enumerate(chunks):
            current_chunk = i + 1

            # Progress updates for the UI polling loop; keeps the user informed.
            update_status_in_database(
                document_id,
                ProcessingStatus.SUMMARISING,
            )

            # Normalize the raw chunk into typed content buckets (text/tables/images, etc.).
            # content_data = {
            #     "text": "This is the main text content of the chunk...",
            #     "tables": ["<table><tr><th>Header</th></tr><tr><td>Data</td></tr></table>"],
            #     "images": ["iVBORw0KGgoAAAANSUhEUgAA..."],  # base64 encoded image strings
            #     "types": ["text", "table", "image"]  # or ["text"], ["text", "table"], etc.
            # }
            content_data = separate_content_types(chunk, source_type)

            # * Use AI summarization only when the chunk contains at least one table or image.
            if content_data["tables"] or content_data["images"]:
                enhanced_content = create_ai_summary(
                    content_data["text"], content_data["tables"], content_data["images"]
                )
            else:
                enhanced_content = content_data["text"]

            # Preserve the original content structure for traceability in the UI.
            original_content = {"text": content_data["text"]}
            if content_data["tables"]:
                original_content["tables"] = content_data["tables"]
            if content_data["images"]:
                original_content["images"] = content_data["images"]

            # Assemble the final searchable unit with minimal but useful metadata.
            processed_chunk = {
                "content": enhanced_content,
                "original_content": original_content,
                "type": content_data["types"],
                "page_number": get_page_number(chunk, i),
                "char_count": len(enhanced_content),
            }
            

            # Rough example for processed_chunk:
            # {
            #     "content": "AI-enhanced summary of the chunk... Image looks like this: <image_base64> ... Table looks like this: <table_html> ...",
            #     "original_content": {
            #         "text": "Full paragraph of the chunk...",
            #         "tables": ["<table><tr><th>Region</th><th>Revenue</th></tr><tr><td>APAC</td><td>$1.2M</td></tr></table>"],
            #         "images": ["iVBORw0KGgoAAA...base64..."]
            #     },
            #     "type": ["text", "table", "image"],
            #     "page_number": 3,
            #     "char_count": 142
            # }

            processed_chunks.append(processed_chunk)

        return processed_chunks
    except Exception as e:
        raise Exception(f"Failed to summarise chunks: {str(e)}")


def vectorize_chunks_summary_and_store_in_database(processed_chunks, document_id):
    """Generate vector embeddings of the ai-summary of the chunks and store in the database."""

    try:
        # processed_chunks example (list of dicts):

        # processed chunks = [{
        #     "content": "Ai-enhanced summary of the chunk...", <----- **This is the content that will be vectorized.**
        #     "original_content": {"text": "...", "tables": ["<table...>"], "images": ["<base64>"]},
        #     "type": ["text", "table", "image"],
        #     "page_number": 3,
        #     "char_count": 142
        # }, {....}]
        # Step 1 : Vectorizing Chunks
        ai_summary_list = [chunk["content"] for chunk in processed_chunks]
        # ai_summary_list = ["Ai-enhanced summary of the chunk...", "Ai-enhanced summary of the chunk...", ...]

        # Edge case : More chunks < More API calls. In Case we exceed the API limit. We will generate in batches.
        batch_size = 10
        all_vectorized_embeddings = []

        for start in range(0, len(ai_summary_list), batch_size):

            # Splits into chunks of batch_size - 10
            end = start + batch_size
            batch_texts = ai_summary_list[start:end]
            batch_num = (start // batch_size) + 1
            total_batches = (len(ai_summary_list) + batch_size - 1) // batch_size

            # Simple retry with exponential backoff
            attempt = 0
            while True:
                try:
                    ai_summary_list = normalize_content(batch_texts)

# Remove any empty strings just in case
                    ai_summary_list = [t for t in ai_summary_list if t.strip()]
                    embeddings = gemini["embeddings"].embed_documents(ai_summary_list)
                    all_vectorized_embeddings.extend(embeddings)  # 'extend' - built-in list method that adds multiple elements to the end of the list.
                    break
                except Exception as e:
                    attempt += 1
                    if attempt >= 3:
                        raise e
                    wait_time = 2**attempt
                    time.sleep(wait_time)

        # Step 2 : Storing Chunks with Embeddings
        # chunk_embedding_pairs: list of tuples (processed_chunk, embedding_vector)
        # Example:
        # [
        #     ({"content": "...", "page_number": 1, "type": ["text"]}, [0.123, -0.456, 0.789, ...]),
        #     ({"content": "...", "page_number": 2, "type": ["text", "table"]}, [0.234, -0.567, 0.890, ...]),
        #     ...
        # ]
        chunk_embedding_pairs = list(zip(processed_chunks, all_vectorized_embeddings))
        stored_chunk_ids = []

        for i, (processed_chunk, embedding_vector) in enumerate(chunk_embedding_pairs):
            # Add document_id, chunk_index, and embedding to each processed_chunk
            # chunk_data_with_embedding example:
            # {
            #     * Same as above but added document_id, chunk_index, and embedding.
            #     "content": "AI-enhanced summary of the chunk...","original_content": {"text": "...", "tables": ["<table>...</table>"], "images": ["<base64>"]},"type": ["text", "table", "image"],"page_number": 3,"char_count": 142,
            #     "document_id": "doc_123",
            #     "chunk_index": 0,
            #     "embedding": [0.123, -0.456, 0.789, 0.234, ...]  # 1536 dimensions
            # }
            chunk_data_with_embedding = {**processed_chunk, "document_id": document_id, "chunk_index": i, "embedding": embedding_vector}
            result = supabase.table("document_chunks").insert(chunk_data_with_embedding).execute()
            stored_chunk_ids.append(result.data[0]["id"])

        return stored_chunk_ids

    except Exception as e:
        raise Exception(f"Failed to vectorize chunks and store in database: {str(e)}")


def normalize_content(content):
    texts = []

    if isinstance(content, str):
        if content.strip():
            texts.append(content.strip())

    elif isinstance(content, dict):
        if "text" in content and content["text"].strip():
            texts.append(content["text"].strip())

    elif isinstance(content, list):
        for item in content:
            texts.extend(normalize_content(item))

    return texts