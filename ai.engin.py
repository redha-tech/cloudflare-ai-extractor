import streamlit as st
import json
import re
import pandas as pd
from PIL import Image
import docx
from docx.document import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
import pdfplumber
from groq import Groq
import google.generativeai as genai

# --- 1. إعدادات المفاتيح الذكية ---
GROQ_KEYS = st.secrets.get("GROQ_API_KEYS", [])
GEMINI_KEYS = st.secrets.get("GEMINI_KEYS", [])

# دالة مساعدة لتبديل المفاتيح عند الضرورة
if 'groq_idx' not in st.session_state: 
    st.session_state.groq_idx = 0
if 'gem_idx' not in st.session_state: 
    st.session_state.gem_idx = 0

# --- 2. دالة التنقل الذكي في ملفات Word (تأخذ النص والجداول بالترتيب) ---
def iter_block_items(parent):
    if isinstance(parent, Document):
        parent_elm = parent.element.body
    else:
        raise TypeError("Parent must be a Document object")

    for child in parent_elm.iterchildren():
        if isinstance(child, docx.oxml.text.paragraph.CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, docx.oxml.table.CT_Tbl):
            yield Table(child, parent)

# --- 3. أدوات تنظيف البيانات وحساب الأوزان (Logic) ---
def clean_numeric_string(val):
    if pd.isna(val) or val == "": 
        return 0.0
    s = str(val).replace('$', '').replace('*', '').replace(',', '').strip()
    try:
        return float(s)
    except:
        nums = re.findall(r"[-+]?\d*\.\d+|\d+", s)
        return float(nums[0]) if nums else 0.0

def apply_weight_distribution(df):
    """توزيع الأوزان بناءً على القيمة إذا كان الوزن الإجمالي معروفاً والأوزان الفرعية مفقودة"""
    if df.empty: 
        return df
    
    df["qty"] = pd.to_numeric(df["qty"], errors='coerce').fillna(0).astype(int)
    for col in ["unit_price", "amount", "gross_weight", "net_weight"]:
        if col in df.columns:
            df[col] = df[col].apply(clean_numeric_string).astype(float).round(3)
    
    total_gw = df["gross_weight"].max()
    
    # محاولة استخراج الوزن من الوصف إذا كان الوزن صفر
    for index, row in df.iterrows():
        weight_match = re.search(r'(\d*\.?\d+)\s*(gm|kg)', str(row['description']).lower())
        if weight_match and row['gross_weight'] == 0:
            val = float(weight_match.group(1))
            unit = weight_match.group(2)
            kg_weight = (val / 1000) if unit == 'gm' else val
            df.at[index, 'gross_weight'] = round(kg_weight * row['qty'], 3)

    # توزيع الوزن المتبقي نسبياً بناءً على القيمة (Amount)
    if total_gw > 0:
        mask = (df["gross_weight"] == 0)
        if mask.any():
            remaining_gw = total_gw - df.loc[~mask, "gross_weight"].sum()
            if remaining_gw > 0:
                weights = df.loc[mask, "amount"].replace(0, 0.01)
                df.loc[mask, "gross_weight"] = (weights / weights.sum()) * remaining_gw
            else:
                df.loc[mask, "gross_weight"] = 0.001 

    df['net_weight'] = df.apply(lambda x: x['gross_weight'] if x['net_weight'] <= 0 else x['net_weight'], axis=1)
    return df

# --- 4. محركات الاستخراج (AI Engines) ---
def extract_json_safely(text):
    try:
        text = re.sub(r'```json|```', '', text).strip()
        match = re.search(r'\{.*\}', text, re.DOTALL)
        return json.loads(match.group()) if match else json.loads(text)
    except: 
        return None

