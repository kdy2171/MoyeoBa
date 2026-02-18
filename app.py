import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json

st.set_page_config(page_title="시간표", layout="wide")
st.title("통합 시간표 관리 화면")

시간대 = [f"{i}시({i-8}교시)" for i in range(9, 24)]
요일 = ["월", "화", "수", "목", "금"]
부원항목 = ["이름", "학번", "학과", "학년", "전화번호", "파트", "통학여부", "회비여부", "개요1", "개요2", "개요3", "개요4"]

@st.cache_resource
def 구글문서연결():
    접속권한 = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    신분증 = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=접속권한)
    연결망 = gspread.authorize(신분증)
    return 연결망.open("동아리_DB").sheet1

시트 = 구글문서연결()

def 자료저장():
    방자료 = st.session_state.room_db.to_json()
    부원 = st.session_state.부원자료.to_json()
    개인 = json.dumps({이름: 표.to_json() for 이름, 표 in st.session_state.db.items()})
    설정 = json.dumps({
        "학과": st.session_state.항목_학과,
        "학년": st.session_state.항목_학년,
        "파트": st.session_state.항목_파트,
        "통학": st.session_state.항목_통학,
        "회비": st.session_state.항목_회비,
        "비밀번호": st.session_state.비밀번호
    })
    시트.update(values=[[방자료], [부원], [개인], [설정]], range_name="A1:A4")

if '초기설정완료' not in st.session_state:
    try:
        모든값 = 시트.get_all_values()
        if len(모든값) >= 4:
            st.session_state.room_db = pd.read_json(모든값[0][0]).fillna("")
            st.session_state.부원자료 = pd.read_json(모든값[1][0]).fillna("")
            임시db = json.loads(모든값[2][0])
            st.session_state.db = {이름: pd.read_json(표).fillna("") for 이름, 표 in 임시db.items()}
            설정 = json.loads(모든값[3][0])
            st.session_state.항목_학과 = 설정.get("학과", ["물리치료학과", "기타학과"])
            st.session_state.항목_학년 = 설정.get("학년", ["1", "2", "3", "4"])
            st.session_state.항목_파트 = 설정.get("파트", ["보컬", "보컬2", "기타1", "기타2", "통기타", "베이스", "드럼", "키보드", "기타악기"])
            st.session_state.항목_통학 = 설정.get("통학", ["o", "x"])
            st.session_state.항목_회비 = 설정.get("회비", ["o", "x"])
            st.session_state.비밀번호 = 설정.get("비밀번호", "0000")
        else:
            raise Exception("자료없음")
    except:
        st.session_state.db = {}
        st.session_state.room_db = pd.DataFrame("", index=시간대, columns=요일)
        st.session_state.부원자료 = pd.DataFrame(columns=부원항목)
        st.session_state.항목_학과 = ["물리치료학과", "기타학과"]
        st.session_state.항목_학년 = ["1", "2", "3", "4"]
        st.session_state.항목_파트 = ["보컬", "보컬2", "기타1", "기타2", "통기타", "베이스", "드럼", "키보드", "기타악기"]
        st.session_state.항목_통학 = ["o", "x"]
        st.session_state.항목_회비 = ["o", "x"]
        st.session_state.비밀번호 = "0000"
        자료저장()
    
    st.session_state.새부원표 = pd.DataFrame([["", "", st.session_state.항목_학과[0], "1", "", "보컬", "x", "x", "", "", "", ""]], columns=부원항목)
    st.session_state.인증완료 = False
    st.session_state.새로고침번호 = 0
    st.session_state.초기설정완료 = True

탭일, 탭이, 탭삼, 탭사 = st.tabs(["동아리방 관리", "개인 시간표 및 공강 확인", "학생 시간표 기입란", "부원 정보 관리"])

with 탭일:
    st.header("동아리방 시간표 관리")
    변경된방자료 = st.data_editor(st.session_state.room_db, use_container_width=True, key=f"방기입란_{st.session_state.새로고침번호}")
    if st.button("동아리방 시간표 저장하기"):
        st.session_state.room_db = 변경된방자료.fillna("")
        자료저장()
        st.session_state.새로고침번호 += 1
        st.rerun()

