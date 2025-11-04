from fastapi import APIRouter, Depends, HTTPException,UploadFile,Form,File,Response, status, Body, Path, Query
import azure.cognitiveservices.speech as speechsdk
import tempfile
import os
import time
from pydantic import BaseModel
from typing import List
import aiofiles
import asyncio
from dotenv import load_dotenv
import aiohttp
import json
import uuid
import base64

load_dotenv(".env")
import datetime
subscription =  os.getenv("subscription")

router = APIRouter(prefix="/gt/api/speech", tags=["speech"])

class SpeechRecognitionResponse(BaseModel):
    text: str
    status: str
    

speech_config = speechsdk.SpeechConfig(  
        subscription=subscription,  
        region="centralindia",  
    )
speech_config_ = speechsdk.SpeechConfig(  
        subscription=subscription,  
        region="centralindia",  
    )    
@router.post("/stt", response_model=SpeechRecognitionResponse)  
async def speech_recognition_endpoint(file: UploadFile = File(...), language_code: str = Form(...)):  
    """  
    FastAPI endpoint that accepts an audio file via POST request and  
    performs continuous speech recognition using Azure Speech SDK.  
    """ 
    print(file) 
    # Check file type (optional)  
    if not file.content_type.startswith("audio/"):  
        raise HTTPException(status_code=400, detail="File must be an audio file")  
  
    # Unfortunately, the Speech SDK requires a file on disk  
    # We need to temporarily save the file  
    async with aiofiles.tempfile.NamedTemporaryFile(delete=False) as temp_file:  
        temp_file_name = temp_file.name  
  
    try:  
        # Write uploaded file content to temporary file  
        async with aiofiles.open(temp_file_name, "wb") as buffer:  
            content = await file.read()  
            await buffer.write(content)  
  
        # Call the continuous speech recognition function  
        recognized_text = await stt(temp_file_name, language_code)  
  
        return SpeechRecognitionResponse(  
            text=recognized_text,  
            status="success"  
        )  
    finally:  
        # Clean up the temporary file  
        if os.path.exists(temp_file_name):  
            os.unlink(temp_file_name)  
  
async def stt(filename, language):  
    """  
    Continuous speech recognition function that processes an audio file  
    and returns the recognized text.  
    """  
    result_text = []  
  

    speech_config.set_profanity(speechsdk.ProfanityOption.Raw)
    speech_config.speech_recognition_language = language 
  
    audio_config = speechsdk.audio.AudioConfig(filename=filename)  
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)  
  
    done = asyncio.Event()  
  
    def stop_cb(evt: speechsdk.SessionEventArgs):  
        """callback that signals to stop continuous recognition upon receiving an event `evt`"""  
        done.set()  
  
    # Connect callbacks to the events fired by the speech recognizer  
    speech_recognizer.recognized.connect(lambda evt: result_text.append(evt.result.text))  
    # Stop continuous recognition on either session stopped or canceled events  
    speech_recognizer.session_stopped.connect(stop_cb)  
    speech_recognizer.canceled.connect(stop_cb)  
  
    # Start continuous speech recognition  
    speech_recognizer.start_continuous_recognition_async()  
  
    # Wait until recognition is done  
    await done.wait()  
  
    speech_recognizer.stop_continuous_recognition_async()  
  
    text = " ".join(result_text)  
    print("YOU: ", text)  
    return text 



@router.post("/tts")
async def text_to_speech(
    message: str = Form(...),
    voice_id: str = Form(default="ar-SA-HamedNeural"),
):

    speech_config_.speech_synthesis_voice_name = voice_id
    print(voice_id)
    # Use default speaker output but capture the result
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config_, audio_config=None)
    start=datetime.datetime.now()
    print(start)
    result = synthesizer.speak_text_async(message).get()
    print(datetime.datetime.now()-start)
    print(result)
    # if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
    return Response(
            content=result.audio_data,
            media_type="audio/wav",
            headers={"Content-Disposition": "attachment; filename=speech.wav"}
        )
    # else:
    #     return Response(
    #         content=f"Speech synthesis failed: {result.cancellation_details}",
    #         status_code=500
    #     )

