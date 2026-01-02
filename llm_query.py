import anthropic
import os

user_input = input("enter your question: ")  #str
cyy_api = os.environ.get('ANTHROPIC_API_KEY')
message = anthropic.Anthropic(api_key=cyy_api).messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": user_input}
    ]
)

for block in message.content:
    if hasattr(block,"text"):
        print(block.text)
    else:
        print("no text found")