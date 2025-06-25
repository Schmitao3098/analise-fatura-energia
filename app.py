import streamlit as st
import fitz  # PyMuPDF
import re

st.set_page_config(page_title="Analisador de Faturas Copel", layout="centered")
st.title("📊 Analisador de Faturas Copel - Solar & Estratégia")
st.markdown("Envie a fatura em PDF e veja a análise automática com sugestões.")

uploaded_file = st.file_uploader("Envie a fatura (PDF)", type="pdf")


# ===== EXTRATOR =====
def extrair_texto(pdf):
    texto = ""
    for page in pdf:
        texto += page.get_text()
    return texto


# ===== ANALISADOR COMPLETO =====
def analisar_fatura(texto):
    resultado = {}

    # 1. Grupo tarifário
    if "Grupo de Tensao / Modalidade Tarifaria: B" in texto:
        resultado["grupo"] = "Grupo B"
    elif "Grupo A" in texto:
        resultado["grupo"] = "Grupo A"
    else:
        resultado["grupo"] = "Não identificado"

    # 2. Valor total da fatura
    match_total = re.search(r"05/2025\s+\d{2}/06/2025\s+R\$([0-9\.,]+)", texto)
    resultado["valor_total"] = match_total.group(1) if match_total else "Não encontrado"

    # 3. Extrair histórico de consumo (últimos 12 meses)
    historico = re.findall(r"([A-Z]{3}\d{2})\s+(\d{3,6})", texto)
    consumo_mensal = {mes: int(kwh) for mes, kwh in historico if len(kwh) > 3}
    resultado["consumos"] = consumo_mensal

    if consumo_mensal:
        valores = list(consumo_mensal.values())
        resultado["media"] = sum(valores) / len(valores)
        resultado["pico"] = max(valores)
        resultado["minimo"] = min(valores)
        resultado["sazonalidade"] = resultado["pico"] - resultado["minimo"]
    else:
        resultado["media"] = resultado["pico"] = resultado["minimo"] = resultado["sazonalidade"] = "Indisponível"

    return resultado


# ===== SUGESTÕES DINÂMICAS =====
def gerar_sugestoes(resultado):
    sugestoes = []

    if isinstance(resultado["media"], (int, float)):
        media = resultado["media"]

        if media < 1500:
            sugestoes.append("🔍 Consumo baixo: instalação solar pode não compensar.")
        elif 1500 <= media <= 4000:
            sugestoes.append("🟡 Consumo médio: avaliar solar on-grid com atenção ao perfil horário.")
        else:
            sugestoes.append("✅ Excelente perfil para energia solar fotovoltaica.")

        if resultado["grupo"] == "Grupo B":
            sugestoes.append("⚡ Grupo B: zero grid pode compensar mais com alto consumo diurno.")
        elif resultado["grupo"] == "Grupo A":
            sugestoes.append("📈 Grupo A: avaliar demanda e horário ponta fora de ponta antes de instalar solar.")

        if resultado["sazonalidade"] and resultado["sazonalidade"] > 3000:
            sugestoes.append("📉 Consumo muito variável: baterias (BESS) podem trazer estabilidade.")

    return sugestoes


# ===== INTERFACE =====
if uploaded_file:
    with fitz.open(stream=uploaded_file.read(), filetype="pdf") as pdf:
        texto = extrair_texto(pdf)
        resultado = analisar_fatura(texto)

        st.subheader("🔍 Resultado da Análise:")

        st.write(f"**Grupo Tarifário:** {resultado['grupo']}")
        st.write(f"**Valor Total da Fatura (maio):** R$ {resultado['valor_total']}")

        if resultado["consumos"]:
            st.write("**Histórico de Consumo (kWh):**")
            st.json(resultado["consumos"], expanded=False)

            st.write(f"📊 **Média Mensal:** {round(resultado['media'], 2)} kWh")
            st.write(f"📈 **Pico de Consumo:** {resultado['pico']} kWh")
            st.write(f"📉 **Menor Consumo:** {resultado['minimo']} kWh")
            st.write(f"🔄 **Sazonalidade:** {resultado['sazonalidade']} kWh")
        else:
            st.warning("Não foi possível identificar os dados mensais de consumo.")

        st.subheader("💡 Sugestões Estratégicas:")
        sugestoes = gerar_sugestoes(resultado)
        for s in sugestoes:
            st.markdown(f"- {s}")
