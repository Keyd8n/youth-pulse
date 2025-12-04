import streamlit as st
import pandas as pd
import plotly.express as px
from utils.db import get_survey_by_id

st.set_page_config(page_title="Analytics Dashboard", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>[data-testid="stSidebar"] {display: none;}</style>""", unsafe_allow_html=True)

def extract_rating_number(series):
    return series.astype(str).apply(lambda x: int(x.split()[0]) if x.split()[0].isdigit() else 0)

def generate_insight(df, question_type):
    if question_type == 'text':
        return f"Зібрано {len(df)} текстових відповідей.", "info", str(len(df)), 0
        
    if df.empty: return "Немає даних", "error", "-", 0
    
    winner = df.sort_values(by='Кількість', ascending=False).iloc[0]
    total = df['Кількість'].sum()
    if total == 0: return "Немає даних", "error", "-", 0
    
    percent = (winner['Кількість'] / total) * 100
    insight_text, status = "", "info"
    
    if question_type == 'rating':
        try:
            vals = extract_rating_number(df['Відповідь'])
            avg_score = (vals * df['Кількість']).sum() / total
            insight_text = f"Середня оцінка: **{avg_score:.1f} / 5.0**"
            if avg_score < 3: status = "error"
            elif avg_score >= 4: status = "success"
            return insight_text, status, f"{avg_score:.1f}", avg_score * 20 
        except:
            return "Помилка розрахунку", "warning", "N/A", 0
    else:
        if percent > 50:
            insight_text = f"Абсолютний лідер: **{winner['Відповідь']}**"
            status = "success"
        else:
            insight_text = f"Лідирує **{winner['Відповідь']}**"
            if percent < 30: status = "warning"
        return insight_text, status, winner['Відповідь'], percent

def generate_detailed_text(df, question_type):
    if question_type == 'text':
        return "Це відкрите питання. Рекомендується ручний аналіз наведених вище відповідей для формування якісних висновків."
    
    total = df['Кількість'].sum()
    sorted_df = df.sort_values(by='Кількість', ascending=False)
    winner = sorted_df.iloc[0]
    
    if question_type == 'rating':
        try:
            vals = extract_rating_number(df['Відповідь'])
            avg = (vals * df['Кількість']).sum() / total
            text = f"Середній індекс: **{avg:.1f} з 5**. "
            if avg < 3: text += "Низький показник, є проблеми."
            elif avg > 4.2: text += "Висока оцінка аудиторії."
            else: text += "Стабільний середній результат."
            return text
        except: return "Дані рейтингу не розпізнано."
    else:
        text = f"Лідер: **«{winner['Відповідь']}»** ({winner['Кількість']} голосів). "
        if len(df) > 1:
            gap = winner['Кількість'] - sorted_df.iloc[1]['Кількість']
            if gap < total * 0.05: text += "Конкуренція дуже висока."
            else: text += "Значний відрив від конкурентів."
        return text

if st.button("⬅️ Назад до стрічки"):
    st.switch_page("main.py")

survey_id = st.session_state.get("selected_survey_id", None)
if not survey_id: st.stop()

current_survey = get_survey_by_id(survey_id)
if not current_survey: st.error("Опитування не знайдено"); st.stop()

st.title(f"{current_survey.get('title', 'Без назви')}")
c1, c2 = st.columns([3, 1])
c1.markdown(f"**Організація:** {current_survey.get('organization', 'Unknown')}")
c2.metric("Учасників", f"{current_survey.get('participants', 0)}")
st.divider()

for i, q in enumerate(current_survey.get('questions', [])):
    q_text = q.get('text', '')
    q_type = q.get('type', 'single_choice')
    q_data = q.get('data', {})
    
    if not q_data: continue

    if q_type == 'text':
        if isinstance(q_data, dict) and "answers" in q_data:
            data_list = q_data["answers"]
        elif isinstance(q_data, list):
            data_list = q_data
        else:
            data_list = list(q_data.keys())
        df = pd.DataFrame(data_list, columns=['Текстові відповіді'])
    else:
        df = pd.DataFrame(list(q_data.items()), columns=['Відповідь', 'Кількість'])

    with st.container(border=True):
        st.subheader(f"{i+1}. {q_text}")
        
        col_viz, col_info = st.columns([2, 1])
        
        with col_viz:
            if q_type == 'text':
                st.dataframe(df, use_container_width=True, height=300, hide_index=True)
            else:
                fig = None
                if q_type == 'single_choice':
                    fig = px.pie(df, values='Кількість', names='Відповідь', hole=0.5)
                elif q_type == 'multiple_choice':
                    df = df.sort_values(by='Кількість', ascending=True)
                    fig = px.bar(df, x='Кількість', y='Відповідь', orientation='h')
                elif q_type == 'rating':
                    try:
                        df['sort'] = extract_rating_number(df['Відповідь'])
                        df = df.sort_values('sort')
                    except: pass
                    df['Відповідь'] = df['Відповідь'].astype(str)
                    fig = px.bar(df, x='Відповідь', y='Кількість')

                if fig:
                    fig.update_layout(margin=dict(t=30, b=0, l=0, r=0), height=350)
                    st.plotly_chart(fig, use_container_width=True, key=f"chart_{i}")

        with col_info:
            insight, status, val, pct = generate_insight(df, q_type)
            st.markdown("Аналітика")
            if status == "success": st.success(insight)
            elif status == "warning": st.warning(insight)
            elif status == "error": st.error(insight)
            else: st.info(insight)
            
            st.markdown("---")
            if q_type != 'text':
                if q_type == 'rating':
                    st.metric("Середній бал", val)
                    st.progress(int(float(pct)))
                else:
                    st.metric("Лідер", val)
                    st.metric("Підтримка", f"{pct:.1f}%")
            else:
                st.caption("Кількісні метрики недоступні")

        st.divider()
        st.write(f"Висновок: {generate_detailed_text(df, q_type)}")