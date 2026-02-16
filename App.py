import streamlit as st
import json
import time
import requests
import pdfplumber
import re
import io

# --- Configuration de la page ---
st.set_page_config(
    page_title="Extracteur de Relevés de Propriété",
    page_icon="📄",
    layout="wide"
)

# --- Fonctions d'Extraction ---

def extract_data_from_pdf(pdf_file, target_section):
    """
    Extrait les données des propriétaires, adresses et lots.
    Gère les indivisions et les adresses multi-lignes.
    """
    extracted_results = []
    
    with pdfplumber.open(pdf_file) as pdf:
        full_text_pages = [page.extract_text() or "" for page in pdf.pages]
        raw_text = "\n".join(full_text_pages)
        
        # 1. Extraction des Titulaires (Gestion Indivision)
        # On cherche les blocs de titulaires qui commencent souvent par "Droit réel"
        # et contiennent Nom et Prénom
        owners_data = []
        
        # On divise le texte par "Numéro propriétaire" pour isoler chaque individu
        owner_blocks = re.split(r"Numéro propriétaire:", raw_text)
        
        for block in owner_blocks[1:]: # On saute le premier bloc avant le premier proprio
            # Extraction Nom et Prénom
            nom_match = re.search(r"Nom:\s*([A-Z\s\-]+)", block, re.IGNORECASE)
            prenom_match = re.search(r"Prénom:\s*([A-Z\s\-]+)", block, re.IGNORECASE)
            
            # Extraction Adresse spécifique à ce propriétaire
            addr_match = re.search(r"Adresse:\s*(.*?)(?=Droit réel|Propriété|Identification|Page|Numéro|$)", block, re.DOTALL | re.IGNORECASE)
            
            if nom_match:
                name = f"{nom_match.group(1).strip()}"
                if prenom_match:
                    name += f" {prenom_match.group(1).strip()}"
                
                address = "Non détectée"
                if addr_match:
                    address = re.sub(r'\s+', ' ', addr_match.group(1)).strip()
                
                owners_data.append({"name": name, "address": address})

        # Synthèse des propriétaires pour l'affichage final
        titulaire_total = " / ".join([o["name"] for o in owners_data]) if owners_data else "Inconnu"
        adresse_totale = " | ".join(list(set([o["address"] for o in owners_data]))) if owners_data else "Inconnue"

        # 2. Analyse des Lots
        lines = raw_text.split('\n')
        for i, line in enumerate(lines):
            # Recherche de la section cible (ex: AS)
            if re.search(rf'"{target_section}"|\b{target_section}\b', line):
                # On regarde le contexte (ligne actuelle + 8 suivantes) pour trouver les lots
                context = " ".join(lines[i:i+10])
                context = re.sub(r'\s+', ' ', context)
                
                # Cherche "LOT XXXXXXX" suivi de la quote-part "XX/XXXXX"
                lots = re.findall(r"LOT\s*(\d+)\s*(\d+/\d+)", context)
                
                for lot_num, qp in lots:
                    # Éviter les doublons de lots identiques
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
    """Analyse synthétique via Gemini."""
    api_key = "" # Géré par l'environnement
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={api_key}"
    
    prompt = "Analyse ces données de relevés de propriété. Identifie les propriétaires et résume les biens (lots et quotes-parts) de manière concise."
    
    payload = {
        "contents": [{"parts": [{"text": f"{prompt}\n\nDonnées: {json.dumps(data)}"}]}]
    }
    
    try:
        res = requests.post(url, json=payload, timeout=15)
        if res.status_code == 200:
            return res.json()['candidates'][0]['content']['parts'][0]['text']
    except:
        return "Erreur lors de la génération de la synthèse."

# --- Interface ---

st.title("Extracteur de Relevés (Multi-Propriétaires) 📄")
st.info("Cette version gère les indivisions et les adresses sur plusieurs lignes.")

with st.sidebar:
    st.header("Paramètres")
    section_target = st.text_input("Section à extraire", value="AS").upper()

uploaded_files = st.file_uploader("Déposez vos PDF", type="pdf", accept_multiple_files=True)

if st.button("Lancer l'extraction"):
    if not uploaded_files:
        st.warning("Merci de charger au moins un fichier.")
    else:
        results = []
        progress = st.progress(0)
        
        for idx, file in enumerate(uploaded_files):
            data = extract_data_from_pdf(file, section_target)
            results.extend(data)
            progress.progress((idx + 1) / len(uploaded_files))
            
        if results:
            st.success(f"{len(results)} lots trouvés.")
            st.table(results)
            
            with st.expander("🤖 Synthèse IA"):
                summary = call_gemini_analysis(results)
                st.write(summary)
            
            # Export CSV
            csv_data = "Propriétaire;Adresse;Lot;Section;Quote-part\n"
            for r in results:
                csv_data += f"{r['proprietaire']};{r['adresse']};{r['lot']};{r['section']};{r['quotePart']}\n"
            st.download_button("Télécharger CSV", csv_data, "extraction.csv", "text/csv")
        else:
            st.error(f"Aucun lot trouvé pour la section {section_target}.")
