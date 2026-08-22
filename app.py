import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime

# 1. 필수 기본 설정
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

# 3. 데이터 스키마 및 기본 구조 방어 엔진
def 빈_시간표():
    return pd.DataFrame("", index=시간대, columns=요일)

def 시간표_복원(데이터_딕셔너리):
    if not isinstance(데이터_딕셔너리, dict):
        return 빈_시간표()
    return pd.DataFrame.from_dict(데이터_딕셔너리).reindex(index=시간대, columns=요일).fillna("")

def 기본_방_상태(방번호="", 팀이름=""):
    return {
        "방번호": 방번호,
        "팀이름": 팀이름,
        "room_db": 빈_시간표(),
        "부원자료": pd.DataFrame(columns=부원항목),
        "db": {},
        "설정": {
            "학과": ["물리치료학과", "기타학과"],
            "학년": ["1", "2", "3", "4"],
            "파트": ["보컬", "보컬2", "기타1", "기타2", "통기타", "베이스", "드럼", "키보드", "기타악기"],
            "통학": ["o", "x"],
            "회비": ["o", "x"],
            "비밀번호": "0000"
        },
        "게시판": [],
        "곡정보": {},
        "메모장": "",
        "채팅": {}
    }

def 방찾기(번호):
    try:
        모든데이터 = 시트.get_all_values()
        for i, 줄 in enumerate(모든데이터):
            if 줄 and len(줄) > 0 and str(줄[0]).strip() == str(번호).strip():
                return i + 1, 줄 
        return None, None
    except Exception:
        return None, None

def 데이터_동기화(방번호):
    줄번호, 데이터 = 방찾기(방번호)
    if not 줄번호:
        return False
    
    기본 = 기본_방_상태(데이터[0], 데이터[1] if len(데이터) > 1 else "")
    
    def 안전파싱(idx, fallback):
        if len(데이터) > idx and 데이터[idx].strip():
            try:
                return json.loads(데이터[idx])
            except Exception:
                return fallback
        return fallback

    기본["room_db"] = 시간표_복원(안전파싱(2, {}))
    
    부원_목록 = 안전파싱(3, [])
    if isinstance(부원_목록, list):
        기본["부원자료"] = pd.DataFrame(부원_목록).reindex(columns=부원항목).fillna("")
    
    개인시간표_딕셔너리 = 안전파싱(4, {})
    if isinstance(개인시간표_딕셔너리, dict):
        기본["db"] = {n: 시간표_복원(p) for n, p in 개인시간표_딕셔너리.items() if isinstance(p, dict)}
    
    불러온설정 = 안전파싱(5, {})
    if isinstance(불러온설정, dict):
        기본["설정"].update(불러온설정)
        
    기본["게시판"] = 안전파싱(6, [])
    기본["곡정보"] = 안전파싱(7, {})
    기본["메모장"] = 데이터[8] if len(데이터) > 8 else ""
    기본["채팅"] = 안전파싱(9, {})

    st.session_state.방정보 = 기본
    return True

def 자료저장():
    상태 = st.session_state.방정보
    
    방자료 = json.dumps(상태["room_db"].to_dict(), ensure_ascii=False, separators=(',', ':'))
    부원자료 = json.dumps(상태["부원자료"].to_dict('records'), ensure_ascii=False, separators=(',', ':'))
    개인db = json.dumps({이름: 표.to_dict() for 이름, 표 in 상태["db"].items()}, ensure_ascii=False, separators=(',', ':'))
    설정 = json.dumps(상태["설정"], ensure_ascii=False, separators=(',', ':'))
    게시판 = json.dumps(상태["게시판"], ensure_ascii=False, separators=(',', ':'))
    곡정보 = json.dumps(상태["곡정보"], ensure_ascii=False, separators=(',', ':'))
    메모장 = 상태["메모장"]
    
    for 곡 in 상태["채팅"]:
        상태["채팅"][곡] = 상태["채팅"][곡][-100:]
    채팅 = json.dumps(상태["채팅"], ensure_ascii=False, separators=(',', ':'))
    
    새데이터 = [상태["방번호"], 상태["팀이름"], 방자료, 부원자료, 개인db, 설정, 게시판, 곡정보, 메모장, 채팅]
    줄번호, _ = 방찾기(상태["방번호"])
    
    if 줄번호:
        시트.update(range_name=f"A{줄번호}:J{줄번호}", values=[새데이터], value_input_option="RAW")
    else:
        시트.append_row(새데이터, value_input_option="RAW")

