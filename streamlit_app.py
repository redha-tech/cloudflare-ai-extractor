import streamlit as st
import pandas as pd
import json
import base64
import io
from mistralai import Mistral

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="Mistral Vision Pro", layout="wide")

# جلب المفتاح من Secrets
MISTRAL_KEY = st.secrets.get("MISTRAL_API_KEY")

# --- 2. دالة المعالجة ---
def process_with_mistral(file_bytes, mime_type):
    if not MISTRAL_KEY:
        st.error("🚨 المفتاح MISTRAL_API_KEY غير موجود في Secrets!")
        return None

    client = Mistral(api_key=MISTRAL_KEY)

    # تحويل الملف إلى Base64
    base64_file = base64.b64encode(file_bytes).decode('utf-8')
    data_url = f"data:{mime_type};base64,{base64_file}"

    prompt = (
        "Extract all items from this document image into a JSON format. "
        "Fields: hs_code, description, qty, unit_price, amount, origin. "
        "Keep Arabic descriptions exactly as they appear. "
        "Return ONLY the JSON object with the key 'items'."
    )

    try:
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
st.title("🌪️ Mistral Vision | Pro Extractor")
st.markdown("تم تحديث النظام بالكامل. ارفع الصورة وابدأ التحليل.")

uploaded_file = st.file_uploader("ارفع صورة المستند (JPG/PNG/JPEG)", type=['jpg', 'jpeg', 'png'])

if uploaded_file:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.image(uploaded_file, caption="المستند المرفوع", use_container_width=True)
    
    with col2:
        if st.button("🚀 ابدأ تحليل البيانات الآن", use_container_width=True, type="primary"):
            with st.spinner("جاري تحليل الصورة..."):
                data = process_with_mistral(uploaded_file.getvalue(), uploaded_file.type)
                
                if data and 'items' in data:
                    df = pd.DataFrame(data['items'])
                    st.success(f"✅ تم استخراج {len(df)} صنف بنجاح!")
                    st.dataframe(df, use_container_width=True)
                    
                    # تحويل الجدول لملف إكسل
                    buf = io.BytesIO()
                    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                        df.to_excel(writer, index=False)
                    
                    st.download_button(
                        label="📥 تحميل النتائج كملف Excel",
                        data=buf.getvalue(),
                        file_name=f"Mistral_Extract_{uploaded_file.name}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                else:
                    st.error("❌ فشل المحرك في تنظيم البيانات. تأكد من جودة الصورة.")

st.divider()
st.caption("Powered by Clik-Plus & Mistral AI")
