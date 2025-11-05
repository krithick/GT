from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Type
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import FastAPI, HTTPException, Depends, Query
import importlib
import inspect
from fastapi import FastAPI, HTTPException, Depends, Form, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel,Field
from typing import Dict, List, Optional
from datetime import datetime
import motor.motor_asyncio
import uuid
from fastapi.middleware.cors import CORSMiddleware
import json
import random
import uvicorn
import re
import os
from dotenv import load_dotenv
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
import time

import base64
from mongo import MongoDB
from factory_azure import DynamicBotFactory
from models import (
    Message, ChatSession, ChatResponse, ChatReport, BotConfig, BotConfigAnalyser,
    QuestionScenarioDoc, ParaphrasedQuestionCache, QuestionSession)
from speech import router as speech_router
# from question_bot import QuestionBot
load_dotenv('.env')
# MongoDB configuration
MONGO_URL = os.getenv("MONGO_URL")
DATABASE_NAME = os.getenv("DATABASE_NAME")
print(MONGO_URL,DATABASE_NAME)



        

 

# FastAPI Application Setup
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = MongoDB(MONGO_URL,DATABASE_NAME)
app.include_router(speech_router)
@app.get("/gt/api/check")
async def say_hi():
    return {"message": "hi"}	
# Create bot factory
bot_factory = DynamicBotFactory(
    mongodb_uri=os.getenv("MONGO_URL"), 
    database_name=os.getenv("DATABASE_NAME")
)
bot_factory_analyser = DynamicBotFactory(
    mongodb_uri=os.getenv("MONGO_URL"), 
    database_name=os.getenv("DATABASE_NAME")
)

@app.on_event("startup")
async def startup_event():
    """
    Initialize bots when application starts
    """
    await bot_factory.initialize_bots()
    await bot_factory_analyser.initialize_bots_analyser()
# Dependency to get database
async def get_db():
    return db
def replace_name(original_text, your_name,replace):
    if replace in original_text:
        return original_text.replace(replace, your_name)
    return original_text

from fastapi.responses import StreamingResponse
from fastapi import Query

