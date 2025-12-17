import streamlit as st
from pymongo import MongoClient
from bson.objectid import ObjectId

@st.cache_resource
def init_connection():
    uri = st.secrets["mongo"]["uri"]
    return MongoClient(uri)

def get_db():
    client = init_connection()
    db_name = st.secrets["mongo"]["db_name"]
    return client[db_name]

def get_all_surveys():
    db = get_db()
    return list(db.surveys.find({}, {"_id": 0}))

def get_survey_by_id(survey_id):
    db = get_db()
    return db.surveys.find_one({"id": survey_id}, {"_id": 0})

def save_ai_result(survey_id, question_index, analysis_text):
    db = get_db()
    
    # MongoDB дозволяє звертатися до елементів масиву через крапку: questions.0.ai_analysis
    key = f"questions.{question_index}.ai_analysis"
    
    db.surveys.update_one(
        {"id": survey_id}, # Знаходимо опитування за ID
        {"$set": {key: analysis_text}} # Записуємо текст
    )