from fastapi import APIRouter, Form, HTTPException, UploadFile, File as FastAPIFile, Depends
from helpers.jwt_token import get_current_user
from models.user import User
from models.document import Document
from typing import Annotated
import httpx
import io
from helpers.vapi_helper import get_headers, generate_token, get_file_headers

vapi_header = get_headers()
kb_router = APIRouter()

token = generate_token()

@kb_router.post("/documents")
async def upload_documents(user: Annotated[User, Depends(get_current_user)],
 file: UploadFile = FastAPIFile(...), name : str = Form(...)):
    try:
        if file.filename.split('.')[-1].lower() not in ["pdf", "doc", "docx", "txt"]:
            raise HTTPException(
                status_code=400,
                detail="Unsupported Format. Only PDF and DOC/DOCX files are allowed."
            )
        # headers = {
        #     "Authorization": f"Bearer {token}"
        # }
        vapi_url = "https://api.vapi.ai/file"
        async with httpx.AsyncClient() as client:
            print("Content type of file is: ", file.content_type)
            vapi_response = await client.post(
                vapi_url,
                headers=get_file_headers(),
                files={"file": (f"{name}.{file.filename.split('.')[-1].lower()}",  io.BytesIO(await file.read()), file.content_type)}
            )
        if vapi_response.status_code not in [200, 201]:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload file to vapi.ai: {vapi_response.text}"
            )

        print(vapi_response.headers)
        

        vapi_file_id = vapi_response.json().get("id")

        file_record = Document(file_name=name, user=user, vapi_file_id=vapi_file_id)
        await file_record.save()
        return {"success": True, "detail": "File uploaded successfully!"}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Document Upload Failed!!\n{str(e)}")


@kb_router.get("/vapi_docs")
async def vapi_docs(user: Annotated[User, Depends(get_current_user)]):
    try:
        return await Document.filter(user=user).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch files\n{str(e)}")


@kb_router.get("/all_vapi_docs")
async def vapi_docs(user: Annotated[User, Depends(get_current_user)]):
    try:
        return [
            {
                **dict(document),
                "user_name": document.user.name if document.user else None
            }
            for document in await Document.all().prefetch_related("user")
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch files\n{str(e)}")
    
    
    
@kb_router.delete("/delete_vapi_doc/{vapi_file_id}")
async def delete_vapi_doc(
    vapi_file_id: str,
    user: Annotated[User, Depends(get_current_user)],

):
    try:
        print("vapi_header:",vapi_header)
        document = await Document.get(vapi_file_id=vapi_file_id , user_id= user.id) 
        vapi_url = f"https://api.vapi.ai/file/{vapi_file_id}"
       
        
        async with httpx.AsyncClient() as client:
            response = await client.delete(vapi_url, headers=get_file_headers())
        if response.status_code in [200, 204]:
            await document.delete()
            return {"success": True, "detail": "Document deleted successfully."}
        else:
            response_data = response.json()
            raise HTTPException(status_code=response.status_code, detail=f"Failed to delete from vapi: {response_data.get('message')}")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")

