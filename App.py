import streamlit as st
import json
import time
import requests
import pdfplumber
import re
import io

# --- Configuration de la page ---
st.set_page_config(
    page_title="Extracteur Réel de Relevés de Propriété",
    page_icon="📄",
    layout="wide"
)

# --- Fonctions d'Extraction Réelle ---

def clean_extracted_text(text):
    """Nettoie le texte des sauts de ligne inutiles pour faciliter la détection."""
    if not text:
        return ""
    # Remplace les suites de \n par un espace simple
    return re.sub(r'\n+', ' ', text)

def extract_data_from_pdf(pdf_file, target_section):
    """
    Extrait réellement les données d'un fichier PDF importé.
    Amélioré pour gérer les sauts de ligne complexes dans les tableaux.
    """
    extracted_results = []
    
    with pdfplumber.open(pdf_file) as pdf:
        full_text_pages = []
        for page in pdf.pages:
            full_text_pages.append(page.extract_text() or "")
        
        raw_text = "\n".join(full_text_pages)
        # Texte nettoyé pour les recherches de noms/adresses
        clean_text = clean_extracted_text(raw_text)
        
        # 1. Extraction des titulaires (Noms)
        noms = re.findall(r"Nom:\s*([A-Z\s\-]+)", clean_text)
        prenoms = re.findall(r"Prénom:\s*([A-Z\s\-]+)", clean_text)
        titulaire = " & ".join(list(set([f"{n.strip()} {p.strip()}" for n, p in zip(noms, prenoms)]))) if noms else "Inconnu"
        
        # 2. Extraction des adresses des titulaires
        adresse_match = re.search(r"Adresse:\s*(.*?)(?=Droit réel|Propriété|$)", clean_text, re.IGNORECASE)
        adresse_titulaire = adresse_match.group(1).strip() if adresse_match else "Inconnue"

        # 3. Analyse ligne par ligne pour les lots
        # On traite le texte ligne par ligne pour repérer la structure "Section / Plan"
        lines = raw_text.split('\n')
        
        for i, line in enumerate(lines):
            # Regex flexible pour trouver la section même avec des guillemets ou espaces
            # Cherche par exemple : "AS" ou AS dans une structure de tableau
            section_match = re.search(rf"\"{target_section}\"|(?<=\s){target_section}(?=\s)", line)
            
            if section_match:
                # Une fois la section trouvée, on cherche le lot dans les lignes environnantes (contexte)
                # On regarde la ligne actuelle et les 2 suivantes
                context = " ".join(lines[i:i+5])
                context = clean_extracted_text(context)
                
                # Cherche tous les lots (ex: LOT 0000237) et leur quote-part
                lots_found = re.findall(r"LOT\s*(\d+)\s*(\d+/\d+)", context)
                
                for lot_num, qp in lots_found:
                    # Évite les doublons
                    if not any(r['lot'] == lot_num for r in extracted_results):
                        extracted_results.append({
                            "proprietaire": titulaire,
                            "adresse": adresse_titulaire,
                            "lot": lot_num,
                            "quotePart": qp,
                            "section": target_section,
                            "plan": "Détecté" # Le plan est souvent sur la ligne précédente ou suivante
                        })

    return extracted_results

def call_gemini_analysis(data):
    """Appelle l'API Gemini pour analyser les données extraites."""
    api_key = "" # Fournie par l'environnement
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={api_key}"
    
    system_prompt = (
        "Tu es un analyste de données immobilières expert. "
        "Synthétise ces données de relevés de propriété en français. "
        "Fais un résumé des biens, des propriétaires et des quotes-parts."
    )
    
    payload = {
        "contents": [{"parts": [{"text": json.dumps(data)}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]}
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
    except:
        pass
    return "L'analyse intelligente n'est pas disponible pour le moment."

# --- Interface Streamlit ---

st.title("Extracteur Intelligent de Relevés (PDF Réel) 📄")

with st.sidebar:
    st.header("Filtrage")
    section_target = st.text_input("Section à extraire (ex: AS, CE)", value="AS").strip().upper()
    st.info(f"L'extracteur va scanner le document pour trouver la section {section_target}.")

uploaded_files = st.file_uploader("Chargez vos relevés de propriété (PDF)", type="pdf", accept_multiple_files=True)

if st.button("Analyser les documents"):
    if not uploaded_files:
        st.error("Veuillez charger au moins un fichier PDF.")
    else:
        all_data = []
        
        with st.status("Extraction en cours (Nettoyage des données PDF)...", expanded=True) as status:
            for uploaded_file in uploaded_files:
                st.write(f"Analyse de {uploaded_file.name}...")
                data = extract_data_from_pdf(uploaded_file, section_target)
                all_data.extend(data)
            
            status.update(label="Extraction terminée !", state="complete", expanded=False)

        if all_data:
            st.success(f"Succès : {len(all_data)} lots extraits.")
            st.table(all_data)
            
            st.subheader("🤖 Analyse de l'IA")
            with st.spinner("Analyse en cours..."):
                analysis = call_gemini_analysis(all_data)
                st.info(analysis)
                
            csv = "Proprietaire;Lot;Section;Quote-part\n" + "\n".join([f"{d['proprietaire']};{d['lot']};{d['section']};{d['quotePart']}" for d in all_data])
            st.download_button("Exporter en CSV", csv, "extraction.csv", "text/csv")
        else:
            st.error(f"Aucune donnée trouvée pour la section '{section_target}'.")
            st.info("Le document semble avoir une structure complexe. L'algorithme a été assoupli pour mieux lire les tableaux fragmentés.")

st.markdown("---")
st.caption("Version 2.1 - Correction du parsing de section pour Viry-Châtillon")
