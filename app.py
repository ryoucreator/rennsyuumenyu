import sqlite3
import pandas as pd
import plotly.express as px
import streamlit as st

DB_FILE = "jump_team_v3.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # 1. 選手マスター (性別・M1/M2/社会人を追加)
    c.execute('''
        CREATE TABLE IF NOT EXISTS athletes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sex TEXT NOT NULL,
            grade TEXT NOT NULL,
            event TEXT NOT NULL,
            team TEXT NOT NULL
        )
    ''')
    # 2. 練習メニューマスター
    c.execute('''
        CREATE TABLE IF NOT EXISTS menu_master (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            menu_name TEXT NOT NULL UNIQUE,
            target_note TEXT
        )
    ''')
    # 3. 練習ログ (menu_idで外部キー参照)
    c.execute('''
        CREATE TABLE IF NOT EXISTS practice_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            athlete_id INTEGER NOT NULL,
            menu_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            weight_or_dist REAL,
            sets_reps TEXT,
            load_rpe INTEGER,
            fatigue_level INTEGER,
            memo TEXT,
            FOREIGN KEY(athlete_id) REFERENCES athletes(id),
            FOREIGN KEY(menu_id) REFERENCES menu_master(id)
        )
    ''')
    
    # 初期メニューマスターデータの挿入 (未登録の場合)
    c.execute("SELECT COUNT(*) FROM menu_master")
    if c.fetchone()[0] == 0:
        default_menus = [
            ("ウエイトトレーニング", "ハングクリーン", "股関節の爆発的伸展"),
            ("ウエイトトレーニング", "バックスクワット", "下肢の最大筋力強化"),
            ("スプリント・走系", "120m wave run", "疾走局面での脱力と維持"),
            ("スプリント・走系", "20min jog", "ウォーミングアップ・有酸素ベース"),
            ("跳躍・技術練習", "立五段跳", "踏み切り時の水平速度維持"),
            ("補強・サーキット", "Core strength circuit 10", "体幹部（腸腰筋・腹斜筋）の補強"),
            ("コンディショニング/ケア", "ストレッチ＆フォームローラー", "疲労回復・可動域確保")
        ]
        c.executemany("INSERT INTO menu_master (category, menu_name, target_note) VALUES (?, ?, ?)", default_menus)
        
    conn.commit()
    conn.close()

init_db()

def get_connection():
    return sqlite3.connect(DB_FILE)

st.set_page_config(page_title="跳躍ブロック 練習＆コンディション管理 v3", layout="wide")
st.title("🏃 陸上競技部 跳躍ブロック 練習＆コンディション管理システム")

tab1, tab2, tab3, tab4 = st.tabs(["👥 選手登録・管理", "📖 メニューマスター管理", "📝 練習メニュー入力", "📊 強度・疲労度分析"])

# -------------------------------------------------------------------
# タブ1: 選手登録・管理
# -------------------------------------------------------------------
with tab1:
    st.header("選手登録・属性設定")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("新規選手追加")
        with st.form("add_athlete_form", clear_on_submit=True):
            name = st.text_input("選手氏名", placeholder="例: 順天堂 太郎")
            sex = st.radio("性別", ["男子", "女子"], horizontal=True)
            grade = st.selectbox("学年・所属", ["1年", "2年", "3年", "4年", "M1", "M2", "社会人"])
            event = st.selectbox("主種目", ["走高跳(HJ)", "棒高跳(PV)", "走幅跳(LJ)", "三段跳(TJ)", "混成(Deca/Hep)"])
            team = st.selectbox("所属チーム", ["Aチーム", "Bチーム", "Cチーム", "Dチーム"])
            submit_athlete = st.form_submit_button("選手を登録する")
            if submit_athlete:
                if name.strip():
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("INSERT INTO athletes (name, sex, grade, event, team) VALUES (?, ?, ?, ?, ?)", (name, sex, grade, event, team))
                    conn.commit()
                    conn.close()
                    st.success(f"選手「{name}」（{sex}・{grade}・{team}）を登録しました！")
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
            filter_sex = st.multiselect("性別で絞り込み", options=["男子", "女子"], default=["男子", "女子"])
            filtered_df = athletes_df[(athletes_df['team'].isin(filter_team)) & (athletes_df['sex'].isin(filter_sex))]
            st.dataframe(filtered_df, use_container_width=True)
        else:
            st.info("登録されている選手はいません。左のフォームから追加してください。")

