import streamlit as st
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import re

st.set_page_config(page_title="Analisador de Fatura Copel", layout="wide")
st.title("📄 Diagnóstico da Fatura (Não identificado)")

uploaded_file = st.file_uploader("Envie a fatura (PDF ou imagem)", type=["pdf", "png", "jpg", "jpeg"])

def extract_text_from_pdf(file):
    text = ""
    doc = fitz.open(stream=file.read(), filetype="pdf")
    for page in doc:
        text += page.get_text()
    return text

def extract_consumo_mensal(text):
    padrao = r"(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)[0-9]{2}"
    valores = re.findall(rf"({padrao})\D+?(\d+)", text)
    return {mes: int(kwh) for mes, kwh in valores}

def extrair_grupo_tarifario(text):
    if "Grupo A" in text or "GRUPO A" in text:
        return "Grupo A"
    elif "Grupo B" in text or "GRUPO B" in text or "B - CONVENCIONAL" in text:
        return "Grupo B"
    return "Não identificado"

def extrair_endereco(text):
    match = re.search(r"Cidade:\s*(.+?)\s*-\s*Estado:\s*([A-Z]{2})", text)
    return f"{match.group(1)} - {match.group(2)}" if match else "Localização não encontrada"

def detectar_demanda(text):
    demanda = {}
    if "Demanda Contratada" in text:
        demanda["contratada"] = True
    if "Fora Ponta" in text or "fora ponta" in text:
        demanda["fora_ponta"] = True
    if "Ponta" in text:
        demanda["ponta"] = True
    return demanda if demanda else None

def simular_solar(media_kwh, irradiacao=4.2):
    kwp = round(media_kwh / (30 * irradiacao), 1)
    economia = round(media_kwh * 0.745, 2)
    return kwp, economia

def sugerir_estrategias(grupo, media_kwh, sazonalidade, demanda):
    sugestoes = []
    if grupo == "Grupo B":
        if media_kwh < 300:
            sugestoes.append("⚠️ Consumo baixo: sistema solar pode não compensar.")
        else:
            sugestoes.append("✅ Bom perfil para energia solar fotovoltaica.")
        sugestoes.append("⚡ Zero grid pode compensar se o consumo for diurno.")
    elif grupo == "Grupo A":
        if demanda:
            sugestoes.append("🔌 Há demanda contratada: análise de ponta é essencial.")
        if sazonalidade > (media_kwh * 0.5):
            sugestoes.append("🔋 Consumo variável: considerar sistema híbrido ou BESS.")
    if not sugestoes:
        sugestoes.append("📌 Sem dados suficientes para sugerir estratégias.")
    return sugestoes

if uploaded_file:
    if uploaded_file.type == "application/pdf":
        text = extract_text_from_pdf(uploaded_file)
    else:
        img = Image.open(uploaded_file)
        text = pytesseract.image_to_string(img)

    grupo = extrair_grupo_tarifario(text)
    endereco = extrair_endereco(text)
    consumo = extract_consumo_mensal(text)
    demanda = detectar_demanda(text)

    st.subheader(f"📄 Análise: {uploaded_file.name}")
    st.markdown(f"**Grupo Tarifário:** {grupo}")
    st.markdown(f"**📍 Localização:** {endereco}")

    if consumo:
        valores = list(consumo.values())
        media = sum(valores) / len(valores)
        pico = max(valores)
        minimo = min(valores)
        sazonalidade = pico - minimo
        kwp, economia = simular_solar(media)

        st.subheader("📊 Histórico de Consumo (12 meses):")
        st.dataframe({"Mês": list(consumo.keys()), "kWh": list(consumo.values())})

        st.markdown(f"🔷 **Média:** {round(media, 2)} kWh | 🧾 **Pico:** {pico} | 💡 **Mínimo:** {minimo}")
        st.markdown(f"🔵 **Sazonalidade:** {sazonalidade} kWh")

        st.subheader("🌞 Simulação Solar")
        st.markdown(f"🔋 Sistema estimado: **{kwp} kWp**")
        st.markdown(f"💰 Economia estimada: **R$ {economia}/mês**")

        st.subheader(f"⚡ Diagnóstico Técnico {grupo}")
        if demanda:
            st.json(demanda)
        else:
            st.markdown("Sem informações específicas de demanda contratada.")

        st.subheader("💡 Estratégias Sugeridas")
        for sugestao in sugerir_estrategias(grupo, media, sazonalidade, demanda):
            st.markdown(f"- {sugestao}")

    else:
        st.warning("⚠️ Não foi possível extrair o histórico de consumo da fatura.")
