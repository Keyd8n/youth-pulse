import streamlit as st
import pandas as pd
import re
from utils.db import get_db
from utils.ai_helper import generate_survey_description

st.set_page_config(page_title="Адмін-панель", page_icon="🛠")

# ФУНКЦІЇ ОЧИЩЕННЯ ДАНИХ
def normalize_text(text):
    # Видаляє пусті значення
    if pd.isna(text): return None
    text = str(text).strip()
    # Список значень які вважаються пустими відповідями
    garbage = ["", "-", "—", "–", "_", ".", "?", "!", "n/a", "nan", "null", "none", "немає", "не знаю", "no"]
    if text.lower() in garbage: return None
    return " ".join(text.split())  # Нормалізує пробіли

def smart_split(text, delimiter=','):
    # Розбиває текст на частини за розділювачем, ігноруючи символи в дужках
    if not isinstance(text, str): return [text]
    # Регулярний вираз для розділення по комі, але НЕ всередині дужок
    pattern = r',\s*(?![^()]*\))'
    parts = text.split(';') if delimiter == ';' else re.split(pattern, text)
    return [normalize_text(p) for p in parts if normalize_text(p)]

# АВТОМАТИЧНЕ ВИЯВЛЕННЯ ТИПУ ПИТАННЯ
def detect_type(series):
    # Визначає тип питання на основі аналізу його відповідей
    clean_series = series.apply(normalize_text).dropna()
    if clean_series.empty: return "text"

    # Базові статистики для аналізу
    total_rows = len(clean_series)
    unique_vals = clean_series.nunique()  # Кількість унікальних відповідей
    avg_len = clean_series.astype(str).map(len).mean()  # Середня довжина відповіді

    # МНОЖИННИЙ ВИБІР - якщо у відповідях є крапка з комою (;)
    cnt_semicolon = clean_series.str.contains(';', regex=False).sum()
    if cnt_semicolon >= 1:  # Якщо в 50%+ відповідей є крапка з комою
        return "multiple_choice"  # Це множинний вибір

    # РЕЙТИНГ - числові оцінки від 1 до 10
    counts = clean_series.value_counts()
    try:
        first_chars = [str(k).split()[0] for k in counts.keys()]
        # Якщо всі значення - цифри 0-10 і їх не більше 12 варіантів
        if all(c.isdigit() and 0 <= int(c) <= 10 for c in first_chars) and len(counts) <= 12:
            return "rating"
    except: pass

    # ТЕКСТ - дуже багато унікальних або дуже довгих відповідей
    # Якщо відповідей майже скільки рядків (80%+) абоони дуже довгі (>80 символів)
    if (unique_vals > 50 and (unique_vals / total_rows) > 0.8) or avg_len > 80:
        return "text"

    # ОДНА ВІДПОВІДЬ - за замовчуванням категоріальні дані
    return "single_choice"

# ПІДГОТОВКА ДАНИХ ПІД ТИП
def format_data_for_type(series, selected_type):
    # Форматує дані виходячи з обраного типу питання
    clean_series = series.apply(normalize_text).dropna()
    
    # ТЕКСТ - зберігаємо як список відповідей (топ 300)
    if selected_type == "text":
        return {"answers": clean_series.head(300).tolist()} 
    
    # МНОЖИННИЙ ВИБІР - розбиваємо на окремі елементи та рахуємо
    if selected_type == "multiple_choice":
        # Визначаємо розділювач (крапка з комою або кома)
        cnt_semicolon = clean_series.str.contains(';', regex=False).sum()
        delimiter = ';' if cnt_semicolon > 0 else ','
        
        # Розбиваємо кожну відповідь на частини
        expanded_list = []
        for item in clean_series:
            expanded_list.extend(smart_split(item, delimiter))
        
        # Рахуємо, скільки разів кожний варіант зустрічається
        counts = pd.Series(expanded_list).value_counts()
    else:
        # ОДИНАРНИЙ ВИБІР та РЕЙТИНГ - просто рахуємо унікальні значення
        counts = clean_series.value_counts()
        
    # Зберігаємо топ-50 варіантів (щоб не переповнити базу даних)
    return counts.head(50).to_dict()

st.title("🛠 Імпорт та Налаштування")

# Кнопка повернення на головну
if st.button("⬅️ На головну", width='content'):
    st.switch_page("main.py")

