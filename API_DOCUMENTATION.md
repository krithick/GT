# Chat & Speech API Documentation

## Overview
Two-step chat system with streaming responses, TTS (Text-to-Speech), and STT (Speech-to-Text) support.

## Base URL
```
https://meta.novactech.in
```

## Authentication
None required for current implementation.

---

## Chat APIs

### 1. Send Message
**POST** `/gt/api/chat`

Send a message to start or continue a chat session.

#### Request
**Content-Type:** `multipart/form-data`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `message` | string | Yes | User message content |
| `id` | string | No | Session ID (omit for new session) |
| `scenario_name` | string | No* | Bot scenario name (*required for new sessions) |
| `name` | string | No | User name for personalization |

#### Response
```json
{
  "message": "Message received, processing...",
  "id": "session_123",
  "scenario_name": "farmer_scenario"
}
```

#### Examples

**cURL:**
```bash
# New session
curl -X POST https://meta.novactech.in/gt/api/chat \
  -F "message=Hello" \
  -F "scenario_name=farmer_scenario"

# Existing session
curl -X POST https://meta.novactech.in/gt/api/chat \
  -F "message=How are you?" \
  -F "id=session_123"
```

**C#:**
```csharp
using var client = new HttpClient();
var formData = new MultipartFormDataContent();
formData.Add(new StringContent("Hello"), "message");
formData.Add(new StringContent("farmer_scenario"), "scenario_name");

var response = await client.PostAsync("https://meta.novactech.in/gt/api/chat", formData);
var result = await response.Content.ReadAsStringAsync();
```

---

### 2. Stream Response
**GET** `/gt/api/chat/stream`

Stream the bot's response in real-time with optional TTS.

#### Request
**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `id` | string | Yes | - | Session ID from POST response |
| `name` | string | No | - | User name for personalization |
| `voice_id` | string | No | `ar-SA-HamedNeural` | Azure TTS voice ID |

#### Response
**Content-Type:** `text/event-stream`

Server-Sent Events stream with JSON data:

```json
{
  "response": "Hello! How can I help you?",
  "emotion": "neutral",
  "complete": false,
  "correct": true,
  "correct_answer": "",
  "finish": null,
  "audio": "base64_encoded_audio_data",
  "audio_format": "wav"
}
```

#### Response Fields
| Field | Type | Description |
|-------|------|-------------|
| `response` | string | Current bot response text |
| `emotion` | string | Bot emotion state |
| `complete` | boolean | Whether response is complete |
| `correct` | boolean | Whether user input was correct |
| `correct_answer` | string | Correction if needed |
| `finish` | string | "stop" when complete |
| `audio` | string | Base64 encoded audio (when complete) |
| `audio_format` | string | Audio format ("wav") |

#### Examples

**C# with Server-Sent Events:**
```csharp
using var client = new HttpClient();
var stream = await client.GetStreamAsync(
    "https://meta.novactech.in/gt/api/chat/stream?id=session_123&voice_id=ar-SA-HamedNeural");

using var reader = new StreamReader(stream);
while (!reader.EndOfStream)
{
    var line = await reader.ReadLineAsync();
    if (line?.StartsWith("data: ") == true)
    {
        var json = line.Substring(6);
        var data = JsonSerializer.Deserialize<ChatResponse>(json);
        Console.WriteLine(data.response);
        
        if (!string.IsNullOrEmpty(data.audio))
        {
            var audioBytes = Convert.FromBase64String(data.audio);
            // Play audio bytes
        }
    }
}
```

**C# Response Model:**
```csharp
public class ChatResponse
{
    public string response { get; set; }
    public string emotion { get; set; }
    public bool complete { get; set; }
    public bool correct { get; set; }
    public string correct_answer { get; set; }
    public string finish { get; set; }
    public string audio { get; set; }
    public string audio_format { get; set; }
}
```

---

## Speech APIs

### 1. Speech-to-Text (STT)
**POST** `/gt/api/speech/stt`

Convert audio file to text using Azure Speech Services.

#### Request
**Content-Type:** `multipart/form-data`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | file | Yes | Audio file (wav, mp3, m4a, etc.) |
| `language_code` | string | Yes | Language code (e.g., "ar-SA", "en-US") |

