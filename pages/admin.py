import streamlit as st
import pandas as pd
import re
from utils.db import get_db

st.set_page_config(page_title="Адмін-панель", page_icon="🛠")

# --- ДОПОМІЖНІ ФУНКЦІЇ ---

def normalize_text(text):
    """
    Очищає текст і видаляє сміттєві відповіді (прочерки, крапки).
    """
    if pd.isna(text):
        return None
    
    # Перетворюємо в рядок і прибираємо пробіли з країв
    text = str(text).strip()
    
    # 🛑 СПИСОК СМІТТЯ (Garbage Values)
    # Якщо відповідь збігається з цим списком, ми її ігноруємо
    garbage_values = [
        "", "-", "—", "–", "_",          # Різні види тире і пусті рядки
        ".", "?", "!",                   # Розділові знаки
        "n/a", "nan", "null", "none",    # Технічні слова
        "немає", "не знаю", "no", "-"    # Відмови від відповіді
    ]
    
    if text.lower() in garbage_values:
        return None  # Pandas видалить це значення
        
    # Прибираємо зайві пробіли всередині ("Java    Script" -> "Java Script")
    return " ".join(text.split())

def smart_split(text, delimiter=','):
    """
    Розумне розбиття рядка. Ігнорує коми всередині дужок (...).
    """
    if not isinstance(text, str): return [text]
    
    pattern = r',\s*(?![^()]*\))'
    if delimiter == ';':
        parts = text.split(';')
    else:
        parts = re.split(pattern, text)
        
    # Чистимо кожну частину і викидаємо сміття
    clean_parts = []
    for p in parts:
        cleaned = normalize_text(p) # Рекурсивно чистимо кожну частину
        if cleaned:
            clean_parts.append(cleaned)
            
    return clean_parts

def analyze_column(series):
    # 1. Базова очистка (тут видаляються "-" і " ")
    clean_series = series.apply(normalize_text).dropna()
    
    if clean_series.empty: return "text", {}

    total_rows = len(clean_series)
    unique_vals = clean_series.nunique()
    
    # --- ЕТАП 1: ПЕРЕВІРКА НА РОЗДІЛЬНИКИ ---
    cnt_semicolon = clean_series.str.contains(';', regex=False).sum()
    cnt_comma = clean_series.str.contains(',', regex=False).sum()
    
    delimiter = None
    if cnt_semicolon >= 1: delimiter = ';'
    elif cnt_comma >= 1: delimiter = ','
    
    is_multiple = False
    final_expanded = clean_series

    if delimiter:
        expanded_list = []
        for item in clean_series:
            # Використовуємо smart_split, який теж чистить сміття
            expanded_list.extend(smart_split(item, delimiter))
        
        if expanded_list:
            temp_expanded = pd.Series(expanded_list).str.capitalize()
            unique_options_count = temp_expanded.nunique()
            
            if unique_options_count <= 40:
                is_multiple = True
                final_expanded = temp_expanded

    # --- ЕТАП 2: ВИЗНАЧЕННЯ ТИПУ ---
    q_type = "single_choice"
    
    if is_multiple:
        q_type = "multiple_choice"
        counts = final_expanded.value_counts()
    else:
        clean_series = clean_series.str.capitalize()
        counts = clean_series.value_counts()
        
        # Рейтинг
        try:
            first_chars = [str(k).split()[0] for k in counts.keys()]
            if all(c.isdigit() and 0 <= int(c) <= 10 for c in first_chars) and len(counts) <= 12:
                q_type = "rating"
        except: pass

        # Текст
        if q_type != "rating":
            avg_len = clean_series.astype(str).map(len).mean()
            unique_ratio = unique_vals / total_rows
            
            # Якщо речення довгі АБО дуже різноманітні
            if avg_len > 35 or (unique_vals > 15 and unique_ratio > 0.7):
                q_type = "text"
                return "text", {"answers": clean_series.head(100).tolist()}

    # --- ЕТАП 3: ФОРМУВАННЯ ДАНИХ ---
    final_data = {}
    if len(counts) > 15:
        top_15 = counts.head(15)
        other = counts.iloc[15:].sum()
        final_data = top_15.to_dict()
        if other > 0: final_data["Інше / Рідкісні"] = int(other)
    else:
        final_data = counts.to_dict()
        
    return q_type, final_data


# --- ГОЛОВНИЙ ІНТЕРФЕЙС ---
st.title("🛠 Імпорт та Нормалізація")

uploaded_file = st.file_uploader("Оберіть CSV файл", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.write("### Попередній перегляд")
    st.dataframe(df.head(3))

    with st.form("survey_form"):
        st.subheader("Налаштування")
        title = st.text_input("Назва опитування", value=uploaded_file.name.replace(".csv", ""))
        org = st.text_input("Організація", "IT Kamianets")
        category = st.selectbox("Категорія", ["Dev", "QA", "Psychology", "General"])
        
        # Авто-вибір колонок для видалення
        all_cols = df.columns.tolist()
        stop_words = ["час", "time", "timestamp", "email", "пошта", "піб", "name", "ім'я", "прізвище", "user"]
        default_drop = [c for c in all_cols if any(sw in c.lower() for sw in stop_words)]
        
        cols_to_drop = st.multiselect("Видалити конфіденційні колонки:", all_cols, default=default_drop)
        
        submit = st.form_submit_button("Обробити дані")

    if submit:
        processing_df = df.drop(columns=cols_to_drop)
        questions_list = []
        bar = st.progress(0)
        
        for idx, col in enumerate(processing_df.columns):
            q_type, q_data = analyze_column(processing_df[col])
            
            questions_list.append({
                "text": col,
                "type": q_type,
                "data": q_data
            })
            bar.progress((idx + 1) / len(processing_df.columns))

        new_survey = {
            "id": abs(hash(title + pd.Timestamp.now().strftime("%S"))) % 100000,
            "title": title,
            "organization": org,
            "category": category,
            "participants": len(df),
            "date": pd.Timestamp.now().strftime("%Y-%m-%d"),
            "status": "Active",
            "questions": questions_list
        }
        
        get_db().surveys.insert_one(new_survey)
        st.success("✅ Успішно! Дані збережено.")
        
        with st.expander("Деталі обробки (перевірте типи)"):
            for q in questions_list:
                st.markdown(f"**{q['text']}** -> `{q['type']}`")