@router.post("/tts-stream")
async def test_streaming_tts(
    message: str = Form(...),
    voice_id: str = Form(default="ar-SA-HamedNeural"),
):
    """Test endpoint for streaming TTS"""
    audio_data = await generate_audio_for_chat(message, voice_id)
    if audio_data:
        return Response(
            content=audio_data,
            media_type="audio/wav",
            headers={"Content-Disposition": "attachment; filename=stream.wav"}
        )
    else:
        raise HTTPException(status_code=500, detail="Streaming TTS failed")

@router.get("/demo")
async def tts_demo():
    """Frontend demo for testing streaming TTS"""
    with open("core/tts_demo.html", "r", encoding="utf-8") as f:
        html = f.read()
    return Response(content=html, media_type="text/html")

@router.get("/stream-demo")
async def streaming_tts_demo():
    """Demo for true streaming TTS"""
    with open("core/streaming_tts_demo.html", "r", encoding="utf-8") as f:
        html = f.read()
    return Response(content=html, media_type="text/html")

class StreamingTTSHandler:
    def __init__(self, voice_id: str = "ar-SA-HamedNeural"):
        # Setup like your example
        self.speech_config = speechsdk.SpeechConfig(
            subscription=subscription,
            region="centralindia"
        )
        self.speech_config.speech_synthesis_voice_name = voice_id
        # self.speech_config.set_property(speechsdk.PropertyId.SpeechSynthesis_FrameTimeoutInterval, "100000000")
        # self.speech_config.set_property(speechsdk.PropertyId.SpeechSynthesis_RtfTimeoutThreshold, "10")
        
        self.synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.speech_config)
        self.tts_request = None
        self.tts_task = None
        
    def start_streaming(self):
        # Create TextStream request like your example
        self.tts_request = speechsdk.SpeechSynthesisRequest(
            input_type=speechsdk.SpeechSynthesisRequestInputType.TextStream
        )
        self.tts_task = self.synthesizer.speak_async(self.tts_request)
        
    def add_text(self, text: str):
        if self.tts_request and text:
            self.tts_request.input_stream.write(text)
            
    def finish_streaming(self) -> bytes:
        try:
            if self.tts_request:
                self.tts_request.input_stream.close()
            if self.tts_task:
                result = self.tts_task.get()
                print(f"TTS result reason: {result.reason}")
                if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                    return result.audio_data
                else:
                    print(f"TTS failed: {result.reason}")
                    if hasattr(result, 'cancellation_details'):
                        print(f"TTS error: {result.cancellation_details.reason,result.cancellation_details.error_details}")
        except Exception as e:
            print(f"TTS exception: {e}")
        return b""

async def generate_audio_for_chat(message: str, voice_id: str = "ar-SA-HamedNeural") -> bytes:
    """Generate audio using simple TTS synthesis"""
    try:
        speech_config = speechsdk.SpeechConfig(
            subscription=subscription,
            region="centralindia"
        )
        speech_config.speech_synthesis_voice_name = voice_id
        
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
        
        def sync_tts():
            result = synthesizer.speak_text_async(message).get()
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                return result.audio_data
            return b""
        
        loop = asyncio.get_event_loop()
        audio_data = await loop.run_in_executor(None, sync_tts)
        return audio_data
        
    except Exception as e:
        print(f"TTS error: {e}")
        return b""

def create_wav_header(data_length: int) -> bytes:
    """Create WAV header for 24kHz 16-bit mono PCM"""
    sample_rate = 24000
    bits_per_sample = 16
    channels = 1
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    
    header = b"RIFF"
    header += (36 + data_length).to_bytes(4, "little")
    header += b"WAVE"
    header += b"fmt "
    header += (16).to_bytes(4, "little")
    header += (1).to_bytes(2, "little")  # PCM
    header += channels.to_bytes(2, "little")
    header += sample_rate.to_bytes(4, "little")
    header += byte_rate.to_bytes(4, "little")
    header += block_align.to_bytes(2, "little")
    header += bits_per_sample.to_bytes(2, "little")
    header += b"data"
    header += data_length.to_bytes(4, "little")
    
    return header