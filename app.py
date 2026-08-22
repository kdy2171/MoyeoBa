import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime

# 1. 필수 기본 설정
st.set_page_config(page_title="시간표", layout="wide")

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

# 3. 데이터 관리 및 동시성 제어 로직
def 방찾기(번호):
    try:
        모든데이터 = 시트.get_all_values()
        for i, 줄 in enumerate(모든데이터):
            if 줄[0] == 번호:
                return i + 1, 줄 
        return None, None
    except:
        return None, None

def 최신_데이터_동기화(방번호):
    """저장 직전 서버의 최신 데이터를 불러와 세션과 병합하여 Race Condition 방지"""
    줄번호, 데이터 = 방찾기(방번호)
    if not 줄번호: return False
    
    st.session_state.room_db = pd.DataFrame.from_dict(json.loads(데이터[2])).reindex(index=시간대, columns=요일).fillna("") if 데이터[2] else pd.DataFrame("", index=시간대, columns=요일)
    st.session_state.부원자료 = pd.DataFrame.from_dict(json.loads(데이터[3])).fillna("") if 데이터[3] else pd.DataFrame(columns=부원항목)
    
    임시db = json.loads(데이터[4]) if 데이터[4] else {}
    st.session_state.db = {n: pd.DataFrame.from_dict(p).reindex(index=시간대, columns=요일).fillna("") for n, p in 임시db.items() if p}
    
    s = json.loads(데이터[5]) if 데이터[5] else {}
    st.session_state.항목_학과 = s.get("학과", ["물리치료학과", "기타학과"])
    st.session_state.항목_학년 = s.get("학년", ["1", "2", "3", "4"])
    st.session_state.항목_파트 = s.get("파트", ["보컬", "보컬2", "기타1", "기타2", "통기타", "베이스", "드럼", "키보드", "기타악기"])
    st.session_state.항목_통학, st.session_state.항목_회비, st.session_state.비밀번호 = s.get("통학", ["o","x"]), s.get("회비", ["o","x"]), s.get("비밀번호", "0000")
    
    st.session_state.게시판 = json.loads(데이터[6]) if len(데이터) > 6 and 데이터[6] else []
    st.session_state.곡정보 = json.loads(데이터[7]) if len(데이터) > 7 and 데이터[7] else {}
    st.session_state.메모장 = 데이터[8] if len(데이터) > 8 else ""
    st.session_state.채팅 = json.loads(데이터[9]) if len(데이터) > 9 and 데이터[9] else {}
    return True

def 자료저장():
    """불필요한 공백 제거(separators) 및 딕셔너리 변환으로 JSON 용량 최적화"""
    방자료 = json.dumps(st.session_state.room_db.to_dict(), ensure_ascii=False, separators=(',', ':'))
    부원자료 = json.dumps(st.session_state.부원자료.to_dict('records'), ensure_ascii=False, separators=(',', ':'))
    개인db_dict = {이름: 표.to_dict() for 이름, 표 in st.session_state.db.items()}
    개인db = json.dumps(개인db_dict, ensure_ascii=False, separators=(',', ':'))
    설정 = json.dumps({
        "학과": st.session_state.항목_학과, "학년": st.session_state.항목_학년, "파트": st.session_state.항목_파트,
        "통학": st.session_state.항목_통학, "회비": st.session_state.항목_회비, "비밀번호": st.session_state.비밀번호,
        "팀이름": st.session_state.팀이름
    }, ensure_ascii=False, separators=(',', ':'))
    게시판 = json.dumps(st.session_state.게시판, ensure_ascii=False, separators=(',', ':'))
    곡정보 = json.dumps(st.session_state.곡정보, ensure_ascii=False, separators=(',', ':'))
    메모장 = st.session_state.메모장
    
    # 채팅 용량 제한 (각 방별 최신 100개 유지)
    for 곡 in st.session_state.채팅:
        st.session_state.채팅[곡] = st.session_state.채팅[곡][-100:]
    채팅 = json.dumps(st.session_state.채팅, ensure_ascii=False, separators=(',', ':'))
    
    새데이터 = [st.session_state["방번호"], st.session_state["팀이름"], 방자료, 부원자료, 개인db, 설정, 게시판, 곡정보, 메모장, 채팅]
    줄번호, _ = 방찾기(st.session_state["방번호"])
    
    if 줄번호:
        시트.update(values=[새데이터], range_name=f"A{줄번호}:J{줄번호}", value_input_option="RAW")
    else:
        시트.append_row(새데이터, value_input_option="RAW")


