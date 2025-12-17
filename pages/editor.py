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

st.markdown("""
<style>
    [data-testid="stSidebar"] {display: none;}
    [data-testid="stMainMenuButton"] {display: none;}
</style>
""", unsafe_allow_html=True)

# === CALLBACK ФУНКЦІЯ ДЛЯ AI ===
# Ця функція запуститься ПЕРЕД перезавантаженням сторінки
def generate_desc_callback(title, questions):
    # Викликаємо AI генерацію
    ai_desc = generate_survey_description(title, questions)
    if ai_desc:
        # Безпечно оновлюємо стан, бо віджети ще не намальовані
        st.session_state.editor_desc = ai_desc
        st.success("Опис згенеровано! (Вгорі)") # Повідомлення з'явиться зверху

def get_all_surveys_with_id():
    db = get_db()
    return list(db.surveys.find({}))

def update_survey(survey_id, updated_data):
    db = get_db()
    db.surveys.update_one(
        {"_id": ObjectId(survey_id)},
        {"$set": updated_data}
    )

def delete_survey(survey_id):
    db = get_db()
    db.surveys.delete_one({"_id": ObjectId(survey_id)})

def format_date(date_str):
    try:
        return pd.to_datetime(date_str).strftime("%d.%m.%Y")
    except:
        return date_str

# ПОЧАТОК ДОДАТКУ
st.title("✏️ Редактор опитувань")
st.markdown("Редагуйте назву, організацію та інші параметри опитувань")

nav_col1, nav_col2, nav_col3 = st.columns([8, 1, 1])
with nav_col2:
    if st.button("🛠 Адмін", width='stretch', key='to_admin'):
        st.switch_page("pages/admin.py")
with nav_col3:
    if st.button("⬅️ На головну", width='stretch', key='to_home'):
        st.switch_page("main.py")

st.divider()

try:
    surveys = get_all_surveys_with_id()
except Exception as e:
    st.error(f"Помилка при завантаженні опитувань: {e}")
    st.stop()

if not surveys:
    st.info("📭 Немає опитувань для редагування.")
    st.stop()

# ФІЛЬТРИ
st.subheader("🔍 Фільтри")
f_col1, f_col2, f_col3 = st.columns(3)

with f_col1:
    all_orgs = ["Всі"] + list(set([s.get("organization", "Невідома") for s in surveys]))
    selected_org = st.selectbox("Організація", all_orgs)

with f_col2:
    search_query = st.text_input("Пошук по назві", "")

with f_col3:
    sort_by = st.selectbox("Сортування", ["За датою (нові першими)", "За датою (старі першими)", "За назвою"])

# ЛОГІКА ФІЛЬТРАЦІЇ
filtered_surveys = surveys.copy()
if selected_org != "Всі":
    filtered_surveys = [s for s in filtered_surveys if s.get("organization") == selected_org]
if search_query:
    filtered_surveys = [s for s in filtered_surveys if search_query.lower() in s.get("title", "").lower()]

if sort_by == "За датою (нові першими)":
    filtered_surveys = sorted(filtered_surveys, key=lambda x: x.get("date", ""), reverse=True)
elif sort_by == "За датою (старі першими)":
    filtered_surveys = sorted(filtered_surveys, key=lambda x: x.get("date", ""))
else:
    filtered_surveys = sorted(filtered_surveys, key=lambda x: x.get("title", ""))

st.subheader(f"📋 Опитування ({len(filtered_surveys)})")

if filtered_surveys:
    for idx, survey in enumerate(filtered_surveys):
        with st.container(border=True):
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
                    # Очищаємо старий опис зі стейта при відкритті нового
                    if "editor_desc" in st.session_state:
                        del st.session_state.editor_desc
                    st.rerun()

            if survey.get("ai_description"):
                with st.expander("📖 Опис"):
                    st.write(survey["ai_description"])

st.divider()

# ФОРМА РЕДАГУВАННЯ
if "editing_survey_id" in st.session_state:
    editing_survey = None
    for s in surveys:
        if str(s["_id"]) == st.session_state.editing_survey_id:
            editing_survey = s
            break
    
    if editing_survey:
        st.subheader(f"Редагування: {editing_survey.get('title')}")
        
        # Ініціалізація змінної стану для опису, якщо її немає
        if "editor_desc" not in st.session_state:
            st.session_state.editor_desc = editing_survey.get("ai_description", "")

        with st.form("edit_survey_form"):
            st.write("**Основні параметри**")
            col1, col2 = st.columns(2)
            with col1:
                new_title = st.text_input("Назва опитування", value=editing_survey.get("title", ""))
            with col2:
                new_org = st.text_input("Організація", value=editing_survey.get("organization", ""))
            
            st.write("**Додаткова інформація**")
            new_participants = st.number_input("Кількість учасників", 
                                              value=int(editing_survey.get("participants", 0)), 
                                              min_value=0)
            
            new_date = st.date_input("Дата опитування", 
                                    value=pd.to_datetime(editing_survey.get("date", "today")))
            
            st.write("**Опис опитування**")
            desc_col1, desc_col2 = st.columns([5, 1])
            
            with desc_col1:
                # ВАЖЛИВО: key="editor_desc" зв'язує це поле з session_state
                st.text_area("Опис (AI-сгенерований)", 
                             key="editor_desc",
                             height=100,
                             label_visibility="collapsed")
            
            with desc_col2:
                st.write("")
                st.write("")
                # ВИКОРИСТОВУЄМО CALLBACK (on_click)
                # Це викличе функцію generate_desc_callback ПЕРЕД тим як сторінка перезавантажиться
                # Тому помилки не буде
                st.form_submit_button(
                    "🤖 Згенерувати", 
                    width='stretch',
                    on_click=generate_desc_callback,
                    args=(new_title, editing_survey.get("questions", []))
                )
            
            btn_col1, btn_col2, btn_col3 = st.columns(3)
            with btn_col1:
                btn_save = st.form_submit_button("💾 Зберегти", use_container_width=True)
            with btn_col2:
                btn_cancel = st.form_submit_button("❌ Скасувати", use_container_width=True)
            with btn_col3:
                btn_delete = st.form_submit_button("🗑️ Видалити", use_container_width=True)
            
            if btn_save:
                # Отримуємо фінальний текст прямо зі стейту
                final_desc = st.session_state.editor_desc
                updated_data = {
                    "title": new_title,
                    "organization": new_org,
                    "participants": int(new_participants),
                    "date": new_date.strftime("%Y-%m-%d"),
                    "ai_description": final_desc
                }
                try:
                    update_survey(st.session_state.editing_survey_id, updated_data)
                    st.success("✅ Опитування успішно оновлено!")
                    del st.session_state.editing_survey_id
                    del st.session_state.editor_desc
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Помилка при збереженні: {e}")
            
            if btn_cancel:
                del st.session_state.editing_survey_id
                if "editor_desc" in st.session_state:
                    del st.session_state.editor_desc
                st.rerun()
            
            if btn_delete:
                try:
                    delete_survey(st.session_state.editing_survey_id)
                    st.success("✅ Опитування видалено!")
                    del st.session_state.editing_survey_id
                    if "editor_desc" in st.session_state:
                        del st.session_state.editor_desc
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Помилка при видаленні: {e}")
else:
    st.info("Оберіть опитування для редагування")