with 탭이:
    st.header("부원 시간표 및 공통 공강 확인")
    if st.session_state.db:
        선택된부원 = st.multiselect("확인할 부원을 선택하세요", list(st.session_state.db.keys()))
        
        if len(선택된부원) == 1:
            st.dataframe(st.session_state.db[선택된부원[0]], use_container_width=True)
            
        elif len(선택된부원) >= 2:
            공통시간표 = pd.DataFrame("", index=시간대, columns=요일)
            
            for 시간 in 시간대:
                for 일 in 요일:
                    모든값 = [str(st.session_state.db[부원].loc[시간, 일]).strip() for 부원 in 선택된부원]
                    의미있는값 = [값 for 값 in 모든값 if 값 != ""]
                    
                    if len(의미있는값) == 0:
                        공통시간표.loc[시간, 일] = ""
                    elif len(set(의미있는값)) == 1 and len(의미있는값) == len(선택된부원):
                        공통시간표.loc[시간, 일] = 의미있는값[0]
                    else:
                        공통시간표.loc[시간, 일] = " "

            def 배경색상적용(값):
                if 값 == " ":
                    return "background-color: #d3d3d3; color: #d3d3d3"
                elif 값 != "":
                    return "background-color: #FFF2CC; color: black"
                return "background-color: transparent"

            st.write("아래 표는 확인용입니다. 공통 일정은 표 밑에서 추가해 주세요.")
            스타일적용표 = 공통시간표.style.map(배경색상적용)
            st.dataframe(스타일적용표, use_container_width=True)
            
            st.subheader("공통 일정 추가하기")
            열일, 열이, 열삼 = st.columns([1, 1, 2])
            with 열일:
                선택요일 = st.selectbox("요일", 요일)
            with 열이:
                선택시간 = st.selectbox("시간", 시간대)
            with 열삼:
                입력내용 = st.text_input("일정 내용")
                
            if st.button("선택한 부원들에게 일정 추가"):
                if 입력내용:
                    for 부원 in 선택된부원:
                        st.session_state.db[부원].loc[선택시간, 선택요일] = 입력내용
                    st.session_state.room_db.loc[선택시간, 선택요일] = 입력내용
                    자료저장()
                    st.session_state.새로고침번호 += 1
                    st.rerun()
                else:
                    st.error("일정 내용을 적어주세요.")
    else:
        st.info("등록된 자료가 없습니다.")

with 탭삼:
    st.header("부원 시간표 등록")
    
    등록된이름목록 = sorted(list(st.session_state.db.keys()))
    선택목록 = ["새로 입력"] + 등록된이름목록

    열일, 열이 = st.columns([1, 3])
    with 열일:
        선택된이름 = st.selectbox("이름 선택", 선택목록, key=f"이름선택_{st.session_state.새로고침번호}")
        if 선택된이름 == "새로 입력":
            입력이름 = st.text_input("새 이름 입력", key=f"이름입력란_{st.session_state.새로고침번호}")
        else:
            입력이름 = 선택된이름
            st.info("기존 자료를 불러왔습니다. 수정 후 다시 저장할 수 있습니다.")

    if 입력이름 and 입력이름 in st.session_state.db:
        초기표 = st.session_state.db[입력이름].copy()
    else:
        초기표 = pd.DataFrame("", index=시간대, columns=요일)
    
    작성된표 = st.data_editor(초기표, use_container_width=True, key=f"시간표입력란_{st.session_state.새로고침번호}")
    
    if st.button("시간표 저장하기"):
        if 입력이름:
            st.session_state.db[입력이름] = 작성된표.fillna("")
            자료저장()
            st.session_state.새로고침번호 += 1
            st.rerun()
        else:
            st.error("이름을 먼저 적어주세요.")