@app.get("/gt/api/chat/stream")
async def chat_stream(
    id: str = Query(...),
    name: Optional[str] = Query(None),
    voice_id: Optional[str] = Query(default="ar-SA-HamedNeural"),
    db: MongoDB = Depends(get_db)
):
    """
    Stream the response for a chat message.
    """
    # Get session
    session = await db.get_session(id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get bot
    bot = await bot_factory.get_bot(session.scenario_name)
    
    # Get the most recent user message
    if not session.conversation_history:
        raise HTTPException(status_code=400, detail="No conversation history found")
    
    previous_message = session.conversation_history[-1]
    message = previous_message.content
    
    # Process the message and get the response stream
    try:
        response = await bot.process_message(
            message,
            session.conversation_history,
            name
        )
        
        async def stream_chat():
            import base64
            import re
            
            full_text = ""
            audio_data = None
            
            async for chunk_data in response:
                updated_message = chunk_data["chunk"]
                full_text = updated_message
                
                # Check if complete
                if chunk_data["finish"] == "stop" and chunk_data["usage"] is not None:
                    # Add bot message to conversation history
                    bot_message = Message(
                        role=bot.bot_role,
                        content=updated_message,
                        timestamp=datetime.now()
                    )
                    session.conversation_history.append(bot_message)
                    await db.update_session(session)
                    
                    # Generate TTS for complete response
                    try:
                        from speech import generate_audio_for_chat
                        clean_text = re.sub(r'\[CORRECT\].*?\[CORRECT\]', '', full_text, flags=re.DOTALL)
                        clean_text = clean_text.replace("[FINISH]", "").replace("*", "").replace("#", "").strip()
                        audio_data = await generate_audio_for_chat(clean_text, voice_id)
                    except Exception as e:
                        print(f"TTS generation failed: {e}")
                        audio_data = None
                
                # Parse for correct formatting tags
                result = re.split(r"\[CORRECT\]", updated_message)
                correct_answer = ''
                if len(result) >= 3:
                    correct_answer = result[1]
                    answer = result[0]
                else:
                    answer = re.sub(r"\[CORRECT\]", "", updated_message)
                
                # Check if this is the end of the conversation
                is_finished = "[FINISH]" in updated_message
                if is_finished:
                    answer = updated_message.replace("[FINISH]", " ")
                    complete = True
                else:
                    complete = False
                
                # Check if correction is needed
                correct = "[CORRECT]" not in updated_message
                
                response_data = {
                    "response": answer,
                    "emotion": "neutral",
                    "complete": complete,
                    "correct": correct,
                    "correct_answer": correct_answer,
                    "finish": "stop" if chunk_data["finish"] == "stop" else None
                }
                
                # Add audio data if available and streaming is finished
                if chunk_data["finish"] == "stop" and audio_data and len(audio_data) > 0:
                    response_data["audio"] = base64.b64encode(audio_data).decode('utf-8')
                    response_data["audio_format"] = "wav"
                
                yield f"data: {json.dumps(response_data)}\n\n"
                
        return StreamingResponse(stream_chat(), media_type="text/event-stream")
        
    except Exception as e:
        print(f"Error in chat stream: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/gt/api/chat")
async def chat(
    message: str = Form(...),
    id: Optional[str] = Form(None),
    scenario_name: Optional[str] = Form(None),
    name: Optional[str] = Form(None),
    db: MongoDB = Depends(get_db)
):
    """
    Send a message to the chat system. Creates new session if id is None.
    """
    # Create new session if no id provided
    if not id:
        if not scenario_name:
            raise HTTPException(status_code=400, detail="scenario_name required for new sessions")
        
        session = ChatSession(
            extra=str(uuid.uuid4()),
            _id=str(uuid.uuid4()),
            session_id=str(uuid.uuid4()),
            scenario_name=scenario_name,
            conversation_history=[]
        )
        await db.create_session(session)
        id = session.session_id
    else:
        # Get existing session
        session = await db.get_session(id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
    
    # Get bot
    bot = await bot_factory.get_bot(session.scenario_name)
    
    # Add user message to conversation history
    user_message = Message(
        role=bot.bot_role_alt,
        content=message,
        timestamp=datetime.now()
    )
    
    # Initialize conversation_history if it doesn't exist
    if not hasattr(session, "conversation_history") or session.conversation_history is None:
        session.conversation_history = []
    
    session.conversation_history.append(user_message)
    
    # Update session in database
    await db.update_session(session)
    
    # Return acknowledgment with session id
    return {
        "message": "Message received, processing...",
        "id": id,
        "scenario_name": session.scenario_name
    }

@app.post("/gt/api/chat/legacy")
async def chat_legacy(message: str = Form(...),
    session_id: Optional[str] = Form(default=None),
    scenario_name: Optional[str] = Form(default=None),
    name: Optional[str] = Form(default=None),
    spouse_name: Optional[str] = Form(default=None),
    db: MongoDB = Depends(get_db)
):
    """
    Legacy chat endpoint (non-streaming)
    """
    if not session_id:
        if not scenario_name:
            raise HTTPException(status_code=400,detail="scenario_name is required for new sessions")
        session = ChatSession(
            extra=str(uuid.uuid4()),
            _id=str(uuid.uuid4()),
            session_id=str(uuid.uuid4()),
            scenario_name=scenario_name,
            conversation_history=[]
        )
        await db.create_session(session)
    else:
        session= await db.get_session(session_id)
        if not session:
            raise HTTPException(status_code=400,detail="Session not found")
    
    bot = await bot_factory.get_bot(session.scenario_name)
    new_message = Message(role=f"{bot.bot_role_alt}", content=message)
    session.conversation_history.append(new_message)
    
    response = await bot.get_farmer_response(
        message, session.scenario_name, session.conversation_history
    )

    bot_message = Message(role=f"{bot.bot_role}", content=response)
    session.conversation_history.append(bot_message)
    await db.update_session(session)

    return ChatResponse(
        session_id=session.session_id,
        response=response,
        emotion="neutral",
        complete=True,
        conversation_history=session.conversation_history
    )

@app.put("/gt/api/bots/{bot_id}")
async def update_bot(bot_id: str, update_data: Dict):
    """
    Update bot configuration
    
    :param bot_id: Bot ID to update
    :param update_data: Configuration update details
    :return: Update confirmation
    """
    await bot_factory.update_bot_config(bot_id, update_data)
    return {"message": "Bot configuration updated successfully"}

@app.get("/gt/api/available_bots")
async def get_available_bots():
    """
    Get list of available active bots
    
    :return: List of active bot IDs
    """
    print(list(bot_factory.bots.keys()),bot_factory.bots)
    return list(bot_factory.bots.keys())

@app.post("/gt/api/createBot")
async def createBot(
    bot_name: str=Form(default=None),
    bot_description: str=Form(default=None),
    bot_role:str=Form(default=None),
    bot_role_alt:str=Form(default=None),
    system_prompt: str=Form(default=None),
    is_active: bool = Form(default=True),
    bot_class: Optional[str] = Form(default=None),
    llm_model: str=Form(default='gpt-4o')):
 
                  
    bot_ = BotConfig(bot_id=str(uuid.uuid4()),
                    bot_name=bot_name,
                    bot_description=bot_description,
                    bot_role=bot_role,
                    bot_role_alt=bot_role_alt,
                    system_prompt=system_prompt,
                    is_active=is_active,
                    bot_class=bot_class,
                  
                    llm_model=llm_model)
    await db.create_bot(bot_)
    # await bot_factory.create_bot(bot_)
    await bot_factory.initialize_bots()
    return bot_
    
@app.post("/gt/api/createBotAnalyser")
async def createBotAnalyser(
    bot_name: str=Form(default=None),
    bot_description: str=Form(default=None),
    bot_schema:str=Form(default=None),
    system_prompt: str=Form(default=None),
    is_active: bool = Form(default=True),
    llm_model: str=Form(default='gpt-4o')):
 
    test=json.loads(bot_schema)
    bot_ = BotConfigAnalyser(bot_id=str(uuid.uuid4()),
                    bot_name=bot_name,
                    bot_description=bot_description,
                    bot_schema=test,
                    system_prompt=system_prompt,
                    is_active=is_active,
                    llm_model=llm_model)
    await db.create_bot_analyser(bot_)
    # await bot_factory.create_bot(bot_)
    await bot_factory_analyser.initialize_bots_analyser()
    return bot_
    
    
@app.get("/gt/api/sessionAnalyser/{session_id}")    
async def get_session_analysis(
    session_id: str,
    db: MongoDB = Depends(get_db)
):
    session2 = await db.get_session_raw(session_id)
    analysis= await db.get_session_analysis(session_id)
    if not session2:
        raise HTTPException(status_code=404, detail="Session not found")
    if not analysis:
    # Access the conversation_history
        conversation_history = session2['conversation_history']


        conversation = {"conversation_history":conversation_history}
        analyzer= await bot_factory_analyser.get_bot_analyser(session2['scenario_name'])
        print(analyzer)
        results = await analyzer.analyze_conversation(conversation)
        results['session_id']=session2['session_id']
        results['conversation_id']=str(uuid.uuid4())
        results['timestamp']=datetime.now()
        category_scores=results['category_scores']
        # results['overall_score']=category_scores['language_and_communication']+category_scores['product_knowledge']+category_scores['empathy_and_trust']+category_scores['process_clarity']+category_scores['product_suitability']
        report = ChatReport(**results)
        model= await db.create_conversation_analysis(report)
        return report
    return analysis

    
@app.get("/gt/api/refreshBots")
async def refresh_bots():
    await bot_factory.initialize_bots()
    await bot_factory_analyser.initialize_bots_analyser()


# ===== BOT MANAGEMENT (Minimal) =====

@app.get("/gt/api/available-scenarios")
async def get_available_scenarios():
    """Get list of available question scenarios"""
    try:
        bots = list(bot_factory.bots.keys())
        return {
            "available_scenarios": bots,
            "total_count": len(bots)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting scenarios: {str(e)}")

@app.post("/gt/api/refresh-bots")
async def refresh_question_bots():
    """Refresh bot factory - reload all question bots"""
    try:
        await bot_factory.initialize_bots()
        return {
            "message": "Question bots refreshed successfully",
            "loaded_scenarios": list(bot_factory.bots.keys())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error refreshing bots: {str(e)}")

