import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime

# 1. 기초 설정 (시간표 틀 및 항목 정의)
st.set_page_config(page_title="동아리 통합 관리", layout="wide")

시간대 = [f"{i}시({i-8}교시)" for i in range(9, 24)]
요일 = ["월", "화", "수", "목", "금"]
부원항목 = ["이름", "학번", "학과", "학년", "전화번호", "파트", "통학여부", "회비여부", "개요1", "개요2", "개요3", "개요4"]

# 2. 구글 시트 연결 설정
@st.cache_resource
def 구글문서연결():
    접속권한 = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    신분증 = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=접속권한)
    연결망 = gspread.authorize(신분증)
    return 연결망.open("동아리_DB").sheet1

시트 = 구글문서연결()

# 3. 팀별 데이터 로직 (방 찾기 및 저장)
def 방찾기(번호):
    try:
        모든데이터 = 시트.get_all_values()
        for i, 줄 in enumerate(모든데이터):
            if 줄[0] == 번호:
                return i + 1, 줄 
        return None, None
    except:
        return None, None

def 자료저장():
    # 모든 데이터를 JSON으로 변환하여 저장 (게시판과 채팅 추가)
    방자료_json = st.session_state.room_db.to_json()
    부원자료_json = st.session_state.부원자료.to_json()
    개인db_json = json.dumps({이름: 표.to_json() for 이름, 표 in st.session_state.db.items()})
    설정_json = json.dumps({
        "학과": st.session_state.항목_학과,
        "학년": st.session_state.항목_학년,
        "파트": st.session_state.항목_파트,
        "통학": st.session_state.항목_통학,
        "회비": st.session_state.항목_회비,
        "비밀번호": st.session_state.비밀번호,
        "팀이름": st.session_state.팀이름
    })
    게시판_json = json.dumps(st.session_state.게시판)
    채팅_json = json.dumps(st.session_state.채팅)
    
    새데이터 = [
        st.session_state["방번호"], 
        st.session_state["팀이름"], 
        방자료_json, 
        부원자료_json, 
        개인db_json, 
        설정_json,
        게시판_json,
        채팅_json
    ]
    줄번호, _ = 방찾기(st.session_state["방번호"])
    
    if 줄번호:
        시트.update(values=[새데이터], range_name=f"A{줄번호}:H{줄번호}")
    else:
        시트.append_row(새데이터)

# 4. 입장 및 초기화 시스템
if "방번호" not in st.session_state: st.session_state["방번호"] = ""
if "팀이름" not in st.session_state: st.session_state["팀이름"] = ""

if st.session_state["방번호"] == "":
    입장탭, 생성탭 = st.tabs(["시간표 방 접속하기", "새로운 팀 방 만들기"])
    
    with 입장탭:
        입력번호 = st.text_input("팀 식별번호를 입력하세요")
        if st.button("입장하기"):
            줄번호, 데이터 = 방찾기(입력번호)
            if 줄번호:
                st.session_state["방번호"] = 데이터[0]
                st.session_state["팀이름"] = 데이터[1]
                st.session_state.room_db = pd.read_json(데이터[2]).fillna("")
                st.session_state.부원자료 = pd.read_json(데이터[3]).fillna("")
                st.session_state.db = {이름: pd.read_json(표).fillna("") for 이름, 표 in json.loads(데이터[4]).items()}
                s = json.loads(데이터[5])
                st.session_state.항목_학과 = s.get("학과", ["물리치료학과", "기타학과"])
                st.session_state.항목_학년 = s.get("학년", ["1", "2", "3", "4"])
                st.session_state.항목_파트 = s.get("파트", ["보컬", "보컬2", "기타1", "기타2", "통기타", "베이스", "드럼", "키보드", "기타악기"])
                st.session_state.항목_통학 = s.get("통학", ["o", "x"])
                st.session_state.항목_회비 = s.get("회비", ["o", "x"])
                st.session_state.비밀번호 = s.get("비밀번호", "0000")
                # 게시판 및 채팅 데이터 로드 (데이터 길이에 따라 예외처리)
                st.session_state.게시판 = json.loads(데이터[6]) if len(데이터) > 6 else []
                st.session_state.채팅 = json.loads(데이터[7]) if len(데이터) > 7 else []
                
                st.session_state.인증완료, st.session_state.새로고침번호 = False, 0
                st.session_state.새부원표 = pd.DataFrame([["", "", st.session_state.항목_학과[0], "1", "", st.session_state.항목_파트[0], "x", "x", "", "", "", ""]], columns=st.session_state.부원자료.columns)
                st.rerun()
            else: st.error("방을 찾을 수 없습니다.")

    with 생성탭:
        새번호 = st.text_input("원하는 식별번호")
        새이름 = st.text_input("팀 이름")
        if st.button("방 만들기"):
            줄, _ = 방찾기(새번호)
            if 줄: st.error("이미 존재하는 번호입니다.")
            elif 새번호 and 새이름:
                st.session_state["방번호"], st.session_state["팀이름"] = 새번호, 새이름
                st.session_state.db, st.session_state.room_db = {}, pd.DataFrame("", index=시간대, columns=요일)
                st.session_state.부원자료 = pd.DataFrame(columns=부원항목)
                st.session_state.게시판, st.session_state.채팅 = [], []
                st.session_state.항목_학과, st.session_state.항목_학년 = ["물리치료학과", "기타학과"], ["1", "2", "3", "4"]
                st.session_state.항목_파트 = ["보컬", "보컬2", "기타1", "기타2", "통기타", "베이스", "드럼", "키보드", "기타악기"]
                st.session_state.항목_통학, st.session_state.항목_회비, st.session_state.비밀번호 = ["o", "x"], ["o", "x"], "0000"
                st.session_state.새부원표 = pd.DataFrame([["", "", st.session_state.항목_학과[0], "1", "", "보컬", "x", "x", "", "", "", ""]], columns=부원항목)
                st.session_state.인증완료, st.session_state.새로고침번호 = False, 0
                자료저장(); st.rerun()
    st.stop()