#### Response
```json
{
  "text": "Hello, how are you?",
  "status": "success"
}
```

#### Examples

**cURL:**
```bash
curl -X POST https://meta.novactech.in/gt/api/speech/stt \
  -F "file=@recording.wav" \
  -F "language_code=ar-SA"
```

**C#:**
```csharp
using var client = new HttpClient();
var formData = new MultipartFormDataContent();

// Add audio file
var audioBytes = await File.ReadAllBytesAsync("recording.wav");
var audioContent = new ByteArrayContent(audioBytes);
audioContent.Headers.ContentType = new MediaTypeHeaderValue("audio/wav");
formData.Add(audioContent, "file", "recording.wav");
formData.Add(new StringContent("ar-SA"), "language_code");

var response = await client.PostAsync("https://meta.novactech.in/gt/api/speech/stt", formData);
var result = await response.Content.ReadAsStringAsync();
var transcription = JsonSerializer.Deserialize<SpeechRecognitionResponse>(result);
```

### 2. Text-to-Speech (TTS)
**POST** `/gt/api/speech/tts`

Convert text to speech audio file.

#### Request
**Content-Type:** `multipart/form-data`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `message` | string | Yes | - | Text to convert to speech |
| `voice_id` | string | No | `ar-SA-HamedNeural` | Azure TTS voice ID |

#### Response
**Content-Type:** `audio/wav`

Returns WAV audio file as binary data.

#### Examples

**cURL:**
```bash
curl -X POST https://meta.novactech.in/gt/api/speech/tts \
  -F "message=Hello, how are you?" \
  -F "voice_id=ar-SA-HamedNeural" \
  -o response.wav
```

**C#:**
```csharp
using var client = new HttpClient();
var formData = new MultipartFormDataContent();
formData.Add(new StringContent("Hello, how are you?"), "message");
formData.Add(new StringContent("ar-SA-HamedNeural"), "voice_id");

var response = await client.PostAsync("https://meta.novactech.in/gt/api/speech/tts", formData);
var audioBytes = await response.Content.ReadAsByteArrayAsync();
await File.WriteAllBytesAsync("response.wav", audioBytes);
```

### 3. Streaming TTS (Test)
**POST** `/gt/api/speech/tts-stream`

Test endpoint for streaming TTS generation.

#### Request
Same as `/gt/api/speech/tts`

#### Response
Same as `/gt/api/speech/tts` but optimized for streaming scenarios.

### Response Models
```csharp
public class SpeechRecognitionResponse
{
    public string text { get; set; }
    public string status { get; set; }
}
```

---

## Legacy API

### Non-Streaming Chat
**POST** `/gt/api/chat/legacy`

Traditional request-response chat (no streaming).

#### Request
Same as `/gt/api/chat` but with additional parameters:
- `session_id` (optional)
- `spouse_name` (optional)

#### Response
```json
{
  "session_id": "session_123",
  "response": "Complete bot response",
  "emotion": "neutral",
  "complete": true,
  "conversation_history": [...]
}
```

---

## Usage Flow

### 1. New Conversation
```
1. POST /gt/api/chat (message + scenario_name)
2. GET /gt/api/chat/stream (with returned session id)
3. Receive streaming response with audio
```

### 2. Continue Conversation
```
1. POST /gt/api/chat (message + existing id)
2. GET /gt/api/chat/stream (same session id)
3. Receive streaming response with audio
```

---

## Error Responses

### 400 Bad Request
```json
{
  "detail": "scenario_name required for new sessions"
}
```

### 404 Not Found
```json
{
  "detail": "Session not found"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Error processing message: [error details]"
}
```

---

## Special Response Tags

The bot may include special formatting tags:

- `[CORRECT]content[CORRECT]` - Correction information
- `[FINISH]` - End of conversation marker
- `[NAME]` - Replaced with user's name

These tags are automatically processed and removed from the final response.

---

## Audio Support

### TTS (Text-to-Speech)
- **Default Voice:** `ar-SA-HamedNeural` (Arabic)
- **Format:** WAV
- **Encoding:** Base64
- **Delivery:** Only with complete responses
- **Fallback:** Graceful degradation if TTS fails

