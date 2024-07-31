from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, validator
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
import httpx

app = FastAPI()

# Set up CORS
origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = AsyncIOMotorClient("mongodb://localhost:27017/?replicaSet=rs0")
db = client.blog


class Comment(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    post_id: str
    content: str

    @validator("id", pre=True, always=True)
    def stringify_id(cls, v):
        return str(v) if isinstance(v, ObjectId) else v


@app.post("/comments", response_model=Comment)
async def create_comment(comment: Comment):
    if not ObjectId.is_valid(comment.post_id):
        raise HTTPException(status_code=400, detail="Invalid post ID")
    comment_dict = comment.dict(by_alias=True, exclude_unset=True)
    result = await db.comments.insert_one(comment_dict)
    comment_dict["_id"] = str(result.inserted_id)

    return Comment(**comment_dict)