# 4. 입장 및 세션 초기화
if "방번호" not in st.session_state: st.session_state["방번호"] = ""
if "팀이름" not in st.session_state: st.session_state["팀이름"] = ""

if st.session_state["방번호"] == "":
    입장탭, 생성탭 = st.tabs(["시간표 방 접속하기", "새로운 팀 방 만들기"])
    
    with 입장탭:
        입력번호 = st.text_input("팀 식별번호를 입력하세요")
        if st.button("입장하기"):
            if 최신_데이터_동기화(입력번호):
                _, 데이터 = 방찾기(입력번호)
                st.session_state["방번호"] = 데이터[0]
                st.session_state["팀이름"] = 데이터[1]
                st.session_state.인증완료 = False
                st.session_state.temp_선택 = [] 
                st.rerun()
            else: 
                st.error("방을 찾을 수 없습니다.")

    with 생성탭:
        새번호, 새이름 = st.text_input("식별번호"), st.text_input("팀 이름")
        if st.button("방 만들기"):
            줄, _ = 방찾기(새번호)
            if 줄: st.error("이미 있는 번호입니다.")
            elif 새번호 and 새이름:
                st.session_state.update({
                    "방번호": 새번호, "팀이름": 새이름, "db": {}, 
                    "room_db": pd.DataFrame("", index=시간대, columns=요일), 
                    "부원자료": pd.DataFrame(columns=부원항목), 
                    "게시판": [], "곡정보": {}, "메모장": "", "채팅": {}, "temp_선택": [],
                    "항목_학과": ["물리치료학과", "기타학과"], "항목_학년": ["1", "2", "3", "4"], 
                    "항목_파트": ["보컬", "보컬2", "기타1", "기타2", "통기타", "베이스", "드럼", "키보드", "기타악기"], 
                    "항목_통학": ["o", "x"], "항목_회비": ["o", "x"], "비밀번호": "0000", 
                    "인증완료": False
                })
                자료저장(); st.rerun()
    st.stop()

# 5. 메인 UI
st.markdown(f"<h1>통합 관리 화면 <span style='font-size: 0.5em; background-color: #f0f2f6; padding: 5px 10px; border-radius: 10px; color: black;'>{st.session_state['팀이름']}</span></h1>", unsafe_allow_html=True)
if st.button("로그아웃"): st.session_state["방번호"] = ""; st.rerun()

탭1, 탭2, 탭3, 탭4, 탭5, 탭6, 탭7 = st.tabs(["동아리방 관리", "개인 시간표 및 곡 관리", "시간표 등록", "부원 정보 관리", "공지 게시판", "메모장", "팀별 채팅방"])

with 탭1:
    st.header("동아리방 시간표 관리")
    st.dataframe(st.session_state.room_db, use_container_width=True)
    
    st.subheader("일정 개별 추가/삭제")
    c1, c2, c3 = st.columns([1, 1, 2])
    선택요일1 = c1.selectbox("요일", 요일, key="room_day")
    선택시간1 = c2.selectbox("시간", 시간대, key="room_time")
    입력내용1 = c3.text_input("일정 내용 (비우면 삭제됨)", key="room_content")
    
    if st.button("동아리방 일정 업데이트"):
        최신_데이터_동기화(st.session_state["방번호"])
        st.session_state.room_db.loc[선택시간1, 선택요일1] = 입력내용1
        자료저장()
        st.success("업데이트 되었습니다.")
        st.rerun()

