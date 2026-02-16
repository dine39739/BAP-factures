import streamlit as st
import json
import requests
import pdfplumber
import re

# --- Configuration de la page ---
st.set_page_config(
    page_title="Extracteur de Relevés de Propriété",
    page_icon="📄",
    layout="wide"
)

# --- Fonctions d'Extraction ---

def clean_text_segment(text):
    """Nettoie un segment de texte en supprimant les sauts de ligne et espaces superflus."""
    if not text:
        return ""
    # Remplace les retours à la ligne par des espaces et supprime les espaces multiples
    text = text.replace('\n', ' ')
    return re.sub(r'\s+', ' ', text).strip()

def extract_data_from_pdf(pdf_file, target_section):
    """
    Extrait les données des propriétaires, adresses et lots.
    Gère les indivisions et les adresses multi-lignes de manière robuste.
    """
    extracted_results = []
    
    with pdfplumber.open(pdf_file) as pdf:
        full_text_pages = [page.extract_text() or "" for page in pdf.pages]
        raw_text = "\n".join(full_text_pages)
        
        # 1. Extraction des Titulaires
        owners_data = []
        
        # On isole la section "Titulaire(s) de droit(s)" pour ne pas polluer avec le reste
        titulaire_section_match = re.search(r"Titulaire\(s\) de droit\(s\)(.*?)Propriété\(s\) bâtie\(s\)", raw_text, re.DOTALL | re.IGNORECASE)
        
        if titulaire_section_match:
            titulaire_text = titulaire_section_match.group(1)
            # On découpe par propriétaire
            owner_blocks = re.split(r"Numéro propriétaire:", titulaire_text)
            
            for block in owner_blocks[1:]:
                # Extraction Nom : cherche jusqu'à "Prénom" ou "Né(e)" ou fin de ligne
                nom_match = re.search(r"Nom:\s*([A-Z\s\-]+?)(?=Prénom|Né\(e\)|Adresse|$)", block, re.IGNORECASE | re.DOTALL)
                prenom_match = re.search(r"Prénom:\s*([A-Z\s\-]+?)(?=Adresse|Né\(e\)|Droit|$)", block, re.IGNORECASE | re.DOTALL)
                
                # Extraction Adresse : capture tout entre "Adresse:" et le prochain mot clé ou fin de bloc
                addr_match = re.search(r"Adresse:\s*(.*?)(?=Droit réel|Numéro|$)", block, re.DOTALL | re.IGNORECASE)
                
                if nom_match:
                    name_part = clean_text_segment(nom_match.group(1))
                    first_name_part = clean_text_segment(prenom_match.group(1)) if prenom_match else ""
                    full_name = f"{name_part} {first_name_part}".strip()
                    
                    address = "Non détectée"
                    if addr_match:
                        address = clean_text_segment(addr_match.group(1))
                    
                    owners_data.append({"name": full_name, "address": address})

        titulaire_total = " / ".join([o["name"] for o in owners_data]) if owners_data else "Inconnu"
        # On prend l'adresse unique (souvent la même pour l'indivision)
        unique_addresses = list(set([o["address"] for o in owners_data if o["address"] != "Non détectée"]))
        adresse_totale = " | ".join(unique_addresses) if unique_addresses else "Non détectée"

        # 2. Analyse des Lots
        # On cherche la section spécifiée (ex: AS)
        # On cherche les lignes contenant la section et un numéro de plan
        lines = raw_text.split('\n')
        for i, line in enumerate(lines):
            if re.search(rf'"{target_section}"|\b{target_section}\b', line):
                # On prend un contexte large pour capturer le tableau
                context = " ".join(lines[i:i+12])
                context = clean_text_segment(context)
                
                # Recherche des patterns LOT + Quote-part
                # Format: LOT 0000237 53/10000
                lots = re.findall(r"LOT\s*(\d+)\s*(\d+/\d+)", context)
                
                for lot_num, qp in lots:
                    if not any(r['lot'] == lot_num for r in extracted_results):
                        extracted_results.append({
                            "proprietaire": titulaire_total,
                            "adresse": adresse_totale,
                            "lot": lot_num,
                            "quotePart": qp,
                            "section": target_section
                        })

    return extracted_results

def call_gemini_analysis(data):
    """Synthèse via Gemini."""
    api_key = "" 
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={api_key}"
    
    payload = {
        "contents": [{"parts": [{"text": f"Résume ces données de propriété : {json.dumps(data)}"}]}]
    }
    try:
        res = requests.post(url, json=payload, timeout=15)
        return res.json()['candidates'][0]['content']['parts'][0]['text']
    except:
        return "Analyse indisponible."

# --- Interface ---

st.title("Extracteur de Relevés de Propriété (Version Corrective) 📄")

with st.sidebar:
    st.header("Paramètres")
    section_target = st.text_input("Section (ex: AS)", value="AS").upper()

uploaded_files = st.file_uploader("Charger les relevés PDF", type="pdf", accept_multiple_files=True)

if st.button("Lancer l'extraction"):
    if not uploaded_files:
        st.warning("Veuillez charger des fichiers.")
    else:
        all_results = []
        for file in uploaded_files:
            data = extract_data_from_pdf(file, section_target)
            all_results.extend(data)
            
        if all_results:
            st.success(f"{len(all_results)} lots extraits.")
            st.table(all_results)
            
            with st.expander("🤖 Synthèse"):
                st.write(call_gemini_analysis(all_results))
                
            csv = "Propriétaire;Adresse;Lot;Section;Quote-part\n"
            for r in all_results:
                csv += f"{r['proprietaire']};{r['adresse']};{r['lot']};{r['section']};{r['quotePart']}\n"
            st.download_button("Exporter CSV", csv, "extraction.csv")
        else:
            st.error("Aucune donnée trouvée. Vérifiez la section demandée.")
