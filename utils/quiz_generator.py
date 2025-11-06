import os
import json
import re
import time
from openai import OpenAI, APIError
import streamlit as st
from dotenv import load_dotenv
from typing import List, Dict, Any

# 사용자 정의 예외 클래스
class QuizGenerationError(Exception):
    """퀴즈 생성 또는 처리 중 발생하는 사용자 정의 예외."""
    pass

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
    # 클라이언트는 스크립트 실행 시 한 번만 초기화
    client = OpenAI(api_key=API_KEY)


# --- 2. 퀴즈 생성 함수 (재시도 및 오류 방지 로직 추가) ---

@st.cache_data(ttl="1d")
def generate_reflection_quiz(quiz_id: str, cache_version: int = 2) -> List[Dict[str, Any]]:
    """
    OpenAI GPT-4o-mini를 사용하여 청소년 대상 자아 발견 퀴즈 질문을 생성합니다.
    NoneType 오류를 방지하고 API 호출 실패 시 재시도합니다.
    """
    
    if not client:
        # API 키가 없어 클라이언트 초기화에 실패한 경우
        raise QuizGenerationError("API 클라이언트가 초기화되지 않았습니다. OpenAI API 키 설정을 확인해주세요.")
    
    MAX_RETRIES = 3 # 최대 재시도 횟수

    # --- 시스템 프롬프트 강화: JSON 출력 및 청소년 지침 ---
    system_prompt = (
        "당신은 중고등학생을 위한 성격 유형 테스트(MBTI 스타일) 질문을 생성하는 전문가입니다. "
        "질문은 반드시 한국어로, 청소년의 일상(학교, 친구, 숙제, 취미, 정서)에 밀접해야 하며, "
        "성인 직장인과 관련된 주제(업무, 회사, 경력)는 엄격히 제외해야 합니다. "
        "절대로 술, 담배, 폭력, 성적인 내용, 비방, 욕설 등 청소년에게 부적절한 단어나 주제를 포함해서는 안 됩니다. "
        "응답은 반드시 5개의 객체로 구성된 JSON 배열로만 응답해야 합니다. 다른 텍스트는 절대 포함하지 마세요."
    )
    
    # AI가 정확히 JSON 배열을 출력하도록 프롬프트에 배열 형태를 명시합니다.
    user_query = "현재의 심리 상태와 자기 이해를 돕기 위한 5가지 문항의 퀴즈를 생성해주세요. "                  "각 문항은 A와 B 중 하나를 선택하는 형식이어야 합니다. "                  "JSON 형식은 다음과 같습니다: [{\"id\": 1, \"question\": \"...\", \"choiceA\": \"...\", \"choiceB\": \"...\"}, ...]"

    for i in range(MAX_RETRIES):
        try:
            # 1. API 호출
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query}
                ],
                temperature=0.7,
                max_tokens=500,
                # JSON 객체 출력을 강제
                response_format={"type": "json_object"} 
            )
            
            # 2. NoneType 오류 방지 및 콘텐츠 추출 (핵심 수정)
            # response.choices[0].message.content가 None일 수 있으므로 이를 먼저 검사합니다.
            content = response.choices[0].message.content 
            
            if content is None or not content.strip():
                # 빈 응답을 받은 경우, 재시도하거나 오류 발생
                raise QuizGenerationError("AI 모델이 빈 텍스트 응답을 반환했습니다. (NoneType 방지)")

            content = content.strip()
            
            # 3. JSON 파싱 및 유효성 검사 (JSON_OBJECT 형식 때문에 정규식은 제거합니다.)
            try:
                # response_format 덕분에 전체 응답이 JSON 객체일 가능성이 높음
                parsed_json = json.loads(content)
            except json.JSONDecodeError:
                # 혹시라도 JSON 파싱이 실패하면 오류 발생
                raise QuizGenerationError(f"AI 응답이 유효한 JSON 형식이 아닙니다. 응답 텍스트: {content[:100]}...")

            # 4. 최종 데이터 검증
            if isinstance(parsed_json, list) and len(parsed_json) == 5 and all(isinstance(item, dict) for item in parsed_json):
                return parsed_json
            else:
                raise QuizGenerationError("AI가 5개의 문항을 포함하는 올바른 JSON 배열 형식(list of dicts)을 반환하지 않았습니다.")

        except QuizGenerationError as e:
            # 우리가 정의한 논리적 오류 (빈 응답, 잘못된 형식)
            error_message = str(e)
        except APIError as e:
            # OpenAI 서버나 인증 관련 오류
            error_message = f"OpenAI API 오류 발생: {e}"
        except Exception as e:
            # 기타 예상치 못한 오류 (네트워크 등)
            error_message = f"예상치 못한 오류: {e}"

        # --- 재시도 및 백오프 ---
        if i == MAX_RETRIES - 1:
            # 최종 시도 실패
            raise QuizGenerationError(f"최대 재시도 횟수 초과. 최종 오류: {error_message}")
        
        # 지수 백오프: 1초, 2초, 4초 대기
        wait_time = 2 ** i
        st.warning(f"퀴즈 생성 실패 ({error_message}). {wait_time}초 후 재시도합니다...")
        time.sleep(wait_time) 

    # 여기까지 도달하면 퀴즈 생성에 실패한 것으로 간주
    raise QuizGenerationError("퀴즈 생성 기능이 작동하지 않습니다.")
