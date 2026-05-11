# wait for pods to be ready by monitoring `kubectl logs -l app=vllm-gemma-4-31b -f`
# kubectl port-forward service/vllm-gemma-4-31b-service 8000:80

from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="EMPTY"
)

response = client.chat.completions.create(
    model="google/gemma-4-31B-it",
    messages=[
        {"role": "user", "content": "Write a poem about the ocean."}
    ],
    max_tokens=512,
    temperature=0.7
)

print(response.choices[0].message.content)