# 4. 방 입장 및 세션 초기화
if "방정보" not in st.session_state:
    st.session_state.방정보 = None
if "인증완료" not in st.session_state:
    st.session_state.인증완료 = False
if "temp_선택" not in st.session_state:
    st.session_state.temp_선택 = []

if st.session_state.방정보 is None:
    입장탭, 생성탭 = st.tabs(["시간표 방 접속하기", "새로운 팀 방 만들기"])
    
    with 입장탭:
        입력번호 = st.text_input("팀 식별번호")
        if st.button("입장하기"):
            if 입력번호 and 데이터_동기화(입력번호):
                st.session_state.인증완료 = False
                st.rerun()
            else:
                st.error("방을 찾을 수 없거나 데이터 동기화에 실패했습니다.")

    with 생성탭:
        새번호, 새이름 = st.text_input("새 식별번호"), st.text_input("팀 이름")
        if st.button("방 만들기"):
            if 새번호 and 새이름:
                줄, _ = 방찾기(새번호)
                if 줄:
                    st.error("이미 존재하는 식별번호입니다.")
                else:
                    st.session_state.방정보 = 기본_방_상태(새번호, 새이름)
                    자료저장()
                    st.rerun()
            else:
                st.warning("식별번호와 팀 이름을 모두 입력하십시오.")
    st.stop()

# 5. 메인 UI
상태 = st.session_state.방정보
st.markdown(f"<h1>통합 관리 화면 <span style='font-size: 0.5em; background-color: #f0f2f6; padding: 5px 10px; border-radius: 10px; color: black;'>{상태['팀이름']}</span></h1>", unsafe_allow_html=True)
if st.button("로그아웃"):
    st.session_state.방정보 = None
    st.rerun()

탭1, 탭2, 탭3, 탭4, 탭5, 탭6, 탭7 = st.tabs(["동아리방 관리", "개인 시간표 및 곡 관리", "시간표 등록", "부원 정보 관리", "공지 게시판", "메모장", "팀별 채팅방"])

with 탭1:
    st.header("동아리방 시간표 관리")
    st.dataframe(상태["room_db"], use_container_width=True)
    
    st.subheader("일정 개별 추가/삭제")
    c1, c2, c3 = st.columns([1, 1, 2])
    선택요일 = c1.selectbox("요일", 요일, key="r_day")
    선택시간 = c2.selectbox("시간", 시간대, key="r_time")
    입력내용 = c3.text_input("일정 내용 (비우고 업데이트 시 삭제)", key="r_val")
    
    if st.button("동아리방 일정 업데이트"):
        데이터_동기화(상태["방번호"])
        st.session_state.방정보["room_db"].loc[선택시간, 선택요일] = 입력내용
        자료저장()
        st.success("반영되었습니다.")
        st.rerun()

