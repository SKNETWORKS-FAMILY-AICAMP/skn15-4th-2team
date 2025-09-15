import streamlit as st
import pandas as pd
import json
import re
import asyncio
from typing import Annotated, TypedDict
from sqlalchemy import create_engine, text

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages

# jobkorea_cli 모듈 (외부 의존)
from jobkorea_cli.models import Spec
from jobkorea_cli.llm import parse_spec, ask_required_batch, map_filters
from jobkorea_cli.cli import crawl_by_roles_multi

# -------- 모델 및 DB 연결 -----------
model = ChatOpenAI(model="gpt-5-2025-08-07")
DB_CONNECTION_URL = 'postgresql+psycopg2://play:123@192.168.0.8:5432/team2'
engine = create_engine(DB_CONNECTION_URL)

# -------- 상태 타입 및 기본 프롬프트 -----------
class State(TypedDict):
    messages: Annotated[list, add_messages]

base_generate_prompt_ko = SystemMessage(
    "당신은 자기소개서를 작성하는 어시스턴트입니다. "
    "입력된 지원 직무와 본인 스펙, 경력, 경험 등을 토대로 최고의 자기소개서를 작성하세요."
)

base_generate_prompt_en = SystemMessage(
    "You are an assistant specialized in writing cover letters. "
    "Based on the given job position, personal qualifications, and experiences, write the best English cover letter."
)

reflection_prompt_ko = SystemMessage(
    "당신은 인사 담당자입니다. "
    "방금 생성된 자기소개서를 읽고 내용, 구체성, 설득력, 어투 등에서 개선이 필요한 부분을 상세하게 피드백하세요."
)

reflection_prompt_en = SystemMessage(
    "You are a hiring manager. "
    "Please review the cover letter and provide detailed feedback on content, concreteness, persuasiveness, and tone."
)

def get_prompts(language: str):
    if language == 'en':
        return base_generate_prompt_en, reflection_prompt_en
    else:
        return base_generate_prompt_ko, reflection_prompt_ko

def make_job_prompt(base_prompt, company_culture=None, example_resume=None, char_limit=0):
    parts = [base_prompt.content]
    if company_culture:
        parts.append(f"\n해당 회사의 인재상:\n{company_culture}")
    if example_resume:
        parts.append("\n내부 DB 자소서 예시 참고 내용:")
        if isinstance(example_resume, dict):
            if example_resume.get("q"):
                parts.append(f"자소서 문항:\n{example_resume['q']}")
            if example_resume.get("a"):
                parts.append(f"예시 답변:\n{example_resume['a']}")
            if example_resume.get("advice"):
                parts.append(f"추가 조언:\n{example_resume['advice']}")
        else:
            parts.append(str(example_resume))
    if char_limit > 0:
        parts.append(f"\n자기소개서는 글자 수 최대 {char_limit}자이며, 가능한 한 {int(char_limit * 0.9)}자 이상으로 작성하세요.")
    parts.append("\n위 정보를 참고하여 자기소개서를 작성하세요.")
    return SystemMessage('\n'.join(parts))

def generate(state: State, generate_prompt: SystemMessage, char_limit: int = 0) -> State:
    for _ in range(3):
        answer = model.invoke([generate_prompt] + state["messages"])
        content = answer.content
        if char_limit <= 0 or len(content) >= char_limit * 0.9:
            return {"messages": [answer]}
    return {"messages": [answer]}

def reflect(state: State, reflection_prompt: SystemMessage) -> State:
    answer = model.invoke([reflection_prompt] + state["messages"])
    return {"messages": [HumanMessage(content=answer.content)]}

def pretty_print(text: str) -> str:
    sentences = re.split(r'(?<=[\.。!！\?？])\s+', text.strip())
    return "\n\n".join(sentences)

def load_ideal_from_db(company, language):
    try:
        df = pd.read_sql("SELECT 회사, 인재상_키워드, 요약, language FROM ideal_table", engine)
        filtered = df[(df['회사'].astype(str).str.contains(company, case=False, na=False)) & (df['language'] == language)]
        if not filtered.empty:
            return filtered.iloc[0]['인재상_키워드'], filtered.iloc[0]['요약']
    except Exception:
        pass
    return None, None

