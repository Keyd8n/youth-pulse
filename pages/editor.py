import streamlit as st
import pandas as pd
from utils.db import get_db, get_all_surveys
from utils.ai_helper import generate_survey_description
from bson.objectid import ObjectId
from utils.auth import check_password
st.set_page_config(page_title="Редактор опитувань", page_icon="✏️", layout="wide")
# === БЛОК БЕЗПЕКИ ===
if not check_password():
    st.stop()
# ===================
# Приховуємо меню та бічну панель
st.markdown("""
<style>
    [data-testid="stSidebar"] {display: none;}
    [data-testid="stMainMenuButton"] {display: none;}
</style>
""", unsafe_allow_html=True)
def get_all_surveys_with_id():
    """Отримує всі опитування з ObjectId"""
    db = get_db()
    return list(db.surveys.find({}))

def update_survey(survey_id, updated_data):
    """Оновлює опитування в базі даних"""
    db = get_db()
    db.surveys.update_one(
        {"_id": ObjectId(survey_id)},
        {"$set": updated_data}
    )

def delete_survey(survey_id):
    """Видаляє опитування з бази даних"""
    db = get_db()
    db.surveys.delete_one({"_id": ObjectId(survey_id)})

# ФУНКЦІЇ ФОРМАТУВАННЯ
def format_date(date_str):
    """Форматує дату для відображення"""
    try:
        return pd.to_datetime(date_str).strftime("%d.%m.%Y")
    except:
        return date_str

def generate_description_for_survey(survey_data):
    """Генерує опис опитування за допомогою AI"""
    title = survey_data.get("title", "")
    questions = survey_data.get("questions", [])
    
    if not title or not questions:
        return None
    
    return generate_survey_description(title, questions)

# ПОЧАТОК ДОДАТКУ
st.title("✏️ Редактор опитувань")
st.markdown("Редагуйте назву, організацію та інші параметри опитувань")

# Кнопки навігації
nav_col1, nav_col2, nav_col3 = st.columns([8, 1, 1])
with nav_col2:
    if st.button("🛠 Адмін", width='stretch', key='to_admin'):
        st.switch_page("pages/admin.py")
with nav_col3:
    if st.button("⬅️ На головну", width='stretch', key='to_home'):
        st.switch_page("main.py")

st.divider()

st.divider()

# Завантажуємо всі опитування
try:
    surveys = get_all_surveys_with_id()
except Exception as e:
    st.error(f"Помилка при завантаженні опитувань: {e}")
    st.stop()

if not surveys:
    st.info("📭 Немає опитувань для редагування. Спочатку завантажте опитування в Адмін-панель.")
    st.stop()

# ФІЛЬТРИ
st.subheader("🔍 Фільтри")
f_col1, f_col2, f_col3 = st.columns(3)

with f_col1:
    all_orgs = ["Всі"] + list(set([s.get("organization", "Невідома") for s in surveys]))
    selected_org = st.selectbox("Організація", all_orgs)

with f_col2:
    search_query = st.text_input("Пошук по названію", "")

with f_col3:
    sort_by = st.selectbox("Сортування", ["За датою (нові першими)", "За датою (старі першими)", "За назвою"])

# ФІЛЬТРАЦІЯ ОПИТУВАНЬ
filtered_surveys = surveys.copy()

# Фільтр по організації
if selected_org != "Всі":
    filtered_surveys = [s for s in filtered_surveys if s.get("organization") == selected_org]

# Пошук по назві
if search_query:
    filtered_surveys = [s for s in filtered_surveys if search_query.lower() in s.get("title", "").lower()]

# Сортування
if sort_by == "За датою (нові першими)":
    filtered_surveys = sorted(filtered_surveys, key=lambda x: x.get("date", ""), reverse=True)
elif sort_by == "За датою (старі першими)":
    filtered_surveys = sorted(filtered_surveys, key=lambda x: x.get("date", ""))
else:
    filtered_surveys = sorted(filtered_surveys, key=lambda x: x.get("title", ""))

# ВІДОБРАЖЕННЯ СТРІЧКИ ОПИТУВАНЬ
st.subheader(f"📋 Опитування ({len(filtered_surveys)})")