# 5. 메인 UI
st.markdown(f"<h1>통합 관리 화면 <span style='font-size: 0.5em; background-color: #f0f2f6; padding: 5px 10px; border-radius: 10px; color: black;'>{st.session_state['팀이름']}</span></h1>", unsafe_allow_html=True)
if st.button("로그아웃"): 
    st.session_state["방번호"] = ""
    st.rerun()

탭1, 탭2, 탭3, 탭4, 탭5, 탭6 = st.tabs(["동아리방 관리", "개인 시간표 확인", "시간표 등록", "부원 정보 관리", "공지 게시판", "익명 채팅방"])

# --- 탭 1 ~ 4: 기존 기능 (유지) ---
with 탭1:
    st.header("동아리방 시간표 관리")
    변경된방자료 = st.data_editor(st.session_state.room_db, use_container_width=True, key=f"방_{st.session_state.새로고침번호}")
    if st.button("방 시간표 저장"):
        st.session_state.room_db = 변경된방자료.fillna("")
        자료저장(); st.rerun()

with 탭2:
    st.header("부원 시간표 및 공통 공강 확인")
    if st.session_state.db:
        선택된부원 = st.multiselect("부원 선택", list(st.session_state.db.keys()))
        if len(선택된부원) >= 2:
            공통표 = pd.DataFrame("", index=시간대, columns=요일)
            for t in 시간대:
                for d in 요일:
                    값들 = [str(st.session_state.db[b].loc[t, d]).strip() for b in 선택된부원 if str(st.session_state.db[b].loc[t, d]).strip()]
                    if len(값들) == len(선택된부원) and len(set(값들)) == 1: 공통표.loc[t, d] = 값들[0]
                    elif 값들: 공통표.loc[t, d] = " "
            def 색상(v):
                if v == " ": return "background-color: #d3d3d3; color: #d3d3d3"
                return "background-color: #FFF2CC; color: black" if v != "" else ""
            st.dataframe(공통표.style.map(색상), use_container_width=True)
    else: st.info("등록된 자료가 없습니다.")

with 탭3:
    st.header("부원 개인 시간표 등록")
    이름들 = ["새로 입력"] + sorted(list(st.session_state.db.keys()))
    선택명 = st.selectbox("이름 선택", 이름들, key=f"이름_{st.session_state.새로고침번호}")
    입력명 = st.text_input("새 이름 입력") if 선택명 == "새로 입력" else 선택명
    기존표 = st.session_state.db[입력명].copy() if 입력명 in st.session_state.db else pd.DataFrame("", index=시간대, columns=요일)
    새표 = st.data_editor(기존표, use_container_width=True, key=f"표_{st.session_state.새로고침번호}")
    if st.button("개인 시간표 저장"):
        if 입력명: st.session_state.db[입력명] = 새표.fillna(""); 자료저장(); st.rerun()