def load_resume_from_db(company, job):
    try:
        df = pd.read_sql("SELECT company, position, q, a, advice FROM merged_resume", engine)
        filtered = df[(df['company'].str.strip() == company) & (df['position'].str.contains(job, case=False, na=False))]
        return filtered
    except Exception:
        return pd.DataFrame()

def company_ideal_talent_api(model: ChatOpenAI, company_name: str, lang: str = 'ko') -> dict:
    if lang == 'ko':
        query = (f"'{company_name}' 회사의 인재상과 핵심 가치·문화를 JSON 형식으로 세 항목으로 요약해 주세요. "
                 "출력 예시: "
                 "{\"회사명\": \"삼성전자\", \"인재상_키워드\": [\"도전\", \"창의\", \"협력\"], \"요약\": \"혁신을 주도하는 인재\"}")
    elif lang == 'en':
        query = (f"Please summarize the ideal talent and core values of '{company_name}' company in JSON format with three items. "
                 "Example format: "
                 "{\"CompanyName\": \"Samsung Electronics\", \"KeyQualities\": [\"Challenge\", \"Creativity\", \"Collaboration\"], \"Summary\": \"Talent leading innovation\"}")
    else:
        query = f"Please provide the ideal talent description of '{company_name}' in {lang} in JSON format."
    response = model.invoke([HumanMessage(content=query)]).content
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return {
            "회사명" if lang == 'ko' else "CompanyName": company_name,
            "인재상_키워드" if lang == 'ko' else "KeyQualities": ["자동추출"],
            "요약" if lang == 'ko' else "Summary": response.strip()
        }

def upsert_ideal_to_db(engine, company_name, keywords, summary, language='ko'):
    insert_query = text("""
        INSERT INTO ideal_table (회사, 인재상_키워드, 요약, language)
        VALUES (:company, :keyword, :summary, :language)
        ON CONFLICT (회사, language) DO UPDATE
        SET 인재상_키워드 = EXCLUDED.인재상_키워드,
            요약 = EXCLUDED.요약
    """)
    with engine.connect() as conn:
        conn.execute(insert_query, {
            'company': company_name,
            'keyword': ",".join(keywords) if isinstance(keywords, list) else str(keywords),
            'summary': summary,
            'language': language
        })
        conn.commit()

# --- Streamlit UI ---

st.title("취업하 JOB")

option = st.sidebar.radio("기능 선택", ["공고 검색", "자기소개서 작성"])

if option == "공고 검색":

    st.header("🔍 역할별 빠른 채용 검색")

    user_text = st.text_area("스펙 입력 (예: '서울 거주 신입, 4년제 졸, 파이썬 가능')")

    if st.button("검색 실행"):

        async def run_cli_side(text):
            spec = await parse_spec(text)
            applied = await map_filters(spec)
            expanded_roles = applied.get("expanded_roles") or []
            results = {}
            if expanded_roles:
                results = await crawl_by_roles_multi(expanded_roles, per_role=2)
            return applied, results

        applied, grouped = asyncio.run(run_cli_side(user_text))

        st.write("## 검색 결과")

        for role_kw in (applied.get("expanded_roles") or []):

            docs = grouped.get(role_kw, [])

            st.subheader(f"▶ {role_kw}")

            if not docs:
                st.write("- (결과 없음)")
            else:
                for d in docs:
                    st.markdown(f"**{d.title if d.title else '(제목 없음)'}**")
                    st.write(f"🔗 [링크]({d.url})")
                    st.markdown("---")

