"""The demo's preset ChalkSQL queries.

Each query names its model-call options with a macro: `{ai}` for the ai_* functions (whose
endpoint option is `url`) and `{llm}` for openai_complete (whose endpoint option is
`api_server`). `render()` expands them for execution, with the gateway's URL and API key, or for
display, with placeholders, so the key never leaves the server.
"""

from __future__ import annotations

from dataclasses import dataclass

from data import tables_cte

MODELS = ["gpt-4.1-mini", "gpt-4.1-nano", "gpt-4o-mini"]

# ai_extract's default prompt ends in a completions-style prefill ('Phrase: "'); a chat model
# repeats that cue instead of continuing it, so chat models get a prompt that asks for the bare span.
EXTRACT_PROMPT = (
    "Text: {text} -- Question: {question} -- Reply with only the words copied exactly from the text "
    "that answer the question, with no quotes or explanation. If the text does not answer it, reply none."
)

TOPICS = [
    "billing",
    "software_bug",
    "shipping",
    "returns",
    "account_access",
    "feature_request",
]


@dataclass(frozen=True)
class Preset:
    id: str
    title: str
    function: str
    blurb: str
    sql: str
    # Whether the visitor may replace `{question}` with their own (length-capped, escaped) question.
    custom_question: bool
    default_question: str
    # Result columns the model produced, which the page highlights.
    model_columns: tuple[str, ...]


def _labels(values: list[str]) -> str:
    return "[" + ", ".join(f"'{v}'" for v in values) + "]"


PRESETS: list[Preset] = [
    Preset(
        id="classify",
        title="Route every ticket",
        function="ai_classify",
        blurb="One model call per row picks a label from a fixed list. The result is a plain string column.",
        sql=f"""SELECT id, customer, body,
  ai_classify(body, 'What is this support ticket about?',
              {_labels(TOPICS)},
              {{ai}}, choice_constraint => 'none') AS topic
FROM tickets
ORDER BY id""",
        custom_question=False,
        default_question="",
        model_columns=("topic",),
    ),
    Preset(
        id="topics",
        title="Count tickets by topic",
        function="ai_classify + GROUP BY",
        blurb="The label is an ordinary column, so GROUP BY, ORDER BY and joins work on it unchanged.",
        sql=f"""SELECT topic, count(*) AS tickets, count_if(plan = 'pro') AS pro_tickets
FROM (
  SELECT plan,
    ai_classify(body, 'What is this support ticket about?',
                {_labels(TOPICS)},
                {{ai}}, choice_constraint => 'none') AS topic
  FROM tickets
)
GROUP BY topic
ORDER BY tickets DESC""",
        custom_question=False,
        default_question="",
        model_columns=("topic",),
    ),
    Preset(
        id="extract",
        title="Pull out order numbers",
        function="ai_extract",
        blurb="ai_extract returns the words of the text that answer the question, or NULL when nothing does.",
        sql="""SELECT id, body,
  ai_extract(body, 'What is the order number?', {ai},
             prompt => '{extract_prompt}', stop => '') AS order_number,
  ai_extract(body, 'Which product is the customer writing about?', {ai},
             prompt => '{extract_prompt}', stop => '') AS product
FROM tickets
ORDER BY id""",
        custom_question=False,
        default_question="",
        model_columns=("order_number", "product"),
    ),
    Preset(
        id="score",
        title="Rank by frustration",
        function="ai_score",
        blurb="ai_score reads P(TRUE) from the model's log-probabilities, so it sorts like any number.",
        sql="""SELECT id, customer, body,
  round(ai_score(body, '{question}', {ai}), 3) AS score
FROM tickets
ORDER BY score DESC
LIMIT 8""",
        custom_question=True,
        default_question="Is the customer frustrated or angry?",
        model_columns=("score",),
    ),
    Preset(
        id="filter",
        title="Find Pro customers about to churn",
        function="ai_filter",
        blurb="A cheap SQL predicate runs first; the model is only asked about the rows it keeps.",
        sql="""SELECT id, customer, body
FROM tickets
WHERE plan = 'pro'
  AND ai_filter(body, '{question}', {ai})
ORDER BY id""",
        custom_question=True,
        default_question="Does the customer say they will cancel or stop buying?",
        model_columns=(),
    ),
    Preset(
        id="summarize",
        title="Summarize reviews, with token counts",
        function="openai_complete",
        blurb="openai_complete returns the full response struct, including the token usage of every call.",
        sql="""SELECT product, stars, body, r.completion AS summary,
  r.prompt_tokens, r.completion_tokens
FROM (
  SELECT product, stars, body,
    openai_complete('Summarize this product review in at most 12 words: ' || body,
                    {llm}, max_tokens => 40) AS r
  FROM reviews
)
ORDER BY stars, product""",
        custom_question=False,
        default_question="",
        model_columns=("summary", "prompt_tokens", "completion_tokens"),
    ),
]

PRESETS_BY_ID = {p.id: p for p in PRESETS}


def _sql_string(value: str) -> str:
    return value.replace("'", "''")


def render(
    preset: Preset,
    *,
    model: str,
    question: str | None,
    gateway_url: str | None,
    gateway_key: str | None,
) -> str:
    """The preset's query. With a gateway URL and key it is the executable query, including the
    table CTE; without them it is the display form, which shows placeholders for both."""
    if model not in MODELS:
        raise ValueError(f"unknown model {model!r}")
    q = question if (preset.custom_question and question) else preset.default_question
    if gateway_url is not None and gateway_key is not None:
        url, key = f"'{_sql_string(gateway_url)}'", f"'{_sql_string(gateway_key)}'"
    else:
        url, key = ":gateway_url", ":gateway_key"
    # temperature 0 keeps reruns of a preset stable, so a cached and a fresh result agree.
    ai = f"model => '{model}', url => {url}, api_key => {key}, extra_body => '{{\"temperature\": 0}}'"
    llm = f"model => '{model}', api_server => {url}, api_key => {key}, temperature => 0"
    body = (
        preset.sql.replace("{ai}", ai)
        .replace("{llm}", llm)
        .replace("{question}", _sql_string(q))
        # After {question}: the prompt keeps its own {text} and {question} for ai_extract to fill.
        .replace("{extract_prompt}", _sql_string(EXTRACT_PROMPT))
    )
    if gateway_url is None:
        return body
    return tables_cte() + body