### STT (Speech-to-Text)
- **Supported Formats:** WAV, MP3, M4A, FLAC
- **Default Language:** `ar-SA` (Arabic)
- **Real-time:** WebSocket streaming
- **Batch:** File upload transcription
- **Confidence Scores:** Included in responses

---

## Rate Limits
No rate limits currently implemented.

## SDK/Client Libraries

### C# Complete Example
```csharp
using System.Text.Json;
using System.Text;

public class ChatClient
{
    private readonly HttpClient _client;
    private string _sessionId;
    
    public ChatClient()
    {
        _client = new HttpClient();
    }
    
    public async Task<string> SendMessageAsync(string message, string scenarioName = null)
    {
        var formData = new MultipartFormDataContent();
        formData.Add(new StringContent(message), "message");
        
        if (string.IsNullOrEmpty(_sessionId))
            formData.Add(new StringContent(scenarioName), "scenario_name");
        else
            formData.Add(new StringContent(_sessionId), "id");
        
        var response = await _client.PostAsync("https://meta.novactech.in/gt/api/chat", formData);
        var result = await response.Content.ReadAsStringAsync();
        var chatResult = JsonSerializer.Deserialize<ChatResult>(result);
        
        _sessionId = chatResult.id;
        return _sessionId;
    }
    
    public async IAsyncEnumerable<ChatResponse> StreamResponseAsync(string voiceId = "ar-SA-HamedNeural")
    {
        var stream = await _client.GetStreamAsync(
            $"https://meta.novactech.in/gt/api/chat/stream?id={_sessionId}&voice_id={voiceId}");
        
        using var reader = new StreamReader(stream);
        while (!reader.EndOfStream)
        {
            var line = await reader.ReadLineAsync();
            if (line?.StartsWith("data: ") == true)
            {
                var json = line.Substring(6);
                var data = JsonSerializer.Deserialize<ChatResponse>(json);
                yield return data;
                
                if (data.finish == "stop") break;
            }
        }
    }
}

public class ChatResult
{
    public string message { get; set; }
    public string id { get; set; }
    public string scenario_name { get; set; }
}
```

### Complete Usage Example
```csharp
// Initialize clients
var chatClient = new ChatClient();
var sttClient = new STTClient();

// 1. Convert speech to text
var audioBytes = await File.ReadAllBytesAsync("user_speech.wav");
var transcription = await TranscribeAudioAsync(audioBytes);

// 2. Send transcribed message to chat
var sessionId = await chatClient.SendMessageAsync(transcription.text, "farmer_scenario");

// 3. Stream bot response with TTS
await foreach (var chunk in chatClient.StreamResponseAsync())
{
    Console.Write(chunk.response);
    
    if (chunk.complete && !string.IsNullOrEmpty(chunk.audio))
    {
        var audioBytes = Convert.FromBase64String(chunk.audio);
        await File.WriteAllBytesAsync("bot_response.wav", audioBytes);
        // Play audio to user
    }
}

// Helper method for STT
public async Task<SpeechRecognitionResponse> TranscribeAudioAsync(byte[] audioData)
{
    using var client = new HttpClient();
    var formData = new MultipartFormDataContent();
    var audioContent = new ByteArrayContent(audioData);
    audioContent.Headers.ContentType = new MediaTypeHeaderValue("audio/wav");
    formData.Add(audioContent, "file", "speech.wav");
    formData.Add(new StringContent("ar-SA"), "language_code");
    
    var response = await client.PostAsync("https://meta.novactech.in/gt/api/speech/stt", formData);
    var json = await response.Content.ReadAsStringAsync();
    return JsonSerializer.Deserialize<SpeechRecognitionResponse>(json);
}

// Helper method for TTS
public async Task<byte[]> GenerateAudioAsync(string text, string voiceId = "ar-SA-HamedNeural")
{
    using var client = new HttpClient();
    var formData = new MultipartFormDataContent();
    formData.Add(new StringContent(text), "message");
    formData.Add(new StringContent(voiceId), "voice_id");
    
    var response = await client.PostAsync("https://meta.novactech.in/gt/api/speech/tts", formData);
    return await response.Content.ReadAsByteArrayAsync();
}
```
