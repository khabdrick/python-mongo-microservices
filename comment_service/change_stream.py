import asyncio
import httpx
from motor.motor_asyncio import AsyncIOMotorClient

client = AsyncIOMotorClient('mongodb://localhost:27017/?replicaSet=rs0')
db = client.blog

async def watch_comments():
    async with db.comments.watch() as stream:
        async for change in stream:
            print("Change detected in comments:", change)
            if change['operationType'] == "insert":
                print("me change seen ......")
                new_comment = change['fullDocument']
                await send_comment_to_post_service(new_comment)

async def send_comment_to_post_service(comment):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"http://localhost:8000/posts/{comment['post_id']}/comments",
            json={
                "post_id": comment['post_id'],
                "content": comment['content']
            }
        )
        if response.status_code == 200:
            print("Comment sent to post service successfully")
        else:
            print(f"Failed to send comment to post service: {response.status_code}")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(watch_comments())
