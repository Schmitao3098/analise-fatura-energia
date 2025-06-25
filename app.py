import streamlit as st
import fitz  # PyMuPDF
import re
import pandas as pd

st.set_page_config(page_title="Analisador de Faturas Copel", layout="centered")
st.title("📊 Analisador de Faturas Copel - Grupo A & B")

uploaded_file = st.file_uploader("📤 Envie a fatura em PDF", type=["pdf"])

# === Funções ===

def extrair_texto_pdf(uploaded_file):
    texto = ""
    with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
        for page in doc:
            texto += page.get_text()
    return texto

def extrair_historico_consumo(texto):
    linhas = texto.splitlines()
    historico = []
    capturar = False
    for linha in linhas:
        if "HISTÓRICO DE CONSUMO" in linha.upper():
            capturar = True
            continue
        if capturar:
            if linha.strip() == "":
                break
            historico.append(linha.strip())

    meses = historico[2:15]
    consumos = historico[15:28]
    dados = {}
    for i in range(min(len(meses), len(consumos))):
        try:
            dados[meses[i]] = int(re.sub(r"[^\d]", "", consumos[i]))
        except:
            continue
    return dados

def simular_sistema(consumo_medio, hsp=4.5):
    kwp = round(consumo_medio / (hsp * 30), 1)
    economia = round(consumo_medio * 0.85 * 0.3, 2)
    return kwp, economia

def extrair_dados_grupo_a(texto):
    dados = {
        "demanda_contratada_kw": None,
        "demanda_ponta_kw": None,
        "demanda_fora_ponta_kw": None,
        "consumo_ponta_kwh": None,
        "consumo_fora_ponta_kwh": None,
        "bandeira_tarifaria": None,
        "penalidade_excedente": None,
        "fator_potencia_irregular": False,
    }

    padroes = {
        "demanda_contratada_kw": r"demanda contratada[:\s]*([\d,.]+)\s?k[wW]",
        "demanda_ponta_kw": r"demanda registrada.*ponta[:\s]*([\d,.]+)\s?k[wW]",
        "demanda_fora_ponta_kw": r"demanda registrada.*fora.*ponta[:\s]*([\d,.]+)\s?k[wW]",
        "consumo_ponta_kwh": r"consumo.*ponta[:\s]*([\d,.]+)\s?k[wW]h",
        "consumo_fora_ponta_kwh": r"consumo.*fora.*ponta[:\s]*([\d,.]+)\s?k[wW]h",
        "bandeira_tarifaria": r"bandeira tarifária[:\s]*([\w\s]+)",
        "penalidade_excedente": r"excedente.*demanda.*[:\s]*R\$\s*([\d,.]+)",
        "fator_potencia_irregular": r"fator de potência.*(abaixo|não conformidade|penalidade)"
    }

    for chave, padrao in padroes.items():
        match = re.search(padrao, texto, re.IGNORECASE)
        if match:
            valor = match.group(1).replace(".", "").replace(",", ".")
            if chave == "fator_potencia_irregular":
                dados[chave] = True
            elif chave == "bandeira_tarifaria":
                dados[chave] = match.group(1).strip()
            else:
                try:
                    dados[chave] = float(valor)
                except:
                    dados[chave] = None
    return dados

# === Execução Principal ===

if uploaded_file:
    texto = extrair_texto_pdf(uploaded_file)
    historico = extrair_historico_consumo(texto)
    grupo = "Grupo A" if "Grupo A" in texto else ("Grupo B" if "Grupo B" in texto else "Não identificado")
    dados_grupo_a = extrair_dados_grupo_a(texto)

    st.markdown(f"### 📄 Diagnóstico da Fatura ({grupo})")

    if historico:
        st.markdown("#### 📈 Histórico de Consumo (12 meses):")
        df = pd.DataFrame(historico.items(), columns=["Mês", "kWh"]).set_index("Mês")
        st.dataframe(df)
        media = sum(historico.values()) / len(historico)
        pico = max(historico.values())
        minimo = min(historico.values())
        sazonalidade = pico - minimo

        st.write(f"🔢 **Média:** {round(media,2)} kWh | 📈 Pico: {pico} | 📉 Mínimo: {minimo}")
        st.write(f"🔁 **Sazonalidade:** {sazonalidade} kWh")

        kwp, economia = simular_sistema(media)
        st.markdown("#### ☀️ Simulação Solar")
        st.write(f"🔋 Sistema estimado: **{kwp} kWp**")
        st.write(f"💰 Economia estimada: **R$ {economia}/mês**")

    if any(v is not None for v in dados_grupo_a.values()):
        st.markdown("#### ⚡ Diagnóstico Técnico Grupo A")
        for chave, valor in dados_grupo_a.items():
            if valor:
                label = chave.replace("_", " ").capitalize()
                if chave == "fator_potencia_irregular" and valor is True:
                    st.error("⚠️ Fator de potência em não conformidade!")
                elif "penalidade" in chave:
                    st.warning(f"⚠️ Penalidade: R$ {valor}")
                else:
                    st.write(f"**{label}:** {valor}")

    st.markdown("#### 💡 Estratégias Sugeridas")
    if grupo == "Grupo B":
        if media < 1500:
            st.write("- ⚠️ Consumo baixo: pode não justificar sistema solar.")
        elif media > 4000:
            st.write("- ✅ Perfil ideal para solar fotovoltaico.")
        else:
            st.write("- 🟡 Avaliar perfil com atenção: consumo médio.")
        st.write("- ⚡ Avaliar zero grid se consumo for diurno.")
    if grupo == "Grupo A":
        st.write("- 📊 Avaliar demanda contratada vs registrada.")
        st.write("- ⏰ Se alto consumo em ponta: sugerir reprogramação ou BESS.")
