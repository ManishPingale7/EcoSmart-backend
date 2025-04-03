from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from auth.router import router as auth_router

app = FastAPI(title="EcoSmart")

origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",  
    "http://127.0.0.1:3000",  
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

app.include_router(auth_router)

@app.get("/")
def root():
    return {"message": "Welcome to the EcoSmart!"}
