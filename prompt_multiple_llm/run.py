import json
import os
import requests
import boto3

def call_openai_api(prompt, api_key):
    url = "https://api.openai.com/v1/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = {
        "model": "text-davinci-003",
        "prompt": prompt,
        "max_tokens": 100,
    }
    response = requests.post(url, json=data, headers=headers)
    return response.json()

async def call_claude_api(prompt):
    from anthropic import AsyncAnthropic
    anthropic = AsyncAnthropic()
    completion = await anthropic.completions.create(
        model="claude-2.1",
        max_tokens_to_sample=300,
        prompt=prompt,
    )
    return completion.completion


def call_bard_api(prompt, api_key):
    from bardapi import Bard
    os.environ['_BARD_API_KEY'] = api_key
    answer = Bard().get_answer(prompt)['content']
    return answer


def get_llm_response(llm_type, prompt):
    """
    Routes the prompt to the specified LLM and returns the response.
    """
    if llm_type.lower() == "openai":
        return call_openai_api(prompt)
    elif llm_type.lower() == "claude":
        return call_claude_api(prompt)
    elif llm_type.lower() == "bard":
        return call_bard_api(prompt)
    else:
        return {"error": "Unsupported LLM type"}

if __name__ == "__main__":
    llm_type = input("Enter LLM type (OpenAI/Claude/Bard): ")
    prompt = input("Enter prompt: ")
    response = get_llm_response(llm_type, prompt)
    print(response)
