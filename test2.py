import requests
import pandas as pd
import streamlit as st
import sqlite3
from datetime import datetime, timedelta
from io import StringIO

if st.button("새로고침"):
    st.rerun()

# 백준 그룹 랭킹 URL
url = 'https://www.acmicpc.net/group/ranklist/23100'
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
}

# 오늘 날짜와 기준 시간 설정
now = datetime.now()
if now.hour < 6:
    today = (now - timedelta(days=1)).strftime('%Y-%m-%d')
    yesterday = (now - timedelta(days=2)).strftime('%Y-%m-%d')
else:
    today = now.strftime('%Y-%m-%d')
    yesterday = (now - timedelta(days=1)).strftime('%Y-%m-%d')

# SQLite 연결
conn = sqlite3.connect("data.db")
cursor = conn.cursor()

# 그룹 멤버 명단을 DB에서 중복 없이 가져오기
cursor.execute("SELECT DISTINCT 아이디 FROM table_data")
group_members = [row[0] for row in cursor.fetchall()]

# 웹 페이지 요청 및 데이터 가져오기
response = requests.get(url, headers=headers)
tables = pd.read_html(StringIO(response.text))

if tables:
    df = tables[0]  # 첫 번째 테이블 선택
    try:
        score_board = df[["등수", "아이디", "맞은 문제"]].copy()
        score_board["맞은 문제"] = pd.to_numeric(score_board["맞은 문제"], errors='coerce').fillna(0).astype(int)
        score_board["날짜"] = today
    except KeyError:
        st.error("테이블 컬럼명이 예상과 다릅니다. 데이터를 확인해주세요.")
        st.write(df.head())
        score_board = df
        score_board["날짜"] = today
    
    # 테이블 생성
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS table_data (
            등수 INTEGER,
            아이디 TEXT,
            맞은문제 INTEGER,
            날짜 TEXT,
            PRIMARY KEY (아이디, 날짜)
        )
    """)
    
    # 데이터 삽입 또는 업데이트
    for _, row in score_board.iterrows():
        cursor.execute("""
            SELECT * FROM table_data WHERE 아이디 = ? AND 날짜 = ?
        """, (row["아이디"], today))
        
        existing_data = cursor.fetchone()
        if existing_data:
            cursor.execute("""
                UPDATE table_data SET 맞은문제 = ? WHERE 아이디 = ? AND 날짜 = ?
            """, (row["맞은 문제"], row["아이디"], today))
        else:
            cursor.execute("""
                INSERT INTO table_data (등수, 아이디, 맞은문제, 날짜) VALUES (?, ?, ?, ?)
            """, (row["등수"], row["아이디"], row["맞은 문제"], today))
    
    conn.commit()
    
    # 오늘 문제를 푼 사람 찾기 (어제보다 맞은 문제가 증가한 경우만)
    solved_today = set()
    cursor.execute("SELECT COUNT(*) FROM table_data WHERE 날짜 = ?", (yesterday,))
    yesterday_data_count = cursor.fetchone()[0]
    
    if yesterday_data_count > 0:
        for user in group_members:
            cursor.execute("SELECT 맞은문제 FROM table_data WHERE 아이디 = ? AND 날짜 = ?", (user, yesterday))
            yesterday_solved = cursor.fetchone()
            
            cursor.execute("SELECT 맞은문제 FROM table_data WHERE 아이디 = ? AND 날짜 = ?", (user, today))
            today_solved = cursor.fetchone()
            
            yesterday_solved = yesterday_solved[0] if yesterday_solved else 0
            today_solved = today_solved[0] if today_solved else 0
            
            if today_solved > yesterday_solved:
                solved_today.add(user)
    
    missing_users = [user for user in group_members if user not in solved_today] if yesterday_data_count > 0 else []
    
    # Streamlit 출력
    st.title("백준 그룹 랭킹 및 미제출자 확인")
    st.subheader("오늘 문제를 안 푼 사람")
    if yesterday_data_count > 0:
        st.write(missing_users if missing_users else "모두 문제를 풀었습니다!")
    else:
        st.write("어제 데이터가 부족하여 판단할 수 없습니다.")
    
    st.subheader("오늘 랭킹")
    st.dataframe(score_board)
    
    conn.close()
else:
    st.error("웹 페이지에서 테이블을 찾을 수 없습니다.")
