import streamlit as st
import pandas as pd
import json
import base64
import io

# --- 1. استيراد المكتبة بأكثر من طريقة لضمان العمل ---
try:
    from mistralai import Mistral
except Exception:
    try:
        from mistralai.client import MistralClient as Mistral
    except Exception:
        st.error("🚨 لم يتم العثور على مكتبة Mistral. تأكد من وجود mistralai في ملف requirements.txt")

# --- 2. إعدادات الصفحة ---
st.set_page_config(page_title="Mistral Vision Pro", layout="wide")

# جلب المفتاح من الـ Secrets
MISTRAL_KEY = st.secrets.get("MISTRAL_API_KEY")

# --- 3. دالة المعالجة ---
def process_with_mistral(file_bytes, mime_type):
    if not MISTRAL_KEY:
        st.error("🚨 المفتاح MISTRAL_API_KEY مفقود!")
        return None

    # محاولة تهيئة العميل بناءً على الطريقة التي نجح بها الاستيراد
    try:
        client = Mistral(api_key=MISTRAL_KEY)
    except:
        client = Mistral(api_key=MISTRAL_KEY)

    # تحويل الملف إلى Base64
    base64_file = base64.b64encode(file_bytes).decode('utf-8')
    data_url = f"data:{mime_type};base64,{base64_file}"

    prompt = (
        "Extract all items from this document into a JSON format. "
        "Keys: hs_code, description, qty, unit_price, amount, origin. "
        "Keep Arabic text exactly as is. Return ONLY JSON with 'items' key."
    )

    try:
        # استخدام موديل pixtral-12b-2409 للرؤية
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

# --- 4. واجهة المستخدم ---
st.title("🌪️ Mistral Vision | Pro Extractor")
st.markdown("مشروع استخراج البيانات الجمركية باستخدام Pixtral.")

uploaded_file = st.file_uploader("ارفع صورة المستند (JPG/PNG/JPEG)", type=['jpg', 'jpeg', 'png'])

if uploaded_file:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.image(uploaded_file, caption="المستند المرفوع", use_container_width=True)
    
    with col2:
        if st.button("🚀 ابدأ تحليل البيانات", use_container_width=True, type="primary"):
            with st.spinner("جاري استخراج البيانات..."):
                data = process_with_mistral(uploaded_file.getvalue(), uploaded_file.type)
                
                if data and 'items' in data:
                    df = pd.DataFrame(data['items'])
                    st.success(f"✅ تم استخراج {len(df)} صنف!")
                    st.dataframe(df, use_container_width=True)
                    
                    # تحويل الجدول لإكسل
                    buf = io.BytesIO()
                    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                        df.to_excel(writer, index=False)
                    
                    st.download_button(
                        "📥 تحميل ملف Excel",
                        buf.getvalue(),
                        f"Mistral_Extract_{uploaded_file.name}.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                else:
                    st.error("❌ تعذر تنظيم البيانات. حاول مرة أخرى.")

st.divider()
st.caption("Clik-Plus Pro | Mistral AI Engine")
