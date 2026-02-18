import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime

# 1. 필수 기본 설정 (NameError 방지)
st.set_page_config(page_title="시간표", layout="wide")

시간대 = [f"{i}시({i-8}교시)" for i in range(9, 24)]
요일 = ["월", "화", "수", "목", "금"]
부원항목 = ["이름", "학번", "학과", "학년", "전화번호", "파트", "통학여부", "회비여부", "개요1", "개요2", "개요3", "개요4"]

# 2. 구글 시트 연결 (보안 설정)
@st.cache_resource
def 구글문서연결():
    접속권한 = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    신분증 = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=접속권한)
    연결망 = gspread.authorize(신분증)
    return 연결망.open("동아리_DB").sheet1

시트 = 구글문서연결()

# 3. 팀별 데이터 관리 로직
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
    # 모든 정보를 시트의 A~H열에 맞춰 저장
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
    
    새데이터 = [st.session_state["방번호"], st.session_state["팀이름"], 방자료_json, 부원자료_json, 개인db_json, 설정_json, 게시판_json, 채팅_json]
    줄번호, _ = 방찾기(st.session_state["방번호"])
    
    if 줄번호:
        시트.update(values=[새데이터], range_name=f"A{줄번호}:H{줄번호}")
    else:
        시트.append_row(새데이터)

# 4. 입장 시스템 및 세션 초기화
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
                st.session_state.db = {n: pd.read_json(p).fillna("") for n, p in json.loads(데이터[4]).items()}
                s = json.loads(데이터[5])
                st.session_state.항목_학과 = s.get("학과", ["물리치료학과", "기타학과"])
                st.session_state.항목_학년 = s.get("학년", ["1", "2", "3", "4"])
                st.session_state.항목_파트 = s.get("파트", ["보컬", "보컬2", "기타1", "기타2", "통기타", "베이스", "드럼", "키보드", "기타악기"])
                st.session_state.항목_통학 = s.get("통학", ["o", "x"])
                st.session_state.항목_회비 = s.get("회비", ["o", "x"])
                st.session_state.비밀번호 = s.get("비밀번호", "0000")
                st.session_state.게시판 = json.loads(데이터[6]) if len(데이터) > 6 else []
                st.session_state.채팅 = json.loads(데이터[7]) if len(데이터) > 7 else []
                st.session_state.인증완료, st.session_state.새로고침번호 = False, 0
                st.rerun()
            else: st.error("방을 찾을 수 없습니다.")

    with 생성탭:
        새번호, 새이름 = st.text_input("식별번호"), st.text_input("팀 이름")
        if st.button("방 만들기"):
            줄, _ = 방찾기(새번호)
            if 줄: st.error("이미 있는 번호입니다.")
            elif 새번호 and 새이름:
                st.session_state.update({"방번호": 새번호, "팀이름": 새이름, "db": {}, "room_db": pd.DataFrame("", index=시간대, columns=요일), "부원자료": pd.DataFrame(columns=부원항목), "게시판": [], "채팅": [], "항목_학과": ["물리치료학과", "기타학과"], "항목_학년": ["1", "2", "3", "4"], "항목_파트": ["보컬", "보컬2", "기타1", "기타2", "통기타", "베이스", "드럼", "키보드", "기타악기"], "항목_통학": ["o", "x"], "항목_회비": ["o", "x"], "비밀번호": "0000", "인증완료": False, "새로고침번호": 0})
                자료저장(); st.rerun()
    st.stop()

# 5. 메인 화면 UI
st.markdown(f"<h1>통합 관리 화면 <span style='font-size: 0.5em; background-color: #f0f2f6; padding: 5px 10px; border-radius: 10px; color: black;'>{st.session_state['팀이름']}</span></h1>", unsafe_allow_html=True)
if st.button("로그아웃"): st.session_state["방번호"] = ""; st.rerun()

탭1, 탭2, 탭3, 탭4, 탭5, 탭6 = st.tabs(["동아리방 관리", "개인 시간표 확인", "시간표 등록", "부원 정보 관리", "공지 게시판", "익명 채팅방"])

with 탭1:
    st.header("동아리방 시간표 관리")
    새방 = st.data_editor(st.session_state.room_db, use_container_width=True, key=f"r_{st.session_state.새로고침번호}")
    if st.button("방 시간표 저장"): st.session_state.room_db = 새방.fillna(""); 자료저장(); st.rerun()

with 탭2:
    st.header("부원 시간표 및 공강 확인")
    if st.session_state.db:
        선택 = st.multiselect("부원 선택", list(st.session_state.db.keys()))
        if len(선택) >= 2:
            공통 = pd.DataFrame("", index=시간대, columns=요일)
            for t in 시간대:
                for d in 요일:
                    값들 = [str(st.session_state.db[b].loc[t, d]).strip() for b in 선택 if str(st.session_state.db[b].loc[t, d]).strip()]
                    if len(값들) == len(선택) and len(set(값들)) == 1: 공통.loc[t, d] = 값들[0]
                    elif 값들: 공통.loc[t, d] = " "
            def 색(v): return "background-color: #d3d3d3; color: #d3d3d3" if v == " " else ("background-color: #FFF2CC; color: black" if v != "" else "")
            st.dataframe(공통.style.map(색), use_container_width=True)

