import streamlit as st
import requests
import json
from pypdf import PdfReader
import os
import time

# ดึง Key จาก Streamlit Secrets โดยตรง
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    API_KEY = "AQ.Ab8RN6Kjm1ZVOumjAx9nBVsoDKGJZP9VgmVzzs2FlfvzRx0lXA"

MODEL_NAME = "gemini-3.6-flash"

st.title("📝 ระบบฝึกทำข้อสอบอัจฉริยะ (Cloud OAuth Fix)")

exam_type = st.selectbox("เลือกประเภทข้อสอบที่ต้องการฝึก:", ["ปรนัย 4 ตัวเลือก", "ข้อเขียน (แบบสั้น)"])

col1, col2 = st.columns(2)
with col1:
    num_questions = st.number_input("จำนวนข้อสอบ (สูงสุด 60 ข้อ):", min_value=1, max_value=60, value=5, step=1)
with col2:
    difficulty = st.selectbox("ระดับความยาก:", ["ง่าย (Easy)", "ปานกลาง (Medium)", "ยาก (Hard)"])

uploaded_file = st.file_uploader("โยนไฟล์ PDF เนื้อหาลงที่นี่", type=["pdf"])

if "exam_data" not in st.session_state:
    st.session_state.exam_data = None
if "submitted" not in st.session_state:
    st.session_state.submitted = False

if uploaded_file is not None:
    if st.button("สร้างข้อสอบ"):
        st.session_state.submitted = False
        with st.spinner(f'กำลังสร้างข้อสอบ {num_questions} ข้อ ระดับ {difficulty}...'):
            temp_path = "temp.pdf"
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            try:
                reader = PdfReader(temp_path)
                file_content = "".join([page.extract_text() for page in reader.pages if page.extract_text()])
                
                if exam_type == "ปรนัย 4 ตัวเลือก":
                    prompt_text = f"""จากเนื้อหานี้:\n{file_content[:20000]}\nจงสร้างข้อสอบปรนัยจำนวน {num_questions} ข้อ ในระดับความยาก '{difficulty}' คืนค่าเป็น JSON รูปแบบนี้เท่านั้น:
                    {{
                      "questions": [
                        {{
                          "question": "คำถาม...?",
                          "options": ["ตัวเลือก1", "ตัวเลือก2", "ตัวเลือก3", "ตัวเลือก4"],
                          "answer": "ตัวเลือกที่ถูกต้อง",
                          "explanation": "คำอธิบาย"
                        }}
                      ]
                    }}"""
                else:
                    prompt_text = f"""จากเนื้อหานี้:\n{file_content[:20000]}\nจงสร้างข้อสอบอัตนัย (ข้อเขียนแบบสั้น) จำนวน {num_questions} ข้อ ในระดับความยาก '{difficulty}' คืนค่าเป็น JSON รูปแบบนี้เท่านั้น:
                    {{
                      "questions": [
                        {{
                          "question": "คำถาม...?",
                          "answer": "แนวคำตอบที่ถูกต้อง",
                          "explanation": "คำอธิบาย"
                        }}
                      ]
                    }}"""

                # ใช้ REST API พร้อมส่งคีย์ AQ ผ่าน Authorization Bearer Header โดยตรง
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {API_KEY}"
                }
                payload = {
                    "contents": [{"parts": [{"text": prompt_text}]}],
                    "generationConfig": {"response_mime_type": "application/json"}
                }
                
                success = False
                result_json = None
                for attempt in range(3):
                    response = requests.post(url, headers=headers, data=json.dumps(payload))
                    result_json = response.json()
                    if response.status_code == 200:
                        success = True
                        break
                    else:
                        time.sleep(2)
                
                if success:
                    raw_text = result_json["candidates"][0]["content"]["parts"][0]["text"]
                    st.session_state.exam_data = json.loads(raw_text)
                else:
                    st.error(f"Google API Error: {result_json}")
                    
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

if st.session_state.exam_data is not None:
    questions = st.session_state.exam_data["questions"]
    st.success(f"โหลดข้อสอบสำเร็จทั้งหมด {len(questions)} ข้อ!")
    
    user_answers = {}
    
    if exam_type == "ปรนัย 4 ตัวเลือก":
        for i, q in enumerate(questions):
            st.subheader(f"ข้อที่ {i+1}: {q['question']}")
            user_answers[i] = st.radio("เลือกคำตอบ:", q["options"], key=f"q_{i}", index=None)
    else:
        for i, q in enumerate(questions):
            st.subheader(f"ข้อที่ {i+1}: {q['question']}")
            user_answers[i] = st.text_area("พิมพ์คำตอบของคุณที่นี่:", key=f"text_{i}")

    st.divider()
    
    if st.button("Submit (ส่งคำตอบและตรวจคะแนน)"):
        st.session_state.submitted = True

    if st.session_state.submitted:
        st.header("📊 สรุปผลคะแนนของคุณ")
        
        if exam_type == "ปรนัย 4 ตัวเลือก":
            score = 0
            total = len(questions)
            wrong_questions = []
            
            for i, q in enumerate(questions):
                ans = user_answers.get(i)
                if ans == q['answer']:
                    score += 1
                else:
                    wrong_questions.append((i + 1, q, ans))
            
            st.metric(label="คะแนนรวม", value=f"{score} / {total}")
            
            if wrong_questions:
                st.subheader("❌ รายละเอียดข้อที่ทำผิดและคำอธิบาย:")
                for q_num, q, user_ans in wrong_questions:
                    with st.expander(f"ข้อที่ {q_num} (ตอบผิด)"):
                        st.write(f"**คำถาม:** {q['question']}")
                        st.write(f"**ที่คุณตอบ:** {user_ans if user_ans else 'ไม่ได้เลือกตอบ'}")
                        st.error(f"**เฉลยที่ถูกต้อง:** {q['answer']}")
                        st.info(f"**คำอธิบาย:** {q['explanation']}")
            else:
                st.balloons()
                st.success("ยินดีด้วย! คุณตอบถูกหมดทุกข้อ!")
        else:
            st.info("สำหรับข้อเขียน ระบบแสดงแนวคำตอบครบทุกข้อเพื่อให้คุณตรวจทานคำตอบด้วยตนเอง:")
            for i, q in enumerate(questions):
                with st.expander(f"ข้อที่ {i+1} - แนวคำตอบ"):
                    st.write(f"**คำถาม:** {q['question']}")
                    st.write(f"**คำตอบที่คุณพิมพ์:** {user_answers.get(i, '')}")
                    st.success(f"**แนวคำตอบ:** {q['answer']}")
                    st.info(f"**คำอธิบาย:** {q['explanation']}")
