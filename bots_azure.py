from abc import ABC, abstractmethod
from typing import Dict, List, Optional, AsyncGenerator
from datetime import datetime
from openai import AsyncAzureOpenAI
import os
from models import Message, BotConfig, BotConfigAnalyser

class BaseLLMBot(ABC):
    """Base class for all LLM-powered bots using Azure OpenAI"""
    
    def __init__(self, config: BotConfig, llm_client: AsyncAzureOpenAI):
        self.config = config
        self.bot_name = config.bot_name
        self.bot_role = config.bot_role
        self.bot_role_alt = config.bot_role_alt
        self.system_prompt = config.system_prompt
        self.llm_model = config.llm_model
        self.llm_client = llm_client
        self.last_used = datetime.now()
        
        # Database connection (to be set by factory)
        self.db = None
    
    async def format_conversation(self, conversation_history: List[Message]) -> List[Dict[str, str]]:
        """Format conversation history for the LLM"""
        contents = []
        
        print(f"🔍 DEBUG: conversation_history length = {len(conversation_history)}")
        
        
        # Add system prompt
        system_content = self.config.system_prompt
        
        contents.append({"role": "system", "content": system_content})
        print(f"🔍 DEBUG: Final system prompt length = {len(system_content)}")
        print(f"🔍 DEBUG: Last 200 chars of system prompt: ")
        
        # Add conversation history
        for message in conversation_history:
            role = "user" if message.role == self.config.bot_role_alt else "assistant"
            content = {
                "role": role,
                "content": message.content
            }
            contents.append(content)
            
        return contents

    def replace_name(self, text: str, name: str) -> str:
        """Replace placeholder with actual name"""
        return text.replace("[NAME]", name) if name else text
    
    async def _process_normal_stream(self, response, name: Optional[str]):
        """Process normal streaming response"""
        async def normal_generator():
            full_response = ""
            
            async for chunk in response:
                if len(chunk.choices) > 0:
                    chunk_text = chunk.choices[0].delta.content
                    finish_reason = chunk.choices[0].finish_reason
                    
                    if chunk_text:
                        full_response += chunk_text
                        
                        # Apply name replacement
                        if name:
                            updated_text = self.replace_name(full_response, name)
                        else:
                            updated_text = full_response
                        
                        yield {"chunk": updated_text, "finish": None, "usage": None}
                    
                    if finish_reason == "stop":
                        if name:
                            final_text = self.replace_name(full_response, name)
                        else:
                            final_text = full_response
                        
                        yield {"chunk": final_text, "finish": "stop", "usage": None}
                
                # Handle usage statistics
                if hasattr(chunk, 'usage') and chunk.usage:
                    yield {
                        "chunk": full_response,
                        "finish": "stop", 
                        "usage": {
                            "completion_tokens": chunk.usage.completion_tokens,
                            "prompt_tokens": chunk.usage.prompt_tokens,
                            "total_tokens": chunk.usage.total_tokens
                        }
                    }
        
        return normal_generator()

    async def process_message(self, message: str, conversation_history: List[Message], name: Optional[str] = None) -> AsyncGenerator:
        """Enhanced process_message with Azure OpenAI client"""
        self.last_used = datetime.now()
        
        # Format conversation for LLM
        contents = await self.format_conversation(conversation_history)
        contents.append({"role": "user", "content": message})
        
        try:
            # Get streaming response from Azure OpenAI
            response = await self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=contents,
                temperature=0.7,
                top_p=0.95,
                max_tokens=1000,
                stream=True,
                stream_options={"include_usage": True}
            )
            
            return await self._process_normal_stream(response, name)
                    
        except Exception as e:
            print(f"Error in process_message: {e}")
            async def error_generator():
                yield {
                    "chunk": f"Error processing message: {str(e)}",
                    "finish": "stop",
                    "usage": None
                }
            return error_generator()

    
    async def get_farmer_response(self, message: str, scenario_name: str, conversation_history: List[Message]) -> str:
        """Get response from the bot"""
        final_response = ""
        async for chunk_data in await self.process_message(message, conversation_history):
            if isinstance(chunk_data, dict):
                final_response = chunk_data.get("chunk", "")
        return final_response


class BaseAnalyserBot(ABC):
    """Base class for analyzer bots using Azure OpenAI"""
    
    def __init__(self, config: BotConfigAnalyser, llm_client: AsyncAzureOpenAI):
        self.config = config
        self.bot_name = config.bot_name
        self.bot_description = config.bot_description
        self.bot_schema = config.bot_schema
        self.system_prompt = config.system_prompt
        self.llm_model = config.llm_model
        self.llm_client = llm_client
        self.last_used = datetime.now()
        
        # Database connection (to be set by factory)
        self.db = None
    
    async def analyze_conversation(self, conversation: Dict) -> Dict:
        """Analyze conversation using Azure OpenAI"""
        try:
            # Format conversation for analysis
            conversation_text = self._format_conversation_for_analysis(conversation)
            
            # Create analysis prompt
            analysis_prompt = f"""
            {self.system_prompt}
            
            Please analyze the following conversation and provide structured feedback based on the schema:
            {conversation_text}
            
            Respond with a JSON object matching the required schema.
            """
            
            response = await self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "You are an expert conversation analyzer."},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            # Parse response and return structured analysis
            analysis_text = response.choices[0].message.content
            # Parse JSON response based on bot_schema
            import json
            try:
                analysis_result = json.loads(analysis_text)
                return analysis_result
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                return {
                    "analysis": analysis_text,
                    "category_scores": {},
                    "overall_score": 0
                }
                
        except Exception as e:
            print(f"Error in analyze_conversation: {e}")
            return {
                "error": str(e),
                "category_scores": {},
                "overall_score": 0
            }
    
    def _format_conversation_for_analysis(self, conversation: Dict) -> str:
        """Format conversation history for analysis"""
        formatted = []
        for message in conversation.get("conversation_history", []):
            role = message.get("role", "unknown")
            content = message.get("content", "")
            formatted.append(f"{role}: {content}")
        return "\n".join(formatted)
    
    @abstractmethod
    async def load_scenarios(self):
        """Load analyzer-specific scenarios"""
        pass