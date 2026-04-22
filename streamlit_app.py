import streamlit as st
import pandas as pd
import json
import base64
import io
import re
import fitz  # PyMuPDF

# --- 1. إعدادات الصفحة والواجهة ---
st.set_page_config(page_title="Clik-Plus | Smart OCR", layout="wide", page_icon="🚢")

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #FF4B4B; color: white; font-weight: bold; }
    .stDataFrame { border: 1px solid #e6e9ef; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# استدعاء مفتاح API من Secrets
MISTRAL_KEY = st.secrets.get("MISTRAL_API_KEY")

# --- 2. الدوال البرمجية الذكية ---

def clean_extracted_dataframe(df):
    """دالة لتوحيد مسميات الأعمدة ومنع التكرار الظاهر في الجداول"""
    mapping = {
        'hs_code': ['HS Code', 'hscode', 'hs code', 'HS_Code', 'تنسيق'],
        'description': ['Description', 'desc', 'items', 'item_description', 'الوصف'],
        'qty': ['Qty', 'quantity', 'Quantity', 'QTY', 'الكمية'],
        'unit_price': ['Unit Price', 'unitprice', 'price', 'Unit_Price', 'Rate', 'السعر'],
        'amount': ['Amount', 'Total Amount', 'total', 'Total_Amount', 'amount_usd', 'القيمة'],
        'origin': ['Origin', 'Country', 'Country of Origin', 'المنشأ'],
        'weight': ['Weight', 'Weight (kg)', 'Net Weight', 'gross_weight', 'الوزن']
    }
    
    new_df = pd.DataFrame()
    
    # البحث عن الأعمدة وتوحيدها
    for target_key, aliases in mapping.items():
        found_col = None
        for col in df.columns:
            if col.lower() == target_key or col.lower() in [a.lower() for a in aliases]:
                found_col = col
                break
        
        if found_col:
            new_df[target_key] = df[found_col]
        else:
            # إنشاء عمود افتراضي إذا لم يوجد
            new_df[target_key] = 0 if target_key in ['qty', 'unit_price', 'amount'] else ""
            
    return new_df

def try_parse_json(text):
    """محاولة تنظيف النص المستخرج وتحويله لـ JSON"""
    try:
        # إزالة أي نصوص خارج حدود الـ JSON (مثل ```json ... ```)
        clean_text = re.search(r'\{.*\}', text, re.DOTALL).group()
        return json.loads(clean_text)
    except:
        return None

# --- 3. دوال الاتصال بمحرك Mistral ---

def process_with_pixtral(file_bytes, mime_type):
    if not MISTRAL_KEY: return None
    try:
        from mistralai import Mistral
        client = Mistral(api_key=MISTRAL_KEY)
        base64_file = base64.b64encode(file_bytes).decode('utf-8')
        actual_mime = mime_type if "pdf" not in mime_type else "image/jpeg"
        
        prompt = (
            "Extract all invoice items into JSON format with these exact keys: "
            "hs_code, description, qty, unit_price, amount, origin, weight. "
            "Important: Keep Arabic text. Return ONLY a JSON object with a single key 'items'."
        )

        response = client.chat.complete(
            model="pixtral-12b-2409",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": f"data:{actual_mime};base64,{base64_file}"}
            ]}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"Vision API Error: {str(e)}")
        return None

def process_pdf_text(text_content):
    if not MISTRAL_KEY: return None
    try:
        from mistralai import Mistral
        client = Mistral(api_key=MISTRAL_KEY)
        prompt = (
            "Extract invoice items from this text into JSON: "
            "hs_code, description, qty, unit_price, amount, origin, weight. "
            f"Keep Arabic. Return ONLY JSON with key 'items'.\n\nText:\n{text_content}"
        )
        response = client.chat.complete(
            model="mistral-small-latest",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"Text API Error: {str(e)}")
        return None

# --- 4. واجهة المستخدم الرسومية ---
st.title("🚢 Clik-Plus | المستخرج الذكي")
st.caption("نظام استخراج بيانات الشحن والخدمات اللوجستية المتطور")

uploaded_file = st.file_uploader("ارفع الملف (PDF, Excel, PNG, JPG)", type=['png', 'jpg', 'jpeg', 'pdf', 'xlsx', 'xls'])

if uploaded_file:
    file_ext = uploaded_file.name.split('.')[-1].lower()
    
    if st.button("🚀 تحليل واستخراج البيانات الآن"):
        with st.spinner("جاري تحليل البيانات وتوحيد الأعمدة..."):
            final_items = []

            # معالجة أنواع الملفات المختلفة
            if file_ext == 'pdf':
                pdf_bytes = uploaded_file.getvalue()
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                full_text = "".join([page.get_text() for page in doc])
                
                if full_text.strip() and len(full_text) > 100:
                    data = process_pdf_text(full_text)
                    if data and 'items' in data: final_items = data['items']
                else:
                    # إذا كان PDF ممسوح ضوئياً (صور)
                    for page in doc:
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                        data = process_with_pixtral(pix.tobytes("jpeg"), "image/jpeg")
                        if data and 'items' in data: final_items.extend(data['items'])
                doc.close()

            elif file_ext in ['xlsx', 'xls']:
                df_excel = pd.read_excel(uploaded_file)
                final_items = df_excel.to_dict(orient='records')

            else:
                data = process_with_pixtral(uploaded_file.getvalue(), uploaded_file.type)
                if data and 'items' in data: final_items = data['items']

            # --- المعالجة النهائية والعرض ---
            if final_items:
                raw_df = pd.DataFrame(final_items)
                
                # توحيد الأعمدة لمنع التكرار (إصلاح مشكلة الصورة الأخيرة)
                df = clean_extracted_dataframe(raw_df)
                
                # جعل الترقيم يبدأ من 1
                df.index = df.index + 1
                df.index.name = "#"

                # تنظيف الأرقام من أي رموز مثل ($ , *) لضمان نجاح عملية الجمع
                for col in ['amount', 'unit_price', 'qty']:
                    df[col] = df[col].astype(str).str.replace(r'[^\d.]', '', regex=True)
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

                # التنبيه في سطر واحد للأصناف الصفرية
                zero_indices = df[df['amount'] <= 0].index.tolist()
                if zero_indices:
                    st.warning(f"⚠️ تنبيه: تم العثور على قيم صفرية أو خصم في الأصناف: {', '.join([f'#{i}' for i in zero_indices])}")

                # حساب الإجمالي الكلي
                total_sum = df['amount'].sum()

                # عرض الجدول والنتائج
                st.success(f"✅ تم استخراج {len(df)} صنف بنجاح!")
                st.dataframe(df, use_container_width=True)
                
                st.info(f"📊 **إجمالي المبلغ الكلي (Total Amount): {total_sum:,.2f}**")
                
                # إعداد ملف Excel للتحميل
                df_export = df.copy()
                df_export.loc['Total'] = None
                df_export.at['Total', 'amount'] = total_sum
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_export.to_excel(writer, index=True, sheet_name='ExtractedData')
                
                st.download_button(
                    label="📥 تحميل النتائج كملف Excel",
                    data=output.getvalue(),
                    file_name=f"ClikPlus_{uploaded_file.name}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.error("⚠️ لم نتمكن من العثور على بيانات منظمة. يرجى التأكد من جودة الملف.")
