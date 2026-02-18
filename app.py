import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json

# 1. 전역 설정 (모든 탭에서 공통으로 사용되는 변수)
st.set_page_config(page_title="시간표", layout="wide")

시간대 = [f"{i}시({i-8}교시)" for i in range(9, 24)]
요일 = ["월", "화", "수", "목", "금"]
부원항목 = ["이름", "학번", "학과", "학년", "전화번호", "파트", "통학여부", "회비여부", "개요1", "개요2", "개요3", "개요4"]

# 2. 구글 시트 연결 (Secrets 보안 방식)
@st.cache_resource
def 구글문서연결():
    접속권한 = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    신분증 = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=접속권한)
    연결망 = gspread.authorize(신분증)
    # 구글 시트 이름이 '동아리_DB'인지 꼭 확인해줘!
    return 연결망.open("동아리_DB").sheet1

시트 = 구글문서연결()

# 3. 데이터 로직 (팀별 줄 찾기 및 저장)
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
    # 현재 세션 정보를 리스트로 변환
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
    줄번호, _ = 방찾기(st.session_state["방번호"])
    
    if 줄번호:
        시트.update(values=[새데이터], range_name=f"A{줄번호}:F{줄번호}")
    else:
        시트.append_row(새데이터)

# 4. 입장 시스템
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
                임시db = json.loads(데이터[4])
                st.session_state.db = {이름: pd.read_json(표).fillna("") for 이름, 표 in 임시db.items()}
                s = json.loads(데이터[5])
                st.session_state.항목_학과 = s.get("학과", ["물리치료학과", "기타학과"])
                st.session_state.항목_학년 = s.get("학년", ["1", "2", "3", "4"])
                st.session_state.항목_파트 = s.get("파트", ["보컬", "기타", "베이스", "드럼", "키보드"])
                st.session_state.항목_통학 = s.get("통학", ["o", "x"])
                st.session_state.항목_회비 = s.get("회비", ["o", "x"])
                st.session_state.비밀번호 = s.get("비밀번호", "0000")
                st.session_state.인증완료, st.session_state.새로고침번호 = False, 0
                st.rerun()
            else: st.error("방을 찾을 수 없습니다. 번호를 확인해주세요.")

    with 생성탭:
        새번호 = st.text_input("원하는 식별번호 (ID)")
        새이름 = st.text_input("팀 이름 (Title)")
        if st.button("방 만들기"):
            줄, _ = 방찾기(새번호)
            if 줄: st.error("이미 존재하는 번호입니다.")
            elif 새번호 and 새이름:
                st.session_state["방번호"], st.session_state["팀이름"] = 새번호, 새이름
                st.session_state.db, st.session_state.room_db = {}, pd.DataFrame("", index=시간대, columns=요일)
                st.session_state.부원자료 = pd.DataFrame(columns=부원항목)
                st.session_state.항목_학과, st.session_state.항목_학년 = ["물리치료학과", "기타학과"], ["1", "2", "3", "4"]
                st.session_state.항목_파트 = ["보컬", "기타", "베이스", "드럼", "키보드"]
                st.session_state.항목_통학, st.session_state.항목_회비, st.session_state.비밀번호 = ["o", "x"], ["o", "x"], "0000"
                자료저장(); st.rerun()
    st.stop()

# 5. 메인 UI (로그인 완료 후)
st.markdown(f"<h1>통합 시간표 관리 화면 <span style='font-size: 0.5em; background-color: #f0f2f6; padding: 5px 10px; border-radius: 10px; color: black;'>{st.session_state['팀이름']}</span></h1>", unsafe_allow_html=True)
if st.button("로그아웃 (다른 방 가기)"):
    st.session_state["방번호"] = ""
    st.rerun()

탭1, 탭2, 탭3, 탭4 = st.tabs(["동아리방 관리", "개인 시간표 및 공강 확인", "학생 시간표 기입란", "부원 정보 관리"])

# --- 탭 1: 동아리방 관리 ---
with 탭1:
    st.header("동아리방 시간표 관리")
    새방 = st.data_editor(st.session_state.room_db, use_container_width=True, key=f"r_{st.session_state.새로고침번호}")
    if st.button("방 시간표 저장"):
        st.session_state.room_db = 새방.fillna("")
        자료저장(); st.rerun()

