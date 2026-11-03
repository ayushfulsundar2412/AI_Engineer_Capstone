from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="AI Engineer Capstone")

class Note(BaseModel):
    title:str
    content:str

notes: list[Note] = []

@app.get("/health")
def health():
    return {"status":"ok"}

@app.post("/notes")
def create_note(note:Note):
    notes.append(note)
    return {"message":"created", "total": len(notes)}

@app.get("/notes")
def list_notes():
    return notes
