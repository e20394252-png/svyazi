import httpx
import json

def test_pollinations():
    url = "https://text.pollinations.ai/openai/chat/completions"
    api_key = "sk_IEBnP2P6kdGlHp6I76uXcwAaSIEqF42b"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Try to get models first
    try:
        models_resp = httpx.get("https://text.pollinations.ai/models", timeout=10)
        print("Models Response:", models_resp.text)
    except Exception as e:
        print("Error getting models:", e)

    # Try a chat completion
    data = {
        "model": "openai",
        "messages": [{"role": "user", "content": "Hello, respond with 'OK'"}]
    }
    
    try:
        resp = httpx.post(url, headers=headers, json=data, timeout=10)
        print("Chat Response Status:", resp.status_code)
        print("Chat Response Body:", resp.text)
    except Exception as e:
        print("Error in chat completion:", e)

if __name__ == "__main__":
    test_pollinations()