with 탭2:
    st.header("부원 시간표 및 곡별 멤버 확인")
    with st.expander("🎸 곡별 참여 멤버 설정"):
        c1, c2 = st.columns([1, 2])
        곡이름 = c1.text_input("곡 이름")
        참여멤버 = c2.multiselect("멤버 선택", list(상태["db"].keys()))
        if st.button("곡 멤버 정보 저장"):
            if 곡이름 and 참여멤버:
                데이터_동기화(상태["방번호"])
                st.session_state.방정보["곡정보"][곡이름] = 참여멤버
                자료저장()
                st.success(f"'{곡이름}' 저장 완료")
                st.rerun()
            else:
                st.warning("곡 이름과 멤버를 입력하십시오.")
        
        if 상태["곡정보"]:
            st.divider()
            for 곡, 멤버들 in list(상태["곡정보"].items()):
                sc1, sc2 = st.columns([4, 1])
                sc1.write(f"**{곡}**: {', '.join(멤버들)}")
                if sc2.button("삭제", key=f"del_{곡}"):
                    데이터_동기화(상태["방번호"])
                    if 곡 in st.session_state.방정보["곡정보"]:
                        del st.session_state.방정보["곡정보"][곡]
                        자료저장()
                    st.rerun()

    if 상태["db"]:
        st.subheader("시간표 확인")
        if 상태["곡정보"]:
            st.write("곡 바로가기:")
            btn_cols = st.columns(max(min(len(상태["곡정보"]), 5), 1))
            for i, 곡 in enumerate(상태["곡정보"].keys()):
                if btn_cols[i % 5].button(곡, key=f"btn_{곡}"):
                    st.session_state.temp_선택 = 상태["곡정보"][곡]
                    st.rerun()

        선택 = st.multiselect("확인할 부원 선택", list(상태["db"].keys()), default=st.session_state.temp_선택)
        
        if len(선택) == 1:
            st.dataframe(상태["db"][선택[0]], use_container_width=True)
        elif len(선택) >= 2:
            공통 = 빈_시간표()
            for t in 시간대:
                for d in 요일:
                    값들 = [str(상태["db"][b].loc[t, d]).strip() for b in 선택 if b in 상태["db"] and str(상태["db"][b].loc[t, d]).strip()]
                    if len(값들) == len(선택) and len(set(값들)) == 1:
                        공통.loc[t, d] = 값들[0]
                    elif 값들:
                        공통.loc[t, d] = " "
            
            def 색(v):
                if v == " ": return "background-color: #d3d3d3; color: #d3d3d3"
                if v != "": return "background-color: #FFF2CC; color: black"
                return ""
            st.dataframe(공통.style.map(색), use_container_width=True)
            
        if len(선택) >= 1:
            st.divider()
            st.subheader("선택 부원 일정 일괄 추가/삭제")
            열일, 열이, 열삼 = st.columns([1, 1, 2])
            선택_요일 = 열일.selectbox("요일", 요일, key="m_day")
            선택_시간 = 열이.selectbox("시간", 시간대, key="m_time")
            입력_내용 = 열삼.text_input("일정 내용", key="m_val")
            
            b1, b2 = st.columns(2)
            with b1:
                if st.button("일정 일괄 추가"):
                    if 입력_내용:
                        데이터_동기화(상태["방번호"])
                        for 부원 in 선택:
                            if 부원 in st.session_state.방정보["db"]:
                                st.session_state.방정보["db"][부원].loc[선택_시간, 선택_요일] = 입력_내용
                        st.session_state.방정보["room_db"].loc[선택_시간, 선택_요일] = 입력_내용
                        자료저장()
                        st.rerun()
                    else:
                        st.warning("일정 내용을 입력하십시오.")
            with b2:
                if st.button("해당 시간 일정 일괄 삭제"):
                    데이터_동기화(상태["방번호"])
                    for 부원 in 선택:
                        if 부원 in st.session_state.방정보["db"]:
                            st.session_state.방정보["db"][부원].loc[선택_시간, 선택_요일] = ""
                    st.session_state.방정보["room_db"].loc[선택_시간, 선택_요일] = ""
                    자료저장()
                    st.rerun()
    else:
        st.info("등록된 부원 시간표가 없습니다.")