with 탭2:
    st.header("부원 시간표 및 곡별 멤버 확인")
    
    with st.expander("🎸 곡별 참여 멤버 설정"):
        c1, c2 = st.columns([1, 2])
        곡이름 = c1.text_input("곡 이름")
        참여멤버 = c2.multiselect("멤버 선택", list(st.session_state.db.keys()))
        if st.button("곡 멤버 정보 저장"):
            if 곡이름 and 참여멤버:
                최신_데이터_동기화(st.session_state["방번호"])
                st.session_state.곡정보[곡이름] = 참여멤버
                자료저장(); st.success(f"'{곡이름}' 멤버 설정 완료"); st.rerun()
            else: st.warning("곡 이름과 멤버를 입력해주세요.")
        
        if st.session_state.곡정보:
            st.write("---")
            for 곡, 멤버들 in list(st.session_state.곡정보.items()):
                sc1, sc2 = st.columns([4, 1])
                sc1.write(f"**{곡}**: {', '.join(멤버들)}")
                if sc2.button("삭제", key=f"del_{곡}"):
                    최신_데이터_동기화(st.session_state["방번호"])
                    if 곡 in st.session_state.곡정보:
                        del st.session_state.곡정보[곡]
                        자료저장()
                    st.rerun()

    if st.session_state.db:
        st.subheader("시간표 확인")
        if st.session_state.곡정보:
            st.write("곡 이름을 누르면 멤버들이 자동으로 선택됩니다:")
            btn_cols = st.columns(max(min(len(st.session_state.곡정보), 5), 1))
            for i, 곡 in enumerate(st.session_state.곡정보.keys()):
                if btn_cols[i % 5].button(곡, key=f"btn_{곡}"):
                    st.session_state.temp_선택 = st.session_state.곡정보[곡]
                    st.rerun()

        선택 = st.multiselect("확인할 부원 선택", list(st.session_state.db.keys()), default=st.session_state.temp_선택)
        
        if len(선택) == 1:
            st.dataframe(st.session_state.db[선택[0]], use_container_width=True)
            
        elif len(선택) >= 2:
            공통 = pd.DataFrame("", index=시간대, columns=요일)
            for t in 시간대:
                for d in 요일:
                    값들 = [str(st.session_state.db[b].loc[t, d]).strip() for b in 선택 if str(st.session_state.db[b].loc[t, d]).strip()]
                    if len(값들) == len(선택) and len(set(값들)) == 1: 공통.loc[t, d] = 값들[0]
                    elif 값들: 공통.loc[t, d] = " "
            def 색(v): return "background-color: #d3d3d3; color: #d3d3d3" if v == " " else ("background-color: #FFF2CC; color: black" if v != "" else "")
            st.dataframe(공통.style.map(색), use_container_width=True)
            
        if len(선택) >= 1:
            st.write("---")
            st.subheader("일정 일괄/개별 추가하기")
            열일, 열이, 열삼 = st.columns([1, 1, 2])
            with 열일: 선택요일 = st.selectbox("요일", 요일)
            with 열이: 선택시간 = st.selectbox("시간", 시간대)
            with 열삼: 입력내용 = st.text_input("일정 내용")
            
            버튼1, 버튼2 = st.columns(2)
            with 버튼1:
                if st.button("선택한 부원(들)에게 일정 추가"):
                    if 입력내용:
                        최신_데이터_동기화(st.session_state["방번호"])
                        for 부원 in 선택: 
                            st.session_state.db[부원].loc[선택시간, 선택요일] = 입력내용
                        st.session_state.room_db.loc[선택시간, 선택요일] = 입력내용
                        자료저장(); st.rerun()
                    else:
                        st.warning("일정 내용을 적어주세요.")
            with 버튼2:
                if st.button("해당 시간 일정 삭제 (Clear)"):
                    최신_데이터_동기화(st.session_state["방번호"])
                    for 부원 in 선택:
                        st.session_state.db[부원].loc[선택시간, 선택요일] = ""
                    st.session_state.room_db.loc[선택시간, 선택요일] = ""
                    자료저장(); st.rerun()
    else: 
        st.info("등록된 부원 시간표가 없습니다.")

