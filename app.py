import sqlite3
import pandas as pd
import plotly.express as px
import streamlit as st
import re

DB_FILE = "jump_team_v3.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 1. 選手マスター
    c.execute("""
        CREATE TABLE IF NOT EXISTS athletes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            name TEXT NOT NULL UNIQUE,
            sex TEXT NOT NULL DEFAULT '未設定',
            grade TEXT NOT NULL DEFAULT '未設定',
            event TEXT NOT NULL DEFAULT '未設定',
            team TEXT NOT NULL DEFAULT '未設定'
        )
    """)
    
    c.execute("PRAGMA table_info(athletes)")
    existing_ath_cols = [col[1] for col in c.fetchall()]
    if "student_id" not in existing_ath_cols:
        c.execute("ALTER TABLE athletes ADD COLUMN student_id TEXT")
    if "sex" not in existing_ath_cols:
        if "gender" in existing_ath_cols:
            c.execute("ALTER TABLE athletes RENAME COLUMN gender TO sex")
        else:
            c.execute("ALTER TABLE athletes ADD COLUMN sex TEXT NOT NULL DEFAULT '未設定'")
    for col_name in ["grade", "event", "team"]:
        if col_name not in existing_ath_cols:
            c.execute(f"ALTER TABLE athletes ADD COLUMN {col_name} TEXT NOT NULL DEFAULT '未設定'")

    # 2. 練習メニューマスター
    c.execute("""
        CREATE TABLE IF NOT EXISTS menu_master (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL DEFAULT '全体メニュー',
            menu_name TEXT NOT NULL UNIQUE,
            target_note TEXT
        )
    """)

    # 3. 練習ログ
    c.execute("""
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
            FOREIGN KEY(athlete_id) REFERENCES athletes(id) ON DELETE CASCADE,
            FOREIGN KEY(menu_id) REFERENCES menu_master(id) ON DELETE CASCADE
        )
    """)
    
    c.execute("PRAGMA table_info(practice_logs)")
    existing_log_cols = [col[1] for col in c.fetchall()]
    log_schema_additions = {
        "weight_or_dist": "REAL",
        "sets_reps": "TEXT",
        "load_rpe": "INTEGER",
        "fatigue_level": "INTEGER",
        "memo": "TEXT"
    }
    for col_name, col_type in log_schema_additions.items():
        if col_name not in existing_log_cols:
            c.execute(f"ALTER TABLE practice_logs ADD COLUMN {col_name} {col_type}")

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
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

# カテゴリのスマート判定関数
def determine_category(raw_cat, menu_name):
    raw_cat_str = str(raw_cat).strip() if pd.notna(raw_cat) else ""
    menu_lower = str(menu_name).lower() if pd.notna(menu_name) else ""
    
    if raw_cat_str in ['WT', 'ウエイト']:
        return 'ウエイトトレーニング'
    elif raw_cat_str in ['Run', 'SPIKE SHOES', '走系', 'スプリント']:
        return 'スプリント・走系'
    elif raw_cat_str in ['跳躍', '技術', 'JUMP']:
        return '跳躍・技術練習'
    elif raw_cat_str in ['補強', 'サーキット', '体幹']:
        return '補強・サーキット'
    
    wt_kw = ['sq', 'squat', 'cl', 'clean', 'jerk', 'lunge', 'rowing', 'dipping', 'bench', 'press', 'deadlift', 'wt', 'weight', 'halteres', 'rdl', 'snatch', 'extension', 'slrdl', 'heel raise', 'nor ham']
    jump_kw = ['jump', 'bound', 'bounding', 'hop', 'hopping', '跳', '技術', 'run-up', 'take off', '助走', 'hj', 'lj', 'tj', 'pv', 'plyo', '立五段', '立幅跳', '立三段跳']
    sprint_kw = ['jog', 'run', 'sprint', 'dash', 'cruising', 'shuttle', 'walk', 'hurdle', '300m', '100m', '120m', '200m', '60m', '40m', '30m', 'sled', '1080', 'spike', 'skipping', 'drill', '加速', 'tempo', 'w-up', 'corner', 'スタート', 'uphill', 'rugby', 'mini hurdle']
    core_kw = ['core', 'circuit', 'cat and dog', 'scorpion', 'bird dog', 'dead bug', '補強', 'st-up', 'stretch', 'care', 'rest', 'roller', 'wiper', 'plank', 'rope', 'bike']

    if any(k in menu_lower for k in wt_kw):
        return 'ウエイトトレーニング'
    elif any(k in menu_lower for k in jump_kw):
        return '跳躍・技術練習'
    elif any(k in menu_lower for k in sprint_kw):
        return 'スプリント・走系'
    elif any(k in menu_lower for k in core_kw):
        return '補強・サーキット'
        
    return '補強・サーキット'

