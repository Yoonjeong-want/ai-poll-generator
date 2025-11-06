import streamlit as st
from utils.question_generator import generate_poll_question
from utils.quiz_generator import generate_reflection_quiz
import time
import datetime
import requests
import json 
import pandas as pd
import altair as alt

# --- Firebase Imports ---
from firebase_admin import firestore, initialize_app
from google.cloud.firestore import Client
from google.auth.exceptions import DefaultCredentialsError

# --- Firestore SDK를 사용하기 위한 초기화 및 인증 ---
def setup_firestore():
    """Firestore 클라이언트 초기화 및 반환"""
    if 'db' not in st.session_state:
        try:
            # 1. Firebase Config 및 App ID 로드 (캔버스 환경 변수 사용)
            app_id = globals().get('__app_id', 'default-app-id')
            firebase_config_str = globals().get('__firebase_config', '{}')
            firebase_config = json.loads(firebase_config_str)
            project_id = firebase_config.get('projectId')
            
            # 2. Firebase Admin SDK 초기화 시도
            import firebase_admin
            if not firebase_admin._apps:
                if project_id:
                    initialize_app(options={'projectId': project_id})
                else:
                    # 프로젝트 ID가 없을 경우, 기본적으로 ADC를 찾아 초기화 시도
                    initialize_app() 

            # 3. Firestore 클라이언트 생성 (Google Cloud SDK 방식 사용)
            if project_id:
                db = firestore.Client(project=project_id)
            else:
                db = firestore.Client()
                
            st.session_state.db = db
            st.session_state.app_id = app_id
            st.session_state.db_error = None
            
        except Exception as e:
            st.session_state.db = None
            st.session_state.app_id = 'default-app-id'
            st.session_state.db_error = str(e)
            # 데이터베이스 인증 오류 메시지를 세션에 저장
            pass # 실패해도 앱이 멈추지 않도록 처리

# --- 데이터베이스 경로 및 함수 ---
def get_quiz_history_ref(db: Client, app_id: str, user_id: str):
    """사용자의 퀴즈 기록 컬렉션 참조 반환"""
    # Private Data Path: /artifacts/{appId}/users/{userId}/quiz_history
    return db.collection('artifacts').document(app_id).collection('users').document(user_id).collection('quiz_history')

def save_quiz_answers(db: Client, app_id: str, user_id: str, quiz_id: str, answers: dict, quiz_data: list):
    """오늘의 퀴즈 답변을 Firestore에 저장 (DB 연결 실패 시 세션 저장소에 임시 저장)"""
    
    # 1. DB에 저장 시도
    if db is not None:
        try:
            doc_ref = get_quiz_history_ref(db, app_id, user_id).document(quiz_id)
            doc_ref.set({
                'quiz_date': quiz_id,
                'answers': answers,
                'quiz_data': quiz_data,
                'timestamp': int(time.time())
            })
            return True
        except Exception as e:
            st.warning(f"데이터베이스 저장 실패 (임시 저장소 사용): {e}")

    # 2. DB 실패 시 세션 저장소에 임시 저장
    if 'temp_quiz_history' not in st.session_state:
        st.session_state.temp_quiz_history = {}
    
    st.session_state.temp_quiz_history[quiz_id] = {
        'quiz_date': quiz_id,
        'answers': answers,
        'quiz_data': quiz_data,
        'timestamp': int(time.time())
    }
    return False

def load_quiz_history(db: Client, app_id: str, user_id: str):
    """Firestore 또는 세션 저장소에서 모든 퀴즈 기록을 불러옵니다."""
    
    history = []
    
    # 1. Firestore에서 로드 시도
    if db is not None:
        try:
            docs = get_quiz_history_ref(db, app_id, user_id).stream()
            history.extend([doc.to_dict() for doc in docs])
        except Exception as e:
            st.warning(f"Firestore 기록 로드 실패: {e}")

    # 2. 세션 저장소에서 로드 (DB 기록보다 세션 기록이 최신일 수 있음)
    if 'temp_quiz_history' in st.session_state:
        # 세션 저장소의 기록을 추가/업데이트합니다. (중복 방지 및 최신화)
        session_history_map = {item['quiz_date']: item for item in history}
        session_history_map.update(st.session_state.temp_quiz_history)
        history = list(session_history_map.values())
        
    return history

# --- 1. 청소년 유해 단어 목록 및 주제 정의 ---
BANNED_WORDS = [
    "술", "담배", "도박", "섹스", "폭력", "자살", "마약", "일진", "외모",
    "비방", "욕설", "싸움", "성인", "죽음", "혐오", "성", "욕", "비난"
]

