# LLM functions in ChalkSQL

Classify, extract, score and summarize every row of a table with OpenAI models, inline in a
ChalkSQL `SELECT`, routed through the Chalk model gateway. This repository is the backend of the
live demo: a small web service that runs a handful of preset queries over a fictional support
queue and shows the results.

```sql
SELECT id, body,
  ai_classify(body, 'What is this support ticket about?',
              ['billing', 'software_bug', 'shipping', 'returns', 'account_access'],
              model => 'gpt-4.1-mini',
              url => :gateway_url,        -- the Chalk model gateway
              api_key => :gateway_key,
              choice_constraint => 'none') AS topic
FROM tickets
```

## The functions

| Function | Returns |
| --- | --- |
| `ai_classify(text, question, [labels], ...)` | the label the model picks, or NULL |
| `ai_extract(text, question, ...)` | the words of the text that answer the question, or NULL |
| `ai_score(text, question, ...)` | P(TRUE) of a yes/no answer, read from log-probabilities |
| `ai_filter(text, question, ...)` | a boolean, for use in `WHERE` |
| `openai_complete(prompt, ...)` | the full response struct: completion, token usage, finish reason |

All of them take `model`, `url` (`api_server` for `openai_complete`) and `api_key`, plus options such
as `max_tokens`, `max_concurrency`, `timeout_seconds` and `extra_body`.

Two details matter with hosted OpenAI models, and the presets in `queries.py` handle both:

- `ai_classify` constrains decoding with a vLLM extension by default. Pass
  `choice_constraint => 'none'` for a hosted API; the model's answer is then matched to a label.
- `ai_extract`'s default prompt is written for a completions model. Chat models answer better with
  a direct request, so the demo passes its own `prompt => '... {text} ... {question} ...'` and
  `stop => ''`. Options such as `prompt` must be a single string literal.

## Files

| File | Role |
| --- | --- |
| `data.py` | The fictional tickets and reviews, rendered as a SQL `WITH` clause. |
| `queries.py` | The preset queries, with the gateway URL and key bound server-side. |
| `server.py` | FastAPI: serves `index.html` and runs the queries with `chalkcompute.SQLClient`. |
| `index.html` | The page: pick a query and a model, run it, see the SQL and the rows. |
| `deploy.py` | Deploys it all as a `chalkcompute.ScalingGroup`. |

## Deploy it

You need [`uv`](https://docs.astral.sh/uv/), a Chalk environment with the model gateway enabled, and
a gateway API key stored as a Chalk secret:

```bash
chalk router api-key create
chalk secrets set CHALK_ROUTER_API_KEY=<key>
./deploy.py
```

The service authenticates to ChalkSQL with its own workload identity (`chalk_identity=True`), so it
holds no client secret. The gateway key reaches it from the Chalk secret, is bound into each query
on the server, and never reaches the browser: the SQL the page shows has `:gateway_url` and
`:gateway_key` placeholders instead.

The service is public by default, so it limits what a visitor can do: results are cached for 15
minutes per query and model, custom questions are capped at 160 characters, and runs are
rate-limited per visitor and overall.

## License

Apache-2.0. Thistle & Pine and all of its tickets and reviews are fictional.

## Local authentication

The SDK reads credentials, API host, and the selected environment from your existing
`chalk login` in `~/.chalk.yml`, including project-scoped and default logins.
For unattended runs, `CHALK_CLIENT_ID` and `CHALK_CLIENT_SECRET` remain supported.
The examples use the current environment selected by your Chalk login.
