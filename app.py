import streamlit as st
import fitz  # PyMuPDF
import re

st.set_page_config(page_title="Analisador de Faturas Copel", layout="centered")
st.title("📊 Analisador de Faturas Copel - Solar & Estratégia")

uploaded_file = st.file_uploader("Envie a fatura (PDF ou imagem escaneada)", type=["pdf"])

def extrair_texto(pdf):
    texto = ""
    for page in pdf:
        texto += page.get_text()
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

    # Extrai apenas os 13 primeiros meses e 13 primeiros valores
    meses = buffer[2:15]
    consumos = buffer[15:28]

    try:
        for i in range(len(meses)):
            mes = meses[i]
            kwh = int(re.sub(r"\D", "", consumos[i]))  # limpa pontos, vírgulas e letras
            historico[mes] = kwh
    except:
        pass  # erro de conversão? ignora

    return historico

def analisar_fatura(texto):
    resultado = {}

    # Grupo tarifário
    if "Grupo de Tensao / Modalidade Tarifaria: B" in texto:
        resultado["grupo"] = "Grupo B"
    elif "Grupo A" in texto:
        resultado["grupo"] = "Grupo A"
    else:
        resultado["grupo"] = "Não identificado"

    # Valor total
    match_total = re.search(r"05/2025\s+\d{2}/06/2025\s+R\$([0-9\.,]+)", texto)
    resultado["valor_total"] = match_total.group(1) if match_total else "Não encontrado"

    # Histórico
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

    return resultado

def calcular_kwp(consumo_mensal):
    # Supondo geração média de 120 kWh/mês por kWp
    return round(consumo_mensal / 120, 1)

def calcular_economia(consumo_mensal):
    # Tarifa média suposta: R$ 0,85/kWh
    return round(consumo_mensal * 0.85, 2)

def gerar_sugestoes(resultado):
    sugestoes = []
    media = resultado["media"]

    if not media:
        return ["⚠️ Não foi possível calcular sugestões por falta de dados."]

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

# ==== INTERFACE ====
if uploaded_file:
    with fitz.open(stream=uploaded_file.read(), filetype="pdf") as pdf:
        texto = extrair_texto(pdf)
        resultado = analisar_fatura(texto)

        st.subheader("🔍 Resultado da Análise:")
        st.write(f"**Grupo Tarifário:** {resultado['grupo']}")
        st.write(f"**Valor Total da Fatura (maio):** R$ {resultado['valor_total']}")

        if resultado["consumos"]:
            st.write("**Histórico de Consumo (últimos 12 meses):**")
            st.json(resultado["consumos"], expanded=False)

            st.write(f"📊 **Média Mensal:** {round(resultado['media'], 2)} kWh")
            st.write(f"📈 **Pico:** {resultado['pico']} kWh | 📉 Mínimo: {resultado['minimo']} kWh")
            st.write(f"🔁 **Sazonalidade:** {resultado['sazonalidade']} kWh")

            # Simulação Solar
            kwp = calcular_kwp(resultado["media"])
            economia = calcular_economia(resultado["media"])
            st.subheader("🔆 Simulação Solar")
            st.write(f"🔋 Sistema estimado: **{kwp} kWp**")
            st.write(f"💰 Economia mensal estimada: **R$ {economia}**")

        else:
            st.warning("Não foi possível extrair o histórico de consumo.")

        st.subheader("💡 Sugestões Estratégicas:")
        for s in gerar_sugestoes(resultado):
            st.markdown(f"- {s}")