PREDEFINED_TOPICS = [
    "-- 주제를 선택하세요 --",
    "학교생활",
    "여행",
    "유머",
    "밈",
    "아이돌",
    "학업",
    "SNS",
    "연애",
    "게임",
    "미래"
]

# --- 2. 페이지 설정 ---
st.set_page_config(
    page_title="AI 유저 투표 & 퀴즈 생성기",
    layout="centered",
    initial_sidebar_state="expanded",
)

st.title("🤝 AI 유저 투표 & 퀴즈 생성기")
st.markdown("맞춤형 셀프 퀴즈와 친목 투표 질문을 만들어 보세요!")
st.markdown("---")

# Firestore 클라이언트 초기화
setup_firestore()

# 사용자 ID (익명 인증을 가정)
# NOTE: 실제 사용자 인증이 필요하다면 __initial_auth_token을 사용해야 하지만,
# Streamlit 환경에서 firestore.Client()만 사용하므로 익명 ID를 사용합니다.
if 'user_id' not in st.session_state:
    st.session_state.user_id = "temp_user_" + str(hash(st.session_state.get('app_id', 'default')))

db_ready = st.session_state.get('db') is not None
db_error = st.session_state.get('db_error')
user_id = st.session_state.user_id
app_id = st.session_state.get('app_id', 'default-app-id')
db = st.session_state.get('db')


# 탭 구조 생성
tab1, tab2 = st.tabs(["👥 투표 질문 생성기", "🌟 오늘의 Quiz"])


# ==============================================================================
# 탭 1: 투표 질문 생성기 
# ==============================================================================
with tab1:
    st.header("1. 투표 질문 설정")
    
    with st.container(border=True):
        
        selected_topic = st.selectbox("1. 주제를 선택하세요:", PREDEFINED_TOPICS)
        custom_topic = st.text_input("2. (선택 사항) 새로운 주제를 직접 입력하세요:", "")
        final_topic = custom_topic.strip() if custom_topic.strip() else selected_topic
        
        num_questions = st.slider(
            "3. 생성할 질문 개수", 
            min_value=1, 
            max_value=5, 
            value=3, 
            step=1
        )
        
        # --- 금지어 검사 로직 ---
        is_banned = False
        found_banned_words = []
        
        if final_topic and final_topic != PREDEFINED_TOPICS[0]:
            topic_lower = final_topic.lower().strip()
            for word in BANNED_WORDS:
                if word in topic_lower:
                    is_banned = True
                    found_banned_words.append(word)
                    
        if is_banned:
            st.error(f"⚠️ **부적절한 주제 경고!** '{', '.join(found_banned_words)}'와(과) 같은 금지어가 포함되어 있습니다. 청소년에게 적합한 주제를 입력해주세요.")
            button_disabled = True
        else:
            button_disabled = False

        is_valid_topic = final_topic.strip() != "" and final_topic != PREDEFINED_TOPICS[0]

        # 버튼
        if st.button("질문 생성하기", disabled=button_disabled or not is_valid_topic, use_container_width=True):
            
            if not is_valid_topic:
                 st.warning("투표 주제를 선택하거나 직접 입력해주세요!")
            else:
                with st.spinner("✨ AI가 재미있는 투표 질문을 생성 중입니다..."):
                    start_time = time.time()
                    try:
                        polls = generate_poll_question(final_topic, num_questions)
                        end_time = time.time()
                    except Exception as e:
                        st.error(f"투표 질문 생성 중 오류 발생: {e}")
                        polls = None
                
                if polls:
                    st.session_state.polls = polls
                    st.session_state.topic = final_topic
                    st.session_state.time_taken = f"{end_time - start_time:.2f}초"
                else:
                     st.error("질문 생성에 실패했거나, AI가 주제가 부적절하다고 판단하여 응답하지 않았습니다. 다른 주제로 시도해주세요.")


    # --- 결과 표시 섹션 ---
    if 'polls' in st.session_state and st.session_state.polls:
        
        st.markdown("---")
        st.header(f"2. 투표 질문 결과 (주제: {st.session_state.topic})")
        
        for i, poll in enumerate(st.session_state.polls):
            with st.expander(f"**❓ {poll['question_phrase']}**", expanded=True):
                st.markdown(f"**투표 문구:** {poll['question_phrase']} (총 {len(poll['choices'])}명)")
                
                cols = st.columns(len(poll['choices']))
                
                # 각 보기별 투표 버튼 생성
                for j, choice in enumerate(poll['choices']):
                    if cols[j].button(f"👤 {choice}", key=f"poll_{i}_choice_{j}", use_container_width=True):
                        # 실제 투표 로직은 구현하지 않고, 버튼 클릭만 표시
                        st.toast(f"'{choice}'에게 투표했습니다!", icon="🗳️")
                        
                st.caption("선택 후에는 다시 투표할 수 없습니다.")


