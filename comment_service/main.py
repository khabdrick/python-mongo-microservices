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

# @app.get("/comments/{post_id}", response_model=List[Comment])
# async def get_comments(post_id: str):
#     if not ObjectId.is_valid(post_id):
#         raise HTTPException(status_code=400, detail="Invalid post ID")
#     comments = await db.comments.find({"post_id": post_id}).to_list(100)
#     for comment in comments:
#         comment["_id"] = str(comment["_id"])
#     return [Comment(**comment) for comment in comments]

clients = {}

@app.websocket("/ws/comments/{post_id}")
async def websocket_endpoint(websocket: WebSocket, post_id: str):
    # monitor and stream real-time updates for comments related to a specific post
    await websocket.accept()
    if post_id not in clients:
        clients[post_id] = []
    clients[post_id].append(websocket)
    try:
        async with db.comments.watch([{'$match': {'fullDocument.post_id': post_id}}]) as stream:
            async for change in stream:
                for client in clients[post_id]:
                    await client.send_json(change['fullDocument'])
    except WebSocketDisconnect:
        clients[post_id].remove(websocket)
        if not clients[post_id]:
            del clients[post_id]
        print(f"Client for post {post_id} disconnected")
