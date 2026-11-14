import ollama

response = ollama.chat(
    model="qwen3.5:4b",
    messages=[
        {"role": "system", "content": "You explain cloud concepts to beginners in two sentences."},
        {"role": "user", "content": "What is a security group?"},
    ],
)
print(response.message.content)