with 탭3:
    st.header("부원 개인 시간표 등록")
    이름들 = ["새로 입력"] + sorted(list(st.session_state.db.keys()))
    선택명 = st.selectbox("이름 선택", 이름들)
    
    if 선택명 == "새로 입력":
        입력명 = st.text_input("새 이름")
        if 입력명:
            st.info("이름을 입력했습니다. 아래에서 일정을 하나씩 추가하여 시간표를 구성하세요.")
    else:
        입력명 = 선택명
        st.dataframe(st.session_state.db[입력명], use_container_width=True)

    if 입력명:
        st.write("---")
        st.subheader("개별 일정 추가 및 수정")
        fc1, fc2, fc3 = st.columns([1,1,2])
        개인요일 = fc1.selectbox("요일 선택", 요일, key="p_day")
        개인시간 = fc2.selectbox("시간 선택", 시간대, key="p_time")
        개인내용 = fc3.text_input("일정 내용 (비우고 저장 시 삭제)", key="p_content")
        
        저장버튼, 삭제버튼 = st.columns(2)
        with 저장버튼:
            if st.button("해당 칸 저장"):
                최신_데이터_동기화(st.session_state["방번호"])
                if 입력명 not in st.session_state.db:
                    st.session_state.db[입력명] = pd.DataFrame("", index=시간대, columns=요일)
                st.session_state.db[입력명].loc[개인시간, 개인요일] = 개인내용
                자료저장()
                st.success("저장되었습니다.")
                st.rerun()
        with 삭제버튼:
            if 선택명 != "새로 입력" and st.button(f"'{선택명}' 부원 정보 완전히 삭제"):
                최신_데이터_동기화(st.session_state["방번호"])
                if 선택명 in st.session_state.db:
                    del st.session_state.db[선택명]
                st.session_state.부원자료 = st.session_state.부원자료[st.session_state.부원자료['이름'] != 선택명]
                for 곡, 멤버들 in st.session_state.곡정보.items():
                    if 선택명 in 멤버들: 멤버들.remove(선택명)
                자료저장(); st.rerun()

with 탭4:
    st.header("부원 정보 관리")
    if not st.session_state.인증완료:
        입력비번 = st.text_input("비밀번호", type="password")
        if st.button("인증"):
            if 입력비번 == st.session_state.비밀번호:
                st.session_state.인증완료 = True
                st.rerun()
            else:
                st.error("비밀번호가 틀렸습니다.")
    else:
        if st.button("잠금"): st.session_state.인증완료 = False; st.rerun()
        with st.expander("⚙️ 설정"):
            현재항목 = st.session_state.부원자료.columns[-4:]
            c1, c2, c3, c4 = st.columns(4)
            새이름일 = c1.text_input("첫 번째", 현재항목[0])
            새이름이 = c2.text_input("두 번째", 현재항목[1])
            새이름삼 = c3.text_input("세 번째", 현재항목[2])
            새이름사 = c4.text_input("네 번째", 현재항목[3])
            if st.button("항목 이름 적용"):
                최신_데이터_동기화(st.session_state["방번호"])
                st.session_state.부원자료 = st.session_state.부원자료.rename(columns={현재항목[0]: 새이름일, 현재항목[1]: 새이름이, 현재항목[2]: 새이름삼, 현재항목[3]: 새이름사})
                자료저장(); st.rerun()
            st.divider()
            sc1, sc2 = st.columns(2)
            st.session_state.항목_학과 = [x.strip() for x in sc1.text_input("학과 리스트", ", ".join(st.session_state.항목_학과)).split(",") if x.strip()]
            st.session_state.항목_파트 = [x.strip() for x in sc1.text_input("파트 리스트", ", ".join(st.session_state.항목_파트)).split(",") if x.strip()]
            st.session_state.항목_학년 = [x.strip() for x in sc2.text_input("학년 리스트", ", ".join(st.session_state.항목_학년)).split(",") if x.strip()]
            st.session_state.비밀번호 = sc2.text_input("비번 변경", st.session_state.비밀번호)
            if st.button("설정 저장"): 
                최신_데이터_동기화(st.session_state["방번호"])
                자료저장(); st.rerun()

        컬럼설정 = {
            "학과": st.column_config.SelectboxColumn(options=st.session_state.항목_학과),
            "학년": st.column_config.SelectboxColumn(options=st.session_state.항목_학년),
            "파트": st.column_config.SelectboxColumn(options=st.session_state.항목_파트),
            "통학여부": st.column_config.SelectboxColumn(options=st.session_state.항목_통학),
            "회비여부": st.column_config.SelectboxColumn(options=st.session_state.항목_회비)
        }

        st.subheader("새 부원 추가")
        st.session_state.새부원표 = pd.DataFrame([["", "", st.session_state.항목_학과[0], st.session_state.항목_학년[0], "", st.session_state.항목_파트[0], "x", "x", "", "", "", ""]], columns=st.session_state.부원자료.columns)
        추가 = st.data_editor(st.session_state.새부원표, column_config=컬럼설정, use_container_width=True, key="add")
        if st.button("명단 추가"):
            if str(추가.iloc[0,0]).strip():
                최신_데이터_동기화(st.session_state["방번호"])
                st.session_state.부원자료 = pd.concat([st.session_state.부원자료, 추가], ignore_index=True)
                자료저장(); st.rerun()
        
        st.subheader("명단 전체 수정")
        st.warning("⚠️ 모바일 환경 주의: 표의 글자를 수정한 뒤, 반드시 표 바깥의 빈 공간을 한 번 터치하여 커서를 없앤 후 '명단 전체 저장' 버튼을 누르세요.")
        수정 = st.data_editor(st.session_state.부원자료, column_config=컬럼설정, use_container_width=True, num_rows="dynamic", key="edit")
        if st.button("명단 전체 저장"): 
            최신_데이터_동기화(st.session_state["방번호"])
            st.session_state.부원자료 = 수정.fillna("")
            자료저장(); st.rerun()

