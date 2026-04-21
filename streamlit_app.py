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
        st.error("🚨 مكتبة Mistral غير مثبتة بشكل صحيح.")

# --- 2. إعدادات الصفحة ---
st.set_page_config(page_title="Mistral Vision Pro | PDF & Image", layout="wide")

MISTRAL_KEY = st.secrets.get("MISTRAL_API_KEY")

# --- 3. دالة المعالجة المحسنة ---
def process_with_mistral(file_bytes, mime_type):
    if not MISTRAL_KEY:
        st.error("🚨 المفتاح MISTRAL_API_KEY مفقود!")
        return None

    try:
        client = Mistral(api_key=MISTRAL_KEY)
    except:
        client = Mistral(api_key=MISTRAL_KEY)

    # تحويل الملف (سواء صورة أو PDF) إلى Base64
    base64_file = base64.b64encode(file_bytes).decode('utf-8')
    data_url = f"data:{mime_type};base64,{base64_file}"

    prompt = (
        "Analyze this document (Image or PDF). Extract all table items into a JSON format. "
        "Keys: hs_code, description, qty, unit_price, amount, origin. "
        "Preserve Arabic text. Return ONLY JSON with 'items' key."
    )

    try:
        # Pixtral يدعم إرسال ملفات PDF مباشرة كـ document أو كـ image_url في الإصدارات الحديثة
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
st.title("🌪️ Mistral Vision | Multi-Format Extractor")
st.info("يدعم الآن: JPG, PNG, و PDF")

# تحديث الـ uploader ليدعم PDF
uploaded_file = st.file_uploader("ارفع المستند (صورة أو PDF)", type=['jpg', 'jpeg', 'png', 'pdf'])

if uploaded_file:
    # عرض معاينة إذا كان صورة، أو أيقونة إذا كان PDF
    if uploaded_file.type == "application/pdf":
        st.write(f"📄 تم رفع ملف PDF: **{uploaded_file.name}**")
    else:
        st.image(uploaded_file, width=300)
    
    if st.button("🚀 ابدأ التحليل الاحترافي", use_container_width=True, type="primary"):
        with st.spinner("جاري معالجة المستند عبر Mistral Pixtral..."):
            data = process_with_mistral(uploaded_file.getvalue(), uploaded_file.type)
            
            if data and 'items' in data:
                df = pd.DataFrame(data['items'])
                st.success(f"✅ تم استخراج {len(df)} صنف!")
                st.dataframe(df, use_container_width=True)
                
                # تصدير إكسل
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False)
                
                st.download_button(
                    "📥 تحميل ملف Excel",
                    buf.getvalue(),
                    f"Mistral_Extract_{uploaded_file.name.split('.')[0]}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            else:
                st.error("❌ تعذر استخراج البيانات. تأكد من جودة الملف أو أن الـ PDF يحتوي على جداول واضحة.")

st.divider()
st.caption("Clik-Plus Pro | Mistral AI Vision v1.2")
