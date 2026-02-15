"""Tool-use Strands Agent deployed to Amazon Bedrock AgentCore Runtime.

This agent demonstrates custom tool integration using the Strands @tool decorator.
The agent can call tools to get weather data, evaluate math expressions, and look
up items in a database. Strands owns the reasoning loop (deciding when and how to
call tools); AgentCore Runtime owns the lifecycle.

The handler remains intentionally thin — all intelligence lives in the agent and
its tools, not here.
"""

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models.bedrock import BedrockModel

from tools import calculate, get_weather, lookup_item

app = BedrockAgentCoreApp()

model = BedrockModel(model_id="eu.anthropic.claude-sonnet-4-5-20250929-v1:0")

agent = Agent(
    model=model,
    system_prompt=(
        "You are a helpful assistant with access to tools. "
        "Use the available tools when they can help answer the user's question. "
        "Always prefer using a tool over guessing. "
        "When reporting tool results, be concise and direct."
    ),
    tools=[get_weather, calculate, lookup_item],
)


@app.entrypoint
def invoke(payload):
    """Process user input and return a response."""
    user_message = payload.get("prompt", "Hello")
    result = agent(user_message)
    return {"result": result.message}


if __name__ == "__main__":
    app.run()
