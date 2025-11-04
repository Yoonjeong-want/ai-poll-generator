import streamlit as st
from utils.question_generator import generate_poll_question

st.set_page_config(page_title="AI 투표 질문 생성기", page_icon="💡", layout="centered")

# 미리 정의된 주제 목록 (사용자가 선택할 수 있도록)
PREDEFINED_TOPICS = [
    "--- 주제를 선택하세요 ---",
    "학교생활",
    "밈",
    "유머",
    "연애",
    "칭찬",
    "SNS",
    "아이돌",
    "예능",
    "게임",
    "미래"
]

st.title("💡 AI 유저 투표 질문 생성기")
st.write("미리 정해진 주제를 선택하거나, 새로운 주제를 입력하여 투표 질문을 만들어 보세요!")
st.write("---")

st.subheader("투표 설정")
# 텍스트 입력 대신 주제 선택(selectbox)을 사용합니다.
selected_topic = st.selectbox("1. 주제를 선택하세요:", PREDEFINED_TOPICS)

# 선택 목록에 없는 경우를 대비해, 사용자가 직접 주제를 입력할 수 있는 옵션을 제공합니다.
custom_topic = st.text_input("2. (선택 사항) 새로운 주제를 직접 입력하세요:", "")

num_questions = st.slider("3. 생성할 질문 수:", 1, 5, 1)

# AI에 전달할 최종 주제를 결정합니다.
# 사용자가 직접 입력한 주제가 있으면 그것을 사용하고, 아니면 선택된 주제를 사용합니다.
final_topic = custom_topic.strip() if custom_topic.strip() else selected_topic

if st.button("투표 질문 생성하기 🚀"):
    # 주제가 선택되지 않았거나, 사용자 입력도 없는 경우
    if final_topic == PREDEFINED_TOPICS[0] or not final_topic.strip():
        st.warning("투표할 주제를 선택하거나 직접 입력해 주세요!")
    else:
        with st.spinner(f"AI가 [{final_topic}] 주제로 가장 재미있는 질문을 생각하는 중... ⏳"):
            try:
                # generate_poll_question 함수에 최종 주제를 전달합니다.
                polls = generate_poll_question(final_topic, num_questions)
                
                if not polls:
                     st.warning("질문을 생성할 수 없습니다. API 키를 확인하거나 다시 시도해 주세요.")
                else:
                    st.success(f"🎉 {len(polls)}개의 투표 질문이 생성되었습니다!")
                    
                    for i, p in enumerate(polls, 1):
                        st.markdown(f"## 🗳️ 투표 질문 {i}")
                        
                        st.markdown(f"### {p['question_phrase']}")
                        
                        st.write("**보기 (랜덤 유저):**")
                        for choice in p["choices"]:
                            st.markdown(f"- **{choice}**")
                            
                        st.caption("🚨 **참고:** 이 투표는 재미로 하는 것이며, 정답은 없습니다.")
                        st.markdown("---")
            
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")