st.set_page_config(page_title="跳躍ブロック 練習＆コンディション管理 v3", layout="wide")
st.title("🏃 陸上競技部 跳躍・混成ブロック 練習＆コンディション管理システム")

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
            student_id = st.text_input("学籍ID", placeholder="例: 1525000")
            name = st.text_input("選手氏名", placeholder="例: 順天堂 太郎")
            sex = st.radio("性別", ["男子", "女子", "未設定"], horizontal=True)
            grade = st.selectbox("学年・所属", ["1年", "2年", "3年", "4年", "M1", "M2", "社会人", "未設定"])
            event = st.selectbox("主種目", ["走高跳(HJ)", "棒高跳(PV)", "走幅跳(LJ)", "三段跳(TJ)", "混成(Deca/Hep)", "未設定"])
            team = st.selectbox("所属チーム", ["Aチーム", "Bチーム", "Cチーム", "Dチーム", "未設定"])
            submit_athlete = st.form_submit_button("選手を登録する")
            if submit_athlete:
                if name.strip():
                    try:
                        conn = get_connection()
                        c = conn.cursor()
                        c.execute("INSERT INTO athletes (student_id, name, sex, grade, event, team) VALUES (?, ?, ?, ?, ?, ?)", (student_id.strip(), name.strip(), sex, grade, event, team))
                        conn.commit()
                        conn.close()
                        st.success(f"選手「{name}」（{sex}・{grade}・{event}・{team}）を登録しました！")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("同名の選手がすでに登録されています。")
                else:
                    st.error("選手氏名を入力してください。")
    with col2:
        st.subheader("登録選手一覧")
        conn = get_connection()
        athletes_df = pd.read_sql("SELECT * FROM athletes ORDER BY id DESC", conn)
        conn.close()
        if not athletes_df.empty:
            filter_team = st.multiselect("チームで絞り込み", options=["Aチーム", "Bチーム", "Cチーム", "Dチーム", "未設定"], default=["Aチーム", "Bチーム", "Cチーム", "Dチーム", "未設定"], key="tab1_filter_team")
            filter_sex = st.multiselect("性別で絞り込み", options=["男子", "女子", "未設定"], default=["男子", "女子", "未設定"], key="tab1_filter_sex")
            filtered_df = athletes_df[(athletes_df['team'].isin(filter_team)) & (athletes_df['sex'].isin(filter_sex))]
            st.dataframe(filtered_df.rename(columns={'student_id': '学籍ID', 'name': '氏名', 'sex': '性別', 'grade': '学年', 'event': '種目', 'team': 'チーム'}), use_container_width=True)
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
                    
        st.markdown("---")
        st.subheader("✏️ メニュー情報の変更（名称・分類）")
        conn = get_connection()
        menu_df_edit = pd.read_sql("SELECT id, category, menu_name, target_note FROM menu_master ORDER BY category, menu_name", conn)
        conn.close()
        
        if not menu_df_edit.empty:
            target_edit_id = st.selectbox(
                "変更するメニューを選択", 
                options=menu_df_edit['id'].tolist(), 
                format_func=lambda x: f"[{menu_df_edit[menu_df_edit['id']==x]['category'].values[0]}] {menu_df_edit[menu_df_edit['id']==x]['menu_name'].values[0]}", 
                key="tab2_edit_menu_select"
            )
            
            selected_menu_row = menu_df_edit[menu_df_edit['id'] == target_edit_id].iloc[0]
            current_cat = selected_menu_row['category']
            current_name = selected_menu_row['menu_name']
            current_note = selected_menu_row['target_note'] if pd.notna(selected_menu_row['target_note']) else ""
            
            cat_options = ["ウエイトトレーニング", "スプリント・走系", "跳躍・技術練習", "補強・サーキット", "コンディショニング/ケア"]
            cat_index = cat_options.index(current_cat) if current_cat in cat_options else 0
            
            new_cat = st.selectbox("新しいカテゴリ（分類）", options=cat_options, index=cat_index, key="tab2_new_cat")
            new_menu_name = st.text_input("新しいメニュー名", value=current_name, key="tab2_new_menu_name")
            new_note = st.text_area("新しい目的・メモ", value=current_note, key="tab2_new_note")
            
            if st.button("✏️ メニュー情報を更新する", type="primary", key="tab2_update_menu_btn"):
                if new_menu_name.strip():
                    try:
                        conn = get_connection()
                        c = conn.cursor()
                        c.execute(
                            "UPDATE menu_master SET category = ?, menu_name = ?, target_note = ? WHERE id = ?", 
                            (new_cat, new_menu_name.strip(), new_note.strip(), target_edit_id)
                        )
                        conn.commit()
                        conn.close()
                        st.success(f"メニュー情報を更新しました！（分類: {new_cat} / 名称: {new_menu_name.strip()}）")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("そのメニュー名はすでに存在します。別の名称を指定してください。")
                else:
                    st.error("メニュー名を入力してください。")

    with col_m2:
        st.subheader("登録済みメニュー一覧（複数選択削除）")
        conn = get_connection()
        menu_df = pd.read_sql("SELECT * FROM menu_master ORDER BY category, menu_name", conn)
        conn.close()
        
        if not menu_df.empty:
            st.caption("💡 削除したいメニューの左側のチェックボックスを選択して、下部の「一括削除」ボタンを押してください。")
            menu_df['削除対象'] = False
            
            edited_menu_table = st.data_editor(
                menu_df[['削除対象', 'id', 'category', 'menu_name', 'target_note']],
                column_config={
                    "削除対象": st.column_config.CheckboxColumn("選択", default=False),
                    "id": st.column_config.NumberColumn("ID", disabled=True),
                    "category": st.column_config.TextColumn("カテゴリ", disabled=True),
                    "menu_name": st.column_config.TextColumn("メニュー名", disabled=True),
                    "target_note": st.column_config.TextColumn("目的・メモ", disabled=True),
                },
                use_container_width=True,
                hide_index=True,
                key="tab2_menu_table_editor"
            )
            
            selected_ids = edited_menu_table[edited_menu_table['削除対象'] == True]['id'].tolist()
            
            if selected_ids:
                st.warning(f"⚠️ 選択した {len(selected_ids)} 件のメニューと、それに関連するすべての練習ログが完全に削除されます。")
                if st.button("🗑️ 選択したメニューを一括削除する", type="primary", key="tab2_batch_delete_btn"):
                    conn = get_connection()
                    c = conn.cursor()
                    placeholders = ','.join(['?'] * len(selected_ids))
                    c.execute(f"DELETE FROM practice_logs WHERE menu_id IN ({placeholders})", selected_ids)
                    c.execute(f"DELETE FROM menu_master WHERE id IN ({placeholders})", selected_ids)
                    conn.commit()
                    conn.close()
                    st.success(f"{len(selected_ids)} 件のメニューおよび関連ログを削除しました！")
                    st.rerun()
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
        target_type = st.radio("入力モードを選択", ["👤 個人を選択して入力", "👥 条件指定で一括入力（グループ/チーム/性別）"], horizontal=True, key="tab3_target_type")
        
        target_athlete_ids = []
        
        if target_type == "👤 個人を選択して入力":
            col_a, col_b = st.columns(2)
            with col_a:
                team_filter = st.selectbox("チーム絞り込み", ["すべて"] + list(athletes_df['team'].unique()), key="tab3_team_filter")
            with col_b:
                disp_athletes = athletes_df[athletes_df['team'] == team_filter] if team_filter != "すべて" else athletes_df
                if not disp_athletes.empty:
                    athlete_option = st.selectbox("選手を選択", options=disp_athletes['id'].tolist(), format_func=lambda x: f"{disp_athletes[disp_athletes['id']==x]['name'].values[0]} ({disp_athletes[disp_athletes['id']==x]['sex'].values[0]} / {disp_athletes[disp_athletes['id']==x]['grade'].values[0]} / 種目:{disp_athletes[disp_athletes['id']==x]['event'].values[0]})", key="tab3_athlete_option")
                    target_athlete_ids = [athlete_option]
                    
                    selected_ath = disp_athletes[disp_athletes['id']==athlete_option].iloc[0]
                    if selected_ath['event'] in ['混成(Deca/Hep)', 'Deca', 'Hep', '十種競技', '七種競技']:
                        st.info("💡 混成選手が選択されています。必要に応じて『混成メニュー』のログを選択してください。")
        else:
            st.subheader("一括入力の対象者を抽出")
            col_g1, col_g2, col_g3, col_g4 = st.columns(4)
            with col_g1:
                sel_team = st.multiselect("対象チーム", options=["Aチーム", "Bチーム", "Cチーム", "Dチーム", "未設定"], default=["Aチーム"], key="tab3_sel_team")
            with col_g2:
                sel_sex = st.multiselect("対象性別", options=["男子", "女子", "未設定"], default=["男子", "女子"], key="tab3_sel_sex")
            with col_g3:
                sel_grade = st.multiselect("対象学年・所属", options=["1年", "2年", "3年", "4年", "M1", "M2", "社会人", "未設定"], default=["1年", "2年", "3年", "4年", "M1", "M2", "社会人"], key="tab3_sel_grade")
            with col_g4:
                sel_event = st.multiselect("対象種目", options=list(athletes_df['event'].unique()), default=list(athletes_df['event'].unique()), key="tab3_sel_event")
            
            matched_df = athletes_df[(athletes_df['team'].isin(sel_team)) & (athletes_df['sex'].isin(sel_sex)) & (athletes_df['grade'].isin(sel_grade)) & (athletes_df['event'].isin(sel_event))]
            
            if not matched_df.empty:
                st.markdown("##### 該当選手一覧 (見学・別メニューの選手はチェックを外してください)")
                excluded_ids = []
                cols = st.columns(4)
                for idx, row in matched_df.reset_index().iterrows():
                    col_idx = idx % 4
                    is_checked = cols[col_idx].checkbox(f"{row['name']} ({row['sex']}/{row['grade']}/{row['event']})", value=True, key=f"ath_check_{row['id']}")
                    if not is_checked:
                        excluded_ids.append(row['id'])
                
                target_athlete_ids = [aid for aid in matched_df['id'].tolist() if aid not in excluded_ids]
                st.info(f"👉 **登録対象人数: {len(target_athlete_ids)} 名**")
            else:
                st.warning("条件に該当する選手がいません。")

        st.markdown("---")
        st.subheader("📝 実施メニューの入力（複数メニューを一括追加可能）")
        
        if "input_menu_count" not in st.session_state:
            st.session_state["input_menu_count"] = 1

        log_date = st.date_input("日付", key="tab3_global_date")

        col_btn1, col_btn2 = st.columns([1, 4])
        with col_btn1:
            if st.button("➕ 練習メニューを追加", key="tab3_add_menu_row"):
                st.session_state["input_menu_count"] += 1
                st.rerun()
        with col_btn2:
            if st.session_state["input_menu_count"] > 1:
                if st.button("➖ 最後の行を削除", key="tab3_del_menu_row"):
                    st.session_state["input_menu_count"] -= 1
                    st.rerun()

        menu_entries = []
        all_menus_dict = {row['id']: f"[{row['category']}] {row['menu_name']}" for _, row in menu_df.iterrows()}

        for i in range(st.session_state["input_menu_count"]):
            st.markdown(f"##### 練習メニュー #{i+1}")
            c1, c2, c3, c4 = st.columns([3, 3, 2, 2])
            with c1:
                sel_m_id = st.selectbox(f"実施メニュー #{i+1}", options=list(all_menus_dict.keys()), format_func=lambda x: all_menus_dict[x], key=f"tab3_m_id_{i}")
            with c2:
                sets_reps_val = st.text_input(f"セット数・回数・設定 #{i+1}", placeholder="例: 80kg x 3回 x 4セット", key=f"tab3_sets_{i}")
            with c3:
                load_rpe_val = st.slider(f"強度 RPE #{i+1}", 1, 10, 7, key=f"tab3_rpe_{i}")
            with c4:
                fatigue_val = st.slider(f"疲労度 #{i+1}", 1, 5, 3, key=f"tab3_fatigue_{i}")
            
            memo_val = st.text_input(f"備考・メモ #{i+1}", placeholder="感覚、技術的ポイントなど", key=f"tab3_memo_{i}")
            st.markdown("---")
            
            menu_entries.append({
                "menu_id": sel_m_id,
                "sets_reps": sets_reps_val,
                "load_rpe": load_rpe_val,
                "fatigue_level": fatigue_val,
                "memo": memo_val
            })

        if st.button("🚀 登録対象の全選手にこの練習ログを一括保存", type="primary", key="tab3_submit_batch_logs"):
            if not target_athlete_ids:
                st.error("対象となる選手が選択されていません。")
            else:
                conn = get_connection()
                c = conn.cursor()
                total_inserted = 0
                for ath_id in target_athlete_ids:
                    for entry in menu_entries:
                        c.execute("""
                            INSERT INTO practice_logs (athlete_id, menu_id, date, weight_or_dist, sets_reps, load_rpe, fatigue_level, memo) 
                            VALUES (?, ?, ?, 0.0, ?, ?, ?, ?)
                        """, (ath_id, entry["menu_id"], str(log_date), entry["sets_reps"], entry["load_rpe"], entry["fatigue_level"], entry["memo"]))
                        total_inserted += 1
                conn.commit()
                conn.close()
                st.success(f"🎉 {len(target_athlete_ids)} 名の選手に対し、合計 {total_inserted} 件の練習ログを一括保存しました！")

