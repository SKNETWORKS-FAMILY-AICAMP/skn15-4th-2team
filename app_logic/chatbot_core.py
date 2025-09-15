from transformers import pipeline
from openai import OpenAI
from langchain_openai import ChatOpenAI
import asyncio
import json

client = OpenAI()

classifier = pipeline(
    "zero-shot-classification",
    model="joeddav/xlm-roberta-large-xnli",
    tokenizer="joeddav/xlm-roberta-large-xnli",
    use_fast=False
)

model = ChatOpenAI(model="gpt-5-2025-08-07")

from utils.cover_letter import company_ideal_talent_api
from utils.job_search import search_jobs

async def handle_input_with_state(user_input: str, context: dict, model: ChatOpenAI) -> str:
    intent = classify_user_input(user_input)
    context["intent"] = intent

    if intent == "자기소개서":
        recent_context = "\n".join(context.get("con_past", [])[-3:])
        prompt_with_context = f"이전 내용:\n{recent_context}\n\n현재 질문:\n{user_input}"
        company, job, spec = extract_info_from_text(prompt_with_context)

        if not company:
            return "회사명이 부족합니다. 다시 작성해 주세요."
        elif not job:
            return "직무 정보가 부족합니다. 다시 작성해 주세요."
        elif not spec:
            return "자기소개서 내용이 부족합니다. 다시 작성해 주세요."

        result = await asyncio.to_thread(company_ideal_talent_api, model, company)
        return json.dumps(result, ensure_ascii=False)  # or return str(result)

    elif intent == "모집공고":
        return search_jobs(user_input)

    else:
        return "자기소개서 또는 모집공고 관련 내용을 입력해 주세요."

def classify_user_input(text: str) -> str:
    candidate_labels = ["자기소개서", "모집공고", "기타"]
    result = classifier(text, candidate_labels, hypothesis_template="이 문장은 {} 요청과 관련이 있다.")
    return result["labels"][0]

def extract_info_from_text(user_input: str) -> tuple[str, str, str]:
    prompt = f"""
    다음 사용자 입력에서 회사명(company), 직무(job), 그리고 자기소개서 내용(spec)을 추출해줘. 
    명확하지 않은 경우는 ""로 반환하고 JSON 형식으로 출력:

    입력:
    \"\"\"{user_input}\"\"\"

    결과:
    {{
      "company": "",
      "job": "",
      "spec": ""
    }}
    """
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    try:
        data = json.loads(response.choices[0].message.content)
        return data.get("company", ""), data.get("job", ""), data.get("spec", "")
    except Exception:
        return "", "", user_input.strip()
