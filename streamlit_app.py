import streamlit as st
import pandas as pd
import json
import base64
import io
import fitz  # PyMuPDF

# --- 1. آلية الاستيراد ---
try:
    from mistralai import Mistral
except ImportError:
    from mistralai.client import Mistral

# --- 2. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus | Smart OCR", layout="wide", page_icon="🚢")

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #FF4B4B; color: white; }
    .stDataFrame { border: 1px solid #e6e9ef; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

MISTRAL_KEY = st.secrets.get("MISTRAL_API_KEY")

# --- 3. التعليمات الذكية (القلب النابض للنظام) ---
# هنا نأمر النظام بالفهم وليس مجرد المطابقة
MASTER_PROMPT = (
    "You are a logistics data expert. Analyze the provided file content and extract items. "
    "IMPORTANT: Field names in the file may vary (e.g., 'Item' instead of 'Description', 'Net' instead of 'net_weight'). "
    "You must map them logically to these keys: "
    "hs_code, description (keep Arabic), qty, unit_price, amount, origin, gross_weight, net_weight, pkg, invoice_number. "
    "If a column clearly doesn't exist, return null. Return ONLY a JSON object with key 'items'."
)

# --- 4. الدوال البرمجية ---

def call_ai_model(content, is_image=False, mime_type=None):
    if not MISTRAL_KEY: return None
    try:
        client = Mistral(api_key=MISTRAL_KEY)
        if is_image:
            base64_file = base64.b64encode(content).decode('utf-8')
            actual_mime = mime_type if "pdf" not in mime_type else "image/jpeg"
            data_url = f"data:{actual_mime};base64,{base64_file}"
            messages = [{"role": "user", "content": [{"type": "text", "text": MASTER_PROMPT}, {"type": "image_url", "image_url": data_url}]}]
            model = "pixtral-12b-2409"
        else:
            messages = [{"role": "user", "content": f"{MASTER_PROMPT}\n\nContent:\n{content}"}]
            model = "mistral-small-latest"

        response = client.chat.complete(model=model, messages=messages, response_format={"type": "json_object"})
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"AI Error: {str(e)}")
        return None

# --- 5. واجهة المستخدم ---
st.title("🚢 Clik-Plus | المستخرج الذكي")

uploaded_file = st.file_uploader("ارفع الملف (PDF, Excel, Images)", type=['png', 'jpg', 'jpeg', 'pdf', 'xlsx', 'xls'])

if uploaded_file:
    file_ext = uploaded_file.name.split('.')[-1].lower()
    
    if st.button("🚀 تحليل واستخراج البيانات الآن"):
        with st.spinner("جاري فهم هيكلة الملف واستخراج البيانات..."):
            extracted_data = None

            if file_ext == 'pdf':
                doc = fitz.open(stream=uploaded_file.getvalue(), filetype="pdf")
                text = "".join([page.get_text() for page in doc])
                if text.strip():
                    extracted_data = call_ai_model(text)
                else:
                    # إذا كان الـ PDF عبارة عن صور
                    pix = doc[0].get_pixmap(matrix=fitz.Matrix(2, 2))
                    extracted_data = call_ai_model(pix.tobytes("jpeg"), is_image=True, mime_type="image/jpeg")
                doc.close()

            elif file_ext in ['xlsx', 'xls']:
                # تحويل الإكسل لنص لإجبار الذكاء الاصطناعي على فهمه سياقياً
                df_excel = pd.read_excel(uploaded_file).ffill()
                extracted_data = call_ai_model(df_excel.to_string())

            else:
                extracted_data = call_ai_model(uploaded_file.getvalue(), is_image=True, mime_type=uploaded_file.type)

            # --- المعالجة والعرض ---
            if extracted_data and 'items' in extracted_data:
                df = pd.DataFrame(extracted_data['items'])
                
                # التأكد من وجود كافة الأعمدة المطلوبة حتى لو لم يجدها النظام
                required_cols = ['hs_code', 'description', 'qty', 'unit_price', 'amount', 'origin', 'gross_weight', 'net_weight', 'pkg', 'invoice_number']
                for col in required_cols:
                    if col not in df.columns: df[col] = None

                # تنظيف البيانات الرقمية للجمع
                num_cols = ['qty', 'unit_price', 'amount', 'gross_weight', 'net_weight']
                for col in num_cols:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

                # تنبيه الخصومات (في سطر واحد)
                zeros = df[df['amount'] <= 0].index.tolist()
                if zeros:
                    st.warning(f"⚠️ تنبيه: قيم صفرية في الأسطر: {', '.join([f'#{i+1}' for i in zeros])}")

                # سطر الإجمالي
                totals = {'description': '--- TOTAL ---'}
                for col in num_cols: totals[col] = df[col].sum()
                for col in [c for c in required_cols if c not in num_cols and c != 'description']: totals[col] = ""

                df_final = pd.concat([df, pd.DataFrame([totals])], ignore_index=True)
                df_final = df_final[required_cols] # ترتيب الأعمدة
                
                # تنسيق الفهرس
                df_final.index = list(range(1, len(df) + 1)) + ["TOTAL"]
                
                st.success(f"✅ تم استخراج {len(df)} صنف بنجاح!")
                st.dataframe(df_final, use_container_width=True)

                # تصدير Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_final.to_excel(writer, index=True, sheet_name='Data')
                st.download_button("📥 تحميل النتائج كملف Excel", output.getvalue(), f"Result_{uploaded_file.name}.xlsx")
            else:
                st.error("❌ فشل النظام في فهم محتوى الملف. تأكد من وضوح البيانات.")