with 탭3:
    st.header("부원 개인 시간표 등록")
    이름목록 = ["새로 입력"] + sorted(list(상태["db"].keys()))
    선택명 = st.selectbox("부원 선택", 이름목록)
    
    입력명 = st.text_input("새 이름") if 선택명 == "새로 입력" else 선택명
    if 입력명:
        if 입력명 in 상태["db"]:
            st.dataframe(상태["db"][입력명], use_container_width=True)
        else:
            st.info(f"'{입력명}' 부원의 시간표가 비어 있습니다. 아래에서 일정을 등록하십시오.")
            
        st.subheader("개별 일정 등록")
        fc1, fc2, fc3 = st.columns([1, 1, 2])
        개인요일 = fc1.selectbox("요일 선택", 요일, key="p_day")
        개인시간 = fc2.selectbox("시간 선택", 시간대, key="p_time")
        개인내용 = fc3.text_input("내용 (비우고 저장 시 삭제)", key="p_val")
        
        sb1, sb2 = st.columns(2)
        with sb1:
            if st.button("개인 일정 저장"):
                데이터_동기화(상태["방번호"])
                if 입력명 not in st.session_state.방정보["db"]:
                    st.session_state.방정보["db"][입력명] = 빈_시간표()
                st.session_state.방정보["db"][입력명].loc[개인시간, 개인요일] = 개인내용
                자료저장()
                st.success("저장 완료")
                st.rerun()
        with sb2:
            if 선택명 != "새로 입력" and st.button(f"'{선택명}' 시간표 데이터 삭제"):
                데이터_동기화(상태["방번호"])
                if 선택명 in st.session_state.방정보["db"]:
                    del st.session_state.방정보["db"][선택명]
                자료저장()
                st.rerun()

