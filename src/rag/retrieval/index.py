from src.services.llm import gemini
from fastapi import HTTPException
from src.services.supabase_client import supabase
from src.rag.retrieval.utils import (
    get_project_settings,
    get_project_document_ids,
    build_context_from_retrieved_chunks,
    generate_query_variations,
    rrf_rank_and_fuse
)
from typing import Any, List, Dict
from langchain.tools import tool



def retrieve_context(project_id, user_query):
    try:
        """
        RAG Retrieval Pipeline Steps:
        * Step 1: Get user's project settings from the database.
        * Step 2: Retrieve the document IDs for the current project.
        * Step 3: Perform a vector search using the RPC function to find the most relevant chunks.
        * Step 4: Perform a hybrid search (combines vector + keyword search) using RPC function.
        * Step 5: Perform multi-query vector search (generate multiple query variations and search)
        * Step 6: Perform multi-query hybrid search (multiple queries with hybrid strategy)
        * Step 7: Build the context from the retrieved chunks and format them into a structured context with citations.
        """
        # Step 1: Get user's project settings from the database.
        project_settings = get_project_settings(project_id)
        strategy = project_settings["rag_strategy"]

        # Step 2: Retrieve the document IDs for the current project.
        document_ids = get_project_document_ids(project_id)
        chunks = []
        if strategy == "basic":
            # Basic RAG Strategy: Vector search only
            chunks = vector_search(user_query, document_ids, project_settings)
        elif strategy == "hybrid":
            # Hybrid RAG Strategy: Combines vector + keyword search with RRF ranking
            chunks = hybrid_search(user_query, document_ids, project_settings)
        elif strategy == "multi-query-vector":
            chunks = multi_query_vector_search(user_query, document_ids, project_settings)
        elif strategy == "multi-query-hybrid":
            chunks = multi_query_hybrid_search(user_query, document_ids, project_settings)


        # Step 8: Selecting top k chunks
        chunks = chunks[: int(project_settings["final_context_size"])]
        texts, images, tables, citations = build_context_from_retrieved_chunks(chunks)
        return texts, images, tables, citations
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed in RAG's Retrieval: {str(e)}")


def vector_search( user_query, document_ids, project_settings):
    user_query_embedding = gemini["embeddings"].embed_documents([user_query])[0]
    document_ids = [int(doc_id) for doc_id in document_ids]
    vector_search_result_chunks = supabase.rpc(
        "vector_search_document_chunks",
        {
            "query_embedding": user_query_embedding,
            "filter_document_ids": document_ids,
            "match_threshold": project_settings["similarity_threshold"],
            "chunks_per_search": project_settings["chunks_per_search"],
        },
    ).execute()
    return vector_search_result_chunks.data if vector_search_result_chunks.data else []


def keyword_search(query, document_ids, settings):
    keyword_search_result_chunks = supabase.rpc(
        "keyword_search_document_chunks",
        {
            "query_text": query,
            "filter_document_ids": document_ids,
            "chunks_per_search": settings["chunks_per_search"],
        },
    ).execute()

    return (
        keyword_search_result_chunks.data if keyword_search_result_chunks.data else []
    )


def hybrid_search(query: str, document_ids: List[str], settings: dict) -> List[Dict]:
    """Execute hybrid search by combining vector and keyword results"""
    # Get results from both search methods
    vector_results = vector_search(query, document_ids, settings)
    keyword_results = keyword_search(query, document_ids, settings)
    return rrf_rank_and_fuse([vector_results, keyword_results], [settings["vector_weight"], settings["keyword_weight"]])


def multi_query_vector_search(user_query, document_ids, project_settings):
    """Execute multi-query vector search using query variations"""
    queries = generate_query_variations(user_query, project_settings["number_of_queries"])

    all_chunks = []
    for index, query in enumerate(queries):
        chunks = vector_search(query, document_ids, project_settings)
        all_chunks.append(chunks)

    final_chunks = rrf_rank_and_fuse(all_chunks)
    return final_chunks


def multi_query_hybrid_search(user_query, document_ids, project_settings):
    """Execute multi-query hybrid search using query variations"""
    queries = generate_query_variations(user_query, project_settings["number_of_queries"])

    all_chunks = []
    for index, query in enumerate(queries):
        chunks = hybrid_search(query, document_ids, project_settings)
        all_chunks.append(chunks)

    final_chunks = rrf_rank_and_fuse(all_chunks)
    return final_chunks