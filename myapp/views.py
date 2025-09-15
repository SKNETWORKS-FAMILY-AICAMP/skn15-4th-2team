import json
import re
import asyncio
from typing import Annotated, TypedDict
import pandas as pd
from sqlalchemy import create_engine, text
from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseServerError
from django.views.decorators.csrf import csrf_exempt
import traceback


# LangChain 및 LLM 관련 임포트
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages

# main.py에서 가져온 외부 의존 모듈
# 실제 프로젝트 구조에 맞게 임포트 경로를 수정해야 합니다.
from jobkorea_cli.models import Spec
from jobkorea_cli.llm import parse_spec, map_filters
from jobkorea_cli.cli import crawl_by_roles_multi

# -------- 모델 및 DB 연결 -----------
# 이 부분은 서버가 시작될 때 한 번만 연결되도록 전역 변수로 설정하는 것이 좋습니다.
try:
    model = ChatOpenAI(model="gpt-5-2025-08-07")
    DB_CONNECTION_URL = 'postgresql+psycopg2://play:123@192.168.0.30:5432/team2'
    engine = create_engine(DB_CONNECTION_URL)
except Exception as e:
    print(f"DB or LLM connection failed: {e}")
    engine = None

# -------- 상태 타입 및 기본 프롬프트 -----------
# 이 부분은 main.py에서 그대로 가져옵니다.
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
    
    if not engine: return None, None
    try:
        with engine.connect() as conn:
            df = pd.read_sql("SELECT 회사, 인재상_키워드, 요약, language FROM ideal_table", conn)
            filtered = df[(df['회사'].astype(str).str.contains(company, case=False, na=False)) & (df['language'] == language)]
            if not filtered.empty:
                return filtered.iloc[0]['인재상_키워드'], filtered.iloc[0]['요약']
    except Exception:
        pass
    return None, None

def load_resume_from_db(company, job):
    if not engine: return pd.DataFrame()
    try:
        with engine.connect() as conn:
            df = pd.read_sql("SELECT company, position, q, a, advice FROM merged_resume", conn)
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
    if not engine: return
    try:
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
    except Exception as e:
        print(f"DB upsert error: {e}")

# --- Django 뷰 함수 ---

def index(request):
    return render(request, 'index.html')

@csrf_exempt
def search_jobs(request):
    # 기존 search_jobs 뷰 함수 (이전 답변에서 제공)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_spec = data.get('spec')
            if not user_spec:
                return HttpResponseBadRequest(json.dumps({'error': 'Spec text is required.'}), content_type="application/json")
            
            async def run_cli_side(text):
                spec = await parse_spec(text)
                applied = await map_filters(spec)
                expanded_roles = applied.get("expanded_roles") or []
                results = {}
                if expanded_roles:
                    results = await crawl_by_roles_multi(expanded_roles, per_role=2)
                return results
            
            results = asyncio.run(run_cli_side(user_spec))
            
            serializable_results = {}
            for role, docs in results.items():
                serializable_results[role] = [{'title': d.title, 'url': d.url} for d in docs]
            
            return JsonResponse(serializable_results)
        except json.JSONDecodeError:
            return HttpResponseBadRequest(json.dumps({'error': 'Invalid JSON.'}), content_type="application/json")
        except Exception as e:
            return HttpResponseServerError(json.dumps({'error': str(e)}), content_type="application/json")
    return HttpResponseBadRequest(json.dumps({'error': 'Only POST method is allowed.'}), content_type="application/json")

