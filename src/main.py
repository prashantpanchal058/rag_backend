from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.route.projectRoutes import router as project_router
from src.route.projectFilesRoutes import router as projectFilesRoutes
from src.route.chatRoutes import router as chat_router
from src.route.messagesRoutes import router as message_router
from src.route.settingsRoutes import router as settings_router

app = FastAPI()

# ✅ MUST be before routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000",],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(project_router, prefix="/api/projects")
app.include_router(chat_router, prefix="/api/chats")
app.include_router(projectFilesRoutes, prefix="/api/projects")
app.include_router(message_router, prefix="/api/projects/message")
app.include_router(settings_router, prefix="/api/projects/settings")