# -------------------------------------------------------------------
# タブ2: メニューマスター管理
# -------------------------------------------------------------------
with tab2:
    st.header("練習メニュー辞書（マスター）設定")
    col_m1, col_m2 = st.columns([1, 2])
    with col_m1:
        st.subheader("新規メニュー登録")
        with st.form("add_menu_form", clear_on_submit=True):
            m_category = st.selectbox("カテゴリ", ["ウエイトトレーニング", "スプリント・走系", "跳躍・技術練習", "補強・サーキット", "コンディショニング/ケア"])
            m_name = st.text_input("メニュー名（正式名称）", placeholder="例: ハングクリーン")
            m_target = st.text_area("意識するポイント・目的", placeholder="例: 股関節の爆発的伸展とキャッチの安定")
            submit_menu = st.form_submit_button("マスターに追加")
            if submit_menu:
                if m_name.strip():
                    try:
                        conn = get_connection()
                        c = conn.cursor()
                        c.execute("INSERT INTO menu_master (category, menu_name, target_note) VALUES (?, ?, ?)", (m_category, m_name.strip(), m_target.strip()))
                        conn.commit()
                        conn.close()
                        st.success(f"メニュー「{m_name}」をマスターに登録しました！")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("同名のメニューがすでに登録されています。")
                else:
                    st.error("メニュー名を入力してください。")
    with col_m2:
        st.subheader("登録済みメニュー一覧")
        conn = get_connection()
        menu_df = pd.read_sql("SELECT * FROM menu_master", conn)
        conn.close()
        if not menu_df.empty:
            st.dataframe(menu_df, use_container_width=True)
        else:
            st.info("登録されているメニューはありません。")

