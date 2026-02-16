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

def extract_owners_from_text(text):
    """
    Extrait tous les propriétaires/indivisaires - VERSION CORRIGÉE
    """
    owners = []
    
    # Pattern principal : capture Numéro propriétaire + Nom + Prénom + Adresse
    owner_pattern = re.compile(
        r"Numéro propriétaire\s*:\s*(\w+).*?" +
        r"Nom\s*:\s*([A-ZÀ-Ü\s\-]+?)\s+" +
        r"Prénom\s*:\s*([A-ZÀ-Ü\s\-]+?)" +
        r"(?:\s+Adresse\s*:\s*(.*?))?(?=Numéro propriétaire|Propriété|$)",
        re.DOTALL | re.IGNORECASE
    )
    
    for match in owner_pattern.finditer(text):
        numero = match.group(1).strip()
        nom = clean_text_segment(match.group(2))
        prenom = clean_text_segment(match.group(3))
        adresse_raw = match.group(4) if match.group(4) else ""
        adresse = clean_text_segment(adresse_raw) if adresse_raw else "Non détectée"
        full_name = f"{nom} {prenom}".strip()
        
        if full_name:
            owners.append({
                "name": full_name,
                "address": adresse,
                "numero": numero
            })
    
    # Pattern de secours si le premier échoue (sans numéro propriétaire)
    if not owners:
        alt_pattern = re.compile(
            r"Nom\s*:\s*([A-ZÀ-Ü\s\-]+?)\s+" +
            r"Prénom\s*:\s*([A-ZÀ-Ü\s\-]+?)" +
            r"(?:.*?Adresse\s*:\s*(.*?))?(?=Nom\s*:|Propriété|$)",
            re.DOTALL | re.IGNORECASE
        )
        
        for match in alt_pattern.finditer(text):
            nom = clean_text_segment(match.group(1))
            prenom = clean_text_segment(match.group(2))
            adresse_raw = match.group(3) if match.group(3) else ""
            adresse = clean_text_segment(adresse_raw) if adresse_raw else "Non détectée"
            full_name = f"{nom} {prenom}".strip()
            
            if full_name:
                owners.append({
                    "name": full_name,
                    "address": adresse,
                    "numero": "N/A"
                })
    
    return owners
def extract_data_from_pdf(pdf_file, target_section):
    """
    Extrait les données des propriétaires et des lots depuis le PDF.
    """
    extracted_results = []
    
    with pdfplumber.open(pdf_file) as pdf:
        full_text_pages = [page.extract_text() or "" for page in pdf.pages]
        raw_text = "\n".join(full_text_pages)
        
        # 1. Extraction des Titulaires (Zone délimitée)
        titulaire_section_match = re.search(r"Titulaire\(s\) de droit\(s\)(.*?)Propriété\(s\) bâtie\(s\)", raw_text, re.DOTALL | re.IGNORECASE)
        
        owners_list = []
        if titulaire_section_match:
            owners_list = extract_owners_from_text(titulaire_section_match.group(1))
        else:
            # Fallback si la section n'est pas bien délimitée
            owners_list = extract_owners_from_text(raw_text[:2000])

        titulaire_total = " / ".join([o["name"] for o in owners_list]) if owners_list else "Inconnu"
        unique_addresses = list(set([o["address"] for o in owners_list if o["address"] != "Non détectée"]))
        adresse_totale = " | ".join(unique_addresses) if unique_addresses else "Non détectée"

        # 2. Analyse des Lots (Recherche de la section ex: AS)
        lines = raw_text.split('\n')
        for i, line in enumerate(lines):
            if re.search(rf'"{target_section}"|\b{target_section}\b', line):
                # Analyse du contexte pour trouver LOT et Quote-part
                context = " ".join(lines[i:i+15])
                context = clean_text_segment(context)
                
                # Capture des lots (ex: LOT 0000003 72/10000)
                lots_found = re.findall(r"LOT\s*(\d+)\s*(\d+/\d+)", context)
                
                for lot_num, qp in lots_found:
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
    """Synthèse des données via l'IA."""
    api_key = "" 
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={api_key}"
    
    payload = {
        "contents": [{"parts": [{"text": f"Analyse et résume ces données de relevés de propriété immobilière : {json.dumps(data)}"}]}]
    }
    try:
        res = requests.post(url, json=payload, timeout=15)
        return res.json()['candidates'][0]['content']['parts'][0]['text']
    except:
        return "L'IA n'a pas pu générer de synthèse."

# --- Interface Streamlit ---

st.title("Extracteur de Relevés de Propriété (Multi-Titulaires) 📄")
st.markdown("Cette version est optimisée pour détecter tous les indivisaires et leurs adresses.")

with st.sidebar:
    st.header("Filtrage")
    section_target = st.text_input("Section cadastrale (ex: AS)", value="AS").upper()

uploaded_files = st.file_uploader("Chargez les fichiers PDF", type="pdf", accept_multiple_files=True)

if st.button("Lancer l'analyse"):
    if not uploaded_files:
        st.warning("Veuillez charger au moins un fichier PDF.")
    else:
        final_data = []
        for file in uploaded_files:
            data = extract_data_from_pdf(file, section_target)
            final_data.extend(data)
            
        if final_data:
            st.success(f"Extraction réussie : {len(final_data)} lots identifiés.")
            st.table(final_data)
            
            with st.expander("🤖 Synthèse de l'IA"):
                st.write(call_gemini_analysis(final_data))
                
            csv_output = "Propriétaire;Adresse;Lot;Section;Quote-part\n"
            for r in final_data:
                csv_output += f"{r['proprietaire']};{r['adresse']};{r['lot']};{r['section']};{r['quotePart']}\n"
            st.download_button("Télécharger au format CSV", csv_output, "extraction_propriete.csv")
        else:
            st.error(f"Aucune donnée trouvée pour la section {section_target}. Vérifiez le document.")

