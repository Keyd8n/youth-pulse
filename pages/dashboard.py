import streamlit as st
import pandas as pd
import plotly.express as px
import textwrap
import re # Додано імпорт
from utils.db import get_survey_by_id, save_ai_result
from utils.ai_helper import get_ai_analysis, analyze_whole_survey

st.set_page_config(page_title="Dashboard", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""
<style>
    [data-testid="stSidebar"] {display: none;}
    [data-testid="stMainMenuButton"] {display: none;}
    h2 {word-wrap: break-word; overflow-wrap: break-word; word-break: break-word;}
</style>
""", unsafe_allow_html=True)

def extract_rating_number(series):
    return series.astype(str).apply(lambda x: int(x.split()[0]) if x.split()[0].isdigit() else 0)

def smart_wrap(text, width=30):
    if pd.isna(text): return ""
    text = str(text)
    if len(text) > 120: text = text[:117] + "..."
    return "<br>".join(textwrap.wrap(text, width=width))

def calculate_chart_height(df, base_height=350, row_height=45):
    if df.empty: return base_height
    dynamic_height = base_height + (len(df) * row_height)
    return dynamic_height

def generate_insight(df, question_type):
    if df.empty: return "Немає даних", "error", "-", 0
    if question_type == 'text': return f"Отримано {len(df)} відповідей.", "info", str(len(df)), 0
    if question_type == 'matrix': return "Матричне питання.", "info", "Matrix", 0

    sorted_df = df.sort_values(by='Кількість', ascending=False)
    winner = sorted_df.iloc[0]
    total = df['Кількість'].sum()
    if total == 0: return "Err", "error", "-", 0
    
    percent = (winner['Кількість'] / total) * 100
    
    if question_type == 'rating':
        try:
            vals = extract_rating_number(df['Відповідь'])
            avg = (vals * df['Кількість']).sum() / total
            status = "success" if avg >= 4 else "warning"
            return f"Середня: **{avg:.1f}**", status, f"{avg:.1f}", avg*20
        except: return "Помилка", "warning", "-", 0
        
    return f"Лідер: **{winner['Відповідь'][:20]}...**", "success", str(winner['Кількість']), percent

PLOTLY_CONFIG = {
    'displayModeBar': False,
    'scrollZoom': False,
    'showAxisDragHandles': False,
    'staticPlot': False
}

if st.button("⬅️ Назад до стрічки"):
    st.switch_page("main.py")

survey_id = st.session_state.get("selected_survey_id")
if not survey_id: st.stop()
survey = get_survey_by_id(survey_id)

st.title(survey.get('title'))

questions = survey.get('questions', [])
missing_analysis = any(not q.get('ai_analysis') for q in questions)

if missing_analysis:
    with st.container(border=True):
        c_text, c_btn = st.columns([3, 1])
        c_text.info("💡 Ви можете згенерувати висновки для всього опитування одним кліком.")
        if c_btn.button("⚡ Проаналізувати ВСЕ", type="primary", use_container_width=True):
            with st.spinner("Gemini аналізує все опитування..."):
                batch_results = analyze_whole_survey(survey.get('title'), questions)
                if batch_results:
                    bar = st.progress(0)
                    for q_idx_str, text in batch_results.items():
                        idx = int(q_idx_str)
                        save_ai_result(survey.get('id'), idx, text)
                        bar.progress((idx + 1) / len(batch_results))
                    st.success("Готово!")
                    st.rerun()
                else:
                    st.error("Помилка генерації.")

st.divider()

for i, q in enumerate(questions):
    raw_q_text = q.get('text', 'Питання')
    # === ОЧИЩЕННЯ ВІД НУМЕРАЦІЇ ===
    # Видаляє "1. ", "2)", "3 - " з початку тексту
    clean_q_text = re.sub(r'^\d+[\.\)\-\s]+\s*', '', raw_q_text)
    
    q_type = q.get('type', 'single_choice')
    q_data = q.get('data', {})
    
    if not q_data: continue

    if q_type == 'text':
        data_list = q_data.get("answers", []) if isinstance(q_data, dict) else []
        df = pd.DataFrame(data_list, columns=['Text'])
    elif q_type == 'matrix':
        df = pd.DataFrame() 
    else:
        df = pd.DataFrame(list(q_data.items()), columns=['Відповідь', 'Кількість'])
        df['Label'] = df['Відповідь'].apply(lambda x: smart_wrap(x, 30))

    with st.container(border=True):
        # Використовуємо чистий текст для заголовка
        st.subheader(f"{i+1}. {clean_q_text}")
        
        col_viz = st.container()
        
        with col_viz:
            if q_type == 'text':
                st.markdown("##### 💬 Відгуки")
                if not df.empty:
                    with st.container(height=300):
                        for txt in df['Text']:
                            if len(str(txt)) > 1:
                                with st.container(border=True): st.write(txt)
                else: st.caption("Пусто.")

            elif q_type == 'matrix':
                matrix_rows = []
                for sub_q, sub_votes in q_data.items():
                    tot = sum(sub_votes.values())
                    for ans, cnt in sub_votes.items():
                        pct = (cnt / tot * 100) if tot > 0 else 0
                        matrix_rows.append({
                            "Питання": smart_wrap(sub_q, 25),
                            "Відповідь": ans, 
                            "Кількість": cnt, 
                            "Відсоток": pct
                        })
                df_m = pd.DataFrame(matrix_rows)
                if not df_m.empty:
                    h = calculate_chart_height(df_m, base_height=400, row_height=50)
                    fig = px.bar(df_m, x="Відсоток", y="Питання", color="Відповідь", 
                                 orientation='h', text_auto='.0f')
                    fig.update_layout(
                        height=h,
                        legend=dict(orientation="h", y=-0.2, x=0),
                        margin=dict(t=20, b=50),
                        xaxis_fixedrange=True,
                        yaxis_fixedrange=True,
                        yaxis=dict(automargin=True, title=None), 
                        xaxis=dict(title=None),
                        dragmode=False
                    )
                    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, key=f"chart_matrix_{i}")

            elif q_type == 'multiple_choice':
                df = df.sort_values('Кількість')
                h = calculate_chart_height(df, base_height=350, row_height=45)
                fig = px.bar(df, x='Кількість', y='Label', orientation='h', text='Кількість')
                fig.update_layout(
                    showlegend=False,
                    height=h,
                    margin=dict(t=30, b=20),
                    xaxis_fixedrange=True,
                    yaxis_fixedrange=True,
                    yaxis=dict(automargin=True, title=None),
                    xaxis=dict(title=None), 
                    dragmode=False
                )
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, key=f"chart_multiple_{i}")

            elif q_type in ['single_choice', 'rating']:
                if q_type == 'single_choice':
                    fig = px.pie(df, values='Кількість', names='Label', hole=0.4)
                    fig.update_layout(
                        legend=dict(orientation="h", y=-0.2, x=0), 
                        height=450,
                        margin=dict(l=10, r=10, t=30, b=80),
                        dragmode=False
                    )
                    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, key=f"chart_single_{i}")
                else:
                    fig = px.bar(df, x='Label', y='Кількість', color='Кількість')
                    fig.update_layout(
                        showlegend=False,
                        height=400,
                        margin=dict(l=20, r=0, t=20, b=80),
                        xaxis_fixedrange=True,
                        yaxis_fixedrange=True,
                        xaxis=dict(tickangle=-45, automargin=True, title=None),
                        yaxis=dict(title=None),
                        dragmode=False
                    )
                    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, key=f"chart_rating_{i}")

        st.divider()
        txt, status, val, pct = generate_insight(df, q_type)
        c_s1, c_s2 = st.columns([3, 1])
        with c_s1:
            if status == 'success': st.success(txt)
            elif status == 'warning': st.warning(txt)
            else: st.info(txt)
        with c_s2:
            if q_type != 'text': st.metric("Кількість відповідей", val)

        st.divider()
        existing_ai = q.get('ai_analysis')
        
        if existing_ai:
            st.markdown("##### 🤖 Висновок AI:")
            st.info(existing_ai, icon="💡")
        else:
            if st.button(f"✨ Аналізувати питання", key=f"btn_{i}"):
                with st.spinner("Аналіз..."):
                    if q_type == 'text': d = df['Text'].tolist(); dt = 'text'
                    elif q_type == 'matrix': d = str(q_data); dt = 'matrix'
                    else: d = dict(zip(df['Відповідь'], df['Кількість'])); dt = q_type
                    
                    # Використовуємо clean_q_text для AI, щоб він не бачив зайвих цифр
                    res = get_ai_analysis(clean_q_text, d, dt)
                    save_ai_result(survey.get('id'), i, res)
                    st.rerun()