# -------------------------------------------------------------------
# タブ4: 強度・疲労度分析 & 過去練習ログ検索
# -------------------------------------------------------------------
with tab4:
    st.header("練習強度・疲労度分析 & 過去ログ検索・編集")
    conn = get_connection()
    logs_df = pd.read_sql("""
        SELECT p.id as log_id, p.date, p.weight_or_dist, p.sets_reps, p.load_rpe, p.fatigue_level, p.memo,
               a.name, a.sex, a.grade, a.event, a.team, m.menu_name, m.category 
        FROM practice_logs p 
        JOIN athletes a ON p.athlete_id = a.id
        JOIN menu_master m ON p.menu_id = m.id
    """, conn)
    conn.close()
    
    if logs_df.empty:
        st.info("分析・閲覧可能な練習ログがまだ存在しません。練習メニューを入力してください。")
    else:
        view_mode = st.radio(
            "表示モードを選択", 
            ["📜 過去練習ログの遡り・検索＆編集", "🏆 チーム・性別比較グラフトレンド", "⚖️ 練習カテゴリバランス", "📈 負荷・疲労度推移（全体・絞り込み）"], 
            horizontal=True,
            key="tab4_view_mode"
        )
        st.markdown("---")
        
        def render_filters_with_date(key_prefix, include_menu_filter=False):
            col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns(5)
            with col_f1:
                teams = ["すべて"] + sorted(list(logs_df['team'].unique()))
                filter_t = st.selectbox("チーム", teams, key=f"{key_prefix}_team")
            with col_f2:
                sexes = ["すべて"] + sorted(list(logs_df['sex'].unique()))
                filter_s = st.selectbox("性別", sexes, key=f"{key_prefix}_sex")
            with col_f3:
                grades = ["すべて"] + sorted(list(logs_df['grade'].unique()))
                filter_g = st.selectbox("学年・所属", grades, key=f"{key_prefix}_grade")
            with col_f4:
                events = ["すべて"] + sorted(list(logs_df['event'].unique()))
                filter_e = st.selectbox("主種目", events, key=f"{key_prefix}_event")
            with col_f5:
                all_names = ["全員"] + sorted(list(logs_df['name'].unique()))
                filter_n = st.selectbox("個人（選手名）", all_names, key=f"{key_prefix}_name")
                
            selected_menus = []
            if include_menu_filter:
                st.markdown("##### 🏋️‍♂️ 実施種目（練習メニュー名）で絞り込み")
                all_menu_names = sorted(list(logs_df['menu_name'].dropna().unique()))
                selected_menus = st.multiselect("確認したい種目名を選択（複数選択可能・未選択で全種目）", options=all_menu_names, default=[], key=f"{key_prefix}_menu_names")
                
            st.markdown("##### 📅 期間で絞り込み")
            min_d = pd.to_datetime(logs_df['date']).min().date()
            max_d = pd.to_datetime(logs_df['date']).max().date()
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                start_date = st.date_input("開始日", min_d, key=f"{key_prefix}_start_date")
            with col_d2:
                end_date = st.date_input("終了日", max_d, key=f"{key_prefix}_end_date")
                
            filtered = logs_df.copy()
            if filter_t != "すべて": filtered = filtered[filtered['team'] == filter_t]
            if filter_s != "すべて": filtered = filtered[filtered['sex'] == filter_s]
            if filter_g != "すべて": filtered = filtered[filtered['grade'] == filter_g]
            if filter_e != "すべて": filtered = filtered[filtered['event'] == filter_e]
            if filter_n != "全員": filtered = filtered[filtered['name'] == filter_n]
            if selected_menus: filtered = filtered[filtered['menu_name'].isin(selected_menus)]
            
            filtered['date_dt'] = pd.to_datetime(filtered['date']).dt.date
            filtered = filtered[(filtered['date_dt'] >= start_date) & (filtered['date_dt'] <= end_date)]
            
            return filtered, start_date, end_date

        if view_mode == "📜 過去練習ログの遡り・検索＆編集":
            st.subheader("🔍 過去練習ログの絞り込み・直接編集・変更")
            search_df, start_date, end_date = render_filters_with_date("tab4_m1", include_menu_filter=True)
            search_df = search_df.sort_values(by='date', ascending=False)
            
            st.markdown("---")
            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("該当ログ件数", f"{len(search_df)} 件")
            
            valid_rpe = search_df['load_rpe'].dropna()
            valid_fatigue = search_df['fatigue_level'].dropna()
            
            col_m2.metric("平均 RPE (強度)", f"{valid_rpe.mean():.1f}" if not valid_rpe.empty else "未設定")
            col_m3.metric("平均 疲労度", f"{valid_fatigue.mean():.1f}" if not valid_fatigue.empty else "未設定")
            
            if not search_df.empty:
                st.info("💡 下の表内で『セット数・回数』『強度(RPE)』『疲労度』『備考・メモ』『日付』を直接修正して『✏️ 変更を確定して保存』ボタンを押してください。")
                
                edit_logs_df = search_df[['log_id', 'date', 'name', 'team', 'category', 'menu_name', 'sets_reps', 'load_rpe', 'fatigue_level', 'memo']].copy()
                
                edited_logs_table = st.data_editor(
                    edit_logs_df,
                    column_config={
                        "log_id": st.column_config.NumberColumn("ログID", disabled=True),
                        "date": st.column_config.TextColumn("日付"),
                        "name": st.column_config.TextColumn("氏名", disabled=True),
                        "team": st.column_config.TextColumn("チーム", disabled=True),
                        "category": st.column_config.TextColumn("カテゴリ", disabled=True),
                        "menu_name": st.column_config.TextColumn("メニュー名", disabled=True),
                        "sets_reps": st.column_config.TextColumn("セット数・回数・設定"),
                        "load_rpe": st.column_config.NumberColumn("強度(RPE 1-10)", min_value=1, max_value=10),
                        "fatigue_level": st.column_config.NumberColumn("疲労度(1-5)", min_value=1, max_value=5),
                        "memo": st.column_config.TextColumn("備考・メモ")
                    },
                    use_container_width=True,
                    hide_index=True,
                    key="tab4_logs_editor"
                )
                
                col_save, col_down, col_del = st.columns([2, 2, 1])
                with col_save:
                    if st.button("✏️ 編集した内容をデータベースに保存", type="primary", key="tab4_save_edited_logs"):
                        conn = get_connection()
                        c = conn.cursor()
                        for _, row in edited_logs_table.iterrows():
                            c.execute("""
                                UPDATE practice_logs 
                                SET date = ?, sets_reps = ?, load_rpe = ?, fatigue_level = ?, memo = ?
                                WHERE id = ?
                            """, (str(row['date']), str(row['sets_reps']), row['load_rpe'], row['fatigue_level'], str(row['memo']), int(row['log_id'])))
                        conn.commit()
                        conn.close()
                        st.success("🎉 過去練習ログの変更内容を正常に保存しました！")
                        st.rerun()

                with col_down:
                    csv_data = edited_logs_table.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label="📥 検索結果をCSVダウンロード",
                        data=csv_data,
                        file_name=f"practice_logs_{start_date}_to_{end_date}.csv",
                        mime="text/csv",
                        key="tab4_csv_btn"
                    )
                with col_del:
                    with st.expander("🗑️ 過去練習ログの消去"):
                        selected_log_id = st.selectbox("削除するログIDを選択", options=edited_logs_table['log_id'].tolist(), key="tab4_del_log_id")
                        if st.button("❌ 選択したログを削除", type="primary", key="tab4_del_log_btn"):
                            conn = get_connection()
                            c = conn.cursor()
                            c.execute("DELETE FROM practice_logs WHERE id = ?", (selected_log_id,))
                            conn.commit()
                            conn.close()
                            st.success(f"ログID: {selected_log_id} を削除しました。")
                            st.rerun()
            else:
                st.warning("指定された条件に該当する練習ログは見つかりませんでした。")

        elif view_mode == "🏆 チーム・性別比較グラフトレンド":
            st.subheader("📈 練習強度（RPE）と疲労度の推移・比較グラフ")
            
            st.markdown("##### 🔍 分析対象の絞り込み（属性＋期間）")
            trend_df, start_d, end_d = render_filters_with_date("tab4_m2")
            
            st.markdown("---")
            group_col = st.selectbox("グラフの比較軸（グループ分け）を選択", ["team", "sex", "grade", "event"], key="tab4_group_col")
            
            if not trend_df.empty:
                daily_grp = trend_df.groupby(['date', group_col])[['load_rpe', 'fatigue_level']].mean().reset_index()
                
                fig_rpe = px.line(daily_grp, x='date', y='load_rpe', color=group_col, markers=True, title=f"{group_col} 別 平均練習強度 (RPE) 推移 ({start_d} 〜 {end_d})")
                st.plotly_chart(fig_rpe, use_container_width=True)
                
                fig_fatigue = px.line(daily_grp, x='date', y='fatigue_level', color=group_col, markers=True, title=f"{group_col} 別 平均疲労度 推移 ({start_d} 〜 {end_d})")
                st.plotly_chart(fig_fatigue, use_container_width=True)
            else:
                st.warning("該当するデータが存在しません。絞り込み条件を変更してください。")

        elif view_mode == "⚖️ 練習カテゴリバランス":
            st.subheader("⚖️ 実施練習カテゴリの割合 & 日別実施推移")
            
            st.markdown("##### 🔍 対象グループ・個人・期間の絞り込み")
            cat_filtered_df, start_d, end_d = render_filters_with_date("tab4_m3")
            
            st.markdown("---")
            if not cat_filtered_df.empty:
                cat_filtered_df = cat_filtered_df.sort_values('date')
                
                col_c1, col_c2 = st.columns([1, 1])
                with col_c1:
                    cat_counts = cat_filtered_df['category'].value_counts().reset_index()
                    cat_counts.columns = ['category', 'count']
                    fig_pie = px.pie(cat_counts, values='count', names='category', title=f"練習カテゴリ構成割合 ({start_d} 〜 {end_d})", hole=0.4)
                    st.plotly_chart(fig_pie, use_container_width=True)
                with col_c2:
                    st.markdown("##### 📊 カテゴリ別実施回数内訳")
                    st.dataframe(cat_counts.rename(columns={'category': '練習カテゴリ', 'count': '実施回数（件）'}), use_container_width=True)
                
                st.markdown("---")
                st.subheader("📅 日付ごとのカテゴリ実施推移")
                cat_daily_counts = cat_filtered_df.groupby(['date', 'category']).size().reset_index(name='count')
                fig_cat_timeline = px.bar(
                    cat_daily_counts, 
                    x='date', 
                    y='count', 
                    color='category', 
                    title=f"日付ごとの練習カテゴリ実施件数推移 ({start_d} 〜 {end_d})",
                    labels={'count': '実施メニュー数', 'date': '日付', 'category': 'カテゴリ'}
                )
                st.plotly_chart(fig_cat_timeline, use_container_width=True)
            else:
                st.warning("該当するデータが存在しません。絞り込み条件を変更してください。")

        elif view_mode == "📈 負荷・疲労度推移（全体・絞り込み）":
            st.subheader("📈 負荷・疲労度の推移 & ログ一覧")
            
            st.markdown("##### 🔍 分析対象の絞り込み（属性＋期間）")
            load_filtered_df, start_d, end_d = render_filters_with_date("tab4_m4")
            
            st.markdown("---")
            if not load_filtered_df.empty:
                load_filtered_df = load_filtered_df.sort_values('date')
                
                fig_load = px.bar(
                    load_filtered_df, 
                    x='date', 
                    y='load_rpe', 
                    color='category', 
                    hover_data=['name', 'menu_name', 'sets_reps', 'memo'], 
                    title=f"対象データの練習強度 (RPE) & 実施カテゴリ履歴 ({start_d} 〜 {end_d})"
                )
                st.plotly_chart(fig_load, use_container_width=True)
                
                daily_fatigue = load_filtered_df.groupby('date')['fatigue_level'].mean().reset_index()
                fig_fatigue = px.line(
                    daily_fatigue, 
                    x='date', 
                    y='fatigue_level', 
                    markers=True, 
                    title=f"対象データの平均疲労度推移 ({start_d} 〜 {end_d})"
                )
                st.plotly_chart(fig_fatigue, use_container_width=True)
                
                st.markdown("##### 📋 対象ログデータ")
                show_load_df = load_filtered_df[['date', 'name', 'team', 'sex', 'grade', 'event', 'category', 'menu_name', 'weight_or_dist', 'sets_reps', 'load_rpe', 'fatigue_level', 'memo']]
                st.dataframe(show_load_df.rename(columns={
                    'date': '日付', 'name': '氏名', 'team': 'チーム', 'sex': '性別', 'grade': '学年・所属', 'event': '主種目',
                    'category': 'カテゴリ', 'menu_name': 'メニュー名', 'weight_or_dist': '重量/距離',
                    'sets_reps': 'セット数・回数', 'load_rpe': '強度(RPE)', 'fatigue_level': '疲労度', 'memo': '備考・メモ'
                }), use_container_width=True)
            else:
                st.warning("該当するデータが存在しません。絞り込み条件を変更してください。")

