import streamlit as st
from utils.question_generator import generate_poll_question
import time

# --- 1. 청소년 유해 단어 목록 및 주제 정의 ---
BANNED_WORDS = [
    "술", "담배", "도박", "섹스", "폭력", "자살", "마약", 
    "비방", "욕설", "싸움", "성인", "죽음", "혐오"
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
    page_title="AI 투표 질문 생성기 (청소년용)",
    layout="centered",
    initial_sidebar_state="expanded",
)

st.title("💡 AI 유저 투표 질문 생성기")
st.write("미리 정해진 주제를 선택하거나, 새로운 주제를 입력하여 투표 질문을 만들어 보세요!")
st.markdown("---")


# --- 3. 사용자 입력 섹션 ---
with st.container(border=True):
    st.header("1. 질문 주제 입력")
    
    # 주제 선택(selectbox)
    selected_topic = st.selectbox("1. 주제를 선택하세요:", PREDEFINED_TOPICS)

    # 선택 목록에 없는 경우를 대비해, 사용자가 직접 주제를 입력할 수 있는 옵션을 제공합니다.
    custom_topic = st.text_input("2. (선택 사항) 새로운 주제를 직접 입력하세요:", "")
    
    # AI에 전달할 최종 주제를 결정합니다.
    # custom_topic이 있으면 그것을 사용하고, 아니면 selected_topic을 사용합니다.
    final_topic = custom_topic.strip() if custom_topic.strip() else selected_topic
    
    # 생성할 질문 개수 (슬라이더)
    num_questions = st.slider(
        "3. 생성할 질문 개수", 
        min_value=1, 
        max_value=5, 
        value=3, 
        step=1
    )
    
    # --- 4. 금지어 검사 로직 ---
    # 입력된 주제를 소문자화하고 금지어 목록과 비교
    is_banned = False
    found_banned_words = []
    
    # 최종 주제(final_topic)가 선택/입력되었고, 플레이스홀더가 아닌 경우에만 검사
    if final_topic and final_topic != PREDEFINED_TOPICS[0]:
        topic_lower = final_topic.lower().strip()
        for word in BANNED_WORDS:
            if word in topic_lower:
                is_banned = True
                found_banned_words.append(word)
                
    # 금지어가 발견되었을 경우 경고 메시지 표시 및 버튼 비활성화
    if is_banned:
        st.error(f"⚠️ **부적절한 주제 경고!** '{', '.join(found_banned_words)}'와(과) 같은 금지어가 포함되어 있습니다. 청소년에게 적합한 주제를 입력해주세요.")
        button_disabled = True
    else:
        button_disabled = False

    # 최종적으로 유효한 주제인지 확인 (플레이스홀더 선택 방지)
    is_valid_topic = final_topic.strip() != "" and final_topic != PREDEFINED_TOPICS[0]

    # 버튼
    if st.button("질문 생성하기", disabled=button_disabled or not is_valid_topic, use_container_width=True):
        
        # 버튼이 눌렸을 때 최종적으로 주제가 유효하지 않으면 경고 표시
        if not is_valid_topic:
             st.warning("투표 주제를 선택하거나 직접 입력해주세요!")
        else:
            with st.spinner("✨ AI가 재미있는 투표 질문을 생성 중입니다..."):
                start_time = time.time()
                # API 호출 (utils에서 처리) - final_topic 사용
                polls = generate_poll_question(final_topic, num_questions)
                end_time = time.time()
            
            if polls:
                st.session_state.polls = polls
                st.session_state.topic = final_topic # final_topic을 세션 상태에 저장
                st.session_state.time_taken = f"{end_time - start_time:.2f}초"
            else:
                 st.error("질문 생성에 실패했거나, AI가 주제가 부적절하다고 판단하여 응답하지 않았습니다. 다른 주제로 시도해주세요.")


# --- 5. 결과 표시 섹션 ---
if 'polls' in st.session_state and st.session_state.polls:
    
    st.markdown("---")
    st.header(f"2. 투표 질문 결과 (주제: {st.session_state.topic})")
    st.caption(f"생성 시간: {st.session_state.time_taken}")
    
    
    for i, poll in enumerate(st.session_state.polls):
        with st.container(border=True):
            
            # 질문 제목
            st.subheader(f"🗳️ 질문 {i+1}: {poll['question_phrase']}")
            
            # 보기 표시 (4개)
            cols = st.columns(4)
            for j, choice in enumerate(poll['choices']):
                with cols[j]:
                    st.metric(label=f"보기 {j+1}", value=choice)