# -------------------------------------------------------------------
# タブ3: 練習メニュー入力 (個人入力 & 条件指定一括入力)
# -------------------------------------------------------------------
with tab3:
    st.header("練習ログ・コンディション入力")
    conn = get_connection()
    athletes_df = pd.read_sql("SELECT * FROM athletes", conn)
    menu_df = pd.read_sql("SELECT * FROM menu_master", conn)
    conn.close()
    
    if athletes_df.empty:
        st.warning("先に「選手登録・管理」タブで選手を登録してください。")
    elif menu_df.empty:
        st.warning("先に「メニューマスター管理」タブで練習メニューを登録してください。")
    else:
        target_type = st.radio("入力モードを選択", ["👤 個人を選択して入力", "👥 条件指定で一括入力（グループ/チーム/性別）"], horizontal=True)
        
        target_athlete_ids = []
        
        if target_type == "👤 個人を選択して入力":
            col_a, col_b = st.columns(2)
            with col_a:
                team_filter = st.selectbox("チーム絞り込み", ["すべて"] + list(athletes_df['team'].unique()))
            with col_b:
                disp_athletes = athletes_df[athletes_df['team'] == team_filter] if team_filter != "すべて" else athletes_df
                if not disp_athletes.empty:
                    athlete_option = st.selectbox("選手を選択", options=disp_athletes['id'].tolist(), format_func=lambda x: f"{disp_athletes[disp_athletes['id']==x]['name'].values[0]} ({disp_athletes[disp_athletes['id']==x]['sex'].values[0]} / {disp_athletes[disp_athletes['id']==x]['grade'].values[0]} / {disp_athletes[disp_athletes['id']==x]['team'].values[0]})")
                    target_athlete_ids = [athlete_option]
        else:
            st.subheader("一括入力の対象者を抽出")
            col_g1, col_g2, col_g3, col_g4 = st.columns(4)
            with col_g1:
                sel_team = st.multiselect("対象チーム", options=["Aチーム", "Bチーム", "Cチーム", "Dチーム"], default=["Aチーム"])
            with col_g2:
                sel_sex = st.multiselect("対象性別", options=["男子", "女子"], default=["男子", "女子"])
            with col_g3:
                sel_grade = st.multiselect("対象学年・所属", options=["1年", "2年", "3年", "4年", "M1", "M2", "社会人"], default=["1年", "2年", "3年", "4年", "M1", "M2", "社会人"])
            with col_g4:
                sel_event = st.multiselect("対象種目", options=list(athletes_df['event'].unique()), default=list(athletes_df['event'].unique()))
            
            matched_df = athletes_df[(athletes_df['team'].isin(sel_team)) & (athletes_df['sex'].isin(sel_sex)) & (athletes_df['grade'].isin(sel_grade)) & (athletes_df['event'].isin(sel_event))]
            
            if not matched_df.empty:
                st.markdown("##### 該当選手一覧 (見学・別メニューの選手はチェックを外してください)")
                excluded_ids = []
                cols = st.columns(4)
                for idx, row in matched_df.reset_index().iterrows():
                    col_idx = idx % 4
                    is_checked = cols[col_idx].checkbox(f"{row['name']} ({row['sex']}/{row['grade']})", value=True, key=f"ath_check_{row['id']}")
                    if not is_checked:
                        excluded_ids.append(row['id'])
                
                target_athlete_ids = [aid for aid in matched_df['id'].tolist() if aid not in excluded_ids]
                st.info(f"👉 **登録対象人数: {len(target_athlete_ids)} 名**")
            else:
                st.warning("条件に該当する選手がいません。")

        st.markdown("---")
        st.subheader("実施メニュー＆負荷の記録")
        with st.form("log_input_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                log_date = st.date_input("日付")
                selected_cat = st.selectbox("メニューカテゴリ", options=list(menu_df['category'].unique()))
                filtered_menus = menu_df[menu_df['category'] == selected_cat]
                selected_menu_id = st.selectbox("実施メニュー (マスターより参照)", options=filtered_menus['id'].tolist(), format_func=lambda x: filtered_menus[filtered_menus['id']==x]['menu_name'].values[0])
            with col2:
                weight_or_dist = st.number_input("重量(kg) または 距離(m) [任意]", min_value=0.0, value=0.0, step=2.5)
                sets_reps = st.text_input("セット数・回数 [任意]", placeholder="例: 80kg x 3回 x 4セット")
                memo = st.text_input("備考・メモ", placeholder="動きの感覚、意識点など")
            with col3:
                load_rpe = st.slider("練習強度 (RPE 1-10)", min_value=1, max_value=10, value=7)
                fatigue_level = st.slider("主観的疲労度 (1-5)", min_value=1, max_value=5, value=3)
                
            submit_log = st.form_submit_button("練習ログを登録実行")
            
            if submit_log:
                if not target_athlete_ids:
                    st.error("対象となる選手が選択されていません。")
                else:
                    conn = get_connection()
                    c = conn.cursor()
                    for ath_id in target_athlete_ids:
                        c.execute("INSERT INTO practice_logs (athlete_id, menu_id, date, weight_or_dist, sets_reps, load_rpe, fatigue_level, memo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                                  (ath_id, selected_menu_id, str(log_date), weight_or_dist, sets_reps, load_rpe, fatigue_level, memo))
                    conn.commit()
                    conn.close()
                    st.success(f"{len(target_athlete_ids)} 名分の練習ログを正常に記録しました！")

# -------------------------------------------------------------------
# タブ4: 強度・疲労度分析
# -------------------------------------------------------------------
with tab4:
    st.header("練習強度・疲労度・コンディション分析")
    conn = get_connection()
    logs_df = pd.read_sql('''
        SELECT p.*, a.name, a.sex, a.grade, a.event, a.team, m.menu_name, m.category 
        FROM practice_logs p 
        JOIN athletes a ON p.athlete_id = a.id
        JOIN menu_master m ON p.menu_id = m.id
    ''', conn)
    conn.close()
    
    if logs_df.empty:
        st.info("分析可能な練習ログがまだ存在しません。練習メニューを入力してください。")
    else:
        view_mode = st.radio("分析視点を選択", ["🏆 チーム・性別比較", "⚖️ 練習カテゴリバランス", "👤 個人別負荷・疲労度推移"], horizontal=True)
        st.markdown("---")
        
        if view_mode == "🏆 チーム・性別比較":
            st.subheader("チーム・性別ごとの平均練習強度（RPE）と疲労度")
            group_col = st.selectbox("比較軸を選択", ["team", "sex", "grade"])
            daily_grp = logs_df.groupby(['date', group_col])[['load_rpe', 'fatigue_level']].mean().reset_index()
            
            fig_rpe = px.line(daily_grp, x='date', y='load_rpe', color=group_col, markers=True, title=f"{group_col} 別 平均練習強度 (RPE) 推移")
            st.plotly_chart(fig_rpe, use_container_width=True)
            
            fig_fatigue = px.line(daily_grp, x='date', y='fatigue_level', color=group_col, markers=True, title=f"{group_col} 別 平均疲労度 推移")
            st.plotly_chart(fig_fatigue, use_container_width=True)
            
        elif view_mode == "⚖️ 練習カテゴリバランス":
            st.subheader("実施カテゴリの比率分析")
            sel_team_cat = st.selectbox("対象チーム", ["全体"] + list(logs_df['team'].unique()))
            cat_df = logs_df[logs_df['team'] == sel_team_cat] if sel_team_cat != "全体" else logs_df
            cat_counts = cat_df['category'].value_counts().reset_index()
            cat_counts.columns = ['category', 'count']
            
            fig_pie = px.pie(cat_counts, values='count', names='category', title=f"{sel_team_cat} の練習カテゴリ割合", hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)
            
        elif view_mode == "👤 個人別負荷・疲労度推移":
            st.subheader("個人ごとのコンディション・ログ一覧")
            selected_person = st.selectbox("選手を選択", logs_df['name'].unique())
            person_df = logs_df[logs_df['name'] == selected_person].sort_values('date')
            
            fig_person = px.bar(person_df, x='date', y='load_rpe', color='category', hover_data=['menu_name', 'sets_reps', 'memo'], title=f"{selected_person} 選手の練習強度 (RPE) & 実施カテゴリ履歴")
            st.plotly_chart(fig_person, use_container_width=True)
            
            st.dataframe(person_df[['date', 'category', 'menu_name', 'weight_or_dist', 'sets_reps', 'load_rpe', 'fatigue_level', 'memo']], use_container_width=True)
