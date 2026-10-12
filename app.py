import sqlite3
import pandas as pd
import plotly.express as px
import streamlit as st

DB_FILE = "jump_team_v2.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS athletes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            grade INTEGER,
            event TEXT,
            team TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS practice_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            athlete_id INTEGER,
            date TEXT NOT NULL,
            category TEXT,
            menu_name TEXT,
            weight_or_dist REAL,
            sets_reps TEXT,
            load_rpe INTEGER,
            fatigue_level INTEGER,
            memo TEXT,
            FOREIGN KEY(athlete_id) REFERENCES athletes(id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_connection():
    return sqlite3.connect(DB_FILE)

st.set_page_config(page_title="跳躍ブロック 練習＆コンディション管理", layout="wide")
st.title("🏃 陸上競技部 跳躍ブロック 練習＆コンディション管理システム")

tab1, tab2, tab3 = st.tabs(["👥 選手登録・管理", "📝 練習メニュー追加", "📊 強度・疲労度グラフ"])

with tab1:
    st.header("選手登録・所属チーム設定")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("新規選手追加")
        with st.form("add_athlete_form", clear_on_submit=True):
            name = st.text_input("選手氏名", placeholder="例: 順天堂 太郎")
            grade = st.selectbox("学年", [1, 2, 3, 4], index=0)
            event = st.selectbox("主種目", ["走高跳(HJ)", "棒高跳(PV)", "走幅跳(LJ)", "三段跳(TJ)", "混成(Deca/Hep)"])
            team = st.selectbox("所属チーム", ["Aチーム", "Bチーム", "Cチーム", "Dチーム"])
            submit_athlete = st.form_submit_button("選手を登録する")
            if submit_athlete:
                if name.strip():
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("INSERT INTO athletes (name, grade, event, team) VALUES (?, ?, ?, ?)", (name, grade, event, team))
                    conn.commit()
                    conn.close()
                    st.success(f"選手「{name}」 ({team}) を登録しました！")
                    st.rerun()
                else:
                    st.error("選手氏名を入力してください。")
    with col2:
        st.subheader("登録選手一覧")
        conn = get_connection()
        athletes_df = pd.read_sql("SELECT * FROM athletes", conn)
        conn.close()
        if not athletes_df.empty:
            filter_team = st.multiselect("チームで絞り込み", options=["Aチーム", "Bチーム", "Cチーム", "Dチーム"], default=["Aチーム", "Bチーム", "Cチーム", "Dチーム"])
            filtered_df = athletes_df[athletes_df['team'].isin(filter_team)]
            st.dataframe(filtered_df, use_container_width=True)
        else:
            st.info("登録されている選手はいません。左のフォームから追加してください。")

with tab2:
    st.header("練習メニュー＆強度・疲労度入力")
    conn = get_connection()
    athletes_df = pd.read_sql("SELECT * FROM athletes", conn)
    conn.close()
    if athletes_df.empty:
        st.warning("先に「選手登録・管理」タブで選手を登録してください。")
    else:
        target_type = st.radio("入力対象を選択してください", ["👤 個人を選択して入力", "👥 グループ（チーム/学年/種目）で一括入力"], horizontal=True)
        selected_athlete_ids = []
        if target_type == "👤 個人を選択して入力":
            col_a, col_b = st.columns(2)
            with col_a:
                team_filter = st.selectbox("絞り込み（チーム）", ["すべて"] + list(athletes_df['team'].unique()))
            with col_b:
                disp_athletes = athletes_df[athletes_df['team'] == team_filter] if team_filter != "すべて" else athletes_df
                athlete_option = st.selectbox("選手を選択", options=disp_athletes['id'].tolist(), format_func=lambda x: f"{disp_athletes[disp_athletes['id']==x]['name'].values[0]} ({disp_athletes[disp_athletes['id']==x]['team'].values[0]})")
                selected_athlete_ids = [athlete_option]
        else:
            st.info("選択条件に該当する全員に対して、一括で練習ログを登録します。")
            col_g1, col_g2, col_g3 = st.columns(3)
            with col_g1:
                sel_team = st.multiselect("対象チーム", options=["Aチーム", "Bチーム", "Cチーム", "Dチーム"], default=["Aチーム"])
            with col_g2:
                sel_grade = st.multiselect("対象学年", options=[1, 2, 3, 4], default=[1, 2, 3, 4])
            with col_g3:
                sel_event = st.multiselect("対象種目", options=list(athletes_df['event'].unique()), default=list(athletes_df['event'].unique()))
            matched_df = athletes_df[(athletes_df['team'].isin(sel_team)) & (athletes_df['grade'].isin(sel_grade)) & (athletes_df['event'].isin(sel_event))]
            selected_athlete_ids = matched_df['id'].tolist()
            st.write(f"対象選手: **{len(selected_athlete_ids)}名** ({', '.join(matched_df['name'].tolist()) if not matched_df.empty else '該当者なし'})")
        st.markdown("---")
        with st.form("log_input_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                log_date = st.date_input("日付")
                category = st.selectbox("種目カテゴリ", ["ウエイトトレーニング", "スプリント・走系", "跳躍・技術練習", "補強・サーキット", "コンディショニング/ケア"])
            with col2:
                menu_name = st.text_input("具体的なメニュー名", placeholder="例: クリーン, 120m wave run, 立五段跳")
                weight_or_dist = st.number_input("重量(kg) または 距離(m) [任意]", min_value=0.0, value=0.0, step=2.5)
                sets_reps = st.text_input("セット数・回数 [任意]", placeholder="例: 80kg x 3回 x 4セット")
            with col3:
                load_rpe = st.slider("練習強度 (RPE)", min_value=1, max_value=10, value=7)
                fatigue_level = st.slider("本人の疲労度 (1〜5)", min_value=1, max_value=5, value=3)
                memo = st.text_input("備考・メモ", placeholder="動きの感覚、注意点など")
            submit_log = st.form_submit_button("練習ログを登録")
            if submit_log:
                if not selected_athlete_ids:
                    st.error("対象となる選手が選択されていません。")
                elif not menu_name.strip():
                    st.error("メニュー名を入力してください。")
                else:
                    conn = get_connection()
                    c = conn.cursor()
                    for ath_id in selected_athlete_ids:
                        c.execute("INSERT INTO practice_logs (athlete_id, date, category, menu_name, weight_or_dist, sets_reps, load_rpe, fatigue_level, memo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (ath_id, str(log_date), category, menu_name, weight_or_dist, sets_reps, load_rpe, fatigue_level, memo))
                    conn.commit()
                    conn.close()
                    st.success(f"{len(selected_athlete_ids)}名分の練習ログを登録しました！")

with tab3:
    st.header("練習強度・疲労度・トレーニングバランス分析")
    conn = get_connection()
    logs_df = pd.read_sql("SELECT p.*, a.name, a.team, a.grade, a.event FROM practice_logs p JOIN athletes a ON p.athlete_id = a.id", conn)
    conn.close()
    if logs_df.empty:
        st.info("分析する練習データがまだありません。練習メニューを追加してください。")
    else:
        view_mode = st.radio("分析視点を選択", ["🏆 チーム別（A/B/C/D）強度・疲労度比較", "⚖️ 種目カテゴリバランス（割合）", "👤 個人別の強度・疲労度推移"], horizontal=True)
        st.markdown("---")
        if view_mode == "🏆 チーム別（A/B/C/D）強度・疲労度比較":
            st.subheader("チーム別 日次平均強度（RPE）と疲労度の推移")
            team_daily = logs_df.groupby(['date', 'team'])[['load_rpe', 'fatigue_level']].mean().reset_index()
            fig_rpe = px.line(team_daily, x='date', y='load_rpe', color='team', markers=True, title="チーム別 平均練習強度 (RPE 1-10) 推移")
            st.plotly_chart(fig_rpe, use_container_width=True)
            fig_fatigue = px.line(team_daily, x='date', y='fatigue_level', color='team', markers=True, title="チーム別 平均疲労度 (1-5) 推移")
            st.plotly_chart(fig_fatigue, use_container_width=True)
        elif view_mode == "⚖️ 種目カテゴリバランス（割合）":
            st.subheader("チーム / 全体のトレーニング種目バランス")
            sel_team_cat = st.selectbox("チームで絞り込み", ["全体"] + list(logs_df['team'].unique()))
            cat_df = logs_df[logs_df['team'] == sel_team_cat] if sel_team_cat != "全体" else logs_df
            cat_counts = cat_df['category'].value_counts().reset_index()
            cat_counts.columns = ['category', 'count']
            fig_pie = px.pie(cat_counts, values='count', names='category', title=f"{sel_team_cat} の練習種目カテゴリ比率", hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)
        elif view_mode == "👤 個人別の強度・疲労度推移":
            st.subheader("個人ごとのコンディション・負荷推移")
            selected_person = st.selectbox("選手を選択", logs_df['name'].unique())
            person_df = logs_df[logs_df['name'] == selected_person].sort_values('date')
            fig_person = px.bar(person_df, x='date', y='load_rpe', color='category', title=f"{selected_person} 選手の練習強度 (RPE) & 実施カテゴリ履歴")
            st.plotly_chart(fig_person, use_container_width=True)
            st.dataframe(person_df[['date', 'category', 'menu_name', 'load_rpe', 'fatigue_level', 'memo']], use_container_width=True)
