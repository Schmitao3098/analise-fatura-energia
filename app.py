import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
import re
import io
import matplotlib.pyplot as plt
import pandas as pd
from fpdf import FPDF
import os

st.set_page_config(page_title="Analisador Solar", layout="centered")
st.title("🔎 Analisador de Faturas Copel - Solar & Estratégia")

uploaded_file = st.file_uploader("Envie a fatura (PDF ou imagem)", type=["pdf", "png", "jpg", "jpeg"])

def extrair_texto(file):
    if file.type == "application/pdf":
        texto = ""
        with fitz.open(stream=file.read(), filetype="pdf") as doc:
            for page in doc:
                texto += page.get_text()
        return texto
    else:
        image = Image.open(file).convert("L")
        return pytesseract.image_to_string(image, lang="por")

def extrair_historico(texto):
    linhas = texto.splitlines()
    historico = {}
    for linha in linhas:
        if re.match(r"^[A-Z]{3}\d{2}", linha):
            partes = linha.split()
            if len(partes) >= 2:
                mes, valor = partes[0], re.sub(r"[^\d]", "", partes[1])
                if valor.isdigit():
                    historico[mes] = int(valor)
    return historico

def analisar(texto):
    resultado = {}
    resultado["grupo"] = "Grupo B" if "Modalidade Tarifaria: B" in texto else "Grupo A" if "Grupo A" in texto else "Não identificado"

    match_total = re.search(r"R\$\s*([\d\.,]+)", texto)
    resultado["valor_total"] = match_total.group(1) if match_total else "Desconhecido"

    match_cidade = re.search(r"Cidade:\s+([A-Za-z\s]+)\s+-\s+Estado:\s+([A-Z]{2})", texto)
    resultado["cidade"] = match_cidade.group(1).strip() if match_cidade else "Toledo"
    resultado["estado"] = match_cidade.group(2).strip() if match_cidade else "PR"

    resultado["consumos"] = extrair_historico(texto)
    return resultado

def simular(resultado):
    consumos = list(resultado["consumos"].values())

    if not consumos:
        return {
            "media": 0,
            "pico": 0,
            "minimo": 0,
            "sazonalidade": 0,
            "kwp": 0,
            "economia": 0,
            "payback": 0
        }

    media = sum(consumos) / len(consumos)
    pico = max(consumos)
    minimo = min(consumos)
    sazonalidade = pico - minimo

    irradiancia = {
        "Toledo - PR": 140,
        "Curitiba - PR": 115,
        "Campo Grande - MS": 150
    }.get(f"{resultado['cidade']} - {resultado['estado']}", 120)

    kwp = round(media / irradiancia, 1)
    economia = round(media * 0.85, 2)
    payback = round((kwp * 1300) / economia, 1) if economia > 0 else 0

    return {
        "media": media,
        "pico": pico,
        "minimo": minimo,
        "sazonalidade": sazonalidade,
        "kwp": kwp,
        "economia": economia,
        "payback": payback
    }

def gerar_sugestoes(res):
    sugestoes = []
    if res["media"] < 1500:
        sugestoes.append("🔍 Consumo baixo: sistema solar pode não compensar.")
    else:
        sugestoes.append("✅ Bom perfil para energia solar.")

    if res["grupo"] == "Grupo B":
        sugestoes.append("⚡ Grupo B: zero grid pode compensar se o consumo for diurno.")
    else:
        sugestoes.append("⚠️ Grupo A: atenção à demanda e horários de ponta.")

    if res["sazonalidade"] > 4000:
        sugestoes.append("📉 Sazonalidade alta: baterias (BESS) podem ajudar.")

    return sugestoes

def gerar_grafico(consumos):
    df = pd.DataFrame(list(consumos.items()), columns=["Mês", "kWh"])
    fig, ax = plt.subplots(figsize=(8,4))
    ax.bar(df["Mês"], df["kWh"], color='goldenrod')
    ax.set_title("Histórico de Consumo (kWh)")
    ax.set_ylabel("Consumo (kWh)")
    plt.xticks(rotation=45)
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png")
    buf.seek(0)
    return buf

def gerar_pdf(resumo, grafico_buffer):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, "Relatório Solar - Análise de Fatura", ln=True)
    pdf.cell(200, 10, f"Grupo: {resumo['grupo']}", ln=True)
    pdf.cell(200, 10, f"Média: {resumo['media']} kWh | Sistema: {resumo['kwp']} kWp", ln=True)
    pdf.cell(200, 10, f"Economia: R$ {resumo['economia']} | Payback: {resumo['payback']} anos", ln=True)
    img_path = "grafico_temp.png"
    with open(img_path, "wb") as f:
        f.write(grafico_buffer.read())
    pdf.image(img_path, x=10, y=60, w=180)
    os.remove(img_path)
    pdf_output = io.BytesIO()
    pdf.output(pdf_output)
    pdf_output.seek(0)
    return pdf_output

# === EXECUÇÃO ===
if uploaded_file:
    texto = extrair_texto(uploaded_file)
    dados = analisar(texto)
    resumo = simular(dados)
    dados.update(resumo)

    st.subheader("📊 Diagnóstico da Fatura")
    st.write(f"**Grupo Tarifário:** {dados['grupo']}")
    st.write(f"**Valor Total:** R$ {dados['valor_total']}")
    st.write(f"📍 Localização: {dados['cidade']} - {dados['estado']}")

    st.subheader("📈 Histórico de Consumo (12 meses):")
    st.write(dados["consumos"])
    st.write(f"🔹 **Média:** {resumo['media']} | 🔺 Pico: {resumo['pico']} | 🔻 Mínimo: {resumo['minimo']}")
    st.write(f"📉 Sazonalidade: {resumo['sazonalidade']} kWh")

    st.subheader("🔆 Simulação Solar")
    st.write(f"🔋 Sistema estimado: **{resumo['kwp']} kWp**")
    st.write(f"💰 Economia estimada: **R$ {resumo['economia']}/mês**")
    st.write(f"📅 Payback estimado: **{resumo['payback']} anos**")

    st.subheader("💡 Estratégias Sugeridas")
    for s in gerar_sugestoes(resumo):
        st.markdown(f"- {s}")

    grafico = gerar_grafico(dados["consumos"])
    st.image(grafico)

    pdf_download = gerar_pdf(dados, grafico)
    st.download_button("📥 Baixar Relatório em PDF", data=pdf_download, file_name="relatorio_solar.pdf")
