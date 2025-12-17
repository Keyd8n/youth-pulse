import streamlit as st
from utils.db import get_all_surveys

# НАЛАШТУВАННЯ СТОРІНКИ
st.set_page_config(
    page_title="YouthPulse | IT Моніторинг",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    [data-testid="stSidebar"] {display: none;}
    [data-testid="stMainMenuButton"] {display: none;}
</style>
""", unsafe_allow_html=True)

# ЗАВАНТАЖЕННЯ ДАНИХ З БД
try:
    surveys_data = get_all_surveys()
except Exception as e:
    st.error(f"Помилка підключення до бази даних: {e}")
    st.stop()

# ЗАГОЛОВОК СТОРІНКИ
st.title("📊 Моніторинг потреб молоді в IT")
st.markdown("Стрічка актуальних опитувань")

with st.expander("🔍 Фільтри та налаштування", expanded=False):

    f_col1, f_col2, f_col3 = st.columns([1, 1, 2])
    
    with f_col1:
        all_categories = ["Всі"] + list(set([s.get("category", "Інше") for s in surveys_data]))
        selected_category = st.selectbox("Категорія", all_categories)
        
    with f_col2:
        st.write("")
        st.write("")
        
    with f_col3:
        st.caption("YouthPulse v1.0 | Dev: Dmytro Demchenko")

st.divider()

# ЛОГІКА ФІЛЬТРАЦІЇ
filtered_surveys = surveys_data

if selected_category != "Всі":
    filtered_surveys = [s for s in filtered_surveys if s.get("category") == selected_category]

# ВІДОБРАЖЕННЯ КАРТОК ОПИТУВАНЬ
if not filtered_surveys:
    st.info("За вашими критеріями опитувань не знайдено. Спробуйте змінити фільтри.")
else:
    cols = st.columns(2)
    
    for index, survey in enumerate(filtered_surveys):
        col = cols[index % 2]
        
        with col:
            with st.container(border=True):
                st.caption(f"📅 {survey.get('date', 'N/A')} | 🏢 {survey.get('organization', 'Unknown')}")

                st.subheader(survey.get('title', 'Без назви'))

                ai_description = survey.get('ai_description')
                if ai_description:
                    st.markdown(f"✨ {ai_description}")
                
                st.divider()

                col_stat, col_btn = st.columns([1, 1])
                
                with col_stat:
                    participants = survey.get('participants', 0)
                    st.markdown(f"**👥 {participants}** учасників")
                    st.caption(f"#{survey.get('category', 'General')}")
                
                with col_btn:
                    btn_key = f"btn_{survey.get('id')}"
                    if st.button("📊 Результати", key=btn_key, width='stretch'):
                        st.session_state["selected_survey_id"] = survey.get('id')
                        st.switch_page("pages/dashboard.py")