# --- 새로운 뷰 함수: 회사 정보 및 자소서 문항 로드 ---
@csrf_exempt
def get_company_info(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            company = data.get('company')
            job = data.get('job')
            language = data.get('language')
            use_example = data.get('use_example')

            if not all([company, job, language]):
                return JsonResponse({'error': 'Missing required fields.'}, status=400)

            company_culture_info = ""
            keyword, summary = load_ideal_from_db(company, language)
            
            if keyword and summary:
                company_culture_info = f"내부 DB 인재상 정보 조회됨:\n인재상 키워드: {keyword}\n요약: {summary}"
            else:
                api_result = company_ideal_talent_api(model, company, lang=language)
                if language == 'ko':
                    keywords = api_result.get("인재상_키워드", [])
                    summary_text = api_result.get("요약", "")
                else:
                    keywords = api_result.get("KeyQualities", [])
                    summary_text = api_result.get("Summary", "")
                
                company_culture_info = f"API로 인재상 정보를 조회했습니다.\n인재상 키워드: {', '.join(keywords)}\n요약: {summary_text}"
                upsert_ideal_to_db(engine, company, keywords, summary_text, language)

            q_list = []
            if use_example:
                filtered_resume = load_resume_from_db(company, job)
                if not filtered_resume.empty:
                    q_list = filtered_resume['q'].dropna().unique().tolist()
            
            if not q_list:
                q_list = [
                    "자기소개 (대인관계, 장단점, 성장과정 등)", "지원동기 및 입사 후 포부",
                    "본인의 강점 및 역량", "위기극복 사례", "주도적으로 업무 수행한 경험"
                ] if language == 'ko' else [
                    "Introduction and motivation", "Key experience and skills",
                    "Fit with company and role", "Background and strengths",
                    "Goals and aspirations"
                ]
            
            return JsonResponse({
                'company_culture': company_culture_info,
                'questions': q_list
            })
        except Exception as e:
            tb = traceback.format_exc()
            print("오류 발생!\n", tb)
            return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)
    return JsonResponse({'error': 'Invalid request method.'}, status=405)

# --- 새로운 뷰 함수: 자기소개서 생성 및 첨삭 ---
@csrf_exempt
def generate_resume(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            print("data : " ,data)
            company = data.get('company')
            job = data.get('job')
            spec = data.get('spec')
            language = data.get('language')
            char_limit = int(data.get('char_limit', 0))
            use_example = data.get('use_example')
            selected_question = data.get('question')

            #if not all([company, job, spec, language, selected_question]):
            #    print("333333")
            #    return JsonResponse({'error': 'Missing required fields.'}, status=400)

            # 인재상 및 자소서 예시 데이터 준비
            company_culture_info = ""
            keyword, summary = load_ideal_from_db(company, language)
            if keyword and summary:
                company_culture_info = f"인재상 키워드: {keyword}\n요약: {summary}"

            example_resume = None
            if use_example:
                filtered_resume = load_resume_from_db(company, job)
                if not filtered_resume.empty and selected_question in filtered_resume['q'].values:
                    chosen_row = filtered_resume[filtered_resume['q'] == selected_question].iloc[0]
                    example_resume = {
                        "q": selected_question,
                        "a": chosen_row.get('a', ''),
                        "advice": chosen_row.get('advice', ''),
                    }

            if example_resume is None:
                example_resume = {"q": selected_question, "a": "", "advice": ""}

            # LLM 프롬프트 및 그래프 실행
            base_prompt, reflection_prompt = get_prompts(language)
            generate_prompt = make_job_prompt(
                base_prompt,
                company_culture=company_culture_info,
                example_resume=example_resume,
                char_limit=char_limit
            )
            state = {"messages": [HumanMessage(content=f"지원 회사: {company}\n지원 직무: {job}\n스펙 및 경험: {spec}\n자소서 문항: {selected_question}")]}
            
            builder = StateGraph(State)
            builder.add_node("generate", lambda s: generate(s, generate_prompt, char_limit))
            builder.add_node("reflect", lambda s: reflect(s, reflection_prompt))
            builder.add_edge(START, "generate")
            builder.add_edge("reflect", "generate")
            graph = builder.compile()

            final_resume = ""
            reflection_content = ""

            for stream_item in graph.stream(state):
                node, val = list(stream_item.items())[0]
                content = val["messages"][-1].content
                if node == "generate":
                    final_resume = pretty_print(content)
                elif node == "reflect":
                    reflection_content = pretty_print(content)
            
            return JsonResponse({
                'final_resume': final_resume,
                'reflection_content': reflection_content
            })
        except Exception as e:
            return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)
    return JsonResponse({'error': 'Invalid request method.'}, status=405)