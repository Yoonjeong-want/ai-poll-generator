import os
import json
import random
import re
from openai import OpenAI
import streamlit as st 
from dotenv import load_dotenv

# --- 1. 환경 설정 및 API 클라이언트 ---

# Streamlit Cloud 배포와 로컬 실행을 모두 지원하는 키 로딩 로직
API_KEY = None
client = None

# 1. Streamlit Cloud 환경에서 키를 찾으려고 시도
try:
    # st.secrets가 초기화되어 있고 키가 있다면 사용
    if "OPENAI_API_KEY" in st.secrets:
        API_KEY = st.secrets["OPENAI_API_KEY"]
except Exception:
    # 로컬에서 secrets.toml 파일이 없으면 예외 발생 -> 다음 단계로 넘어감
    pass

# 2. API_KEY가 설정되지 않았으면 로컬 .env 파일에서 로드 시도
if not API_KEY:
    load_dotenv()
    API_KEY = os.getenv("OPENAI_API_KEY")

# 3. 키가 확보되었으면 OpenAI 클라이언트 초기화
if API_KEY:
    client = OpenAI(api_key=API_KEY)


# 테스트를 위한 임시 사용자 목록
SAMPLE_USERS = [
    "김민준", "이서윤", "박도현", "정하윤", "최지우",
    "강서준", "문예준", "한지아", "오시후", "신수아",
    "장서연", "황지훈", "고은채", "유승민", "송나영"
]


# --- 2. 투표 질문 생성 함수 ---

# 함수 시작 부분에서 클라이언트가 초기화되었는지 확인하는 로직 추가
def generate_poll_question(topic: str, num_questions: int):
    """
    OpenAI GPT-4o-mini를 사용하여 특정 주제에 맞는 투표 질문 구문을 생성하고,
    SAMPLE_USERS에서 4명을 랜덤으로 뽑아 보기로 구성합니다.
    """
    
    # 클라이언트가 없으면 바로 오류를 반환하여 Streamlit UI에 표시
    if not client:
        raise Exception("API 클라이언트가 초기화되지 않았습니다. API 키 설정을 확인해주세요.")
        
    system_prompt = "당신은 만13세 ~ 만18세 사용자들의 흥미와 관계를 증진시키는 투표 질문을 생성하는 전문가입니다. 한국어로 응답해야 하며, 결과는 반드시 제공된 JSON 스키마를 따라야 합니다."
    user_query = f"""
    주제 '{topic}'에 맞춰 재미있고 친목을 위한 캐주얼한 투표 질문 {num_questions}개를 
    '~한 사람?', '~하지 않은 사람?', 또는 '~할 것 같은 사람?' 형식의 구문으로만 만들어주세요. 
    예를 들어 주제가 '점심 메뉴'라면 '오늘의 급식메뉴 항상 알고 있을 것 같은 사람?'처럼 구체적이어야 합니다.
    
    Output must be JSON with keys:
    [
        {{
            "poll_phrase": "..."
        }}
    ]
    Return ONLY valid JSON array, nothing else.
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            temperature=0.8,
            max_tokens=500,
        )
        
        content = response.choices[0].message.content.strip()
        
        match = re.search(r'\[.*\]', content, re.S)
        if not match:
            raise ValueError(f"AI 응답에서 유효한 JSON을 찾을 수 없습니다: {content}")
        
        question_phrases = json.loads(match.group())

    except Exception as e:
        print(f"OpenAI API 호출 또는 JSON 처리 중 오류 발생: {e}")
        return []

    
    polls = []
    
    for item in question_phrases:
        phrase = item.get('poll_phrase', f'주제 [{topic}]에 대해 투표할 사람?')
        
        if len(SAMPLE_USERS) < 4:
            raise Exception("투표에 필요한 최소 4명의 유저가 없습니다.")
            
        random_choices = random.sample(SAMPLE_USERS, 4)
        
        polls.append({
            "question_phrase": phrase,
            "choices": random_choices,
            "ideal_answer": "투표 결과에 따라 다름", 
        })
        
    return polls
