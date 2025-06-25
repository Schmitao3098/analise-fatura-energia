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

st.set_page_config(page_title="Analisador Solar v2.5", layout="centered")
st.title("🔎 Analisador de Faturas Copel - v2.5")
st.markdown("Envie uma ou mais faturas (PDF ou imagem) para análise completa.")

uploaded_files = st.file_uploader("Envie as faturas:", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)

# === Funções de Extração e Análise ===

def extrair_texto_pdf(file):
    texto = ""
    with fitz.open(stream=file.read(), filetype="pdf") as doc:
        for page in doc:
            texto += page.get_text()
    return texto

def extrair_texto_imagem(file):
    image = Image.open(file).convert("L")
    texto = pytesseract.image_to_string(image, lang="por")
    return texto

def extrair_historico_blocos(texto):
    linhas = texto.splitlines()
    historico = {}
    capturando = False
    buffer = []

    for linha in linhas:
        if "HISTÓRICO DE CONSUMO" in linha.upper():
            capturando = True
            continue
        if capturando:
            if linha.strip() == "":
                break
            buffer.append(linha.strip())

    meses = buffer[2:15]
    consumos = buffer[15:28]

    try:
        for i in range(len(meses)):
            mes = meses[i]
            kwh = int(re.sub(r"\D", "", consumos[i]))
            historico[mes] = kwh
    except:
        pass

    return historico

def analisar_texto(texto):
    resultado = {}

    if "Grupo de Tensao / Modalidade Tarifaria: B" in texto:
        resultado["grupo"] = "Grupo B"
    elif "Grupo A" in texto:
        resultado["grupo"] = "Grupo A"
    else:
        resultado["grupo"] = "Não identificado"

    match_total = re.search(r"05/2025\s+\d{2}/06/2025\s+R\$([0-9\.,]+)", texto)
    resultado["valor_total"] = match_total.group(1) if match_total else "Não encontrado"

    historico = extrair_historico_blocos(texto)
    resultado["consumos"] = historico

    if historico:
        valores = list(historico.values())
        resultado["media"] = sum(valores) / len(valores)
        resultado["pico"] = max(valores)
        resultado["minimo"] = min(valores)
        resultado["sazonalidade"] = resultado["pico"] - resultado["minimo"]
    else:
        resultado["media"] = resultado["pico"] = resultado["minimo"] = resultado["sazonalidade"] = None

    match_cidade = re.search(r"Cidade:\s+([A-Za-z\s]+)\s+-\s+Estado:\s+([A-Z]{2})", texto)
    if match_cidade:
        resultado["cidade"] = match_cidade.group(1).strip()
        resultado["estado"] = match_cidade.group(2).strip()
    else:
        resultado["cidade"] = "Toledo"
        resultado["estado"] = "PR"

    return resultado

# === Cálculos e Sugestões ===

def calcular_kwp(consumo_mensal, cidade="Toledo", estado="PR"):
    irradiancia_por_cidade = {
        "Toledo - PR": 140,
        "Curitiba - PR": 115,
        "Campo Grande - MS": 150,
        "São Paulo - SP": 125,
        "Recife - PE": 130
    }
    chave = f"{cidade} - {estado}"
    irradiancia = irradiancia_por_cidade.get(chave, 120)
    return round(consumo_mensal / irradiancia, 1)

def calcular_economia(consumo_mensal):
    return round(consumo_mensal * 0.85, 2)