elif option == "자기소개서 작성":

    st.header("✍️ 자기소개서 작성 & 첨삭")

    company = st.text_input("지원 회사명")
    job = st.text_input("지원 직무")
    spec = st.text_area("본인 스펙 및 경험 입력")
    language = st.selectbox("언어 선택", ["ko", "en"])
    char_limit = st.number_input("최대 글자 수 (0은 제한 없음)", min_value=0, step=10, value=0)
    use_example = st.checkbox("내부 DB 자소서 예시 참고 사용")

    if company and job and spec:
        # 인재상 조회
        keyword, summary = load_ideal_from_db(company, language)
        if keyword and summary:
            company_culture = f"인재상 키워드: {keyword}\n요약: {summary}"
            st.success(f"내부 DB 인재상 정보 조회됨:\n{company_culture}")
        else:
            api_result = company_ideal_talent_api(model, company, lang=language)
            if language == 'ko':
                keywords = api_result.get("인재상_키워드", [])
                summary_text = api_result.get("요약", "")
            else:
                keywords = api_result.get("KeyQualities", [])
                summary_text = api_result.get("Summary", "")
            company_culture = f"인재상 키워드: {', '.join(keywords)}\n요약: {summary_text}"
            st.info("API로 인재상 정보를 조회했습니다.")
            st.write(company_culture)
            try:
                upsert_ideal_to_db(engine, company, keywords, summary_text, language)
            except Exception as e:
                st.warning(f"DB 저장 오류: {e}")

        # 자소서 예시 조회
        filtered_resume = load_resume_from_db(company, job)

        # 문항 리스트 출력 및 선택 UI
        if use_example and not filtered_resume.empty:
            q_list = filtered_resume['q'].dropna().unique().tolist()
        else:
            q_list = [
                "자기소개 (대인관계, 장단점, 성장과정 등)",
                "지원동기 및 입사 후 포부",
                "본인의 강점 및 역량",
                "위기극복 사례",
                "주도적으로 업무 수행한 경험"
            ] if language == 'ko' else [
                "Introduction and motivation",
                "Key experience and skills",
                "Fit with company and role",
                "Background and strengths",
                "Goals and aspirations"
            ]

        selected_idx = st.selectbox(
            "작성할 자기소개서 문항을 선택하세요",
            options=range(1, len(q_list) + 1),
            format_func=lambda x: f"{x}. {q_list[x-1]}"
        )
        selected_question = q_list[selected_idx - 1]
        st.write(f"선택한 문항: {selected_question}")

        if st.button("자기소개서 생성 및 첨삭"):
            example_resume = None
            if use_example and not filtered_resume.empty and selected_question in filtered_resume['q'].values:
                chosen_row = filtered_resume[filtered_resume['q'] == selected_question].iloc[0]
                example_resume = {
                    "q": selected_question,
                    "a": chosen_row.get('a', ''),
                    "advice": chosen_row.get('advice', ''),
                }
            if example_resume is None:
                example_resume = {"q": selected_question, "a": "", "advice": ""}

            base_prompt, reflection_prompt = get_prompts(language)
            generate_prompt = make_job_prompt(base_prompt, company_culture=company_culture,
                                              example_resume=example_resume, char_limit=char_limit)

            state = {"messages": [HumanMessage(content=f"지원 회사: {company}\n지원 직무: {job}\n스펙 및 경험: {spec}")]}

            builder = StateGraph(State)
            builder.add_node("generate", lambda s: generate(s, generate_prompt, char_limit))
            builder.add_node("reflect", lambda s: reflect(s, reflection_prompt))
            builder.add_edge(START, "generate")
            builder.add_edge("reflect", "generate")

            graph = builder.compile()

            stream_outputs = graph.stream(state)

            final_resume = None
            reflection_content = None

            for stream_item in stream_outputs:
                node, val = list(stream_item.items())[0]
                content = val["messages"][-1].content

                if char_limit > 0 and len(content) > char_limit:
                    st.warning(f"⚠️ 생성된 자기소개서가 {char_limit}자를 초과했습니다.")

                if node == "generate":
                    final_resume = content
                    st.subheader("생성된 자기소개서")
                    st.text_area("자기소개서 내용", pretty_print(final_resume), height=300)
                elif node == "reflect":
                    reflection_content = content
                    st.subheader("첨삭 피드백")
                    st.text_area("피드백 내용", pretty_print(reflection_content), height=200)

                state["messages"].append(val["messages"][-1])

    else:
        st.info("지원 회사명, 지원 직무, 본인 스펙을 모두 입력해주세요.")
