# Cloud IaC Agent (working title)

> An AI agent that scans an existing cloud account, generates Terraform for it, flags cost and security issues, and requires human review before anything is committed.

**Status:** Planning / Week 1 (foundations). Problem statement being validated with industry practitioners.

---

## 1. Problem

Many large companies run big cloud environments that were built by hand in the cloud console over years ("ClickOps"). As a result they have:

- **No version control:** nobody knows who changed what, or when, and changes cannot be rolled back.
- **No reproducibility:** if something breaks, the environment cannot be rebuilt from code.
- **Poor cost control:** wasted, forgotten or oversized resources are hard to find.

The standard fix is Infrastructure as Code (IaC), for example Terraform. Converting a large existing estate by hand takes months. This project explores how AI agents can speed that up safely.

## 2. Solution

An agent pipeline:

```
Scan -> Map -> Generate Terraform -> Validate -> Cost/Risk Report -> Pull Request for Human Review
```

| Stage | What it does |
|---|---|
| Scan | Reads existing cloud resources (read-only) |
| Map | Builds an understanding of resources and their dependencies |
| Generate | LLM produces Terraform (HCL) for each resource |
| Validate | Runs `terraform validate` / `plan` to check the output is correct |
| Report | Flags cost waste and security risks |
| Review | Opens a pull request; a human approves before anything is merged |

**Design principles:** understand before generating, validate before delivering, keep a human in the loop.

## 3. Scope (v1)

- **Cloud:** AWS only
- **Resource types:** S3, EC2, security groups, (stretch: RDS)
- **Access:** read-only; the agent never changes the real account
- **Data:** mock AWS-style JSON first, then a sandbox account
- **Out of scope for v1:** multi-cloud, auto-apply, very large estates

## 4. Planned architecture

```
project/
├── app/                 # FastAPI backend
├── llm_core/            # structured outputs, retries, routing, caching
├── rag/                 # retrieval over Terraform/AWS docs
├── agents/              # tools, MCP server, multi-agent workflow
├── evals/               # golden dataset, metrics, regression tests
├── observability/       # OpenTelemetry tracing
├── security/            # guardrails, injection tests
├── .github/workflows/   # CI/CD
├── docs/                # DESIGN.md, diagrams, notes
└── docker-compose.yml
```

## 5. Roadmap (8 weeks)

| Week | Focus | Project deliverable |
|---|---|---|
| 1 | Python, FastAPI, Pydantic, SQL, Git, Docker | API + PostgreSQL storage for scanned resources |
| 2 | ML basics, LLM fundamentals | Notebooks, first LLM API calls |
| 3 | Context and LLM app engineering | Terraform generation with structured outputs and tool calling |
| 4 | RAG | Retrieval over Terraform/AWS docs with citations |
| 5 | Agents and multi-agent systems | Scan-generate-validate workflow with human approval |
| 6 | Evaluation, observability, security | Evals, tracing dashboard, `SECURITY.md` |
| 7 | GenAIOps, cloud deploy, system design | CI/CD with evals, live deployment, `DESIGN.md` |
| 8 | Polish | Demo video, README, results table |

## 6. Success metrics (to be measured, not assumed)

- % of generated Terraform that passes `terraform validate`
- % of generated resources that match the scanned resource
- Cost and latency per scan
- Number of injected-prompt attacks tested and blocked

## 7. Research notes

- Market feedback: pending a conversation between my internship manager and a platform engineering consultant.
- Related space: AI platforms for large-scale code refactoring (for example Blitzy), which map a codebase before changing it. This project applies a similar "understand first, validate, then deliver" pattern to cloud infrastructure.

## 8. Tech stack

Python, FastAPI, Pydantic, PostgreSQL, Redis, Docker, Terraform, LangGraph (planned), OpenTelemetry, GitHub Actions.