with 탭사:
    st.header("부원 정보 관리")
    
    if not st.session_state.인증완료:
        입력암호 = st.text_input("관리자 비밀번호 네 자리를 입력하세요", type="password")
        if st.button("확인"):
            if 입력암호 == st.session_state.비밀번호:
                st.session_state.인증완료 = True
                st.rerun()
            else:
                st.error("비밀번호가 틀렸습니다.")
    else:
        상단좌측, 상단우측 = st.columns([8, 1])
        with 상단좌측:
            st.write("부원들의 개인정보를 기록하는 공간입니다.")
        with 상단우측:
            if st.button("화면 잠금"):
                st.session_state.인증완료 = False
                st.rerun()

        with st.expander("설정"):
            st.write("자유 항목 이름 변경")
            현재항목 = st.session_state.부원자료.columns[-4:]
            칸일, 칸이, 칸삼, 칸사 = st.columns(4)
            with 칸일: 새이름일 = st.text_input("첫 번째", 현재항목[0])
            with 칸이: 새이름이 = st.text_input("두 번째", 현재항목[1])
            with 칸삼: 새이름삼 = st.text_input("세 번째", 현재항목[2])
            with 칸사: 새이름사 = st.text_input("네 번째", 현재항목[3])
            
            if st.button("항목 이름 적용"):
                변경규칙 = {
                    현재항목[0]: 새이름일,
                    현재항목[1]: 새이름이,
                    현재항목[2]: 새이름삼,
                    현재항목[3]: 새이름사
                }
                st.session_state.부원자료 = st.session_state.부원자료.rename(columns=변경규칙)
                st.session_state.새부원표 = st.session_state.새부원표.rename(columns=변경규칙)
                자료저장()
                st.rerun()
                
            st.divider()
            st.write("선택창 보기 항목 추가 및 변경")
            설정열일, 설정열이 = st.columns(2)
            with 설정열일:
                입력_학과 = st.text_input("학과 (쉼표로 구분)", value=", ".join(st.session_state.항목_학과))
                입력_학년 = st.text_input("학년 (쉼표로 구분)", value=", ".join(st.session_state.항목_학년))
                입력_파트 = st.text_input("파트 (쉼표로 구분)", value=", ".join(st.session_state.항목_파트))
            with 설정열이:
                입력_통학 = st.text_input("통학여부 (쉼표로 구분)", value=", ".join(st.session_state.항목_통학))
                입력_회비 = st.text_input("회비여부 (쉼표로 구분)", value=", ".join(st.session_state.항목_회비))
            
            if st.button("보기 설정 적용"):
                st.session_state.항목_학과 = [값.strip() for 값 in 입력_학과.split(",") if 값.strip()]
                st.session_state.항목_학년 = [값.strip() for 값 in 입력_학년.split(",") if 값.strip()]
                st.session_state.항목_파트 = [값.strip() for 값 in 입력_파트.split(",") if 값.strip()]
                st.session_state.항목_통학 = [값.strip() for 값 in 입력_통학.split(",") if 값.strip()]
                st.session_state.항목_회비 = [값.strip() for 값 in 입력_회비.split(",") if 값.strip()]
                자료저장()
                st.rerun()
                
            st.divider()
            st.write("비밀번호 변경")
            새비밀번호 = st.text_input("새 암호", type="password")
            if st.button("암호 저장"):
                st.session_state.비밀번호 = 새비밀번호
                자료저장()
                st.success("변경되었습니다.")

        st.write("---")
        st.subheader("새로운 사람 기입란")
        
        선택창설정_새부원 = {
            "학과": st.column_config.SelectboxColumn("학과", options=st.session_state.항목_학과),
            "학년": st.column_config.SelectboxColumn("학년", options=st.session_state.항목_학년),
            "통학여부": st.column_config.SelectboxColumn("통학여부", options=st.session_state.항목_통학),
            "회비여부": st.column_config.SelectboxColumn("회비여부", options=st.session_state.항목_회비),
            "파트": st.column_config.SelectboxColumn("파트", options=st.session_state.항목_파트)
        }
        
        입력된새부원 = st.data_editor(
            st.session_state.새부원표,
            column_config=선택창설정_새부원,
            num_rows="fixed",
            use_container_width=True,
            key=f"새부원입력_{st.session_state.새로고침번호}"
        )
        
        if st.button("명단에 추가하기"):
            if str(입력된새부원.iloc[0, 0]).strip() != "":
                st.session_state.부원자료 = pd.concat([st.session_state.부원자료, 입력된새부원], ignore_index=True)
                
                기본학과 = st.session_state.항목_학과[0] if st.session_state.항목_학과 else ""
                기본학년 = st.session_state.항목_학년[0] if st.session_state.항목_학년 else ""
                기본파트 = st.session_state.항목_파트[0] if st.session_state.항목_파트 else ""
                기본통학 = st.session_state.항목_통학[0] if st.session_state.항목_통학 else ""
                기본회비 = st.session_state.항목_회비[0] if st.session_state.항목_회비 else ""
                
                st.session_state.새부원표 = pd.DataFrame([["", "", 기본학과, 기본학년, "", 기본파트, 기본통학, 기본회비, "", "", "", ""]], columns=st.session_state.부원자료.columns)
                자료저장()
                st.session_state.새로고침번호 += 1
                st.rerun()
            else:
                st.error("이름을 적어주십시오.")
                
        st.write("---")
        st.subheader("기존 정보 수정")
        
        편집된부원자료 = st.data_editor(
            st.session_state.부원자료,
            num_rows="fixed",
            use_container_width=True,
            key=f"부원편집_{st.session_state.새로고침번호}"
        )
        
        if st.button("수정 내용 저장하기"):
            st.session_state.부원자료 = 편집된부원자료.fillna("")
            자료저장()
            st.session_state.새로고침번호 += 1

            st.rerun()
