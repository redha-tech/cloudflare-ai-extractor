import streamlit as st
import pandas as pd
from mistralai import Mistral
import json
import base64
import io

# --- 1. إعدادات الصفحة وجلب المفتاح ---
st.set_page_config(page_title="Mistral Vision Independent Project", layout="wide")

MISTRAL_KEY = st.secrets.get("MISTRAL_API_KEY")

# --- 2. محرك Mistral Vision المحسن ---
def process_with_mistral(file_bytes, mime_type):
    if not MISTRAL_KEY:
        st.error("🚨 Mistral API Key is missing!")
        return None

    client = Mistral(api_key=MISTRAL_KEY)
    
    # تحويل الملف إلى Base64 ليفهمه محرك Vision
    base64_file = base64.b64encode(file_bytes).decode('utf-8')
    data_url = f"data:{mime_type};base64,{base64_file}"

    prompt = """
    Extract all items from this document into a structured JSON. 
    Required keys: hs_code, description, qty, unit_price, amount, origin. 
    Return ONLY a JSON object with a root key 'items'. 
    Keep Arabic text as is in the description.
    """

    try:
        # استخدام موديل Pixtral المخصص للرؤية
        response = client.chat.complete(
            model="pixtral-12b-2409",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": data_url}
                    ]
                }
            ],
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"Mistral API Error: {str(e)}")
        return None

# --- 3. واجهة المستخدم ---
st.title("🌪️ Clik-Plus | Mistral Vision Edition")
st.info("مشروع مستقل لاختبار محرك Mistral Pixtral على ملفات الجمارك.")

uploaded_file = st.file_uploader("ارفع صورة الفاتورة أو ملف (JPG/PNG)", type=['jpg', 'jpeg', 'png'])

if uploaded_file:
    # عرض الصورة المرفوعة
    st.image(uploaded_file, caption="المستند المرفوع", width=400)
    
    if st.button("🚀 تحليل باستخدام Mistral Vision", use_container_width=True, type="primary"):
        with st.spinner("Mistral يحلل الصورة الآن..."):
            file_bytes = uploaded_file.getvalue()
            mime_type = uploaded_file.type
            
            data = process_with_mistral(file_bytes, mime_type)
            
            if data and 'items' in data:
                df = pd.DataFrame(data['items'])
                st.success(f"تم استخراج {len(df)} صنف بنجاح!")
                st.dataframe(df, use_container_width=True)
                
                # تصدير للـ Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False)
                
                st.download_button(
                    "📥 تحميل النتائج كملف Excel",
                    output.getvalue(),
                    f"Mistral_Extract_{uploaded_file.name}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("⚠️ تعذر استخراج البيانات. تأكد من وضوح الصورة.")

st.divider()
st.caption("نظام Clik-Plus | محرك Mistral Pixtral المستقل")
