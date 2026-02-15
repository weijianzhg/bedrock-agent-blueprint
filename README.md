# Bedrock AgentCore Blueprint

A production-ready template for building AI agents with [Strands Agents SDK](https://strandsagents.com/) and deploying them to [Amazon Bedrock AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html). Infrastructure is managed with [Terraform](https://www.terraform.io/).

## Architecture

```mermaid
flowchart TB
    subgraph dev [Developer]
        Code[Agent Code]
        TF[Terraform]
    end

    subgraph build [Build and Package]
        Docker[Docker ARM64 Image]
        ECR[Amazon ECR]
    end

    subgraph runtime [AgentCore Runtime]
        RT[Agent Runtime MicroVM]
        Strands[Strands Agent Loop]
        Tools[Agent Tools]
    end

    subgraph infra [AWS Infrastructure]
        IAM[IAM Roles and Policies]
        CW[CloudWatch and OTEL]
        Bedrock[Bedrock Model Access]
    end

    Code --> Docker --> ECR --> RT
    TF --> IAM
    TF --> RT
    RT --> Strands --> Tools
    Strands --> Bedrock
    RT --> CW
```

## Project Structure

```
bedrock-agent-blueprint/
├── agents/                        # Agent code (what you edit)
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── main.py
│   └── tools.py
│
├── infra/                         # Terraform (ECR, IAM, AgentCore Runtime)
│   ├── main.tf
│   ├── variables.tf
│   ├── iam.tf
│   ├── ecr.tf
│   ├── agent.tf
│   ├── outputs.tf
│   └── terraform.tfvars.example
│
├── scripts/
│   ├── build_and_push.sh          # Build Docker image and push to ECR
│   └── invoke.py                  # Call the deployed agent
│
├── tests/
│   └── test_agent.py
│
├── .gitignore
└── README.md
```

## Prerequisites

- **AWS Account** with [AgentCore permissions](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html)
- **Python 3.10+** and [**uv**](https://docs.astral.sh/uv/)
- **Terraform >= 1.5**
- **Docker** (with buildx support) for building ARM64 images
- **AWS CLI** configured with credentials

> **Tip:** Terraform uses the default AWS credential chain. To use a named profile, run `export AWS_PROFILE=my-profile` before any Terraform or AWS CLI commands.

## Quick Start

### 1. Deploy infrastructure

```bash
git clone <this-repo>
cd bedrock-agent-blueprint

cp infra/terraform.tfvars.example infra/terraform.tfvars
# Edit infra/terraform.tfvars with your AWS region, project name, etc.

terraform -chdir=infra init
terraform -chdir=infra apply
```

This creates all AWS resources in one step: an ECR repository, IAM roles and policies, and the AgentCore runtime.

### 2. Build and push the agent image

```bash
./scripts/build_and_push.sh
```

The script builds an ARM64 Docker image, tags it with the current git short SHA (e.g. `a1b2c3d`) and `latest`, and pushes both to ECR.

### 3. Deploy the updated image

```bash
terraform -chdir=infra apply -var="container_tag=<git-sha>"
```

Use the tag printed at the end of the build script.

### 4. Invoke the agent

```bash
# Uses the built-in get_weather tool
python scripts/invoke.py --prompt "What's the weather in Seattle?"

# Uses the built-in calculate tool
python scripts/invoke.py --prompt "What is sqrt(144) + 3 * 2?"

# Uses the built-in lookup_item tool
python scripts/invoke.py --prompt "Look up item ITEM-001 in inventory"
```

You can also pass the runtime ARN directly:

```bash
python scripts/invoke.py \
  --arn "arn:aws:bedrock-agentcore:eu-west-1:123456789012:runtime/my-agent" \
  --prompt "What's the weather in Seattle?"
```

### Day-to-day workflow

After the initial setup, the typical development loop is just two commands:

```bash
./scripts/build_and_push.sh
terraform -chdir=infra apply -var="container_tag=<new-sha>"
```

## Local Development

You can test the agent locally without deploying to AWS.

### Run the agent locally

```bash
cd agents
uv sync
uv run python main.py
```

Then, in another terminal:

```bash
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello!"}'
```

### Run the tests

```bash
cd agents
uv sync --dev
uv run pytest ../tests/ -v
```

The tests exercise tool functions directly -- no AWS credentials needed.

## The Agent

The included agent (`agents/`) demonstrates custom tool integration using the Strands `@tool` decorator. It comes with three example tools:

- **`get_weather`** -- Returns weather data for a city (mock, replace with a real API)
- **`calculate`** -- Safely evaluates math expressions
- **`lookup_item`** -- Searches a database by item ID (mock, replace with DynamoDB/RDS)

## Customization

### Add your own tools

1. Create a new function in `tools.py` (or a new file):

```python
from strands import tool

@tool
def my_tool(param: str) -> dict:
    """Description of what this tool does.

    Args:
        param: Description of the parameter.
    """
    return {"status": "success", "content": [{"text": do_something(param)}]}
```

2. Import and add it to the agent's `tools` list in `main.py`:

```python
from tools import my_tool

agent = Agent(
    tools=[my_tool],
    system_prompt="...",
)
```

### Change the model

The agent uses Claude Sonnet 4.5 via cross-region inference (`eu.anthropic.claude-sonnet-4-5-20250929-v1:0`) by default. To use a different model or region prefix, update `main.py`:

```python
from strands.models.bedrock import BedrockModel

model = BedrockModel(model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0")

agent = Agent(
    model=model,
    system_prompt="...",
)
```

### Switch to VPC networking

In `infra/terraform.tfvars`:

```hcl
network_mode = "VPC"
```

You will also need to add `subnets` and `security_groups` to the network configuration in `infra/agent.tf`.

### Add JWT authorization

Add an `authorizer_configuration` block to the runtime resource in `infra/agent.tf`:

```hcl
authorizer_configuration {
  custom_jwt_authorizer {
    discovery_url    = "https://accounts.google.com/.well-known/openid-configuration"
    allowed_audience = ["my-app"]
    allowed_clients  = ["client-123"]
  }
}
```

## Observability

The Dockerfile includes `opentelemetry-instrument`, which automatically sends traces and metrics to CloudWatch -- no code changes needed.

To view your agent's observability data:

1. Enable [CloudWatch Transaction Search](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html) (one-time setup)
2. Open the CloudWatch console
3. Navigate to **GenAI Observability** to see traces, metrics, and logs

## Tear Down

To remove all deployed resources and avoid ongoing charges:

```bash
terraform -chdir=infra destroy
```

This deletes the AgentCore runtime, IAM roles, and the ECR repository (including all pushed images for non-prod environments).

> **Note:** In production (`environment = "prod"`), the ECR repository has deletion protection enabled. You will need to manually empty and delete it, or set `force_delete = true` in `infra/ecr.tf` before destroying.

## When To Use This Setup

**Use Strands + AgentCore Runtime when:**

- You want full control over agent reasoning
- You care about research-grade agent design
- You expect agents to evolve rapidly
- You still want serverless scaling, IAM, and observability

**Consider native Bedrock Agents instead if:**

- You want the simplest possible Bedrock-native agent
- You're fine with AWS-managed planning logic

## License

MIT