# ==============================================================================
# 탭 2: 오늘의 Quiz 
# ==============================================================================
today_quiz_id = datetime.datetime.now().strftime("%Y-%m-%d")

with tab2:
    st.header("1. 오늘의 Quiz")
    
    # DB 연결 상태 표시
    if db_error:
        st.warning(f"⚠️ **데이터베이스 연결 실패.** {db_error[:50]}... (퀴즈 기록은 현재 세션에만 임시 저장됩니다.)")
    elif not db_ready:
         st.info("💡 **데이터베이스 준비 중...** 퀴즈 기록은 현재 세션에만 임시 저장됩니다.")
    
    # --- 퀴즈 로드 및 생성 ---
    
    # 퀴즈 기록 로드
    quiz_history = load_quiz_history(db, app_id, user_id)
    
    # 오늘 퀴즈 완료 여부 확인
    is_completed_today = any(q['quiz_date'] == today_quiz_id for q in quiz_history)
    
    if is_completed_today:
        st.success("✅ 오늘 퀴즈를 이미 완료했습니다. 결과를 확인하세요!")
        st.session_state.quiz_data = next(q['quiz_data'] for q in quiz_history if q['quiz_date'] == today_quiz_id)
        st.session_state.quiz_answers = next(q['answers'] for q in quiz_history if q['quiz_date'] == today_quiz_id)

    else:
        # 퀴즈 데이터 생성 시도
        try:
            # 퀴즈 데이터 로드 (캐시 무효화를 위해 버전 인자 전달)
            # st.rerun() 때문에 quiz_data가 재호출되면 안 되므로 @st.cache_data를 사용합니다.
            quiz_data = generate_reflection_quiz(quiz_id=today_quiz_id, cache_version=2)
            if quiz_data:
                st.session_state.quiz_data = quiz_data
                st.session_state.quiz_answers = st.session_state.get('quiz_answers', {}) # 답변 초기화
            else:
                st.error("AI 질문 생성에 실패했습니다. 잠시 후 다시 시도해주세요.")
        except Exception as e:
            st.error(f"퀴즈 로드 중 알 수 없는 오류 발생: {e}. AI 질문 생성에 실패했습니다.")
            st.session_state.quiz_data = None
            
        
    # --- 퀴즈 표시 및 답변 처리 ---
    if 'quiz_data' in st.session_state and st.session_state.quiz_data:
        
        quiz_form = st.form(key='quiz_form')
        
        # 퀴즈 질문 표시 및 답변 기록
        for i, item in enumerate(st.session_state.quiz_data):
            # 답변이 이미 기록되어 있다면, 해당 값을 기본값으로 사용
            current_answer = st.session_state.quiz_answers.get(str(item['id']), None)
            
            # 라디오 버튼으로 질문 표시
            # key를 'quiz_answer_{item["id"]}'로 설정하여 고유성 확보
            choice = quiz_form.radio(
                f"**{item['id']}. {item['question']}**",
                (item['choiceA'], item['choiceB']),
                key=f"quiz_answer_{item['id']}",
                index=(0 if current_answer == item['choiceA'] else 1 if current_answer == item['choiceB'] else None),
                disabled=is_completed_today
            )
            
            # 답변 기록 (폼 제출 전에 미리 세션 상태에 저장)
            st.session_state.quiz_answers[str(item['id'])] = choice
            
            quiz_form.markdown("---") # 질문 간 구분선

        # 폼 제출 버튼
        submit_button = quiz_form.form_submit_button(
            "오늘의 퀴즈 제출하기", 
            disabled=is_completed_today, 
            use_container_width=True
        )

        if submit_button and not is_completed_today:
            # 제출 시 모든 질문에 답변했는지 확인
            if len(st.session_state.quiz_answers) == len(st.session_state.quiz_data):
                
                # 답변 저장 (DB 또는 임시 세션)
                save_quiz_answers(
                    db, app_id, user_id, today_quiz_id, 
                    st.session_state.quiz_answers, st.session_state.quiz_data
                )
                st.session_state.quiz_completed = True
                st.success("🎉 답변이 제출되었습니다! 결과를 확인하세요.")
                st.rerun() # 새로고침하여 완료 상태로 전환 (st.experimental_rerun()에서 수정됨)
            else:
                st.warning("모든 질문에 답변해주세요!")

    # ==============================================================================
    # 2. 나의 퀴즈 분석
    # ==============================================================================
    
    st.markdown("---")
    st.header("2. 나의 퀴즈 분석")
    
    # 퀴즈 기록이 있는 경우에만 분석을 실행합니다.
    if quiz_history:
        
        # --- 전체 답변 취합 및 성향 분석 ---
        total_a = 0
        total_b = 0
        
        # 모든 답변 기록을 순회하며 A/B 개수 집계
        for record in quiz_history:
            for answer in record['answers'].values():
                # A/B 선택지 구분을 위해 임시로 첫 번째 질문의 선택지를 기준으로 판단
                # (실제 MBTI처럼 A/B가 일관된 성향을 나타낸다고 가정)
                first_question = record['quiz_data'][0]
                
                if answer == first_question['choiceA']:
                    total_a += 1
                elif answer == first_question['choiceB']:
                    total_b += 1
        
        total_selections = total_a + total_b
        
        if total_selections == 0:
            st.info("아직 퀴즈 기록이 없습니다. 오늘 퀴즈를 풀고 결과를 확인하세요!")
        else:
            # --- 분석 결과 시각화 (Altair 사용) ---
            
            # 데이터프레임 생성 (Pandas DataFrame)
            chart_data = pd.DataFrame({
                '성향': ['A 성향 (내향/사고 등)', 'B 성향 (외향/감정 등)'],
                '선택 횟수': [total_a, total_b]
            })

            # Altair 차트 정의
            base = alt.Chart(chart_data).encode(
                y=alt.Y('선택 횟수', title='누적 선택 횟수'), # Y 축
                tooltip=['성향', '선택 횟수'] # 마우스 오버 시 표시
            ).properties(
                title='누적 퀴즈 답변 성향 분석'
            )

            # 막대 차트 레이어
            bars = base.mark_bar().encode(
                x=alt.X('성향', title='성향'), # X 축
                color=alt.Color('성향', 
                                scale=alt.Scale(domain=['A 성향 (내향/사고 등)', 'B 성향 (외향/감정 등)'],
                                                range=['#FF5733', '#337AFF']),
                                legend=None) # 색상 인코딩을 성향별로 명확하게 지정
            )
            
            # 텍스트 레이어 (값 표시)
            text = base.mark_text(
                align='center',
                baseline='bottom',
                dy=-5  # 막대 위로 약간 띄우기
            ).encode(
                x=alt.X('성향'),
                text=alt.Text('선택 횟수'),
                color=alt.value('black') # 텍스트 색상
            )

            # 차트 결합 및 표시
            st.altair_chart(bars + text, use_container_width=True)

            # --- 해석 및 추가 분석 ---
            st.markdown("---")
            st.subheader("📊 나의 성향 요약")
            
            primary_trait = ""
            secondary_trait = ""
            ratio = ""
            
            if total_a > total_b:
                primary_trait = "A 성향"
                secondary_trait = "B 성향"
                ratio = f"{total_a / total_selections * 100:.1f}%"
            elif total_b > total_a:
                primary_trait = "B 성향"
                secondary_trait = "A 성향"
                ratio = f"{total_b / total_selections * 100:.1f}%"
            
            
            if total_a != total_b:
                st.markdown(f"**결론:** 사용자님은 총 **{total_selections}**번의 답변 중 **{primary_trait}**을 **{ratio}** 비율로 선택했습니다. 이는 전반적으로 **{primary_trait.split(' ')[0]}** 쪽의 성향이 강함을 보여줍니다.")
                st.caption(f"({primary_trait.split('(')[-1].replace(')', '')})")
            else:
                 st.info("A 성향과 B 성향의 선택 횟수가 같습니다. 균형 잡힌 성향을 가지고 있습니다!")

            st.markdown("---")
            st.caption(f"총 기록 횟수: {len(quiz_history)}일 | 사용자 ID: ")
            st.caption("**참고:** 이 분석은 A와 B 선택지에 부여된 임의의 성향을 기준으로 합니다.")
            
    else:
        st.info("아직 퀴즈 기록이 없습니다. 오늘 퀴즈를 풀고 결과를 확인하세요!")