if filtered_surveys:
    for idx, survey in enumerate(filtered_surveys):
        with st.container(border=True):
            # ОСНОВНА ІНФОРМАЦІЯ
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                st.markdown(f"### {survey.get('title', 'Без названия')}")
                org = survey.get("organization", "Невідома організація")
                participants = survey.get("participants", 0)
                date = format_date(survey.get("date", ""))
                st.caption(f"🏢 {org} | 👥 {participants} учасників | 📅 {date}")
            
            with col2:
                st.metric("Питань", len(survey.get("questions", [])))
            
            with col3:
                if st.button("✏️ Редагувати", key=f"edit_btn_{idx}"):
                    st.session_state.editing_survey_id = str(survey["_id"])
                    st.rerun()

            # ОПИС ОПИТУВАННЯ (якщо є)
            if survey.get("ai_description"):
                with st.expander("📖 Опис"):
                    st.write(survey["ai_description"])

st.divider()

# ФОРМА РЕДАГУВАННЯ (якщо вибране опитування)
if "editing_survey_id" in st.session_state:
    # Знаходимо опитування за ID
    editing_survey = None
    for s in surveys:
        if str(s["_id"]) == st.session_state.editing_survey_id:
            editing_survey = s
            break
    
    if editing_survey:
        st.subheader(f"Редагування: {editing_survey.get('title')}")
        
        with st.form("edit_survey_form"):
            # ОСНОВНІ ПАРАМЕТРИ
            st.write("**Основні параметри**")
            
            col1, col2 = st.columns(2)
            with col1:
                new_title = st.text_input("Назва опитування", value=editing_survey.get("title", ""))
            with col2:
                new_org = st.text_input("Організація", value=editing_survey.get("organization", ""))
            
            # ІНШІ ПАРАМЕТРИ
            st.write("**Додаткова інформація**")
            new_participants = st.number_input("Кількість учасників", 
                                              value=int(editing_survey.get("participants", 0)), 
                                              min_value=0)
            
            new_date = st.date_input("Дата опитування", 
                                    value=pd.to_datetime(editing_survey.get("date", "today")))
            
            # ОПИС ОПИТУВАННЯ
            st.write("**Опис опитування**")
            desc_col1, desc_col2 = st.columns([5, 1])
            
            with desc_col1:
                new_description = st.text_area("Опис (AI-сгенерований)", 
                                              value=editing_survey.get("ai_description", ""),
                                              height=100,
                                              label_visibility="collapsed")
            
            with desc_col2:
                st.write("")
                st.write("")
                if st.form_submit_button("🤖 Згенерувати", width='stretch'):
                    with st.spinner("Генерую опис..."):
                        ai_desc = generate_description_for_survey(editing_survey)
                        if ai_desc:
                            st.success("✅ Опис згенерований!")
                            # Оновлюємо значення в формі
                            new_description = ai_desc
                        else:
                            st.warning("⚠️ Не вдалось згенерувати опис. Спробуйте пізніше.")
            
            # КНОПКИ ДІЙ
            btn_col1, btn_col2, btn_col3 = st.columns(3)
            
            with btn_col1:
                btn_save = st.form_submit_button("💾 Зберегти", use_container_width=True)
            
            with btn_col2:
                btn_cancel = st.form_submit_button("❌ Скасувати", use_container_width=True)
            
            with btn_col3:
                btn_delete = st.form_submit_button("🗑️ Видалити", use_container_width=True)
            
            # ОБРОБКА КНОПОК
            if btn_save:
                updated_data = {
                    "title": new_title,
                    "organization": new_org,
                    "participants": int(new_participants),
                    "date": new_date.strftime("%Y-%m-%d"),
                    "ai_description": new_description
                }
                try:
                    update_survey(st.session_state.editing_survey_id, updated_data)
                    st.success("✅ Опитування успішно оновлено!")
                    del st.session_state.editing_survey_id
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Помилка при збереженні: {e}")
            
            if btn_cancel:
                del st.session_state.editing_survey_id
                st.rerun()
            
            if btn_delete:
                try:
                    delete_survey(st.session_state.editing_survey_id)
                    st.success("✅ Опитування видалено!")
                    del st.session_state.editing_survey_id
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Помилка при видаленні: {e}")

else:
    st.info("Оберіть опитування для редагування")
