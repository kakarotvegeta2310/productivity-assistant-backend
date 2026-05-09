from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.assistant import router as assistant_router

app = FastAPI(title="Productivity Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
allow_origins=[
    "http://localhost:3000",
    "https://your-app.vercel.app"
],
app.include_router(assistant_router)

@app.get("/")
def root():
    return {"message": "Backend is running"}

@app.get("/health")
def health():
    return {"status": "ok"}