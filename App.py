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

def extract_data_from_pdf(pdf_file, target_section):
    """
    Extrait réellement les données d'un fichier PDF importé.
    Cherche les informations correspondant à la section cible.
    """
    extracted_results = []
    
    with pdfplumber.open(pdf_file) as pdf:
        full_text = ""
        for page in pdf.pages:
            full_text += page.extract_text() + "\n"
        
        # 1. Extraction des titulaires (Noms)
        # On cherche les lignes après "Nom:"
        noms = re.findall(r"Nom:\s*([A-Z\s]+)", full_text)
        prenoms = re.findall(r"Prénom:\s*([A-Z\s]+)", full_text)
        titulaire = " & ".join([f"{n} {p}" for n, p in zip(noms, prenoms)]) if noms else "Inconnu"
        
        # 2. Extraction des adresses des titulaires
        adresse_match = re.search(r"Adresse:\s*(.*?)(?=\n\n|\nPropriété)", full_text, re.DOTALL)
        adresse_titulaire = adresse_match.group(1).replace('\n', ' ').strip() if adresse_match else "Inconnue"

        # 3. Analyse des tableaux de propriétés
        # On cherche les lignes qui contiennent la section et le lot
        # Format type : "21", "AS", "108", , "68", "AV DU GENERAL..."
        # On utilise une regex pour capturer les lignes de lots
        lines = full_text.split('\n')
        current_plan = ""
        
        for line in lines:
            # Detection du plan et de la section (ex: "21", "AS", "108")
            # Cette regex cherche des séquences de codes cadastraux
            match_table = re.search(r"\"(\d+)\"\s*,\s*\"([A-Z]{1,2})\"\s*,\s*\"(\d+)\"", line)
            if match_table:
                section_found = match_table.group(2)
                plan_found = match_table.group(3)
                
                # Si la section correspond à celle recherchée par l'utilisateur
                if section_found == target_section:
                    # On cherche le lot et la quote-part dans les lignes suivantes ou la même ligne
                    lot_match = re.search(r"LOT\s*(\d+)\s*(\d+/\d+)", line)
                    if lot_match:
                        extracted_results.append({
                            "proprietaire": titulaire,
                            "adresse": adresse_titulaire,
                            "lot": lot_match.group(1),
                            "quotePart": lot_match.group(2),
                            "section": section_found,
                            "plan": plan_found
                        })

    return extracted_results

def call_gemini_analysis(data):
    """Appelle l'API Gemini pour analyser les données extraites."""
    api_key = "" # Fournie par l'environnement
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={api_key}"
    
    system_prompt = (
        "Tu es un analyste de données immobilières expert. "
        "Synthétise ces données de relevés de propriété extraites d'un PDF en français. "
        "Fais un résumé des biens possédés par la personne, les localisations et les quotes-parts."
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
st.markdown("Cette version analyse **réellement** le texte des PDF que vous téléchargez.")

with st.sidebar:
    st.header("Filtrage")
    section_target = st.text_input("Section à extraire (ex: AS, CE)", value="AS").strip().upper()
    st.info("L'extracteur cherchera tous les lots de cette section dans vos fichiers.")

uploaded_files = st.file_uploader("Chargez vos relevés de propriété (PDF)", type="pdf", accept_multiple_files=True)

if st.button("Analyser les documents"):
    if not uploaded_files:
        st.error("Veuillez charger au moins un fichier PDF.")
    else:
        all_data = []
        
        with st.status("Lecture des PDF et extraction des données...", expanded=True) as status:
            for uploaded_file in uploaded_files:
                st.write(f"Traitement de : {uploaded_file.name}")
                # Appel de la fonction d'extraction réelle
                data = extract_data_from_pdf(uploaded_file, section_target)
                all_data.extend(data)
            
            status.update(label="Extraction terminée !", state="complete", expanded=False)

        if all_data:
            st.success(f"Extraction réussie : {len(all_data)} lots trouvés pour la section {section_target}.")
            
            # Affichage des données
            st.subheader("Données Extraites")
            st.table(all_data)
            
            # Analyse IA
            st.divider()
            st.subheader("🤖 Synthèse de l'IA (Gemini)")
            with st.spinner("Analyse en cours..."):
                analysis = call_gemini_analysis(all_data)
                st.info(analysis)
                
            # Export
            csv = "Proprietaire;Lot;Section;Plan;Quote-part\n" + "\n".join([f"{d['proprietaire']};{d['lot']};{d['section']};{d['plan']};{d['quotePart']}" for d in all_data])
            st.download_button("Exporter en CSV", csv, "export_cadastre.csv", "text/csv")
        else:
            st.warning(f"Aucun lot trouvé pour la section '{section_target}' dans les fichiers fournis.")
            st.info("Vérifiez que la section saisie correspond bien à celle présente dans le document (ex: AS).")

st.markdown("---")
st.caption("Moteur d'extraction : pdfplumber + Regex | Analyse : Gemini 2.5 Flash")