def process_with_gemini(content_list, prompt):
    """تحديث 2026: اختيار الموديل المتاح تلقائياً لتجنب خطأ 404"""
    if 'gem_idx' not in st.session_state:
        st.session_state.gem_idx = 0
        
    try:
        if not GEMINI_KEYS:
            st.error("🚨 API Keys missing!")
            return None
            
        current_key = GEMINI_KEYS[st.session_state.gem_idx % len(GEMINI_KEYS)]
        genai.configure(api_key=current_key)
        
        # --- استخراج الاسم الصحيح من النظام مباشرة ---
        available_models = [m.name for m in genai.list_models() 
                           if 'generateContent' in m.supported_generation_methods]
        
        # نحدد الموديلات المفضلة بالترتيب (الأحدث أولاً)
        # إذا وجد أي موديل يحتوي على "flash" و "3" سنختاره
        target_model = None
        for name in available_models:
            if "gemini-3-flash" in name:
                target_model = name
                break
        
        # إذا لم يجد "gemini-3-flash" بالاسم الصريح، سيختار أول موديل متاح (الأحدث)
        if not target_model:
            target_model = available_models[0]
            
        st.info(f"Connected to: {target_model}") # لمتابعة الاسم الذي تم اختياره
        
        model = genai.GenerativeModel(
            model_name=target_model,
            generation_config={"response_mime_type": "application/json"}
        )
        
        response = model.generate_content([prompt] + content_list)
        
        if response and response.text:
            return extract_json_safely(response.text)
        return None
        
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        st.session_state.gem_idx = (st.session_state.gem_idx + 1) % len(GEMINI_KEYS)
        return None
        
def process_with_groq(text, prompt):
    if 'groq_idx' not in st.session_state: 
        st.session_state.groq_idx = 0
    
    try:
        if not GROQ_KEYS: 
            st.error("Groq API Keys missing in secrets!")
            return None
            
        current_idx = st.session_state.groq_idx % len(GROQ_KEYS)
        
        client = Groq(api_key=GROQ_KEYS[current_idx])
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": f"{prompt}\n\nDATA:\n{text}"}],
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        st.error(f"Groq Error: {e}")
        return None
        
# --- 5. الموجه الذكي (Smart Router) ---
def smart_route_file(f, sheet_selection, prompt, user_model="Auto (Smart)"):
    ext = f.name.split('.')[-1].lower()
    f.seek(0)
    
    extracted_text = ""
    content_list = []
    
    if ext in ["jpg", "jpeg", "png"]:
        content_list = [Image.open(f)]
    
    elif ext == "pdf":
        with pdfplumber.open(f) as pdf:
            extracted_text = "\n".join([p.extract_text() or "" for p in pdf.pages])
        f.seek(0)
        if len(extracted_text) < 150:
            content_list = [{"mime_type": "application/pdf", "data": f.read()}]
    
    elif ext == "docx":
        doc = docx.Document(f)
        all_elements = []
        for block in iter_block_items(doc):
            if isinstance(block, Paragraph):
                if block.text.strip():
                    all_elements.append(f"CLARIFICATION: {block.text.strip()}")
            elif isinstance(block, Table):
                table_rows = []
                for row in block.rows:
                    row_data = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_data:
                        table_rows.append(" | ".join(row_data))
                if table_rows:
                    all_elements.append("TABLE_DATA:\n" + "\n".join(table_rows))
        extracted_text = "\n\n".join(all_elements)

    elif ext in ["xlsx", "xls"]:
        xl = pd.ExcelFile(f)
        selected = sheet_selection.get(f.name, [xl.sheet_names[0]])
        for sn in selected:
            df_temp = pd.read_excel(f, sheet_name=sn).dropna(how='all')
            extracted_text += f"\n- Sheet: {sn} -\n{df_temp.to_csv(index=False)}"

    chosen_engine = user_model
    if user_model == "Auto (Smart)":
        chosen_engine = "Gemini" if (ext in ["jpg", "png", "jpeg"] or (ext == "pdf" and not extracted_text)) else "Groq"

    if chosen_engine == "Gemini":
        return process_with_gemini(content_list or [extracted_text], prompt), "Gemini"
    else:
        return process_with_groq(extracted_text, prompt), "Groq"
