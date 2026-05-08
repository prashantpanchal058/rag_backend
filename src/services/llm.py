from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from dotenv import load_dotenv
load_dotenv()

gemini = {
    "embeddings_llm": ChatGoogleGenerativeAI(
            model="models/gemini-3.1-flash-lite-preview",
            temperature=0.3
    ),
    "embeddings": GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-2-preview",
        output_dimensionality=768  # ! Do not changes this value. It is used in the document_chunks embedding vector.
    ),
    "chat_llm": ChatGoogleGenerativeAI(
            model="models/gemini-3.1-flash-lite-preview",
            temperature=0.3
    ),
    "mini_llm": ChatGoogleGenerativeAI(
            model="models/gemini-3.1-flash-lite-preview",
            temperature=0.3
    ),
}
