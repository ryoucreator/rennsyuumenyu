import sqlite3
import pandas as pd
import plotly.express as px
import streamlit as st
import re

DB_FILE = "jump_team_v3.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 1. 選手マスター (sex, grade, event, team)
    c.execute('''
        CREATE TABLE IF NOT EXISTS athletes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sex TEXT NOT NULL DEFAULT '未設定',
            grade TEXT NOT NULL DEFAULT '未設定',
            event TEXT NOT NULL DEFAULT '未設定',
            team TEXT NOT NULL DEFAULT '未設定'
        )
    ''')
    
    # 既存DBマイグレーション (athletes)
    c.execute("PRAGMA table_info(athletes)")
    existing_ath_cols = [col[1] for col in c.fetchall()]
    if "sex" not in existing_ath_cols:
        if "gender" in existing_ath_cols:
            c.execute("ALTER TABLE athletes RENAME COLUMN gender TO sex")
        else:
            c.execute("ALTER TABLE athletes ADD COLUMN sex TEXT NOT NULL DEFAULT '未設定'")
    for col_name in ["grade", "event", "team"]:
        if col_name not in existing_ath_cols:
            c.execute(f"ALTER TABLE athletes ADD COLUMN {col_name} TEXT NOT NULL DEFAULT '未設定'")

    # 2. 練習メニューマスター
    c.execute('''
        CREATE TABLE IF NOT EXISTS menu_master (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL DEFAULT '全体メニュー',
            menu_name TEXT NOT NULL UNIQUE,
            target_note TEXT
        )
    ''')

    # 3. 練習ログ
    c.execute('''
        CREATE TABLE IF NOT EXISTS practice_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            athlete_id INTEGER NOT NULL,
            menu_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            weight_or_dist REAL DEFAULT 0.0,
            sets_reps TEXT,
            load_rpe INTEGER DEFAULT 7,
            fatigue_level INTEGER DEFAULT 3,
            memo TEXT,
            FOREIGN KEY(athlete_id) REFERENCES athletes(id),
            FOREIGN KEY(menu_id) REFERENCES menu_master(id)
        )
    ''')
    
    # 既存DBマイグレーション (practice_logs)
    c.execute("PRAGMA table_info(practice_logs)")
    existing_log_cols = [col[1] for col in c.fetchall()]
    log_schema_additions = {
        "weight_or_dist": "REAL DEFAULT 0.0",
        "sets_reps": "TEXT",
        "load_rpe": "INTEGER DEFAULT 7",
        "fatigue_level": "INTEGER DEFAULT 3",
        "memo": "TEXT"
    }
    for col_name, col_type in log_schema_additions.items():
        if col_name not in existing_log_cols:
            c.execute(f"ALTER TABLE practice_logs ADD COLUMN {col_name} {col_type}")

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

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "👥 選手登録・管理", 
    "📖 メニューマスター管理", 
    "📝 練習メニュー入力", 
    "📊 強度・疲労度分析",
    "📂 Excel一括インポート"
])

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
            sex = st.radio("性別", ["男子", "女子", "未設定"], horizontal=True)
            grade = st.selectbox("学年・所属", ["1年", "2年", "3年", "4年", "M1", "M2", "社会人", "未設定"])
            event = st.selectbox("主種目", ["走高跳(HJ)", "棒高跳(PV)", "走幅跳(LJ)", "三段跳(TJ)", "混成(Deca/Hep)", "未設定"])
            team = st.selectbox("所属チーム", ["Aチーム", "Bチーム", "Cチーム", "Dチーム", "未設定"])
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
            filter_team = st.multiselect("チームで絞り込み", options=["Aチーム", "Bチーム", "Cチーム", "Dチーム", "未設定"], default=["Aチーム", "Bチーム", "Cチーム", "Dチーム", "未設定"])
            filter_sex = st.multiselect("性別で絞り込み", options=["男子", "女子", "未設定"], default=["男子", "女子", "未設定"])
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
# タブ3: 練習メニュー入力
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
                sel_team = st.multiselect("対象チーム", options=["Aチーム", "Bチーム", "Cチーム", "Dチーム", "未設定"], default=["Aチーム"])
            with col_g2:
                sel_sex = st.multiselect("対象性別", options=["男子", "女子", "未設定"], default=["男子", "女子"])
            with col_g3:
                sel_grade = st.multiselect("対象学年・所属", options=["1年", "2年", "3年", "4年", "M1", "M2", "社会人", "未設定"], default=["1年", "2年", "3年", "4年", "M1", "M2", "社会人"])
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

