from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .auth import router as auth_router
from .api.routes import router as api_router
from .api.waste_categorization import router as waste_categorization_router
from .database import create_indexes

app = FastAPI(title="EcoSmart")

# Configure CORS
origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",  # For frontend development
    "http://127.0.0.1:3000",  # For frontend development
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Include routers
app.include_router(auth_router)
app.include_router(api_router)
app.include_router(waste_categorization_router, prefix="/waste-categorization", tags=["Waste Categorization"])

@app.on_event("startup")
async def startup_event():
    """Initialize database indexes on startup"""
    await create_indexes()

@app.get("/")
def root():
    return {"message": "Welcome to the EcoSmart!"}
