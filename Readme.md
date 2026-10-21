# SecureShelf

### AppSec RAG Assistant · Fair-Share LLM Quotas · Pull-Request Security Reviews

```{=html}
```
`<strong>`{=html}Security knowledge that scales across teams---without
letting one team consume the shared LLM quota.`</strong>`{=html}
```{=html}
```
SecureShelf is an internal Application Security (AppSec) assistant and
pull-request security review system designed for software engineering
organizations. It combines retrieval-augmented generation (RAG) over
OWASP guidance, per-team API quotas, usage telemetry, and automated
PR-diff checks to help teams apply secure-coding practices consistently.

**Provisioning target:** 12 project teams in Coimbatore\
**API server:** FastAPI on port `8000`\
**Quota policy:** 5 requests/minute and 50 requests/day per team

> **Implementation note:** This README documents the intended system and
> the commands/endpoints supplied with the project. Verify that each
> control is enforced in the deployed implementation before relying on
> it in production. In particular, use authenticated administrative
> access for quota resets and protect team credentials and usage
> telemetry.

------------------------------------------------------------------------

## Contents

-   [Highlights](#highlights)
-   [System Architecture](#system-architecture)
-   [Core Workflows](#core-workflows)
    -   [Ask SecureShelf](#1-ask-secureshelf)
    -   [Fair-Share Quota Enforcement](#2-fair-share-quota-enforcement)
    -   [RAG Retrieval and Answer
        Generation](#3-rag-retrieval-and-answer-generation)
    -   [Pull-Request Security Review](#4-pull-request-security-review)
    -   [Knowledge-Base Ingestion](#5-knowledge-base-ingestion)
-   [Quota Policy](#quota-policy)
-   [Technology Stack](#technology-stack)
-   [Project Structure](#project-structure)
-   [Getting Started](#getting-started)
-   [API Reference](#api-reference)
-   [Testing and Verification](#testing-and-verification)
-   [Security and Production
    Readiness](#security-and-production-readiness)
-   [License and Attribution](#license-and-attribution)

------------------------------------------------------------------------

## Highlights

  -----------------------------------------------------------------------
  Capability                          Purpose
  ----------------------------------- -----------------------------------
  **Team-isolated quotas**            Apply burst and daily request
                                      limits independently to each team.

  **AppSec RAG assistant**            Answer secure-coding questions
                                      using retrieved OWASP material and
                                      citations.

  **Knowledge corpus**                Organize ASVS, Cheat Sheet Series,
                                      and WSTG content for retrieval.

  **PR-diff security checks**         Inspect added code for selected
                                      vulnerability patterns and enrich
                                      findings with guidance.

  **Usage board**                     Surface team usage, remaining
                                      quota, and popular security topics.

  **Fair-share verification**         Test that a noisy team receives a
                                      quota response without consuming
                                      sibling teams' allowances.

  **Demo mode**                       Seed a small offline corpus for
                                      demonstrations without full
                                      indexing.
  -----------------------------------------------------------------------

## System Architecture

The architecture separates the client-facing API, quota enforcement,
retrieval/generation engine, knowledge store, and pull-request workflow.

``` mermaid
flowchart TB
    subgraph Teams["12 Project Engineering Teams"]
        T1["Team 01 · Payments"]
        T2["Team 02 · Banking"]
        T3["Teams 03–11"]
        T12["Team 12 · Healthcare"]
    end

    subgraph Gateway["FastAPI Gateway · :8000"]
        API["REST API"]
        AUTH["API-key authentication"]
        LIMIT["Per-team atomic quota limiter"]
        BOARD["Usage board · GET /"]
    end

    subgraph Engine["SecureShelf RAG Engine"]
        CLASSIFY["Topic classification"]
        RETRIEVE["Semantic retrieval"]
        CONTEXT["Context assembly"]
        LLM["Gemini generation"]
        CITE["Cited response"]
    end

    subgraph Knowledge["Knowledge Store"]
        CORPUS["OWASP source corpus"]
        VECTOR["ChromaDB index"]
        JSONL["JSONL / demo corpus"]
    end

    subgraph PR["Pull-Request Review"]
        DIFF["Unified Git diff"]
        SCAN["PR review agent"]
        RULES["AST / pattern checks"]
        ENRICH["RAG-enriched findings"]
        REVIEW["Review comment + sign-off checklist"]
    end

    Teams --> API
    API --> AUTH --> LIMIT
    LIMIT -->|Allowed| CLASSIFY
    LIMIT -->|Over quota| RATE["429 JSON response"]
    CLASSIFY --> RETRIEVE
    RETRIEVE <--> VECTOR
    RETRIEVE --> CONTEXT --> LLM --> CITE
    CORPUS --> VECTOR
    CORPUS --> JSONL
    BOARD --> API
    DIFF --> SCAN --> RULES --> ENRICH
    ENRICH --> RETRIEVE
    ENRICH --> REVIEW
```

### Trust boundaries

-   **Client boundary:** team clients provide an API key in the
    `X-API-Key` header.
-   **Quota boundary:** authentication must resolve a key to a stable
    team identity before quota accounting.
-   **Model boundary:** retrieved content is context for the model, not
    trusted instructions. The assistant should not follow instructions
    embedded in source documents or user-submitted code.
-   **Administrative boundary:** usage inspection, quota resets, and
    demo-key discovery should be restricted appropriately before
    deployment.
-   **CI boundary:** PR diffs are untrusted input. Treat code snippets
    and comments as data, not executable instructions.

------------------------------------------------------------------------

## Core Workflows

### 1. Ask SecureShelf

This is the typical path for a team asking an AppSec question.

``` mermaid
sequenceDiagram
    autonumber
    participant Client as Team Client
    participant API as FastAPI
    participant Auth as API-key Auth
    participant Quota as Quota Limiter
    participant RAG as SecureShelf RAG
    participant Store as Knowledge Store
    participant LLM as Gemini

    Client->>API: POST /api/v1/ask + X-API-Key
    API->>Auth: Validate key and resolve team
    Auth-->>API: Authenticated team identity
    API->>Quota: Check and atomically consume quota
    alt Request is within quota
        Quota-->>API: Allow
        API->>RAG: Question + request context
        RAG->>Store: Retrieve relevant OWASP chunks
        Store-->>RAG: Relevant passages and metadata
        RAG->>LLM: Question + grounded context
        LLM-->>RAG: Generated answer
        RAG-->>API: Answer with citations
        API-->>Client: 200 response
    else Burst or daily quota exceeded
        Quota-->>API: Reject
        API-->>Client: 429 structured JSON
    end
```

**Expected behavior**

1.  Authenticate the request and map the credential to a team.
2.  Apply that team's burst and daily quotas before calling the RAG/LLM
    pipeline.
3.  Retrieve relevant security guidance and generate a grounded answer.
4.  Return citations or source metadata so developers can inspect the
    supporting guidance.
5.  Return a structured `429` response when the team exceeds its quota.

### 2. Fair-Share Quota Enforcement

The limiter is designed to prevent one team's traffic from consuming the
request allowance assigned to other teams.

``` mermaid
flowchart TD
    START["Incoming request"] --> VALID{"API key valid?"}
    VALID -->|No| UNAUTH["401 / 403 response"]
    VALID -->|Yes| TEAM["Resolve team ID"]
    TEAM --> CHECK["Atomically check team's counters"]
    CHECK --> BURST{"Under 5 requests/minute?"}
    BURST -->|No| REJECT["429 Too Many Requests"]
    BURST -->|Yes| DAILY{"Under 50 requests/day?"}
    DAILY -->|No| REJECT
    DAILY -->|Yes| CONSUME["Atomically consume quota"]
    CONSUME --> CONTINUE["Continue to RAG pipeline"]
    REJECT --> JSON["Structured limit response"]
```

**Quota policy per team**

-   **Burst limit:** 5 requests per minute.
-   **Daily limit:** 50 requests per day.
-   **Isolation:** counters are keyed by team identity, not shared as a
    single organization-wide counter.
-   **Exceeded quota:** return HTTP `429` and do not invoke the model
    for that rejected request.

For multiple API workers or server instances, use a shared store such as
Redis and an atomic operation (for example, a Lua script or transaction)
to check and increment counters together. A process-local in-memory
limiter is suitable only for a single-process demo: it does not
coordinate counters across workers and resets on process restart.

### 3. RAG Retrieval and Answer Generation

``` mermaid
flowchart LR
    Q["Developer question"] --> N["Normalize / classify topic"]
    N --> E["Create query embedding"]
    E --> SEARCH["Similarity search"]
    KB["OWASP corpus"] --> CHUNKS["Parse and chunk documents"]
    CHUNKS --> EMBED["Create document embeddings"]
    EMBED --> INDEX["ChromaDB index"]
    INDEX --> SEARCH
    SEARCH --> FILTER["Select relevant passages"]
    FILTER --> PROMPT["Build grounded prompt"]
    PROMPT --> MODEL["Gemini LLM"]
    MODEL --> ANSWER["Answer with source citations"]
```

**Pipeline stages**

1.  **Ingest:** collect supported OWASP source material and extract
    document text and metadata.
2.  **Chunk:** split documents into retrieval-sized passages while
    preserving source identifiers and relevant headings.
3.  **Index:** generate embeddings and store them in ChromaDB, or use
    the JSONL/demo corpus when indexing is disabled.
4.  **Retrieve:** classify the topic and search for relevant passages.
5.  **Generate:** provide the question and retrieved passages to Gemini
    with instructions to ground the answer in evidence.
6.  **Cite:** return source references alongside the answer. Do not
    present a claim as OWASP-backed if the retrieved evidence does not
    support it.

> **Embedding compatibility:** the query and document embedding models,
> dimensions, and preprocessing must match the index configuration.
> Confirm the configured Gemini model identifiers against the provider's
> current model catalogue; model names and availability can change.

### 4. Pull-Request Security Review

The PR agent checks a unified diff, identifies selected vulnerability
patterns, and enriches the results with relevant security guidance.

``` mermaid
flowchart TD
    PR["Pull request"] --> DIFF["Generate / load unified diff"]
    DIFF --> PARSE["Parse changed lines and context"]
    PARSE --> RULES["AST and pattern checks"]
    RULES --> SQL["SQL injection · CWE-89"]
    RULES --> HASH["Weak password hashing · CWE-916"]
    RULES --> AUTHZ["Missing authorization · CWE-862"]
    SQL --> FINDINGS["Normalize findings"]
    HASH --> FINDINGS
    AUTHZ --> FINDINGS
    FINDINGS --> RAG["Retrieve relevant OWASP guidance"]
    RAG --> ENRICH["Add ASVS requirements and WSTG IDs"]
    ENRICH --> CHECKLIST["Generate senior sign-off checklist"]
    CHECKLIST --> COMMENT["PR review comment / report"]
    COMMENT --> HUMAN["Developer validation and remediation"]
```

**Current detection scope described by this project**

  -----------------------------------------------------------------------
  Check                   Example risk            CWE
  ----------------------- ----------------------- -----------------------
  SQL injection           User-controlled values  CWE-89
                          interpolated into SQL   
                          strings                 

  Weak password hashing   Fast hashes such as MD5 CWE-916
                          or SHA-1 used for       
                          password storage        

  Missing authorization   Sensitive operations    CWE-862
                          lack an appropriate     
                          authorization check     
  -----------------------------------------------------------------------

Each finding is intended to include evidence, severity or prioritization
where implemented, relevant OWASP ASVS requirements, WSTG test IDs, and
a senior-developer sign-off checklist.

**Important:** diff-based patterns are not a complete security analysis.
They can produce false positives and miss vulnerabilities. Findings
require developer review; the agent should not be treated as proof that
a PR is secure.

### 5. Knowledge-Base Ingestion

``` mermaid
flowchart TD
    SOURCES["OWASP ASVS, Cheat Sheet Series, WSTG"] --> FETCH["Fetch / load source documents"]
    FETCH --> EXTRACT["Extract text and metadata"]
    EXTRACT --> CHUNK["Split into chunks"]
    CHUNK --> MANIFEST["Build corpus manifest"]
    CHUNK --> MODE{"Indexing enabled?"}
    MODE -->|Yes| EMBED["Generate embeddings"]
    EMBED --> CHROMA["Persist ChromaDB index"]
    MODE -->|No| JSONL["Write / use JSONL demo corpus"]
    MANIFEST --> SUMMARY["Corpus summary endpoint"]
    CHROMA --> READY["Corpus ready for retrieval"]
    JSONL --> READY
```

The seed/demo path is intended for quick offline testing. Full ingestion
may take longer and should be run when the source material and indexing
dependencies are available.

------------------------------------------------------------------------

## Quota Policy

  ------------------------------------------------------------------------
  Policy                              Per-team limit Purpose
  --------------------- ---------------------------- ---------------------
  Burst                            5 requests/minute Controls short
                                                     traffic spikes

  Daily                              50 requests/day Caps ongoing
                                                     shared-model usage

  Rejected request                        HTTP `429` Signals quota
                                                     exhaustion

  Team isolation                Independent counters Protects sibling
                                                     teams from
                                                     noisy-neighbor
                                                     traffic
  ------------------------------------------------------------------------

### Suggested response contract

The precise response fields depend on the implementation. A useful `429`
payload should clearly identify the limit type and when the client can
retry, without exposing internal credentials.

``` json
{
  "detail": {
    "code": "team_quota_exceeded",
    "limit_type": "per_minute",
    "message": "This team's request limit has been reached.",
    "retry_after_seconds": 60
  }
}
```

Treat this JSON as an **illustrative contract**, not a guarantee of the
current application's exact response shape.

------------------------------------------------------------------------

## Technology Stack

  -----------------------------------------------------------------------
  Layer                               Technology / role
  ----------------------------------- -----------------------------------
  API                                 FastAPI, Uvicorn

  Authentication                      Team API keys via `X-API-Key`

  Rate limiting                       Redis for distributed atomic
                                      limits; in-memory mode for local
                                      demos

  RAG engine                          `SecureShelfRAG`, semantic
                                      retrieval, topic classification

  Knowledge storage                   ChromaDB and/or JSONL demo corpus

  LLM and embeddings                  Google Gemini integrations
                                      configured by the project

  PR review                           `pr_review_agent.py`, unified Git
                                      diffs, AST/pattern checks

  UI                                  Static HTML usage board served at
                                      `/`

  Verification                        Pytest and `test_fair_sharing.py`
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## Project Structure

The following is a **logical map** of the components mentioned in this
README. Actual filenames may differ in your repository.

``` text
SecureShelf/
├── app.py                    # FastAPI app and REST endpoints
├── ingest_owasp.py           # OWASP corpus ingestion and indexing
├── pr_review_agent.py        # PR diff analysis and finding enrichment
├── test_fair_sharing.py      # Fair-sharing and quota tests
├── requirements.txt          # Python dependencies
├── sample_vulnerable_pr.diff # Sample vulnerable changes for demos
├── static/
│   └── index.html            # AppSec team usage board
├── data/                     # Corpus / manifest files (if configured)
└── chroma_db/                # Persistent vector index (if configured)
```

------------------------------------------------------------------------

## Getting Started

### Prerequisites

-   Python installed and available as `python`.
-   Git, if you plan to test PR diffs.
-   Dependencies listed in `requirements.txt`.
-   Gemini credentials and the required model access for live LLM use.
-   Redis if you need shared quota state across workers or instances.

### 1. Create a virtual environment

Run in PowerShell from the project root:

``` powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If script execution is blocked by local PowerShell policy, use your
organization's approved activation method or invoke the environment's
Python executable directly.

### 2. Install dependencies

``` powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a local `.env` file only if the application is configured to load
it, or set the variables in your shell/deployment environment. Use the
exact names expected by the code.

``` text
GEMINI_API_KEY=<your-key>
# Add the Redis URL and model configuration variables required by your implementation.
```

Do not commit real API keys, team credentials, or `.env` files. Keep a
`.env.example` containing placeholder values if you want to document the
configuration.

### 4. Seed the offline demo corpus

``` powershell
python ingest_owasp.py --seed-demo --no-index
```

This path is intended to seed a small demo corpus without building the
full vector index.

### 5. Run full ingestion and indexing

``` powershell
python ingest_owasp.py
```

Run this when you want the configured OWASP corpus ingested and indexed
for semantic retrieval. Confirm source availability, model credentials,
and storage configuration first.

### 6. Start the API server

``` powershell
python -m uvicorn app:app --reload --port 8000
```

Open these local URLs:

-   **Usage board:** <http://localhost:8000/>
-   **FastAPI interactive docs:** <http://localhost:8000/docs>
-   **Health endpoint:** <http://localhost:8000/api/v1/health>

Use `--reload` for local development only, not for production
deployment.

------------------------------------------------------------------------

## API Reference

The table below summarizes the endpoints described by the project.
Authentication requirements must be verified against the route
implementation; administrative and telemetry endpoints should not be
left publicly accessible by default.

  ----------------------------------------------------------------------------------------
  Method            Endpoint                          Purpose           Access guidance
  ----------------- --------------------------------- ----------------- ------------------
  `POST`            `/api/v1/ask`                     Ask a cited       Team API key in
                                                      OWASP/AppSec      `X-API-Key`
                                                      question          

  `GET`             `/api/v1/teams/usage`             View usage,       Restrict to
                                                      remaining quotas, authorized users
                                                      and topic         
                                                      telemetry across  
                                                      teams             

  `POST`            `/api/v1/teams/{team_id}/reset`   Reset a team's    Admin-only; audit
                                                      burst and daily   every reset
                                                      counters          

  `POST`            `/api/v1/pr-review/scan`          Run AST/pattern   Restrict according
                                                      and RAG-enriched  to deployment
                                                      checks on a PR    
                                                      diff              

  `GET`             `/api/v1/pr-review/sample`        Retrieve a sample Demo/test use;
                                                      vulnerable diff   avoid leaking
                                                                        internal samples

  `GET`             `/api/v1/corpus/summary`          Return corpus     Review data
                                                      manifest and      exposure before
                                                      chunk summary     enabling

  `POST`            `/api/v1/simulate-load`           Simulate          Development/test
                                                      noisy-team        only; protect in
                                                      traffic versus    production
                                                      sibling teams     

  `GET`             `/api/v1/health`                  Report health and Expose only
                                                      storage backend   non-sensitive
                                                      status            diagnostics

  `GET`             `/api/v1/demo/teams`              List demo teams   Development only;
                                                      and their API     never expose real
                                                      keys              keys

  `GET`             `/`                               Serve the AppSec  Apply access
                                                      governance and    controls
                                                      usage portal      appropriate to
                                                                        telemetry
  ----------------------------------------------------------------------------------------

### Example: ask a question

``` powershell
$headers = @{
  "X-API-Key" = "<team-api-key>"
  "Content-Type" = "application/json"
}

$body = @{
  question = "How should a Python API prevent SQL injection?"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8000/api/v1/ask" `
  -Headers $headers `
  -Body $body
```

The example assumes the request model accepts a `question` field. Adjust
the body to match the Pydantic schema in your implementation.

------------------------------------------------------------------------

## Testing and Verification

### Run the fair-sharing report

``` powershell
python test_fair_sharing.py
```

### Run the focused pytest suite

``` powershell
pytest test_fair_sharing.py -v
```

### Run the PR review agent in dry-run mode

``` powershell
python pr_review_agent.py --diff-file sample_vulnerable_pr.diff --dry-run
```

### Recommended verification scenarios

``` mermaid
flowchart TD
    START["Start verification"] --> A["Team A sends requests up to burst limit"]
    A --> B["Confirm allowed responses"]
    B --> C["Team A exceeds burst limit"]
    C --> D["Confirm structured 429 response"]
    D --> E["Team B sends a valid request"]
    E --> F{"Is Team B unaffected?"}
    F -->|Yes| G["Pass: isolation verified"]
    F -->|No| H["Fail: inspect shared counters / team keying"]
    G --> I["Test daily quota boundary"]
    I --> J["Test concurrent requests for atomicity"]
    J --> K["Test restart / multi-worker behavior"]
```

A robust test suite should cover:

-   Exactly-at-limit and one-over-limit cases for both burst and daily
    quotas.
-   Concurrent requests racing to consume the final available slot.
-   Independent counters for all team IDs.
-   Invalid, missing, and revoked API keys.
-   Correct `429` status and response fields.
-   Whether rejected requests avoid the LLM call.
-   Counter expiry, day-boundary behavior, and timezone policy.
-   Multi-worker consistency when Redis is enabled.
-   Authorized-only quota resets and audit logging.

------------------------------------------------------------------------

## Security and Production Readiness

Before deploying SecureShelf for internal teams, validate the following
controls:

-   [ ] **Secrets:** store provider keys and team API keys in a secret
    manager or protected environment; never commit real credentials.
-   [ ] **Key handling:** use high-entropy per-team keys, support
    rotation/revocation, compare securely, and avoid logging raw keys.
-   [ ] **Admin routes:** authenticate and authorize usage inspection,
    quota resets, team-key listing, and load simulation.
-   [ ] **Atomic quotas:** use shared atomic state for multi-worker
    deployments; define counter expiry and daily reset semantics.
-   [ ] **RAG provenance:** preserve source URLs, document versions,
    headings, and chunk metadata for citations.
-   [ ] **Prompt-injection resistance:** treat retrieved documents and
    PR content as untrusted data; do not let them override system policy
    or trigger tools.
-   [ ] **Data minimization:** avoid sending secrets, tokens, or
    unnecessary proprietary source code to external model services.
-   [ ] **Telemetry:** do not expose cross-team usage data to ordinary
    team clients unless explicitly intended.
-   [ ] **Error handling:** return useful error codes without leaking
    stack traces, prompts, secrets, or internal configuration.
-   [ ] **Model configuration:** verify current model IDs, access,
    quotas, and embedding compatibility.
-   [ ] **CI behavior:** keep the PR agent advisory unless a validated
    policy explicitly makes checks blocking; provide actionable evidence
    for findings.
-   [ ] **Deployment:** disable debug/reload settings, configure TLS at
    the appropriate boundary, and monitor latency, errors, quota
    rejections, and model usage.

------------------------------------------------------------------------

## License and Attribution

OWASP Application Security Verification Standard (ASVS), OWASP Cheat
Sheet Series, and OWASP Web Security Testing Guide (WSTG) materials are
generally published under **Creative Commons Attribution-ShareAlike 4.0
International (CC BY-SA 4.0)**, subject to the terms and notices of the
specific source material.

When redistributing OWASP-derived content, preserve attribution,
identify modifications where appropriate, and comply with the license.
Check the license and attribution notices of the exact versions ingested
by your pipeline.

SecureShelf's own source-code license should be specified separately by
the project owner.

------------------------------------------------------------------------

```{=html}
<p align="center">
```
`<sub>`{=html}SecureShelf · Internal AppSec enablement · Secure coding,
shared responsibly.`</sub>`{=html}
```{=html}
</p>
```
