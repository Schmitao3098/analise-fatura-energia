import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
import re
import io

st.set_page_config(page_title="Analisador Solar v2.5", layout="centered")
st.title("🔎 Analisador de Faturas Copel - v2.5")
st.markdown("Envie uma ou mais faturas (PDF ou imagem) para análise completa.")

uploaded_files = st.file_uploader("Envie as faturas:", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)

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

    # Cidade (para geração regional)
    match_cidade = re.search(r"Cidade:\s+([A-Za-z\s]+)\s+-\s+Estado:\s+([A-Z]{2})", texto)
    if match_cidade:
        resultado["cidade"] = match_cidade.group(1).strip()
        resultado["estado"] = match_cidade.group(2).strip()
    else:
        resultado["cidade"] = "Toledo"
        resultado["estado"] = "PR"

    return resultado

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

# === Loop principal para múltiplos arquivos ===
def gerar_grafico(consumos):
    if not consumos: return None
    df = pd.DataFrame(list(consumos.items()), columns=["Mês","kWh"])
    fig,ax = plt.subplots(figsize=(8,4))
    ax.bar(df["Mês"],df["kWh"],color='goldenrod')
    ax.set_title("Histórico (kWh)")
    plt.xticks(rotation=45); buf=io.BytesIO()
    plt.tight_layout(); plt.savefig(buf,format="png"); buf.seek(0)
    return buf

def gerar_pdf(r,buf):
    pdf=FPDF(); pdf.add_page(); pdf.set_font("Arial",size=12)
    pdf.cell(200,10,"Relatório Solar",ln=1)
    pdf.cell(200,8,f"Grupo: {r['grupo']}  Total: R$ {r['valor_total']}",ln=1)
    pdf.cell(200,8,f"Média {r['media']:.1f} | Sistema {r['kwp']} kWp | Economia R$ {r['economia']}/mês | Payback {r['payback']} anos",ln=1)
    if buf:
        imgf="graf.png"
        with open(imgf,"wb") as f: f.write(buf.read())
        pdf.image(imgf,x=10,y=50,w=180); os.remove(imgf)
    path="rel_temp.pdf"; pdf.output(path)
    data=open(path,"rb").read(); os.remove(path)
    return data

if uploaded_files:
    uploaded_file = uploaded_files[0]  # pega o primeiro arquivo da lista
    texto = extrair_texto(uploaded_file)
    d = analisar(texto)
    s = simular(d)
    d.update(s)

    st.subheader("📊 Fatura")
    st.write(f"**Grupo:** {d['grupo']}  •  **Total:** R$ {d['valor_total']}")
    st.write(f"📍 {d['cidade']} - {d['estado']}")

    st.subheader("📈 Histórico 12 meses")
    st.json(d["consumos"])
    st.write(f"Média {s['media']:.1f} • Pico {s['pico']} • Mínimo {s['minimo']}")
    st.write(f"Sazonalidade: {s['sazonalidade']} kWh")

    st.subheader("🔆 Simulação")
    st.write(f"Sistema ~**{s['kwp']} kWp**, economia ~**R$ {s['economia']}/mês**, payback **{s['payback']} anos**")

    st.subheader("💡 Sugestões")
    for x in gerar_sugestoes(s): st.markdown(f"- {x}")

    gbuf = gerar_grafico(d["consumos"])
    if gbuf: st.image(gbuf)

    pdf_data = gerar_pdf(d, gbuf)
    st.download_button("📥 Relatório PDF", data=pdf_data, file_name="rel_solar.pdf")