with 탭5:
    st.header("📌 공지 게시판")
    with st.expander("📝 새 글 쓰기 (비번 필수)"):
        제목, 내용 = st.text_input("제목"), st.text_area("내용")
        비번 = st.text_input("관리자 비번", type="password")
        if st.button("등록"):
            if 비번 == st.session_state.비밀번호 and 제목 and 내용:
                최신_데이터_동기화(st.session_state["방번호"])
                st.session_state.게시판.insert(0, {"날짜": datetime.now().strftime("%Y-%m-%d %H:%M"), "제목": 제목, "내용": 내용})
                자료저장(); st.rerun()
    for idx, 글 in enumerate(st.session_state.게시판):
        st.info(f"**[{글['날짜']}] {글['제목']}**\n\n{글['내용']}")
        if st.session_state.인증완료 and st.button(f"삭제 {idx}"): 
            최신_데이터_동기화(st.session_state["방번호"])
            st.session_state.게시판.pop(idx)
            자료저장(); st.rerun()

with 탭6:
    st.header("📝 팀 공용 메모장")
    메모내용 = st.text_area("내용을 입력하고 저장 버튼을 누르세요.", value=st.session_state.메모장, height=500)
    if st.button("메모 저장"):
        최신_데이터_동기화(st.session_state["방번호"])
        st.session_state.메모장 = 메모내용
        자료저장(); st.success("메모가 안전하게 저장되었습니다."); st.rerun()

with 탭7:
    st.header("💬 곡(팀)별 채팅방")
    if not st.session_state.곡정보:
        st.info("곡별 참여 멤버가 설정되지 않았습니다. '개인 시간표 및 곡 관리' 탭에서 먼저 설정하세요.")
    else:
        곡선택 = st.selectbox("채팅방 선택", list(st.session_state.곡정보.keys()))
        
        c1, c2, c3 = st.columns([2, 2, 1])
        입력_이름 = c1.text_input("채팅에 사용할 이름")
        입력_포지션 = c2.selectbox("포지션 선택", st.session_state.항목_파트)
        
        if c3.button("채팅방 입장"):
            if 입력_이름:
                st.session_state.current_chat_user = f"{입력_이름}({입력_포지션})"
            else:
                st.warning("이름을 입력하세요.")
        
        if st.session_state.get("current_chat_user"):
            st.write(f"현재 접속 계정: **{st.session_state.current_chat_user}**")
            
            if st.button("🔄 새 메시지 확인 (새로고침)"):
                최신_데이터_동기화(st.session_state["방번호"])
                st.rerun()
            
            st.divider()
            
            if 곡선택 not in st.session_state.채팅:
                st.session_state.채팅[곡선택] = []
                
            채팅영역 = st.container(height=400)
            for 챗 in st.session_state.채팅[곡선택]:
                채팅영역.markdown(f"**{챗['작성자']}** <span style='font-size:0.8em;color:gray;'>{챗['시간']}</span><br>{챗['메시지']}", unsafe_allow_html=True)
                
            메시지 = st.chat_input("메시지를 입력하세요.")
            if 메시지:
                최신_데이터_동기화(st.session_state["방번호"])
                if 곡선택 not in st.session_state.채팅:
                    st.session_state.채팅[곡선택] = []
                    
                st.session_state.채팅[곡선택].append({
                    "작성자": st.session_state.current_chat_user,
                    "시간": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "메시지": 메시지
                })
                자료저장()
                st.rerun()
