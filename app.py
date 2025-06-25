import streamlit as st
import fitz
from PIL import Image
import pytesseract
import re
import io
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
import os

st.set_page_config(page_title="Analisador Solar", layout="centered")
st.title("🔎 Analisador de Faturas Copel - Solar & Estratégia")

uploaded_file = st.file_uploader("Envie a fatura (PDF ou imagem)", type=["pdf", "png", "jpg", "jpeg"])

def extrair_texto(file):
    if file.type == "application/pdf":
        try:
            texto = ""
            with fitz.open(stream=file.read(), filetype="pdf") as doc:
                for page in doc: texto += page.get_text().strip() + "\n"
            if not texto.strip(): raise ValueError
            return texto
        except:
            file.seek(0)
            doc = fitz.open("pdf", file.read())
            texto = ""
            for page in doc:
                pix = page.get_pixmap(dpi=300)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                texto += pytesseract.image_to_string(img, lang="por") + "\n"
            return texto
    else:
        img = Image.open(file).convert("L")
        return pytesseract.image_to_string(img, lang="por")

def extrair_historico(texto):
    historico = {}
    # Captura os valores logo após os 12 meses, na ordem certa
    meses = ["MAI25","ABR25","MAR25","FEV25","JAN25","DEZ24","NOV24","OUT24","SET24","AGO24","JUL24","JUN24","MAI24"]
    valores = re.findall(r"\b(\d{3,5})\b", texto)
    if len(valores) >= 13:
        for i, mes in enumerate(meses):
            historico[mes] = int(valores[i])
    return historico

def analisar(texto):
    r = {}
    r["grupo"] = "Grupo B" if "Modalidade Tarifaria: B" in texto else "Grupo A" if "Grupo A" in texto else "Não identificado"
    m = re.search(r"R\$\s*([\d\.,]+)", texto)
    r["valor_total"] = m.group(1) if m else "Desconhecido"
    m2 = re.search(r"Cidade:\s*(.*?)\s*-\s*Estado:\s*([A-Z]{2})", texto)
    r["cidade"], r["estado"] = (m2.group(1).strip(), m2.group(2).strip()) if m2 else ("Toledo","PR")
    r["consumos"] = extrair_historico(texto)
    return r

def simular(r):
    c = list(r["consumos"].values())
    if not c: return dict(media=0,pico=0,minimo=0,sazonalidade=0,kwp=0,economia=0,payback=0)
    media, pico, minimo = sum(c)/len(c), max(c), min(c)
    saz = pico-minimo
    irrad = {"Toledo - PR":140,"Curitiba - PR":115,"Campo Grande - MS":150}.get(f"{r['cidade']} - {r['estado']}",120)
    kwp = round(media/irrad,1); econ = round(media*0.85,2)
    pb = round((kwp*1300)/econ,1) if econ>0 else 0
    return dict(media=media,pico=pico,minimo=minimo,sazonalidade=saz,kwp=kwp,economia=econ,payback=pb)

def gerar_sugestoes(r):
    s=[]
    if r["media"]<1500: s.append("🔍 Consumo baixo")
    else: s.append("✅ Bom perfil solar")
    if r["grupo"]=="Grupo B": s.append("⚡ Grupo B: zero‑grid compensa")
    else: s.append("⚠️ Grupo A: atenção à demanda/ponta")
    if r["sazonalidade"]>4000: s.append("📉 Alta sazonalidade: considere BESS")
    return s

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

if uploaded_file:
    texto = extrair_texto(uploaded_file)
    st.subheader("🪪 Texto Extraído (Debug)")
    st.code(texto, language="text")

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
