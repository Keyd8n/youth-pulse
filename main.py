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
</style>
""", unsafe_allow_html=True)

# ЗАВАНТАЖЕННЯ ДАНИХ З БД
try:
    surveys_data = get_all_surveys()
except Exception as e:
    st.error(f"Помилка підключення до бази даних: {e}")
    st.stop()

# ГОЛОВНА ЧАСТИНА
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
        only_active = st.checkbox("Тільки активні", value=True)
        
    with f_col3:

        st.caption("YouthPulse v1.0 | Dev: Dmytro Demchenko")

st.divider()

# ЛОГІКА ФІЛЬТРАЦІЇ
filtered_surveys = surveys_data

if selected_category != "Всі":
    filtered_surveys = [s for s in filtered_surveys if s.get("category") == selected_category]

if only_active:
    filtered_surveys = [s for s in filtered_surveys if s.get("status") == "Active"]

# ВІДОБРАЖЕННЯ КАРТОК
if not filtered_surveys:
    st.info("За вашими критеріями опитувань не знайдено. Спробуйте змінити фільтри.")
else:
    cols = st.columns(2)
    
    for index, survey in enumerate(filtered_surveys):
        col = cols[index % 2]
        
        with col:
            with st.container(border=True):

                c1, c2 = st.columns([3, 1])
                c1.caption(f"📅 {survey.get('date', 'N/A')} | 🏢 {survey.get('organization', 'Unknown')}")
                
                status = survey.get('status', 'Closed')
                if status == 'Active':
                    c2.markdown(":green[**Active**] 🟢")
                else:
                    c2.markdown(":red[**Closed**] 🔴")


                st.subheader(survey.get('title', 'Без назви'))
                st.write(survey.get('description', 'Немає опису'))
                
                st.divider()
                

                col_stat, col_btn = st.columns([1, 1])
                
                with col_stat:
                    participants = survey.get('participants', 0)
                    st.markdown(f"**👥 {participants}** учасників")
                    st.caption(f"#{survey.get('category', 'General')}")
                
                with col_btn:
                    btn_key = f"btn_{survey.get('id')}"
                    if st.button("📊 Результати", key=btn_key, use_container_width=True):
                        st.session_state["selected_survey_id"] = survey.get('id')
                        st.switch_page("pages/dashboard.py")