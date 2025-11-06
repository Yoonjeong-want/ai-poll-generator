import os
import json
import re
import time # time.sleep을 위해 추가
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
    # 로컬 테스트를 위해 os.getenv를 사용합니다.
    API_KEY = os.getenv("OPENAI_API_KEY")

if API_KEY:
    # API 키가 있을 경우에만 클라이언트를 초기화합니다.
    client = OpenAI(api_key=API_KEY)


# --- 2. 퀴즈 생성 함수 ---

# 💡 cache_version 인자를 추가하여 app.py의 호출과 일치시킵니다.
@st.cache_data(ttl="1d")
def generate_reflection_quiz(quiz_id: str, cache_version: int = 1):
    """
    OpenAI GPT-4o-mini를 사용하여 청소년 대상 자아 발견 퀴즈 질문을 생성합니다.
    JSON 파싱 오류를 방지하기 위해 재시도 및 안정적인 파싱 로직을 사용합니다.
    """
    
    if not client:
        raise Exception("API 클라이언트가 초기화되지 않았습니다. API 키 설정을 확인해주세요.")

    # --- 시스템 프롬프트 강화: JSON 출력 및 청소년 지침 ---
    system_prompt = (
        "당신은 중고등학생을 위한 성격 유형 테스트(MBTI 스타일) 질문을 생성하는 전문가입니다. "
        "질문은 반드시 한국어로, 청소년의 일상(학교, 친구, 숙제, 취미, 정서)에 밀접해야 하며, "
        "성인 직장인과 관련된 주제(업무, 회사, 경력)는 엄격히 제외해야 합니다. "
        "**절대로 술, 담배, 폭력, 성적인 내용, 비방, 욕설 등 청소년에게 부적절한 단어나 주제를 포함해서는 안 됩니다.** "
        "응답은 반드시 5개의 JSON 배열로만 응답해야 합니다. 배열을 감싸는 다른 텍스트나 루트 객체는 절대 포함하지 마세요."
    )
    
    user_query = "현재의 심리 상태와 자기 이해를 돕기 위한 5가지 문항의 퀴즈를 생성해주세요. 각 문항은 A와 B 중 하나를 선택하는 형식이어야 합니다. JSON 형식은 다음과 같습니다: [{'id': 1, 'question': '...', 'choiceA': '...', 'choiceB': '...'}, ...]"

    # 재시도 로직을 함수 내부에 구현하여 API 호출의 안정성을 높입니다.
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query}
                ],
                temperature=0.7,
                max_tokens=500,
                # 'json_object' 타입은 모델이 루트 객체를 선호하게 만드나, 배열만 요구하는 프롬프트와 함께 사용됩니다.
                response_format={"type": "json_object"} 
            )
            
            # NoneType 오류 방지를 위해 content에 안전 장치를 추가합니다.
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("AI 응답 내용이 비어 있습니다 (None).")

            content = content.strip()
            
            # --- 개선된 JSON 파싱 로직 ---
            parsed_json = None
            
            # 1. JSON 배열 [...]을 직접 추출 시도 (가장 선호되는 형식)
            match = re.search(r'\[.*\]', content, re.S)
            if match:
                try:
                    parsed_json = json.loads(match.group())
                except json.JSONDecodeError:
                    pass # 배열 추출 실패, 다음 단계로 넘어감
            
            # 2. 전체 응답을 JSON 객체로 파싱 시도 (모델이 배열을 루트 객체로 감싸는 경우 대비)
            if parsed_json is None:
                try:
                    full_json = json.loads(content)
                    
                    # 응답이 배열이 아니고 객체일 경우, 값 중에서 배열을 찾습니다.
                    if isinstance(full_json, dict):
                        for key, value in full_json.items():
                            if isinstance(value, list) and len(value) >= 1 and all(isinstance(item, dict) for item in value):
                                parsed_json = value
                                print(f"경고: 모델이 JSON을 루트 객체로 감싸서 응답했습니다. 키: {key}의 배열을 추출했습니다.")
                                break
                        
                    # 만약 전체 응답 자체가 배열이라면 (프롬프트 요청대로)
                    elif isinstance(full_json, list):
                        parsed_json = full_json
                        
                except json.JSONDecodeError:
                    pass # 전체 파싱 실패, 최종 에러 발생

            # 3. 최종 반환 데이터 검증
            if parsed_json and isinstance(parsed_json, list) and len(parsed_json) == 5 and all(isinstance(item, dict) for item in parsed_json):
                return parsed_json # 성공!
            else:
                # 퀴즈 문항 수(5개)나 형식이 일치하지 않으면 재시도
                # 최종 응답 내용도 함께 포함하여 디버깅을 돕습니다.
                error_detail = f"최종 응답 형식 불일치. 반환된 내용: {content[:100]}..."
                raise ValueError(error_detail)
        
        except Exception as e:
            # 마지막 시도가 아니면 재시도
            if attempt < max_retries - 1:
                # 재시도 전에 대기 시간을 둡니다 (2^attempt 초).
                time.sleep(2 ** attempt) 
                # print(f"퀴즈 생성 실패 ({e}). {2 ** attempt}초 후 재시도합니다...") # 스트림릿 환경에서는 print 대신 로깅을 사용해야 하지만, 디버깅을 위해 남겨둡니다.
                continue
            else:
                # st.error 대신 Exception을 발생시켜 app.py에서 처리하도록 위임
                raise Exception(f"AI 질문 생성 중 알 수 없는 오류 발생: 최대 재시도 횟수 초과. 최종 오류: {e}")

    # 모든 재시도 실패 후에도 도달할 경우를 대비
    raise Exception("최대 재시도 횟수를 초과했습니다. AI 질문 생성에 최종 실패했습니다.")
