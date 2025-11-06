import os
import json
import re
from openai import OpenAI
import streamlit as st 
from dotenv import load_dotenv

# --- 1. 환경 설정 및 API 클라이언트 ---

API_KEY = None
client = None

# Streamlit Cloud 배포와 로컬 실행을 모두 지원하는 키 로딩 로직
try:
    if "OPENAI_API_KEY" in st.secrets:
        API_KEY = st.secrets["OPENAI_API_KEY"]
except Exception:
    pass

if not API_KEY:
    load_dotenv()
    API_KEY = os.getenv("OPENAI_API_KEY")

if API_KEY:
    client = OpenAI(api_key=API_KEY)


# --- 2. 퀴즈 생성 함수 ---

# 💡 cache_version 인자를 추가하여 app.py의 호출과 일치시킵니다.
@st.cache_data(ttl="1d")
def generate_reflection_quiz(quiz_id: str, cache_version: int = 1):
    """
    OpenAI GPT-4o-mini를 사용하여 청소년 대상 자아 발견 퀴즈 질문을 생성합니다.
    """
    
    if not client:
        raise Exception("API 클라이언트가 초기화되지 않았습니다. API 키 설정을 확인해주세요.")

    # --- 시스템 프롬프트 강화: JSON 출력 및 청소년 지침 ---
    system_prompt = (
        "당신은 중고등학생을 위한 성격 유형 테스트(MBTI 스타일) 질문을 생성하는 전문가입니다. "
        "질문은 반드시 한국어로, 청소년의 일상(학교, 친구, 숙제, 취미, 정서)에 밀접해야 하며, "
        "성인 직장인과 관련된 주제(업무, 회사, 경력)는 엄격히 제외해야 합니다. "
        "**절대로 술, 담배, 폭력, 성적인 내용, 비방, 욕설 등 청소년에게 부적절한 단어나 주제를 포함해서는 안 됩니다.** "
        "응답은 반드시 5개의 JSON 배열로만 응답해야 합니다. 다른 텍스트는 절대 포함하지 마세요."
    )
    
    user_query = "현재의 심리 상태와 자기 이해를 돕기 위한 5가지 문항의 퀴즈를 생성해주세요. 각 문항은 A와 B 중 하나를 선택하는 형식이어야 합니다. JSON 형식은 다음과 같습니다: [{'id': 1, 'question': '...', 'choiceA': '...', 'choiceB': '...'}, ...]"

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            temperature=0.7,
            max_tokens=500,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content.strip()
        
        # AI 응답 텍스트에서 유효한 JSON 배열 [..]을 추출
        match = re.search(r'\[.*\]', content, re.S)
        if not match:
            # 유효한 JSON 배열이 없는 경우 응답 전체를 JSON으로 파싱 시도
            try:
                parsed_json = json.loads(content)
            except json.JSONDecodeError:
                raise ValueError(f"AI 응답에서 유효한 JSON 배열을 찾을 수 없습니다: {content}")
        else:
            parsed_json = json.loads(match.group())

        # 최종 반환 데이터 검증
        if isinstance(parsed_json, list) and all(isinstance(item, dict) for item in parsed_json):
            return parsed_json
        else:
            raise ValueError("AI가 올바른 JSON 배열 형식(list of dicts)을 반환하지 않았습니다.")
        
    except Exception as e:
        # st.error 대신 Exception을 발생시켜 app.py에서 처리하도록 위임
        raise Exception(f"AI 질문 생성 중 오류 발생: {e}")