# Ініціалізація стану опитування (якщо його немає)
if 'stage' not in st.session_state: st.session_state.stage = 0
if 'df_clean' not in st.session_state: st.session_state.df_clean = None
if 'survey_meta' not in st.session_state: st.session_state.survey_meta = {}

# Завантаження CSV файлу
uploaded_file = st.file_uploader("1. Оберіть CSV файл", type=["csv"])

if uploaded_file is not None:
    # ПАРАМЕТРИ ОПИТУВАННЯ
    if st.session_state.stage == 0:
        df = pd.read_csv(uploaded_file)
        
        with st.form("settings_form"):
            st.subheader("2. Основні параметри")
            title = st.text_input("Назва", value=uploaded_file.name.replace(".csv", ""))
            org = st.text_input("Організація", "IT Kamianets")
            
            # Видалення ненужних колонок (timestamp, email, ПІБ тощо)
            all_cols = df.columns.tolist()
            stop_words = ["timestamp", "email", "name", "піб", "пошта"]
            default_drop = [c for c in all_cols if any(sw in c.lower() for sw in stop_words)]
            cols_to_drop = st.multiselect("Видалити колонки:", all_cols, default=default_drop)
            
            btn_analyze = st.form_submit_button("➡️ Аналізувати питання")
        
        if btn_analyze:
            # Зберігаємо очищені дані та метаінформацію в session_state
            st.session_state.df_clean = df.drop(columns=cols_to_drop)
            st.session_state.survey_meta = {
                "title": title, "org": org, 
                "participants": len(df)
            }
            # Визначаємо рекомендовані типи для кожного питання
            st.session_state.suggested_types = {} 
            for col in st.session_state.df_clean.columns:
                st.session_state.suggested_types[col] = detect_type(st.session_state.df_clean[col])
            
            st.session_state.stage = 1  # Переходимо на ЕТАП 2
            st.rerun()

    # ЕТАП 2: РЕДАГУВАННЯ ТИПІВ ПИТАНЬ
    if st.session_state.stage == 1:
        st.info("Перевірте та відредагуйте типи питань")
        
        processing_cols = st.session_state.df_clean.columns.tolist()
        
        with st.form("review_form"):
            st.subheader("3. Типи питань")
            
            user_selected_types = {}
            type_options = ["single_choice", "multiple_choice", "text", "rating"]
            type_labels = {
                "single_choice": "Один вибір (Pie Chart)",
                "multiple_choice": "☑️ Множинний вибір (Bar Chart)",
                "text": "Текст / Розгорнуті відповіді",
                "rating": "⭐ Рейтинг (1-5)"
            }

            # Для кожного питання дозволяємо вибрати тип
            for col in processing_cols:
                c1, c2 = st.columns([3, 2])
                with c1:
                    st.write(f"**{col}**")
                    # Показуємо приклад першої відповіді
                    example = str(st.session_state.df_clean[col].dropna().iloc[0])[:60]
                    st.caption(f"Приклад: {example}...")
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
            
        # ЗБЕРІГАННЯ У БАЗУ ДАНИХ
        if btn_save:
            final_questions = []
            
            # Обробляємо кожне питання та форматуємо дані
            progress_bar = st.progress(0)
            for idx, col in enumerate(processing_cols):
                sel_type = user_selected_types[col]
                # Форматуємо дані виходячи з обраного типу
                q_data = format_data_for_type(st.session_state.df_clean[col], sel_type)
                
                final_questions.append({
                    "text": col,
                    "type": sel_type,
                    "data": q_data
                })
                progress_bar.progress((idx + 1) / len(processing_cols))

            # Формуємо документ опитування для MongoDB
            meta = st.session_state.survey_meta
            new_survey = {
                "id": abs(hash(meta["title"] + pd.Timestamp.now().strftime("%S"))) % 100000,
                "title": meta["title"],
                "organization": meta.get("org", ""),
                "participants": meta["participants"],
                "date": pd.Timestamp.now().strftime("%Y-%m-%d"),
                "questions": final_questions
            }
            
            # 🤖 Генеруємо опис опитування за допомогою AI
            ai_description = generate_survey_description(meta["title"], final_questions)
            if ai_description:
                new_survey["ai_description"] = ai_description
            
            # Зберігаємо в базу даних
            get_db().surveys.insert_one(new_survey)
            st.success("✅ Готово! Опитування збережено. Перейдіть на головну.")
            if st.button("Завантажити ще", key="load_more_btn"):
                st.session_state.stage = 0
                st.rerun()