with 탭4:
    st.header("부원 정보 관리")
    if not st.session_state.인증완료:
        입력암호 = st.text_input("관리자 비밀번호 입력", type="password", key="admin_pw")
        if st.button("인증"):
            if 입력암호 == st.session_state.비밀번호: st.session_state.인증완료 = True; st.rerun()
            else: st.error("비밀번호 불일치")
    else:
        if st.button("관리자 잠금"): st.session_state.인증완료 = False; st.rerun()
        with st.expander("⚙️ 설정"):
            st.write("항목 이름 및 리스트 변경")
            # (기존 항목 설정 코드 동일하게 유지...)
            c1, c2 = st.columns(2)
            with c1:
                st.session_state.항목_학과 = [x.strip() for x in st.text_input("학과 리스트", ", ".join(st.session_state.항목_학과)).split(",") if x.strip()]
                st.session_state.항목_파트 = [x.strip() for x in st.text_input("파트 리스트", ", ".join(st.session_state.항목_파트)).split(",") if x.strip()]
            with c2:
                st.session_state.항목_학년 = [x.strip() for x in st.text_input("학년 리스트", ", ".join(st.session_state.항목_학년)).split(",") if x.strip()]
                st.session_state.비밀번호 = st.text_input("관리 비번 변경", st.session_state.비밀번호)
            if st.button("설정 저장"): 자료저장(); st.success("저장됨")
        
        st.subheader("새 부원 추가 및 명단 수정")
        수정표 = st.data_editor(st.session_state.부원자료, use_container_width=True, num_rows="dynamic", key=f"명단_{st.session_state.새로고침번호}")
        if st.button("부원 명단 저장"):
            st.session_state.부원자료 = 수정표.fillna(""); 자료저장(); st.rerun()

# --- 탭 5: 공지 게시판 (읽기 전체, 쓰기 비번 필요) ---
with 탭5:
    st.header("공지 게시판")
    st.write("모든 부원이 볼 수 있는 게시판입니다.")
    
    # 글쓰기 영역
    with st.expander("📝 새 글 작성하기 (비밀번호 필요)"):
        작성자 = st.text_input("작성자 성함", key="board_author")
        제목 = st.text_input("글 제목", key="board_title")
        내용 = st.text_area("내용을 입력하세요", key="board_content")
        확인비번 = st.text_input("관리자 비밀번호를 입력하세요", type="password", key="board_pw")
        
        if st.button("게시물 등록"):
            if 확인비번 == st.session_state.비밀번호:
                if 작성자 and 제목 and 내용:
                    새글 = {
                        "날짜": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "작성자": 작성자,
                        "제목": 제목,
                        "내용": 내용
                    }
                    st.session_state.게시판.insert(0, 새글) # 최신글이 위로
                    자료저장(); st.success("글이 성공적으로 등록되었습니다!"); st.rerun()
                else: st.warning("모든 칸을 입력해주세요.")
            else: st.error("비밀번호가 틀렸습니다.")

    st.divider()
    
    # 게시물 출력
    if st.session_state.게시판:
        for idx, 글 in enumerate(st.session_state.게시판):
            with st.container():
                st.subheader(f"📌 {글['제목']}")
                st.write(f"📅 {글['날짜']} | 👤 작성자: {글['작성자']}")
                st.info(글['내용'])
                if st.session_state.인증완료: # 관리자 로그인 상태면 삭제 버튼 표시
                    if st.button(f"삭제 ({idx})", key=f"del_{idx}"):
                        st.session_state.게시판.pop(idx)
                        자료저장(); st.rerun()
                st.write("---")
    else: st.info("아직 등록된 게시물이 없습니다.")

# --- 탭 6: 익명 채팅방 (누구나 자유롭게) ---
with 탭6:
    st.header("익명 채팅방")
    st.write("별명을 정하고 자유롭게 대화하세요!")
    
    # 채팅 메시지 표시 영역 (스크롤 박스 형태처럼)
    chat_container = st.container()
    with chat_container:
        if st.session_state.채팅:
            for 대화 in st.session_state.채팅[-30:]: # 최근 30개만 표시
                st.markdown(f"**[{대화['시간']}] {대화['닉네임']}**: {대화['메시지']}")
        else: st.info("채팅이 없습니다. 첫 메시지를 남겨보세요!")

    st.write("---")
    
    # 입력 영역
    c1, c2 = st.columns([1, 4])
    with c1: 닉네임 = st.text_input("별명", value="익명", key="chat_nick")
    with c2: 메시지 = st.text_input("메시지 입력", key="chat_msg")
    
    if st.button("전송"):
        if 메시지:
            새채팅 = {
                "시간": datetime.now().strftime("%H:%M"),
                "닉네임": 닉네임,
                "메시지": 메시지
            }
            st.session_state.채팅.append(새채팅)
            자료저장(); st.rerun()