with 탭4:
    st.header("부원 정보 관리")
    if not st.session_state.인증완료:
        입력비번 = st.text_input("관리자 비밀번호", type="password")
        if st.button("인증"):
            if 입력비번 == 상태["설정"]["비밀번호"]:
                st.session_state.인증완료 = True
                st.rerun()
            else:
                st.error("비밀번호 불일치")
    else:
        if st.button("잠금"):
            st.session_state.인증완료 = False
            st.rerun()
            
        with st.expander("⚙️ 항목 설정"):
            현재항목 = 상태["부원자료"].columns[-4:] if len(상태["부원자료"].columns) >= 4 else 부원항목[-4:]
            c1, c2, c3, c4 = st.columns(4)
            새이름 = [c1.text_input("개요1 명칭", 현재항목[0]), c2.text_input("개요2 명칭", 현재항목[1]), c3.text_input("개요3 명칭", 현재항목[2]), c4.text_input("개요4 명칭", 현재항목[3])]
            if st.button("개요 명칭 변경"):
                데이터_동기화(상태["방번호"])
                st.session_state.방정보["부원자료"] = st.session_state.방정보["부원자료"].rename(columns=dict(zip(현재항목, 새이름)))
                자료저장()
                st.rerun()
            
            st.divider()
            sc1, sc2 = st.columns(2)
            st.session_state.방정보["설정"]["학과"] = [x.strip() for x in sc1.text_input("학과 리스트 (쉼표 구분)", ", ".join(상태["설정"]["학과"])).split(",") if x.strip()]
            st.session_state.방정보["설정"]["파트"] = [x.strip() for x in sc1.text_input("파트 리스트", ", ".join(상태["설정"]["파트"])).split(",") if x.strip()]
            st.session_state.방정보["설정"]["학년"] = [x.strip() for x in sc2.text_input("학년 리스트", ", ".join(상태["설정"]["학년"])).split(",") if x.strip()]
            st.session_state.방정보["설정"]["비밀번호"] = sc2.text_input("비밀번호 변경", 상태["설정"]["비밀번호"])
            if st.button("설정 저장"):
                데이터_동기화(상태["방번호"])
                자료저장()
                st.rerun()

        st.subheader("부원 명단 관리")
        부원리스트 = 상태["부원자료"]["이름"].tolist() if "이름" in 상태["부원자료"].columns else []
        선택_편집 = st.selectbox("부원 선택", ["새 부원 추가"] + 부원리스트)
        
        기존값 = {col: "" for col in 부원항목}
        if 선택_편집 != "새 부원 추가" and "이름" in 상태["부원자료"].columns:
            매칭 = 상태["부원자료"][상태["부원자료"]["이름"] == 선택_편집]
            if not 매칭.empty:
                기존값 = 매칭.iloc[0].to_dict()

        c1, c2, c3, c4 = st.columns(4)
        입력_이름 = c1.text_input("이름 (필수)", 기존값.get("이름", ""))
        입력_학번 = c2.text_input("학번", 기존값.get("학번", ""))
        
        학과_idx = 상태["설정"]["학과"].index(기존값["학과"]) if 기존값.get("학과") in 상태["설정"]["학과"] else 0
        입력_학과 = c3.selectbox("학과", 상태["설정"]["학과"], index=학과_idx)
        
        학년_idx = 상태["설정"]["학년"].index(기존값["학년"]) if 기존값.get("학년") in 상태["설정"]["학년"] else 0
        입력_학년 = c4.selectbox("학년", 상태["설정"]["학년"], index=학년_idx)

        c5, c6, c7, c8 = st.columns(4)
        입력_전화 = c5.text_input("전화번호", 기존값.get("전화번호", ""))
        
        파트_idx = 상태["설정"]["파트"].index(기존값["파트"]) if 기존값.get("파트") in 상태["설정"]["파트"] else 0
        입력_파트 = c6.selectbox("파트", 상태["설정"]["파트"], index=파트_idx)
        
        통학_idx = 상태["설정"]["통학"].index(기존값["통학여부"]) if 기존값.get("통학여부") in 상태["설정"]["통학"] else 0
        입력_통학 = c7.selectbox("통학여부", 상태["설정"]["통학"], index=통학_idx)
        
        회비_idx = 상태["설정"]["회비"].index(기존값["회비여부"]) if 기존값.get("회비여부") in 상태["설정"]["회비"] else 0
        입력_회비 = c8.selectbox("회비여부", 상태["설정"]["회비"], index=회비_idx)

        c9, c10, c11, c12 = st.columns(4)
        항목명 = 상태["부원자료"].columns[-4:] if len(상태["부원자료"].columns) >= 4 else 부원항목[-4:]
        개요값 = [c9.text_input(항목명[0], 기존값.get(항목명[0], "")), c10.text_input(항목명[1], 기존값.get(항목명[1], "")), c11.text_input(항목명[2], 기존값.get(항목명[2], "")), c12.text_input(항목명[3], 기존값.get(항목명[3], ""))]

        mb1, mb2 = st.columns(2)
        with mb1:
            if st.button("부원 정보 저장"):
                if 입력_이름.strip():
                    데이터_동기화(상태["방번호"])
                    새_행 = {"이름": 입력_이름, "학번": 입력_학번, "학과": 입력_학과, "학년": 입력_학년, "전화번호": 입력_전화, "파트": 입력_파트, "통학여부": 입력_통학, "회비여부": 입력_회비, 항목명[0]: 개요값[0], 항목명[1]: 개요값[1], 항목명[2]: 개요값[2], 항목명[3]: 개요값[3]}
                    
                    if 선택_편집 != "새 부원 추가" and 선택_편집 != 입력_이름:
                        if 선택_편집 in st.session_state.방정보["db"]:
                            st.session_state.방정보["db"][입력_이름] = st.session_state.방정보["db"].pop(선택_편집)
                        for k in st.session_state.방정보["곡정보"]:
                            st.session_state.방정보["곡정보"][k] = [입력_이름 if x == 선택_편집 else x for x in st.session_state.방정보["곡정보"][k]]
                    
                    기존_인덱스 = st.session_state.방정보["부원자료"][st.session_state.방정보["부원자료"]["이름"] == 선택_편집].index if "이름" in st.session_state.방정보["부원자료"].columns else pd.Index([])
                    if not 기존_인덱스.empty:
                        for k, v in 새_행.items():
                            st.session_state.방정보["부원자료"].at[기존_인덱스[0], k] = v
                    else:
                        st.session_state.방정보["부원자료"] = pd.concat([st.session_state.방정보["부원자료"], pd.DataFrame([새_행])], ignore_index=True)
                    
                    자료저장()
                    st.success("부원 정보 저장 완료")
                    st.rerun()
                else:
                    st.warning("이름은 필수 입력 항목입니다.")
        with mb2:
            if 선택_편집 != "새 부원 추가" and st.button("부원 삭제", type="primary"):
                데이터_동기화(상태["방번호"])
                if "이름" in st.session_state.방정보["부원자료"].columns:
                    st.session_state.방정보["부원자료"] = st.session_state.방정보["부원자료"][st.session_state.방정보["부원자료"]["이름"] != 선택_편집]
                if 선택_편집 in st.session_state.방정보["db"]:
                    del st.session_state.방정보["db"][선택_편집]
                for k in st.session_state.방정보["곡정보"]:
                    st.session_state.방정보["곡정보"][k] = [x for x in st.session_state.방정보["곡정보"][k] if x != 선택_편집]
                자료저장()
                st.rerun()

