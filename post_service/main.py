from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, validator
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from typing import List, Dict, Optional
import httpx


app = FastAPI()

client = AsyncIOMotorClient('mongodb://localhost:27017')
db = client.blog
templates = Jinja2Templates(directory="templates")

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, field=None):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, schema):
        schema.update(type="string")
        return schema

class Post(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    title: str
    content: str

    class Config:
        json_encoders = {
            ObjectId: str,
        }

class Comment(BaseModel):
    id: Optional[str] = Field(None, alias="_id")    
    post_id: str
    content: str

@app.post("/posts", response_model=Post)
async def create_post(post: Post):
    post_dict = post.dict(by_alias=True)
    result = await db.posts.insert_one(post_dict)
    post_dict["_id"] = str(result.inserted_id)
    return post_dict

@app.put("/posts/{id}", response_model=Post)
async def update_post(id: str, post: Post):
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID")
    post_dict = post.dict(by_alias=True)
    await db.posts.update_one({"_id": ObjectId(id)}, {"$set": post_dict})
    post_dict["_id"] = id
    return post_dict

@app.delete("/posts/{id}")
async def delete_post(id: str):
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID")
    result = await db.posts.delete_one({"_id": ObjectId(id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"message": "Post deleted"}

@app.get("/posts/{id}", response_model=Dict)
async def get_post(id: str):
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ID")
    post = await db.posts.find_one({"_id": ObjectId(id)})
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    comments = await fetch_comments(str(post["_id"]))
    post_with_comments = {**post, "comments": comments}
    post_with_comments["_id"] = str(post_with_comments["_id"])
    return post_with_comments

@app.get("/posts", response_model=List[Dict])
async def list_posts():
    posts = await db.posts.find().to_list(100)
    posts_with_comments = []
    for post in posts:
        comments = await fetch_comments(str(post["_id"]))
        post["_id"] = str(post["_id"])
        posts_with_comments.append({**post, "comments": comments})
    return posts_with_comments

async def fetch_comments(post_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:8000/posts/{post_id}/comments")
        if response.status_code == 200:
            return response.json()
        return []

@app.post("/posts/{post_id}/comments")
async def add_comment_to_post(post_id: str, comment: Comment):
    if not ObjectId.is_valid(post_id):
        raise HTTPException(status_code=400, detail="Invalid post ID")
    comment_dict = comment.dict()
    await db.posts.update_one({"_id": ObjectId(post_id)}, {"$push": {"comments": comment_dict}})
    return {"message": "Comment added to post"}

@app.get("/posts/{post_id}/comments", response_model=List[Comment])
async def get_post_comments(post_id: str):
    if not ObjectId.is_valid(post_id):
        raise HTTPException(status_code=400, detail="Invalid post ID")
    post = await db.posts.find_one({"_id": ObjectId(post_id)})
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return post.get("comments", [])

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
