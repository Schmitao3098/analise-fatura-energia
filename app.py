import streamlit as st
import fitz  # PyMuPDF
import re

st.set_page_config(page_title="Analisador de Faturas Copel", layout="centered")
st.title("📊 Analisador de Faturas Copel - Solar & Estratégia")
st.markdown("Envie a fatura em PDF e veja a análise automática com sugestões.")

uploaded_file = st.file_uploader("Envie a fatura (PDF)", type="pdf")

def extrair_texto(pdf):
    texto = ""
    for page in pdf:
        texto += page.get_text()
    return texto

def analisar_fatura(texto):
    analise = {}

    if "Grupo de Tensao / Modalidade Tarifaria: B" in texto:
        analise["grupo"] = "Grupo B"
    elif "Grupo A" in texto:
        analise["grupo"] = "Grupo A"
    else:
        analise["grupo"] = "Não identificado"

    match_consumo = re.search(r"MAI(?:25)?\D+(\d{4,6})", texto)
    if match_consumo:
        analise["consumo_maio"] = int(match_consumo.group(1))
    else:
        analise["consumo_maio"] = "Não encontrado"

    match_total = re.search(r"05/2025\s+\d{2}/06/2025\s+R\$([0-9\.,]+)", texto)
    if match_total:
        analise["valor_total"] = match_total.group(1)
    else:
        analise["valor_total"] = "Não encontrado"

    return analise

if uploaded_file:
    with fitz.open(stream=uploaded_file.read(), filetype="pdf") as pdf:
        texto = extrair_texto(pdf)
        resultado = analisar_fatura(texto)

        st.subheader("🔍 Resultado da Análise:")
        st.write(f"**Grupo Tarifário:** {resultado['grupo']}")
        st.write(f"**Consumo Maio (kWh):** {resultado['consumo_maio']}")
        st.write(f"**Valor Total da Fatura:** R$ {resultado['valor_total']}")

        if resultado['grupo'] == "Grupo B" and isinstance(resultado['consumo_maio'], int):
            if resultado['consumo_maio'] > 4000:
                st.success("✅ Potencial forte para energia solar.")
                st.info("⚠️ Avaliar se sistema 'zero grid' compensa depende do perfil de consumo diurno/noturno.")
            else:
                st.warning("🔍 Consumo abaixo do ideal para solar com bom payback.")