# -------------------------------------------------------------------
# タブ5: Excel一括インポート（選手データ & 練習メニュー）
# -------------------------------------------------------------------
with tab5:
    st.header("📂 Excel一括インポート（選手データ & 練習メニュー）")
    
    with st.expander("👤 選手データの一括登録（シート個別選択・全シート一括対応）", expanded=True):
        uploaded_ath_file = st.file_uploader("選手リストExcel（選手.xlsx）をアップロードしてください", type=["xlsx", "xls"], key="tab5_ath_file")
        if uploaded_ath_file is not None:
            xls_ath = pd.ExcelFile(uploaded_ath_file)
            sheet_options = ["全シートを一括統合"] + xls_ath.sheet_names
            selected_ath_sheet = st.selectbox("取り込むシートを選択", sheet_options, index=0, key="tab5_ath_sheet_select")
            
            if st.button("🔍 指定シートを解析してプレビュー表示", type="primary", key="tab5_parse_ath_btn"):
                parsed_athletes_dict = {}
                target_sheets = xls_ath.sheet_names if selected_ath_sheet == "全シートを一括統合" else [selected_ath_sheet]
                
                for sheet_name in target_sheets:
                    df_ath_raw = pd.read_excel(uploaded_ath_file, sheet_name=sheet_name)
                    
                    column_mapping = {
                        '氏名': 'name', '名前': 'name',
                        '性別': 'sex', '性': 'sex', 'gender': 'sex',
                        'チーム': 'team', '所属': 'team',
                        'ID': 'student_id', '学籍ID': 'student_id',
                        '学年': 'grade',
                        '種目': 'event'
                    }
                    df_ath_raw = df_ath_raw.rename(columns=column_mapping)
                    
                    if 'name' not in df_ath_raw.columns:
                        continue
                        
                    for _, row in df_ath_raw.iterrows():
                        name_val = str(row['name']).strip() if pd.notna(row['name']) else ""
                        if not name_val or name_val.lower() == 'nan': continue
                        
                        sex_val = str(row.get('sex', '')).strip() if pd.notna(row.get('sex')) else ""
                        if sex_val in ['男', '男子']: sex_val = "男子"
                        elif sex_val in ['女', '女子']: sex_val = "女子"
                        else: sex_val = "未設定"
                            
                        team_val = str(row.get('team', '')).strip() if pd.notna(row.get('team')) else ""
                        if team_val in ["A", "B", "C", "D"]: team_val = f"{team_val}チーム"
                        elif team_val not in ["Aチーム", "Bチーム", "Cチーム", "Dチーム"]: team_val = "未設定"
                            
                        grade_val = str(row.get('grade', '')).strip() if pd.notna(row.get('grade')) else ""
                        if grade_val and not grade_val.endswith("年") and grade_val.isdigit(): grade_val = f"{grade_val}年"
                        if grade_val not in ["1年", "2年", "3年", "4年", "M1", "M2", "社会人"]: grade_val = "未設定"
                            
                        raw_event = str(row.get('event', '')).strip() if pd.notna(row.get('event')) else ""
                        if raw_event in ['Deca', 'Hep', '混成']: event_val = "混成(Deca/Hep)"
                        elif raw_event in ['HJ', '走高跳']: event_val = "走高跳(HJ)"
                        elif raw_event in ['PV', '棒高跳']: event_val = "棒高跳(PV)"
                        elif raw_event in ['LJ', '走幅跳']: event_val = "走幅跳(LJ)"
                        elif raw_event in ['TJ', '三段跳']: event_val = "三段跳(TJ)"
                        else: event_val = "未設定"
                        
                        raw_id = row.get('student_id')
                        student_id_val = str(int(raw_id)) if pd.notna(raw_id) and isinstance(raw_id, (int, float)) else (str(raw_id).strip() if pd.notna(raw_id) else "")

                        if name_val not in parsed_athletes_dict:
                            parsed_athletes_dict[name_val] = {
                                "取り込む": True, "学籍ID": student_id_val, "選手氏名": name_val,
                                "性別": sex_val, "学年・所属": grade_val, "主種目": event_val, "所属チーム": team_val
                            }
                        else:
                            curr = parsed_athletes_dict[name_val]
                            if student_id_val and curr["学籍ID"] == "": curr["学籍ID"] = student_id_val
                            if sex_val != "未設定": curr["性別"] = sex_val
                            if grade_val != "未設定": curr["学年・所属"] = grade_val
                            if event_val != "未設定": curr["主種目"] = event_val
                            if team_val != "未設定": curr["所属チーム"] = team_val
                
                df_parsed_ath = pd.DataFrame(list(parsed_athletes_dict.values()))
                st.session_state["tab5_parsed_ath_df"] = df_parsed_ath

        if "tab5_parsed_ath_df" in st.session_state:
            st.markdown("---")
            st.subheader("📋 選手データ解析結果プレビュー")
            edited_ath_file_df = st.data_editor(
                st.session_state["tab5_parsed_ath_df"],
                column_config={
                    "取り込む": st.column_config.CheckboxColumn("取り込む", default=True),
                    "学籍ID": st.column_config.TextColumn("学籍ID"),
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

            if st.button("💾 確定して選手を一括保存・更新", type="primary", key="tab5_save_ath_btn"):
                conn = get_connection()
                c = conn.cursor()
                added_count = 0
                for _, row in edited_ath_file_df.iterrows():
                    if not row["取り込む"]: continue
                    name_val = str(row["選手氏名"]).strip()
                    if not name_val or name_val == "nan": continue
                    
                    sid = str(row.get("学籍ID", "")).strip()
                    sex = str(row.get("性別", "未設定"))
                    grade = str(row.get("学年・所属", "未設定"))
                    event = str(row.get("主種目", "未設定"))
                    team = str(row.get("所属チーム", "未設定"))
                    
                    c.execute("SELECT id FROM athletes WHERE name = ?", (name_val,))
                    existing = c.fetchone()
                    if existing:
                        c.execute("""
                            UPDATE athletes 
                            SET student_id = CASE WHEN ? != '' THEN ? ELSE student_id END,
                                sex = CASE WHEN ? != '未設定' THEN ? ELSE sex END,
                                grade = CASE WHEN ? != '未設定' THEN ? ELSE grade END,
                                event = CASE WHEN ? != '未設定' THEN ? ELSE event END,
                                team = CASE WHEN ? != '未設定' THEN ? ELSE team END
                            WHERE name = ?
                        """, (sid, sid, sex, sex, grade, grade, event, event, team, team, name_val))
                    else:
                        c.execute("INSERT INTO athletes (student_id, name, sex, grade, event, team) VALUES (?, ?, ?, ?, ?, ?)",
                                  (sid, name_val, sex, grade, event, team))
                    added_count += 1
                conn.commit()
                conn.close()
                st.success(f"🎉 {added_count} 名の選手情報をデータベースへ同期・保存しました！")
                del st.session_state["tab5_parsed_ath_df"]
                st.rerun()

    st.markdown("---")

    st.subheader("📂 練習メニューExcel自動分解＆一括インポート（シート選択対応）")
    uploaded_menu_file = st.file_uploader("月別トレーニングメニューExcelをアップロードしてください", type=["xlsx", "xls"], key="tab5_menu_file")

    if uploaded_menu_file is not None:
        xls_menu = pd.ExcelFile(uploaded_menu_file)
        menu_sheet_options = ["全シートを一括解析"] + xls_menu.sheet_names
        selected_menu_sheet = st.selectbox("解析・取り込むシートを選択", menu_sheet_options, index=0, key="tab5_menu_sheet_select")

        if st.button("🔍 自動解析・全体/混成メニュー判定プレビュー実行", type="primary", key="tab5_parse_menu_btn"):
            target_menu_sheets = xls_menu.sheet_names if selected_menu_sheet == "全シートを一括解析" else [selected_menu_sheet]
            parsed_data = []

            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT menu_name, category FROM menu_master")
            db_master_map = {row[0].strip(): row[1].strip() for row in c.fetchall()}
            conn.close()

            ignore_phrases = [
                '各自で', '行う人は', '連絡', '回答期限', 'フォームです', '説明会', 
                '準備', '解散', '集合', '移動', '各自調整', '各自ケア', 'ミーティング', 
                '確認', '持参', '提出', '健康診断', '研究室', '組に分かれて', '以下を', '注意'
            ]

            for s_name in target_menu_sheets:
                df_sheet = pd.read_excel(uploaded_menu_file, sheet_name=s_name)
                
                header_row = 1 if len(df_sheet) > 1 and any('日付' in str(c) or '分類' in str(c) or '全体メニュー' in str(c) for c in df_sheet.iloc[1].values) else 0
                if header_row != 0:
                    df_sheet.columns = df_sheet.iloc[header_row]
                    df_data = df_sheet.iloc[header_row+1:].copy()
                else:
                    df_data = df_sheet.copy()

                col_date = next((c for c in df_data.columns if '日付' in str(c)), None)
                col_cat = next((c for c in df_data.columns if '分類' in str(c) or 'カテゴリ' in str(c)), None)
                col_overall_menu = next((c for c in df_data.columns if any(k in str(c) for k in ['全体メニュー', 'メニュー', '項目'])), None)
                col_combined_menu = next((c for c in df_data.columns if '混成メニュー' in str(c)), None)
                col_memo = next((c for c in df_data.columns if any(k in str(c) for k in ['メモ', '補足'])), None)

                for _, row in df_data.iterrows():
                    date_val = str(row.get(col_date, '')).split(' ')[0] if col_date else ""
                    if not date_val or date_val == 'nan': continue
                    
                    raw_cat_val = str(row.get(col_cat, '')) if col_cat else ""
                    memo_text = str(row.get(col_memo, '')) if col_memo else ""
                    if memo_text == 'nan': memo_text = ""
                    
                    menu_targets = []
                    if col_overall_menu and pd.notna(row.get(col_overall_menu)):
                        menu_targets.append(("全体", str(row.get(col_overall_menu))))
                    if col_combined_menu and pd.notna(row.get(col_combined_menu)):
                        menu_targets.append(("混成", str(row.get(col_combined_menu))))

                    for default_grp, raw_menu_text in menu_targets:
                        if not raw_menu_text.strip() or raw_menu_text == 'nan': continue
                        lines = [line.strip() for line in re.split(r'\r\n|\n|\r', raw_menu_text) if line.strip()]

                        for line in lines:
                            if any(phrase in line for phrase in ignore_phrases): continue

                            bullet_match = re.match(r'^[・＊\-\*\※\◆\■\●\○\s]+', line)
                            if not bullet_match and default_grp != "混成": continue

                            cleaned_line = re.sub(r'^[・＊\-\*\※\◆\■\●\○\s]+', '', line).strip()

                            if default_grp == "混成":
                                target_group = "混成(Deca/Hep)"
                            else:
                                if "女子" in cleaned_line and "男子" not in cleaned_line: target_group = "女子"
                                elif "男子" in cleaned_line and "女子" not in cleaned_line: target_group = "男子"
                                elif "1年生" in cleaned_line or "一般" in cleaned_line: target_group = "1年生/一般"
                                else: target_group = "全体"

                            split_pattern = r'^([a-zA-Z\s\-\(\)\/぀-ゟ゠-ヿ一-鿿]+?)(?:[\s ]+([\d\&\*\-\,\.\%\~x×].*|男子.*|女子.*|M\d.*|W\d.*))?$'
                            match = re.search(split_pattern, cleaned_line)
                            
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

                            if len(menu_name) <= 1 or menu_name in ["・", "＊", "-", "※", "◆", "■", "●", "○"]: continue

                            if menu_name in db_master_map:
                                auto_category = db_master_map[menu_name]
                            else:
                                auto_category = determine_category(raw_cat_val, menu_name)

                            parsed_data.append({
                                "取り込む": True,
                                "対象シート": s_name,
                                "日付": date_val,
                                "対象グループ": target_group,
                                "推定カテゴリ": auto_category,
                                "種目名 (マスター名)": menu_name,
                                "セット数・回数": detail_setting,
                                "備考・メモ": memo_text
                            })

            st.session_state["tab5_parsed_menu_df"] = pd.DataFrame(parsed_data)

    if "tab5_parsed_menu_df" in st.session_state:
        st.markdown("---")
        st.subheader("📋 練習メニュー解析結果プレビュー")
        st.info("💡 シート選択で『特定の1シート』または『全シートを一括解析』から柔軟に選べます。")

        edited_menu_df = st.data_editor(
            st.session_state["tab5_parsed_menu_df"],
            column_config={
                "取り込む": st.column_config.CheckboxColumn("取り込む", default=True),
                "対象シート": st.column_config.TextColumn("対象シート", disabled=True),
                "対象グループ": st.column_config.SelectboxColumn("対象グループ", options=["全体", "男子", "女子", "1年生/一般", "混成(Deca/Hep)", "未設定"], default="全体"),
                "推定カテゴリ": st.column_config.SelectboxColumn("カテゴリ", options=["ウエイトトレーニング", "スプリント・走系", "跳躍・技術練習", "補強・サーキット", "コンディショニング/ケア"], default="補強・サーキット")
            },
            num_rows="dynamic",
            use_container_width=True,
            key="tab5_menu_editor"
        )

        if st.button("💾 確定して練習ログを一括保存", type="primary", key="tab5_save_menu_btn"):
            conn = get_connection()
            c = conn.cursor()
            
            c.execute("SELECT id, sex, event FROM athletes")
            athletes = c.fetchall()

            c.execute("SELECT menu_name, id, category FROM menu_master")
            menu_map = {row[0].strip(): (row[1], row[2].strip()) for row in c.fetchall()}

            saved_count = 0
            for _, row in edited_menu_df.iterrows():
                if not row["取り込む"]: continue

                target_grp = row["対象グループ"]
                cat_val = str(row["推定カテゴリ"]).strip()
                m_name = str(row["種目名 (マスター名)"]).strip()
                sets_reps_val = str(row["セット数・回数"]).strip()
                date_val = row["日付"]
                memo_val = str(row["備考・メモ"]).strip()

                if not m_name: continue

                if m_name not in menu_map:
                    c.execute("INSERT OR IGNORE INTO menu_master (category, menu_name, target_note) VALUES (?, ?, ?)", (cat_val, m_name, "Excel自動登録"))
                    c.execute("SELECT id, category FROM menu_master WHERE menu_name = ?", (m_name,))
                    res = c.fetchone()
                    if res: menu_map[m_name] = (res[0], res[1])

                menu_id, _ = menu_map.get(m_name, (None, None))

                if menu_id and athletes:
                    for a_id, sex, event in athletes:
                        if target_grp == "女子" and sex != '女子': continue
                        if target_grp == "男子" and sex != '男子': continue
                        if target_grp == "混成(Deca/Hep)" and event not in ['混成(Deca/Hep)', 'Deca', 'Hep', '十種競技', '七種競技']: continue

                        c.execute("""
                            INSERT INTO practice_logs 
                            (athlete_id, menu_id, date, weight_or_dist, sets_reps, load_rpe, fatigue_level, memo) 
                            VALUES (?, ?, ?, ?, ?, NULL, NULL, ?)
                        """, (a_id, menu_id, date_val, 0.0, sets_reps_val, memo_val))
                        saved_count += 1

            conn.commit()
            conn.close()
            st.success(f"🎉 練習ログの一括登録が完了しました！（合計 {saved_count} 件のログを追加）")
            del st.session_state["tab5_parsed_menu_df"]
            st.rerun()
