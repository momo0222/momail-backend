from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import emails, config, bulk, agent, dashboard, drafts, files,ai, action
from app.services.agent_service import agent as agent_client
from app.models.email import Email
from app.models.action import Action
from app.database import SessionLocal
import uuid

from contextlib import asynccontextmanager
import asyncio


def reset_demo_db():
        if not settings.demo_mode:
            return
        db = SessionLocal()
        try: 
            db.query(Action).delete()
            db.query(Email).delete()
            demo_emails = [
            Email(
                id=str(uuid.uuid4()),
                thread_id=str(uuid.uuid4()),
                from_address="alex@example.com",
                from_name="Alex",
                from_raw="Alex <alex@example.com>",
                to_address="demo@momail.com",
                subject="Quick question",
                snippet="Hey, are you free to chat later today?",
                body="Hey, are you free to chat later today?",
                classification="personal",
                processed=False,
            ),
            Email(
                id=str(uuid.uuid4()),
                thread_id=str(uuid.uuid4()),
                from_address="newsletter@promo.com",
                from_name="Promo",
                from_raw="Promo <newsletter@promo.com>",
                to_address="demo@momail.com",
                subject="🔥 Limited Time Offer",
                snippet="Don’t miss our exclusive deal!",
                body="Don’t miss our exclusive deal!",
                classification="spam",
                processed=False,
            ),
        ]
            db.add_all(demo_emails)
            db.commit()
        finally:
            db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Starting up {settings.app_name}...")
    print(f"Database: {settings.database_url.split('@')[1]}") 
    reset_demo_db()
    asyncio.create_task(agent_client.run_loop())
    yield
    print(f"Shutting down {settings.app_name}...")

app = FastAPI(
    title=settings.app_name,
    description="AI Email Agent with learning capabilities",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS: Allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000","http://localhost:5173","https://momail-one.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(bulk.router, prefix="/api/bulk", tags=["bulk"])
app.include_router(emails.router, prefix="/api/emails", tags=["emails"])
app.include_router(action.router, prefix="/api/actions", tags=["actions"])
app.include_router(config.router, prefix="/api/config", tags=["config"])
app.include_router(agent.router, prefix="/api/agent", tags=["agent"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(drafts.router, prefix="/api/drafts", tags=["drafts"])
app.include_router(files.router, prefix="/api/files", tags=["files"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])

#Root 
@app.get("/")
def root():
    return {
        "message": "Welcome to the Email Agent API!",
        "version": "0.1.0",
        "status": "running",
        "agent_running": agent_client.running
    }

#Health check
@app.get("/health")
def health():
    return {
        "status": "healthy",
        "agent_running": agent_client.running
    }

# agent control endpoints
@app.post("/api/agent/start")
async def start_agent(background_tasks: BackgroundTasks):
    """Start the background agent service"""
    if agent_client.running:
        return {"message": "Agent is already running."}
    
    background_tasks.add_task(agent_client.run_loop)
    return {"message": "Agent started."}

@app.post("/api/agent/stop")
def stop_agent():
    """Stop the background agent service"""
    if not agent_client.running:
        return {"message": "Agent is not running."}
    
    agent_client.stop()
    return {"message": "Agent stopped."}


