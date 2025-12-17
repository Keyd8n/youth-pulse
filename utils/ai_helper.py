import json
from google import genai
import streamlit as st

def get_client():
    api_key = None
    if "gemini" in st.secrets and "GEMINI_API_KEY" in st.secrets["gemini"]:
        api_key = st.secrets["gemini"]["GEMINI_API_KEY"]
    elif "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
    
    if not api_key: return None
    return genai.Client(api_key=api_key)

def get_ai_analysis(question_text, data, data_type="stats"):
    try:
        client = get_client()
        if not client: return "⚠️ Не знайдено API ключа."

        base_prompt = "Роль: Соціолог. Мова: Українська. Максимум 3 абзаци. Виділяй головне **жирним**."
        
        prompt = ""
        if data_type == "text":
            prompt = f"{base_prompt} Проаналізуй відповіді: '{question_text}'. Список: {str(data[:60])}. Виділи теми та настрій."
        else:
            prompt = f"{base_prompt} Проаналізуй статистику: '{question_text}'. Дані: {data}. Опишіть лідерів та розподіл."

        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=prompt
        )
        return response.text
    except Exception as e:
        return f"Помилка AI: {e}"

def analyze_whole_survey(survey_title, questions_list):

    try:
        client = get_client()
        if not client: return None

        context_data = []
        for idx, q in enumerate(questions_list):
            q_text = q.get('text')
            q_data = q.get('data')

            content = ""
            if q.get('type') == 'text' and isinstance(q_data, dict):
                content = str(q_data.get('answers', [])[:40]) 
            else:
                content = str(q_data)
                
            context_data.append(f"Q_ID {idx}: '{q_text}' -> Data: {content}")

        full_text = "\n".join(context_data)

        prompt = f"""Ти аналітик. Проаналізуй результати опитування.

Назва: {survey_title}

Питання:
{full_text}

Завдання: Для кожного питання (Q_ID) напиши висновок українською мовою (3 абзаци).

ОБОВ'ЯЗКОВО поверни ТІЛЬКИ валідний JSON без додаткового тексту.
Формат: {{"0": "текст висновку", "1": "текст висновку"}}
Не додавай никаких пояснень, тільки JSON."""


        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )

        response_text = response.text.strip()
        if '{' in response_text and '}' in response_text:
            response_text = response_text[response_text.find('{'):response_text.rfind('}')+1]
        
        result = json.loads(response_text)

        filtered_result = {}
        for key, value in result.items():
            try:
                idx = int(key)
                filtered_result[idx] = value
            except ValueError:
                pass
        
        return filtered_result if filtered_result else None

    except Exception as e:
        st.error(f"Batch Error: {e}")
        return None


def generate_survey_description(survey_title, questions_list):
    try:
        client = get_client()
        if not client:
            return None

        # Збираємо список питань (тільки текст)
        questions_text = "\n".join([f"• {q.get('text')}" for q in questions_list])

        prompt = f"""
Задача: Напиши КОРОТКЕ пояснення опитування (2-3 речення максимум) для каталогу опитувань.

Контекст: Це опитування про молодь та IT спеціальності на платформі YouthPulse.

Назва: {survey_title}

Питання в опитуванні:
{questions_text}

Формат відповіді:
1. ЩО досліджується (теми, фокус дослідження)
2. ДЛЯ КОГО це (цільова аудиторія)
3. ЧИМ КОРИСНЕ (які вхідні дані отримають учасники чи що буде з результатами)

Вимоги до тексту:
• Тільки факти, без закликів та емоцій
• Мова: українська
• Об'єм: максимум 3 речення
• Зрозумілий для молоді
• Без слів "дізнатися", "приймати участь", "поділіться"

Приклад формату:
"Опитування досліджує, які IT спеціальності приваблюють молодь [ЩО]. Орієнтоване на школярів та студентів [ДЛЯ КОГО]. Результати допоможуть ЗМІ розібратися в трендах вибору професій [ЧИМ КОРИСНЕ]."
"""

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text

    except Exception as e:
        return None