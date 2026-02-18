import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json

# 1. 기초 설정
st.set_page_config(page_title="시간표", layout="wide")

시간대 = [f"{i}시({i-8}교시)" for i in range(9, 24)]
요일 = ["월", "화", "수", "목", "금"]
부원항목 = ["이름", "학번", "학과", "학년", "전화번호", "파트", "통학여부", "회비여부", "개요1", "개요2", "개요3", "개요4"]

# 2. 구글 시트 연결
@st.cache_resource
def 구글문서연결():
    접속권한 = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    신분증 = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=접속권한)
    연결망 = gspread.authorize(신분증)
    return 연결망.open("동아리_DB").sheet1

시트 = 구글문서연결()

# 3. 방 찾기 및 저장 로직 (핵심 수정)
def 방찾기(번호):
    모든데이터 = 시트.get_all_values()
    for i, 줄 in enumerate(모든데이터):
        if 줄[0] == 번호: # 첫 번째 칸이 방 번호
            return i + 1, 줄 # 몇 번째 줄인지와 그 줄의 데이터 반환
    return None, None

def 자료저장():
    줄번호, _ = 방찾기(st.session_state["방번호"])
    방자료 = st.session_state.room_db.to_json()
    부원 = st.session_state.부원자료.to_json()
    개인 = json.dumps({이름: 표.to_json() for 이름, 표 in st.session_state.db.items()})
    설정 = json.dumps({
        "학과": st.session_state.항목_학과,
        "학년": st.session_state.항목_학년,
        "파트": st.session_state.항목_파트,
        "통학": st.session_state.항목_통학,
        "회비": st.session_state.항목_회비,
        "비밀번호": st.session_state.비밀번호,
        "팀이름": st.session_state.팀이름
    })
    
    새데이터 = [st.session_state["방번호"], st.session_state["팀이름"], 방자료, 부원, 개인, 설정]
    
    if 줄번호: # 이미 있는 방이면 해당 줄 업데이트
        범위 = f"A{줄번호}:F{줄번호}"
        시트.update(values=[새데이터], range_name=범위)
    else: # 새 방이면 맨 아래줄에 추가
        시트.append_row(새데이터)

# 4. 로그인 및 입장 화면
if "방번호" not in st.session_state:
    st.session_state["방번호"] = ""
if "팀이름" not in st.session_state:
    st.session_state["팀이름"] = ""

if st.session_state["방번호"] == "":
    탭_입장, 탭_생성 = st.tabs(["시간표 방 접속하기", "새로운 팀 방 만들기"])
    
    with 탭_입장:
        입력번호 = st.text_input("팀 식별번호를 입력하세요", key="login_id")
        if st.button("입장하기"):
            줄번호, 데이터 = 방찾기(입력번호)
            if 줄번호:
                st.session_state["방번호"] = 데이터[0]
                st.session_state["팀이름"] = 데이터[1]
                # 데이터 불러오기
                st.session_state.room_db = pd.read_json(데이터[2]).fillna("")
                st.session_state.부원자료 = pd.read_json(데이터[3]).fillna("")
                임시db = json.loads(데이터[4])
                st.session_state.db = {이름: pd.read_json(표).fillna("") for 이름, 표 in 임시db.items()}
                설정 = json.loads(데이터[5])
                st.session_state.항목_학과 = 설정.get("학과", ["물리치료학과", "기타학과"])
                st.session_state.항목_학년 = 설정.get("학년", ["1", "2", "3", "4"])
                st.session_state.항목_파트 = 설정.get("파트", ["보컬", "기타", "베이스", "드럼", "키보드"])
                st.session_state.항목_통학 = 설정.get("통학", ["o", "x"])
                st.session_state.항목_회비 = 설정.get("회비", ["o", "x"])
                st.session_state.비밀번호 = 설정.get("비밀번호", "0000")
                st.session_state.초기설정완료 = True
                st.session_state.인증완료 = False
                st.session_state.새로고침번호 = 0
                st.rerun()
            else:
                st.error("해당 식별번호를 가진 방이 없습니다. 번호를 확인하거나 새로 만들어주세요.")

    with 탭_생성:
        새방번호 = st.text_input("원하는 식별번호를 정해주세요", key="new_id")
        새이름 = st.text_input("팀 이름을 정해주세요", key="new_name")
        if st.button("방 만들기"):
            줄번호, _ = 방찾기(새방번호)
            if 줄번호:
                st.error("이미 존재하는 식별번호입니다. 다른 번호를 사용해주세요.")
            elif 새방번호 and 새이름:
                st.session_state["방번호"] = 새방번호
                st.session_state["팀이름"] = 새이름
                # 초기 데이터 생성
                st.session_state.db = {}
                st.session_state.room_db = pd.DataFrame("", index=시간대, columns=요일)
                st.session_state.부원자료 = pd.DataFrame(columns=부원항목)
                st.session_state.항목_학과, st.session_state.항목_학년 = ["물리치료학과", "기타학과"], ["1", "2", "3", "4"]
                st.session_state.항목_파트 = ["보컬", "기타", "베이스", "드럼", "키보드"]
                st.session_state.항목_통학, st.session_state.항목_회비 = ["o", "x"], ["o", "x"]
                st.session_state.비밀번호 = "0000"
                자료저장()
                st.session_state.초기설정완료 = True
                st.rerun()
            else:
                st.warning("번호와 이름을 모두 입력해주세요.")
    st.stop()

# 5. 메인 화면 (로그인 이후)
if '초기설정완료' not in st.session_state:
    st.rerun()

