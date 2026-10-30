"""LLM access. Provider chosen with LLM_PROVIDER (mock | openai | azure | anthropic | groq), see .env.example."""
import os

from dotenv import load_dotenv

from .prompts import (EXEC_SUMMARY_PROMPT, NO_DATA, ROOT_CAUSE_PROMPT, SYSTEM_PROMPT, build_user_prompt)

load_dotenv()


def _call_openai(system: str, user: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    r = client.chat.completions.create(model=os.environ["LLM_MODEL"], temperature=0.2,
                                       messages=[{"role": "system", "content": system},
                                                 {"role": "user", "content": user}])
    return r.choices[0].message.content.strip()


def _call_groq(system: str, user: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1")
    r = client.chat.completions.create(model=os.environ["LLM_MODEL"], temperature=0.2,
                                       messages=[{"role": "system", "content": system},
                                                 {"role": "user", "content": user}])
    return r.choices[0].message.content.strip()


def _call_azure(system: str, user: str) -> str:
    from openai import AzureOpenAI
    client = AzureOpenAI(api_key=os.environ["AZURE_OPENAI_API_KEY"],
                         azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                         api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-06-01"))
    r = client.chat.completions.create(model=os.environ["LLM_MODEL"],  # = deployment name
                                       temperature=0.2,
                                       messages=[{"role": "system", "content": system},
                                                 {"role": "user", "content": user}])
    return r.choices[0].message.content.strip()


def _call_anthropic(system: str, user: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    r = client.messages.create(model=os.environ["LLM_MODEL"], max_tokens=1500, temperature=0.2,
                               system=system, messages=[{"role": "user", "content": user}])
    return "".join(b.text for b in r.content if getattr(b, "type", "") == "text").strip()


PROVIDERS = {"openai": _call_openai, "azure": _call_azure, "anthropic": _call_anthropic, "groq": _call_groq}


def default_provider() -> str:
    return os.environ.get("LLM_PROVIDER", "mock").lower()


def generate(task: str, payload: dict, provider: str | None = None) -> str:
    """task = 'summary' | 'root_cause'. Guardrail in code: no data -> no LLM call."""
    provider = (provider or default_provider()).lower()
    if payload.get("status") != "ok":
        return NO_DATA
    if task == "root_cause" and not payload.get("anomalies"):
        return "No anomaly to explain: nothing exceeded the thresholds in this scope."
    # if provider == "mock":
    #     return mock_llm.executive_summary(payload) if task == "summary" else mock_llm.root_cause(payload)
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider '{provider}'. Use mock, openai, azure, anthropic or groq.")
    template = EXEC_SUMMARY_PROMPT if task == "summary" else ROOT_CAUSE_PROMPT
    return PROVIDERS[provider](SYSTEM_PROMPT, build_user_prompt(template, payload))