# -------------------------------------------------------------------
# タブ5: Excel一括インポート（選手リスト＆練習メニュー）
# -------------------------------------------------------------------
with tab5:
    st.header("📂 Excel一括インポート（選手データ & 練習メニュー）")
    
    # --- A. 選手データの一括取り込みエリア ---
    with st.expander("👤 選手データの一括登録（選手.xlsx 対応）", expanded=True):
        tab_ath_file, tab_ath_batch = st.tabs([
            "📂 選手Excelファイルから一括取り込み", 
            "📋 表形式で直接入力"
        ])
        
        # 1. Excelファイル取り込み
        with tab_ath_file:
            uploaded_ath_file = st.file_uploader("選手リストExcelをアップロード（不足項目は自動的に『未設定』になります）", type=["xlsx", "xls"], key="tab5_ath_file")
            if uploaded_ath_file is not None:
                xls_ath = pd.ExcelFile(uploaded_ath_file)
                selected_ath_sheet = st.selectbox("取り込むシートを選択", xls_ath.sheet_names, key="tab5_ath_sheet")
                dedup_check = st.checkbox("重複する選手行を自動でまとめる", value=True, key="tab5_ath_dedup")
                
                if st.button("🔍 選手データを解析・プレビュー表示", type="primary", key="tab5_parse_ath_btn"):
                    df_ath_raw = pd.read_excel(uploaded_ath_file, sheet_name=selected_ath_sheet)
                    col_name = next((c for c in df_ath_raw.columns if any(k in str(c) for k in ['氏名', '名前', '選手', 'name'])), None)
                    col_sex = next((c for c in df_ath_raw.columns if any(k in str(c) for k in ['性別', '性', 'sex', 'gender'])), None)
                    col_team = next((c for c in df_ath_raw.columns if any(k in str(c) for k in ['チーム', '所属', 'team'])), None)
                    col_grade = next((c for c in df_ath_raw.columns if any(k in str(c) for k in ['学年', 'grade'])), None)
                    col_event = next((c for c in df_ath_raw.columns if any(k in str(c) for k in ['種目', 'event'])), None)

                    parsed_athletes = []
                    for _, row in df_ath_raw.iterrows():
                        name_val = str(row[col_name]).strip() if col_name and pd.notna(row[col_name]) else ""
                        if not name_val or name_val == 'nan': continue
                        
                        sex_val = str(row[col_sex]).strip() if col_sex and pd.notna(row[col_sex]) else "未設定"
                        if sex_val not in ["男子", "女子"]: sex_val = "未設定"
                            
                        team_val = str(row[col_team]).strip() if col_team and pd.notna(row[col_team]) else "未設定"
                        if team_val in ["A", "B", "C", "D"]: team_val = f"{team_val}チーム"
                        elif team_val not in ["Aチーム", "Bチーム", "Cチーム", "Dチーム"]: team_val = "未設定"
                            
                        grade_val = str(row[col_grade]).strip() if col_grade and pd.notna(row[col_grade]) else "未設定"
                        if grade_val not in ["1年", "2年", "3年", "4年", "M1", "M2", "社会人"]: grade_val = "未設定"
                            
                        event_val = str(row[col_event]).strip() if col_event and pd.notna(row[col_event]) else "未設定"
                        if event_val not in ["走高跳(HJ)", "棒高跳(PV)", "走幅跳(LJ)", "三段跳(TJ)", "混成(Deca/Hep)"]: event_val = "未設定"
                        
                        parsed_athletes.append({
                            "取り込む": True,
                            "選手氏名": name_val,
                            "性別": sex_val,
                            "学年・所属": grade_val,
                            "主種目": event_val,
                            "所属チーム": team_val
                        })
                    
                    df_parsed_ath = pd.DataFrame(parsed_athletes)
                    if dedup_check and not df_parsed_ath.empty:
                        df_parsed_ath = df_parsed_ath.drop_duplicates(subset=["選手氏名", "性別", "所属チーム"]).reset_index(drop=True)
                    st.session_state["tab5_parsed_ath_df"] = df_parsed_ath

            if "tab5_parsed_ath_df" in st.session_state:
                st.markdown("---")
                st.subheader("📋 選手データ解析結果プレビュー")
                edited_ath_file_df = st.data_editor(
                    st.session_state["tab5_parsed_ath_df"],
                    column_config={
                        "取り込む": st.column_config.CheckboxColumn("取り込む", default=True),
                        "選手氏名": st.column_config.TextColumn("選手氏名 (必須)"),
                        "性別": st.column_config.SelectboxColumn("性別", options=["男子", "女子", "未設定"], default="未設定"),
                        "学年・所属": st.column_config.SelectboxColumn("学年・所属", options=["1年", "2年", "3年", "4年", "M1", "M2", "社会人", "未設定"], default="未設定"),
                        "主種目": st.column_config.SelectboxColumn("主種目", options=["走高跳(HJ)", "棒高跳(PV)", "走幅跳(LJ)", "三段跳(TJ)", "混成(Deca/Hep)", "未設定"], default="未設定"),
                        "所属チーム": st.column_config.SelectboxColumn("所属チーム", options=["Aチーム", "Bチーム", "Cチーム", "Dチーム", "未設定"], default="未設定")
                    },
                    num_rows="dynamic",
                    use_container_width=True,
                    key="tab5_ath_file_editor"
                )

                if st.button("💾 確定して選手を一括保存", type="primary", key="tab5_save_ath_btn"):
                    conn = get_connection()
                    c = conn.cursor()
                    added_count = 0
                    for _, row in edited_ath_file_df.iterrows():
                        if not row["取り込む"]: continue
                        name_val = str(row["選手氏名"]).strip()
                        if not name_val or name_val == "nan": continue
                        c.execute("INSERT INTO athletes (name, sex, grade, event, team) VALUES (?, ?, ?, ?, ?)",
                                  (name_val, str(row["性別"]), str(row["学年・所属"]), str(row["主種目"]), str(row["所属チーム"])))
                        added_count += 1
                    conn.commit()
                    conn.close()
                    st.success(f"🎉 {added_count} 名の選手情報を保存しました！")
                    del st.session_state["tab5_parsed_ath_df"]
                    st.rerun()

        # 2. 表手動入力
        with tab_ath_batch:
            initial_athlete_data = pd.DataFrame([
                {"選手氏名": "", "性別": "男子", "学年・所属": "1年", "主種目": "走高跳(HJ)", "所属チーム": "Aチーム"},
                {"選手氏名": "", "性別": "女子", "学年・所属": "1年", "主種目": "走幅跳(LJ)", "所属チーム": "Aチーム"}
            ])
            edited_batch_athletes = st.data_editor(
                initial_athlete_data,
                column_config={
                    "選手氏名": st.column_config.TextColumn("選手氏名 (必須)"),
                    "性別": st.column_config.SelectboxColumn("性別", options=["男子", "女子", "未設定"], default="未設定"),
                    "学年・所属": st.column_config.SelectboxColumn("学年・所属", options=["1年", "2年", "3年", "4年", "M1", "M2", "社会人", "未設定"], default="未設定"),
                    "主種目": st.column_config.SelectboxColumn("主種目", options=["走高跳(HJ)", "棒高跳(PV)", "走幅跳(LJ)", "三段跳(TJ)", "混成(Deca/Hep)", "未設定"], default="未設定"),
                    "所属チーム": st.column_config.SelectboxColumn("所属チーム", options=["Aチーム", "Bチーム", "Cチーム", "Dチーム", "未設定"], default="未設定")
                },
                num_rows="dynamic",
                use_container_width=True,
                key="tab5_batch_athlete_editor"
            )
            if st.button("💾 表の選手を一括保存", type="primary", key="tab5_save_batch_ath_btn"):
                conn = get_connection()
                c = conn.cursor()
                added_count = 0
                for _, row in edited_batch_athletes.iterrows():
                    name_val = str(row["選手氏名"]).strip()
                    if not name_val or name_val == "nan": continue
                    c.execute("INSERT INTO athletes (name, sex, grade, event, team) VALUES (?, ?, ?, ?, ?)",
                              (name_val, str(row["性別"]), str(row["学年・所属"]), str(row["主種目"]), str(row["所属チーム"])))
                    added_count += 1
                conn.commit()
                conn.close()
                st.success(f"🎉 {added_count} 名の選手を登録しました！")
                st.rerun()

    st.markdown("---")

    # --- B. 練習メニューExcel自動分解エリア ---
    st.subheader("📂 練習メニューExcel自動分解＆一括インポート")
    uploaded_menu_file = st.file_uploader("月別トレーニングメニューExcelをアップロードしてください", type=["xlsx", "xls"], key="tab5_menu_file")

    if uploaded_menu_file is not None:
        xls_menu = pd.ExcelFile(uploaded_menu_file)
        selected_menu_sheet = st.selectbox("解析・取り込むシートを選択", xls_menu.sheet_names, key="tab5_menu_sheet")

        if st.button("🔍 自動解析・プレビュー実行", type="primary", key="tab5_parse_menu_btn"):
            df_sheet = pd.read_excel(uploaded_menu_file, sheet_name=selected_menu_sheet)
            df_sheet.columns = df_sheet.iloc[1]
            df_data = df_sheet.iloc[2:].copy()

            ignore_keywords = [
                '集合なし', 'フリー', '新入生', '説明会', '不在です', 'http', '健康診断',
                '持っていき', '活用して', '研究室', '組に分かれて', '以下を', '各自調整',
                '連絡', '注意', '準備', '移動', '集合', '解散', '各自'
            ]
            parsed_data = []

            for _, row in df_data.iterrows():
                date_val = str(row.get('日付', '')).split(' ')[0]
                if not date_val or date_val == 'nan': continue
                raw_menu_text = str(row.get('全体メニュー', ''))
                memo_text = str(row.get('メモ', ''))
                if memo_text == 'nan': memo_text = ""
                if pd.isna(raw_menu_text) or not raw_menu_text.strip() or raw_menu_text == 'nan': continue

                lines = [line.strip() for line in raw_menu_text.split('
') if line.strip()]

                for line in lines:
                    cleaned_line = re.sub(r'^[・＊\-\*\s]+', '', line)
                    if any(kw in cleaned_line for kw in ignore_keywords): continue

                    if "女子" in cleaned_line: target_group = "女子"
                    elif "男子" in cleaned_line: target_group = "男子"
                    elif "全体" in cleaned_line: target_group = "全体"
                    elif "1年生" in cleaned_line or "一般" in cleaned_line: target_group = "1年生/一般"
                    else: target_group = "未設定"

                    match = re.search(r'^([a-zA-Z\s\-\(\)\/぀-ゟ゠-ヿ一-鿿]+?)(?:[\s ]+([\d\&\*\-\,\.\%\~x×].*))?$', cleaned_line)
                    if match and match.group(2):
                        menu_name = match.group(1).strip()
                        detail_setting = match.group(2).strip()
                    else:
                        menu_name = cleaned_line.strip()
                        detail_setting = ""

                    if menu_name.lower() in ["med", "w-up", "st-up"] and detail_setting:
                        first_word = detail_setting.split(' ')[0]
                        if re.match(r'^[a-zA-Z]+$', first_word):
                            menu_name = f"{menu_name} {first_word}"
                            detail_setting = " ".join(detail_setting.split(' ')[1:])

                    if len(menu_name) <= 1 or menu_name in ["・", "＊", "-"]: continue

                    parsed_data.append({
                        "取り込む": True,
                        "日付": date_val,
                        "対象グループ": target_group,
                        "種目名 (マスター名)": menu_name,
                        "セット数・回数": detail_setting,
                        "備考・メモ": memo_text
                    })

            st.session_state["tab5_parsed_menu_df"] = pd.DataFrame(parsed_data)

    if "tab5_parsed_menu_df" in st.session_state:
        st.markdown("---")
        st.subheader("📋 練習メニュー解析結果プレビュー")
        st.info("💡 書かれていない項目は自動的に『未設定』に分類されています。手動編集・除外チェックも可能です。")

        edited_menu_df = st.data_editor(
            st.session_state["tab5_parsed_menu_df"],
            column_config={
                "取り込む": st.column_config.CheckboxColumn("取り込む", default=True),
                "対象グループ": st.column_config.SelectboxColumn("対象グループ", options=["全体", "男子", "女子", "1年生/一般", "未設定"])
            },
            num_rows="dynamic",
            use_container_width=True,
            key="tab5_menu_editor"
        )

        if st.button("💾 確定して練習ログを一括保存", type="primary", key="tab5_save_menu_btn"):
            conn = get_connection()
            c = conn.cursor()
            
            c.execute("PRAGMA table_info(athletes)")
            columns = [col[1] for col in c.fetchall()]
            sex_col = "sex" if "sex" in columns else "gender"

            c.execute(f"SELECT id, {sex_col} FROM athletes")
            athletes = c.fetchall()

            c.execute("SELECT id, menu_name FROM menu_master")
            menu_map = {row[1].strip(): row[0] for row in c.fetchall()}

            saved_count = 0
            for _, row in edited_menu_df.iterrows():
                if not row["取り込む"]: continue

                target_grp = row["対象グループ"]
                m_name = str(row["種目名 (マスター名)"]).strip()
                sets_reps_val = str(row["セット数・回数"]).strip()
                date_val = row["日付"]
                memo_val = str(row["備考・メモ"]).strip()

                if not m_name: continue

                if m_name not in menu_map:
                    c.execute("INSERT OR IGNORE INTO menu_master (category, menu_name, target_note) VALUES (?, ?, ?)", ("跳躍・技術練習", m_name, "Excel自動登録"))
                    c.execute("SELECT id FROM menu_master WHERE menu_name = ?", (m_name,))
                    res = c.fetchone()
                    if res: menu_map[m_name] = res[0]

                menu_id = menu_map.get(m_name)

                if menu_id and athletes:
                    for a_id, sex in athletes:
                        if target_grp == "女子" and sex != '女子': continue
                        if target_grp == "男子" and sex != '男子': continue

                        c.execute('''
                            INSERT INTO practice_logs 
                            (athlete_id, menu_id, date, weight_or_dist, sets_reps, load_rpe, fatigue_level, memo) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (a_id, menu_id, date_val, 0.0, sets_reps_val, 7, 3, memo_val))
                        saved_count += 1

            conn.commit()
            conn.close()
            st.success(f"🎉 練習ログの一括登録が完了しました！（合計 {saved_count} 件のログを追加）")
            del st.session_state["tab5_parsed_menu_df"]