st.markdown(f"<h1>통합 시간표 관리 화면 <span style='font-size: 0.5em; background-color: #f0f2f6; padding: 5px 10px; border-radius: 10px; color: black;'>{st.session_state['팀이름']}</span></h1>", unsafe_allow_html=True)
if st.button("로그아웃 (방 나가기)"):
    st.session_state["방번호"] = ""
    st.rerun()

탭일, 탭이, 탭삼, 탭사 = st.tabs(["동아리방 관리", "개인 시간표 및 공강 확인", "학생 시간표 기입란", "부원 정보 관리"])

# (이하 탭별 내용은 네가 준 완벽했던 코드와 동일하게 유지하되 자료저장() 함수만 호출하면 됨)
with 탭일:
    st.header("동아리방 시간표 관리")
    변경된방자료 = st.data_editor(st.session_state.room_db, use_container_width=True, key=f"방_{st.session_state.새로고침번호}")
    if st.button("동아리방 시간표 저장"):
        st.session_state.room_db = 변경된방자료.fillna(""); 자료저장(); st.rerun()

with 탭이:
    st.header("부원 시간표 및 공통 공강 확인")
    if st.session_state.db:
        선택된부원 = st.multiselect("확인할 부원 선택", list(st.session_state.db.keys()))
        if len(선택된부원) >= 2:
            공통표 = pd.DataFrame("", index=시간대, columns=요일)
            for t in 시간대:
                for d in 요일:
                    값들 = [str(st.session_state.db[b].loc[t, d]).strip() for b in 선택된부원 if str(st.session_state.db[b].loc[t, d]).strip()]
                    if len(값들) == len(선택된부원) and len(set(값들)) == 1: 공통표.loc[t, d] = 값들[0]
                    elif 값들: 공통표.loc[t, d] = " "
            st.dataframe(공통표.style.map(lambda x: "background-color: #d3d3d3" if x==" " else ("background-color: #FFF2CC" if x!="" else "")), use_container_width=True)

with 탭삼:
    st.header("부원 시간표 등록")
    이름들 = ["새로 입력"] + sorted(list(st.session_state.db.keys()))
    선택이름 = st.selectbox("이름 선택", 이름들, key=f"이름_{st.session_state.새로고침번호}")
    입력이름 = st.text_input("새 이름") if 선택이름 == "새로 입력" else 선택이름
    기존표 = st.session_state.db[입력이름].copy() if 입력이름 in st.session_state.db else pd.DataFrame("", index=시간대, columns=요일)
    새표 = st.data_editor(기존표, use_container_width=True, key=f"표_{st.session_state.새로고침번호}")
    if st.button("시간표 저장"):
        if 입력이름: st.session_state.db[입력이름] = 새표.fillna(""); 자료저장(); st.rerun()

with 탭사:
    st.header("부원 정보 관리")
    if not st.session_state.인증완료:
        입력암호 = st.text_input("관리자 비밀번호", type="password")
        if st.button("로그인"):
            if 입력암호 == st.session_state.비밀번호:
                st.session_state.인증완료 = True; st.rerun()
            else: st.error("비밀번호 불일치")
    else:
        if st.button("화면 잠금"): st.session_state.인증완료 = False; st.rerun()
        with st.expander("⚙️ 설정"):
            c1, c2 = st.columns(2)
            with c1:
                st.session_state.항목_학과 = [x.strip() for x in st.text_input("학과 리스트", ", ".join(st.session_state.항목_학과)).split(",") if x.strip()]
                st.session_state.항목_파트 = [x.strip() for x in st.text_input("파트 리스트", ", ".join(st.session_state.항목_파트)).split(",") if x.strip()]
            with c2:
                st.session_state.항목_학년 = [x.strip() for x in st.text_input("학년 리스트", ", ".join(st.session_state.항목_학년)).split(",") if x.strip()]
                st.session_state.비밀번호 = st.text_input("관리자 비번 변경", st.session_state.비밀번호)
            if st.button("설정 저장"): 자료저장(); st.success("저장됨")
        
        # 새 부원 추가 및 명단 수정 코드 (기존과 동일)
        st.subheader("➕ 새로운 부원 추가")
        st.session_state.새부원표 = pd.DataFrame([["", "", st.session_state.항목_학과[0], "1", "", st.session_state.항목_파트[0], "x", "x", "", "", "", ""]], columns=부원항목)
        입력새부원 = st.data_editor(st.session_state.새부원표, column_config={
            "학과": st.column_config.SelectboxColumn(options=st.session_state.항목_학과),
            "학년": st.column_config.SelectboxColumn(options=st.session_state.항목_학년),
            "파트": st.column_config.SelectboxColumn(options=st.session_state.항목_파트),
            "통학여부": st.column_config.SelectboxColumn(options=st.session_state.항목_통학),
            "회비여부": st.column_config.SelectboxColumn(options=st.session_state.항목_회비)
        }, use_container_width=True)
        if st.button("명단 추가"):
            if str(입력새부원.iloc[0,0]).strip():
                st.session_state.부원자료 = pd.concat([st.session_state.부원자료, 입력새부원], ignore_index=True); 자료저장(); st.rerun()
        
        st.subheader("📝 전체 명단 수정")
        수정명단 = st.data_editor(st.session_state.부원자료, use_container_width=True, num_rows="dynamic")
        if st.button("명단 저장"): st.session_state.부원자료 = 수정명단.fillna(""); 자료저장(); st.rerun()