with 탭5:
    st.header("📌 공지 게시판")
    with st.expander("📝 새 글 작성"):
        제목, 내용 = st.text_input("제목"), st.text_area("내용")
        비번 = st.text_input("비밀번호", type="password", key="notice_pw")
        if st.button("공지 등록"):
            if 비번 == 상태["설정"]["비밀번호"] and 제목 and 내용:
                데이터_동기화(상태["방번호"])
                st.session_state.방정보["게시판"].insert(0, {"날짜": datetime.now().strftime("%Y-%m-%d %H:%M"), "제목": 제목, "내용": 내용})
                자료저장()
                st.rerun()
            else:
                st.error("비밀번호가 틀렸거나 내용이 비어 있습니다.")
                
    for idx, 글 in enumerate(상태["게시판"]):
        st.info(f"**[{글['날짜']}] {글['제목']}**\n\n{글['내용']}")
        if st.session_state.인증완료 and st.button(f"삭제 {idx}"):
            데이터_동기화(상태["방번호"])
            st.session_state.방정보["게시판"].pop(idx)
            자료저장()
            st.rerun()

with 탭6:
    st.header("📝 팀 공용 메모장")
    메모 = st.text_area("내용", value=상태["메모장"], height=400)
    if st.button("메모 저장"):
        데이터_동기화(상태["방번호"])
        st.session_state.방정보["메모장"] = 메모
        자료저장()
        st.success("메모 저장 완료")
        st.rerun()

with 탭7:
    st.header("💬 곡(팀)별 채팅방")
    if not 상태["곡정보"]:
        st.info("설정된 곡 정보가 없습니다.")
    else:
        곡 = st.selectbox("채팅방 선택", list(상태["곡정보"].keys()))
        c1, c2, c3 = st.columns([2, 2, 1])
        챗이름 = c1.text_input("이름")
        챗파트 = c2.selectbox("파트", 상태["설정"]["파트"])
        if c3.button("입장"):
            if 챗이름:
                st.session_state.chat_user = f"{챗이름}({챗파트})"
        
        if st.session_state.get("chat_user"):
            st.write(f"접속자: **{st.session_state.chat_user}**")
            if st.button("🔄 새로고침"):
                데이터_동기화(상태["방번호"])
                st.rerun()
            
            st.divider()
            if 곡 not in 상태["채팅"]:
                상태["채팅"][곡] = []
            
            채팅창 = st.container(height=350)
            for c in 상태["채팅"][곡]:
                채팅창.markdown(f"**{c['작성자']}** <span style='font-size:0.8em;color:gray;'>{c['시간']}</span><br>{c['메시지']}", unsafe_allow_html=True)
                
            입력메시지 = st.chat_input("메시지 입력")
            if 입력메시지:
                데이터_동기화(상태["방번호"])
                if 곡 not in st.session_state.방정보["채팅"]:
                    st.session_state.방정보["채팅"][곡] = []
                st.session_state.방정보["채팅"][곡].append({
                    "작성자": st.session_state.chat_user,
                    "시간": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "메시지": 입력메시지
                })
                자료저장()
                st.rerun()
