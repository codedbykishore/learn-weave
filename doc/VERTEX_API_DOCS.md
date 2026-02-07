# Vertex AI Gemini 3.0 Documentation Reference

This document provides a comprehensive technical reference for the **Google Vertex AI Gemini 3.0 Flash and Pro** models. It is designed to assist AI coding agents in writing correct API code using the latest syntax and features.

---

## 1. Model Overview

Gemini 3 is Google's most advanced model family, featuring state-of-the-art reasoning, multimodal capabilities, and a massive context window.

### 1.1 Model Variants

| Feature | Gemini 3 Pro | Gemini 3 Flash |
| :--- | :--- | :--- |
| **Model ID** | `gemini-3-pro-preview` | `gemini-3-flash-preview` |
| **Context Window** | 1,048,576 input / 65,536 output | 1,048,576 input / 65,536 output |
| **Primary Use Case** | Complex reasoning, multi-step planning | High-speed, low-latency, agentic workflows |
| **Knowledge Cutoff** | January 2025 | January 2025 |
| **Release Date** | December 17, 2025 | December 17, 2025 |

### 1.2 Technical Specifications

*   **Images**: Up to 900 images per prompt.
*   **Documents**: Up to 900 files/pages per prompt (PDF, Text).
*   **Video**: Up to 45 minutes (with audio) or 1 hour (without audio).
*   **Audio**: Up to 8.4 hours or 1 million tokens.
*   **Default Parameters**:
    *   `temperature`: 1.0 (Range: 0.0 - 2.0)
    *   `topP`: 0.95 (Range: 0.0 - 1.0)
    *   `topK`: 64 (Fixed)
    *   `candidateCount`: 1 (Range: 1 - 8)

---

## 2. New API Parameters

Gemini 3 introduces granular control over reasoning and multimodal processing.

### 2.1 Thinking Level (`thinking_level`)
Controls the internal reasoning budget. Replaces the legacy `thinking_budget`.

*   `MINIMAL`: (Flash only) Near-zero thinking, optimized for throughput.
*   `LOW`: Reduced reasoning for simpler tasks.
*   `MEDIUM`: (Flash only) Balanced speed and reasoning.
*   `HIGH`: Deep reasoning for complex planning and code generation (Default).

### 2.2 Media Resolution (`media_resolution`)
Controls vision processing fidelity.

*   `LOW`, `MEDIUM`, `HIGH`: Available for all multimodal inputs.
*   `ULTRA_HIGH`: Available for **IMAGE** modality only.

---

## 3. Python SDK Syntax (`google-genai`)

The latest documentation recommends the `google-genai` library (v1.51.0+) for Gemini 3 features.

### 3.1 Installation & Setup
```bash
pip install --upgrade google-genai
```

**Environment Variables**:
```bash
export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_CLOUD_LOCATION="global"
export GOOGLE_GENAI_USE_VERTEXAI=True
```

### 3.2 Basic Initialization
```python
from google import genai
from google.genai import types

client = genai.Client()
```

### 3.3 Content Generation with Thinking
```python
response = client.models.generate_content(
    model="gemini-3-pro-preview",
    contents="Implement a thread-safe Singleton in C++.",
    config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            thinking_level=types.ThinkingLevel.HIGH
        )
    )
)
print(response.text)
```

---

## 4. Advanced Features

### 4.1 Multimodal Function Responses
Function responses can now include images and PDFs.

```python
response = client.models.generate_content(
    model="gemini-3-pro-preview",
    contents=[
        types.Content(role="user", parts=[types.Part.from_text("Show me the chart for order 123")]),
        types.Content(role="model", parts=[types.Part.from_function_call(name="get_order_chart", args={"id": "123"})]),
        types.Content(role="user", parts=[
            types.Part.from_function_response(
                name="get_order_chart",
                response={
                    "chart": types.Part.from_uri(file_uri="gs://bucket/chart.png", mime_type="image/png")
                }
            )
        ])
    ]
)
```

### 4.2 Streaming Function Call Arguments
Enables streaming of partial function arguments for better UX.

```python
config = types.GenerateContentConfig(
    tool_config=types.ToolConfig(
        function_calling_config=types.FunctionCallingConfig(
            stream_function_call_arguments=True
        )
    )
)
```

### 4.3 Context Caching (Explicit)
Ideal for large codebases or long documents.

```python
# 1. Create Cache
cache = client.caches.create(
    model="gemini-3-pro-preview",
    config=types.CreateCachedContentConfig(
        contents=[types.Part.from_text("Vast amount of code or documentation...")],
        ttl="3600s"
    )
)

# 2. Use Cache
response = client.models.generate_content(
    model="gemini-3-pro-preview",
    contents="Analyze the security of the cached code.",
    config=types.GenerateContentConfig(
        cached_content=cache.name
    )
)

# 3. Cleanup
client.caches.delete(name=cache.name)
```

### 4.4 Thought Signatures
Gemini 3 returns internal reasoning steps. Access them via:
```python
thought_process = response.candidates[0].content.parts[0].thought
print(f"Model Reasoning: {thought_process}")
```

---

## 5. Best Practices for Coding Agents

1.  **Use HIGH Thinking for Code**: Always set `thinking_level` to `HIGH` when generating or debugging complex code.
2.  **Leverage Context Caching**: For repository-wide analysis, cache the entire codebase once to save costs and reduce latency on subsequent queries.
3.  **Handle Thought Signatures**: Coding agents should parse the `thought` part of the response to understand the model's logic before presenting the final code.
4.  **System Instructions**: Use `system_instruction` in `GenerateContentConfig` to define the agent's persona and coding standards.

---
*Last Updated: January 23, 2026*
*Source: Official Google Cloud Vertex AI Documentation*