with 탭3:
    st.header("부원 개인 시간표 등록")
    이름들 = ["새로 입력"] + sorted(list(st.session_state.db.keys()))
    선택명 = st.selectbox("이름 선택", 이름들, key=f"n_{st.session_state.새로고침번호}")
    입력명 = st.text_input("새 이름") if 선택명 == "새로 입력" else 선택명
    기존 = st.session_state.db[입력명].copy() if 입력명 in st.session_state.db else pd.DataFrame("", index=시간대, columns=요일)
    새표 = st.data_editor(기존, use_container_width=True, key=f"s_{st.session_state.새로고침번호}")
    if st.button("개인 시간표 저장"):
        if 입력명: st.session_state.db[입력명] = 새표.fillna(""); 자료저장(); st.rerun()

with 탭4:
    st.header("부원 정보 관리")
    if not st.session_state.인증완료:
        if st.text_input("비밀번호", type="password") == st.session_state.비밀번호:
            if st.button("인증"): st.session_state.인증완료 = True; st.rerun()
    else:
        if st.button("잠금"): st.session_state.인증완료 = False; st.rerun()
        with st.expander("⚙️ 설정"):
            st.write("자유 항목 이름 변경")
            현재항목 = st.session_state.부원자료.columns[-4:]
            c1, c2, c3, c4 = st.columns(4)
            새이름일 = c1.text_input("첫 번째", 현재항목[0])
            새이름이 = c2.text_input("두 번째", 현재항목[1])
            새이름삼 = c3.text_input("세 번째", 현재항목[2])
            새이름사 = c4.text_input("네 번째", 현재항목[3])
            if st.button("항목 이름 적용"):
                규칙 = {현재항목[0]: 새이름일, 현재항목[1]: 새이름이, 현재항목[2]: 새이름삼, 현재항목[3]: 새이름사}
                st.session_state.부원자료 = st.session_state.부원자료.rename(columns=규칙)
                자료저장(); st.rerun()
            st.divider()
            st.write("선택창 리스트 변경")
            sc1, sc2 = st.columns(2)
            st.session_state.항목_학과 = [x.strip() for x in sc1.text_input("학과 리스트", ", ".join(st.session_state.항목_학과)).split(",") if x.strip()]
            st.session_state.항목_파트 = [x.strip() for x in sc1.text_input("파트 리스트", ", ".join(st.session_state.항목_파트)).split(",") if x.strip()]
            st.session_state.항목_학년 = [x.strip() for x in sc2.text_input("학년 리스트", ", ".join(st.session_state.항목_학년)).split(",") if x.strip()]
            st.session_state.비밀번호 = sc2.text_input("비번 변경", st.session_state.비밀번호)
            if st.button("리스트 및 비번 저장"): 자료저장(); st.rerun()

        st.subheader("새 부원 추가 및 명단 수정")
        st.session_state.새부원표 = pd.DataFrame([["", "", st.session_state.항목_학과[0], st.session_state.항목_학년[0], "", st.session_state.항목_파트[0], "x", "x", "", "", "", ""]], columns=st.session_state.부원자료.columns)
        추가 = st.data_editor(st.session_state.새부원표, column_config={"학과": st.column_config.SelectboxColumn(options=st.session_state.항목_학과), "학년": st.column_config.SelectboxColumn(options=st.session_state.항목_학년), "파트": st.column_config.SelectboxColumn(options=st.session_state.항목_파트)}, use_container_width=True, key="add")
        if st.button("명단 추가"):
            if str(추가.iloc[0,0]).strip():
                st.session_state.부원자료 = pd.concat([st.session_state.부원자료, 추가], ignore_index=True); 자료저장(); st.rerun()
        
        수정 = st.data_editor(st.session_state.부원자료, use_container_width=True, num_rows="dynamic", key="edit")
        if st.button("명단 전체 저장"): st.session_state.부원자료 = 수정.fillna(""); 자료저장(); st.rerun()

with 탭5:
    st.header("📌 공지 게시판")
    with st.expander("📝 새 글 쓰기 (비번 필수)"):
        제목 = st.text_input("제목", key="post_t")
        내용 = st.text_area("내용", key="post_b")
        비번 = st.text_input("관리자 비번", type="password", key="post_p")
        if st.button("등록"):
            if 비번 == st.session_state.비밀번호 and 제목 and 내용:
                st.session_state.게시판.insert(0, {"날짜": datetime.now().strftime("%Y-%m-%d %H:%M"), "제목": 제목, "내용": 내용})
                자료저장(); st.rerun()
    for idx, 글 in enumerate(st.session_state.게시판):
        st.info(f"**[{글['날짜']}] {글['제목']}**\n\n{글['내용']}")
        if st.session_state.인증완료 and st.button(f"삭제 {idx}"): st.session_state.게시판.pop(idx); 자료저장(); st.rerun()

with 탭6:
    st.header("💬 익명 채팅방")
    for 대화 in st.session_state.채팅[-20:]: st.write(f"**[{대화['시간']}] {대화['닉']}**: {대화['메시지']}")
    st.write("---")
    c1, c2 = st.columns([1, 4])
    닉 = c1.text_input("별명", value="익명", key="c_n")
    메 = c2.text_input("메시지", key="c_m")
    if st.button("전송"):
        if 메: st.session_state.채팅.append({"시간": datetime.now().strftime("%H:%M"), "닉": 닉, "메시지": 메}); 자료저장(); st.rerun()
