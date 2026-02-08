"""Simple Strands Agent deployed to Amazon Bedrock AgentCore Runtime.

This is the minimal "hello world" agent — no tools, just Strands + AgentCore SDK
wiring. Demonstrates the "intentionally boring handler" principle: if this file
grows beyond a thin adapter, you're doing it wrong.
"""

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent

app = BedrockAgentCoreApp()

agent = Agent(
    system_prompt="You are a helpful assistant. Answer questions clearly and concisely.",
)


@app.entrypoint
def invoke(payload):
    """Process user input and return a response."""
    user_message = payload.get("prompt", "Hello")
    result = agent(user_message)
    return {"result": result.message}


if __name__ == "__main__":
    app.run()