# --- 탭 2: 공강 확인 ---
with 탭2:
    st.header("부원 시간표 및 공강 확인")
    if st.session_state.db:
        선택 = st.multiselect("확인할 부원 선택", list(st.session_state.db.keys()))
        if len(선택) >= 2:
            공통 = pd.DataFrame("", index=시간대, columns=요일)
            for t in 시간대:
                for d in 요일:
                    v = [str(st.session_state.db[b].loc[t, d]).strip() for b in 선택 if str(st.session_state.db[b].loc[t, d]).strip()]
                    if len(v) == len(선택) and len(set(v)) == 1: 공통.loc[t, d] = v[0]
                    elif v: 공통.loc[t, d] = " "
            st.dataframe(공통.style.map(lambda x: "background-color: #d3d3d3" if x==" " else ("background-color: #FFF2CC" if x!="" else "")), use_container_width=True)

# --- 탭 3: 시간표 등록 ---
with 탭3:
    st.header("부원 시간표 등록")
    이름들 = ["새로 입력"] + sorted(list(st.session_state.db.keys()))
    선택명 = st.selectbox("이름 선택", 이름들, key=f"n_{st.session_state.새로고침번호}")
    입력명 = st.text_input("새 이름") if 선택명 == "새로 입력" else 선택명
    기존 = st.session_state.db[입력명].copy() if 입력명 in st.session_state.db else pd.DataFrame("", index=시간대, columns=요일)
    새표 = st.data_editor(기존, use_container_width=True, key=f"s_{st.session_state.새로고침번호}")
    if st.button("개인 시간표 저장"):
        if 입력명: 
            st.session_state.db[입력명] = 새표.fillna("")
            자료저장(); st.success(f"{입력명}님 저장 완료"); st.rerun()

# --- 탭 4: 부원 정보 관리 (핵심 기능 포함) ---
with 탭4:
    st.header("부원 정보 관리")
    if not st.session_state.인증완료:
        pw = st.text_input("관리자 비밀번호", type="password")
        if st.button("인증하기"):
            if pw == st.session_state.비밀번호:
                st.session_state.인증완료 = True; st.rerun()
            else: st.error("비밀번호 불일치")
    else:
        if st.button("관리 화면 잠금"): st.session_state.인증완료 = False; st.rerun()
        
        # 설정 변경 공간
        with st.expander("⚙️ 항목 설정 및 보기 옵션"):
            c1, c2 = st.columns(2)
            with c1:
                st.session_state.항목_학과 = [x.strip() for x in st.text_input("학과 목록", ", ".join(st.session_state.항목_학과)).split(",") if x.strip()]
                st.session_state.항목_파트 = [x.strip() for x in st.text_input("파트 목록", ", ".join(st.session_state.항목_파트)).split(",") if x.strip()]
            with c2:
                st.session_state.항목_학년 = [x.strip() for x in st.text_input("학년 목록", ", ".join(st.session_state.항목_학년)).split(",") if x.strip()]
                st.session_state.비밀번호 = st.text_input("관리 비번 변경", st.session_state.비밀번호)
            if st.button("설정 적용 및 저장"): 
                자료저장(); st.success("설정이 저장되었습니다.")

        st.subheader("➕ 새로운 부원 추가")
        # 현재 설정된 학과/학년/파트 첫번째 값으로 기본행 생성
        기본행 = pd.DataFrame([["", "", st.session_state.항목_학과[0], st.session_state.항목_학년[0], "", st.session_state.항목_파트[0], "x", "x", "", "", "", ""]], columns=부원항목)
        추가표 = st.data_editor(기본행, column_config={
            "학과": st.column_config.SelectboxColumn(options=st.session_state.항목_학과),
            "학년": st.column_config.SelectboxColumn(options=st.session_state.항목_학년),
            "파트": st.column_config.SelectboxColumn(options=st.session_state.항목_파트),
            "통학여부": st.column_config.SelectboxColumn(options=st.session_state.항목_통학),
            "회비여부": st.column_config.SelectboxColumn(options=st.session_state.항목_회비)
        }, use_container_width=True, key="add_member")
        
        if st.button("명단에 부원 추가"):
            if str(추가표.iloc[0,0]).strip():
                st.session_state.부원자료 = pd.concat([st.session_state.부원자료, 추가표], ignore_index=True)
                자료저장(); st.rerun()
            else: st.error("이름을 적어주세요.")
        
        st.subheader("📝 전체 명단 수정 및 삭제")
        수정표 = st.data_editor(st.session_state.부원자료, use_container_width=True, num_rows="dynamic", key="edit_member")
        if st.button("명단 수정 내용 저장"):
            st.session_state.부원자료 = 수정표.fillna("")
            자료저장(); st.success("전체 명단이 업데이트되었습니다."); st.rerun()