def gerar_sugestoes(resultado):
    sugestoes = []
    media = resultado["media"]
    if not media:
        return ["⚠️ Dados insuficientes para sugestão."]
    if media < 1500:
        sugestoes.append("🔍 Consumo baixo: sistema solar pode não compensar.")
    elif media < 4000:
        sugestoes.append("🟡 Perfil intermediário: avaliar on-grid com atenção ao consumo diurno.")
    else:
        sugestoes.append("✅ Excelente perfil para energia solar fotovoltaica.")
    if resultado["grupo"] == "Grupo B":
        sugestoes.append("⚡ Grupo B: zero grid pode compensar se o consumo for majoritariamente diurno.")
    elif resultado["grupo"] == "Grupo A":
        sugestoes.append("📈 Grupo A: atenção à demanda e horário ponta/fora de ponta.")
    if resultado["sazonalidade"] and resultado["sazonalidade"] > 4000:
        sugestoes.append("📉 Consumo muito variável: baterias (BESS) podem ajudar a equilibrar.")
    return sugestoes

# === Geração do Gráfico ===

def gerar_grafico(consumos):
    df = pd.DataFrame(list(consumos.items()), columns=["Mês", "kWh"])
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(df["Mês"], df["kWh"], color="orange")
    ax.set_title("Histórico de Consumo (kWh)")
    ax.set_ylabel("kWh")
    plt.xticks(rotation=45)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    return buf

# === Geração do PDF ===

def gerar_pdf(resultado, grafico_buffer):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(200, 10, "Relatório Solar - Análise de Fatura", ln=True, align="C")
    pdf.set_font("Arial", "", 12)
    pdf.cell(200, 10, f"Grupo: {resultado['grupo']} | Cidade: {resultado['cidade']} - {resultado['estado']}", ln=True)
    pdf.cell(200, 10, f"Consumo Médio: {round(resultado['media'],2)} kWh", ln=True)
    pdf.cell(200, 10, f"Sistema Estimado: {resultado['kwp']} kWp | Economia: R$ {resultado['economia']}/mês", ln=True)

    if grafico_buffer:
        img_path = "grafico_temp.png"
        with open(img_path, "wb") as f:
            f.write(grafico_buffer.read())
        pdf.image(img_path, x=10, y=60, w=180)
        os.remove(img_path)

    output_path = "relatorio_solar.pdf"
    pdf.output(output_path)
    with open(output_path, "rb") as f:
        return f.read()

# === Execução Principal ===

if uploaded_files:
    for arquivo in uploaded_files:
        st.markdown("---")
        st.subheader(f"📄 Análise: {arquivo.name}")

        tipo = arquivo.type
        texto = extrair_texto_pdf(arquivo) if "pdf" in tipo else extrair_texto_imagem(arquivo)
        resultado = analisar_texto(texto)

        st.write(f"**Grupo Tarifário:** {resultado['grupo']}")
        st.write(f"**Valor Total da Fatura:** R$ {resultado['valor_total']}")
        st.write(f"📍 Localização: {resultado['cidade']} - {resultado['estado']}")

        if resultado["consumos"]:
            st.write("**Histórico de Consumo:**")
            st.json(resultado["consumos"], expanded=False)
            st.write(f"📊 Média: {round(resultado['media'], 2)} kWh | Pico: {resultado['pico']} | Mínimo: {resultado['minimo']}")
            st.write(f"📈 Sazonalidade: {resultado['sazonalidade']} kWh")

            resultado["kwp"] = calcular_kwp(resultado["media"], resultado["cidade"], resultado["estado"])
            resultado["economia"] = calcular_economia(resultado["media"])

            st.subheader("🔆 Simulação Solar")
            st.write(f"🔋 Sistema estimado: **{resultado['kwp']} kWp**")
            st.write(f"💰 Economia estimada: **R$ {resultado['economia']}/mês**")

            st.subheader("📉 Gráfico de Consumo")
            grafico_buf = gerar_grafico(resultado["consumos"])
            st.image(grafico_buf)

            st.subheader("💡 Sugestões Estratégicas:")
            for s in gerar_sugestoes(resultado):
                st.markdown(f"- {s}")

            pdf_bytes = gerar_pdf(resultado, grafico_buf)
            st.download_button("📥 Baixar Relatório em PDF", data=pdf_bytes, file_name="relatorio_solar.pdf", mime="application/pdf")
