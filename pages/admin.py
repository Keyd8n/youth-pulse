import streamlit as st
import pandas as pd
import re
from utils.db import get_db
from utils.ai_helper import generate_survey_description
from utils.auth import check_password

st.set_page_config(page_title="Адмін-панель", page_icon="🛠")

if not check_password():
    st.stop()

st.markdown("""
<style>
    [data-testid="stSidebar"] {display: none;}
    [data-testid="stMainMenuButton"] {display: none;}
</style>
""", unsafe_allow_html=True)

# === ОЧИЩЕННЯ ТЕКСТУ ===
def clean_question_text(text):
    """Видаляє нумерацію на початку (наприклад '1. ', '2) ', '1 - ')"""
    if pd.isna(text): return "Без назви"
    text = str(text).strip()
    return re.sub(r'^\d+[\.\)\-\s]+\s*', '', text)

def normalize_text(text):
    if pd.isna(text): return None
    text = str(text).strip()
    garbage = ["", "-", "—", "–", "_", ".", "?", "!", "n/a", "nan", "null", "none", "немає", "не знаю", "no"]
    if text.lower() in garbage: return None
    return " ".join(text.split())

def smart_split(text, delimiter=','):
    if not isinstance(text, str): return [text]
    pattern = r',\s*(?![^()]*\))'
    parts = text.split(';') if delimiter == ';' else re.split(pattern, text)
    return [normalize_text(p) for p in parts if normalize_text(p)]

def detect_type(series):
    clean_series = series.apply(normalize_text).dropna()
    if clean_series.empty: return "text"
    
    total_rows = len(clean_series)
    unique_vals = clean_series.nunique()
    avg_len = clean_series.astype(str).map(len).mean()

    cnt_semicolon = clean_series.str.contains(';', regex=False).sum()
    if cnt_semicolon >= 1:
        return "multiple_choice"

    counts = clean_series.value_counts()
    try:
        first_chars = [str(k).split()[0] for k in counts.keys()]
        if all(c.isdigit() and 0 <= int(c) <= 10 for c in first_chars) and len(counts) <= 12:
            return "rating"
    except: pass

    if (unique_vals > 50 and (unique_vals / total_rows) > 0.8) or avg_len > 80:
        return "text"

    return "single_choice"

def format_data_for_type(series, selected_type):
    clean_series = series.apply(normalize_text).dropna()
    if selected_type == "text":
        return {"answers": clean_series.head(300).tolist()} 
    
    if selected_type == "multiple_choice":
        cnt_semicolon = clean_series.str.contains(';', regex=False).sum()
        delimiter = ';' if cnt_semicolon > 0 else ','
        expanded_list = []
        for item in clean_series:
            expanded_list.extend(smart_split(item, delimiter))
        counts = pd.Series(expanded_list).value_counts()
    else:
        counts = clean_series.value_counts()
        
    return counts.head(50).to_dict()

# === UI ===
st.title("🛠 Імпорт та Налаштування")
nav_col1, nav_col2, nav_col3 = st.columns([8, 1, 1])
with nav_col2:
    if st.button("✏️ Редактор", width='stretch', key='to_editor'):
        st.switch_page("pages/editor.py")
with nav_col3:
    if st.button("⬅️ На головну", width='stretch', key='to_home'):
        st.switch_page("main.py")

st.divider()

if 'stage' not in st.session_state: st.session_state.stage = 0
if 'df_clean' not in st.session_state: st.session_state.df_clean = None
if 'survey_meta' not in st.session_state: st.session_state.survey_meta = {}

uploaded_file = st.file_uploader("1. Оберіть файл (CSV або Excel)", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    if st.session_state.stage == 0:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)

            df.columns = [clean_question_text(col) for col in df.columns]
            
        except Exception as e:
            st.error(f"Помилка при зчитуванні файлу: {e}")
            st.stop()
        
        with st.form("settings_form"):
            st.subheader("2. Основні параметри")
            clean_filename = uploaded_file.name
            for ext in [".csv", ".xlsx", ".xls"]:
                clean_filename = clean_filename.replace(ext, "")
                
            title = st.text_input("Назва", value=clean_filename)
            org = st.text_input("Організація", "IT Kamianets")
            
            all_cols = df.columns.tolist()
            stop_words = ["timestamp", "email", "name", "піб", "пошта"]
            default_drop = [c for c in all_cols if any(sw in c.lower() for sw in stop_words)]
            cols_to_drop = st.multiselect("Видалити колонки:", all_cols, default=default_drop)
            
            btn_analyze = st.form_submit_button("➡️ Аналізувати питання")
        
        if btn_analyze:
            st.session_state.df_clean = df.drop(columns=cols_to_drop)
            st.session_state.survey_meta = {
                "title": title, "org": org, 
                "participants": len(df)
            }
            st.session_state.suggested_types = {} 
            for col in st.session_state.df_clean.columns:
                st.session_state.suggested_types[col] = detect_type(st.session_state.df_clean[col])
            
            st.session_state.stage = 1
            st.rerun()

    if st.session_state.stage == 1:
        st.info("Перевірте та відредагуйте типи питань")
        processing_cols = st.session_state.df_clean.columns.tolist()
        
        with st.form("review_form"):
            st.subheader("3. Типи питань")
            user_selected_types = {}
            type_options = ["single_choice", "multiple_choice", "text", "rating"]
            type_labels = {
                "single_choice": "🥧 Один вибір (Pie Chart)",
                "multiple_choice": "📶 Множинний вибір (Bar Chart)",
                "text": "💬 Текст / Розгорнуті відповіді",
                "rating": "⭐ Рейтинг (1-5)"
            }

            for col in processing_cols:
                c1, c2 = st.columns([3, 2])
                with c1:
                    st.write(f"**{col}**")
                    try:
                        example = str(st.session_state.df_clean[col].dropna().iloc[0])[:60]
                        st.caption(f"Приклад: {example}...")
                    except IndexError:
                        st.caption("Немає даних")
                with c2:
                    default = st.session_state.suggested_types.get(col, "single_choice")
                    user_selected_types[col] = st.selectbox(
                        "Тип", type_options, 
                        index=type_options.index(default),
                        format_func=lambda x: type_labels[x],
                        key=f"sel_{col}"
                    )
                st.divider()
            
            btn_save = st.form_submit_button("💾 Зберегти опитування")
            
        if btn_save:
            final_questions = []
            progress_bar = st.progress(0)
            for idx, col in enumerate(processing_cols):
                sel_type = user_selected_types[col]
                q_data = format_data_for_type(st.session_state.df_clean[col], sel_type)
                
                final_questions.append({
                    "text": col,
                    "type": sel_type,
                    "data": q_data
                })
                progress_bar.progress((idx + 1) / len(processing_cols))

            meta = st.session_state.survey_meta
            new_survey = {
                "id": abs(hash(meta["title"] + pd.Timestamp.now().strftime("%S"))) % 100000,
                "title": meta["title"],
                "organization": meta.get("org", ""),
                "participants": meta["participants"],
                "date": pd.Timestamp.now().strftime("%Y-%m-%d"),
                "questions": final_questions
            }
            
            ai_description = generate_survey_description(meta["title"], final_questions)
            if ai_description:
                new_survey["ai_description"] = ai_description
            
            get_db().surveys.insert_one(new_survey)
            st.success("✅ Готово! Опитування збережено. Перейдіть на головну.")
            if st.button("Завантажити ще", key="load_more_btn"):
                st.session_state.stage = 0
                st.rerun()